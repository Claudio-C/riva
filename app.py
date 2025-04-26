from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for
import os
import tempfile
import uuid
import threading
import json
import time
import ssl
import queue
from riva_client import RivaClient

app = Flask(__name__, static_folder='static', template_folder='templates')

# SSL certificate paths - add alternative paths as fallbacks
SSL_CERT_PATHS = [
    "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem",
    "/etc/ssl/certs/avatar.ligagc.com/fullchain.pem",
    "/home/ia/certs/fullchain.pem"
]

SSL_KEY_PATHS = [
    "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem",
    "/etc/ssl/private/avatar.ligagc.com/privkey.pem",
    "/home/ia/certs/privkey.pem"
]

# Find the first valid certificate path
SSL_CERT_FILE = next((path for path in SSL_CERT_PATHS if os.path.exists(path)), SSL_CERT_PATHS[0])
SSL_KEY_FILE = next((path for path in SSL_KEY_PATHS if os.path.exists(path)), SSL_KEY_PATHS[0])

# Riva client configuration
RIVA_SERVER = "localhost:50051"  # Default Riva server address

# Available ASR models and languages based on server configuration
ASR_MODELS = {
    "conformer": ["ar-AR", "en-US", "en-GB", "de-DE", "es-ES", "es-US", "fr-FR", "hi-IN", "it-IT", "ja-JP", "ru-RU", "ko-KR", "pt-BR", "zh-CN", "nl-NL", "nl-BE"],
    "conformer_xl": ["en-US"],
    "conformer_unified": ["de-DE", "ja-JP", "zh-CN"],
    "whisper_large": ["multi"],
    "canary_1b": ["multi"]
}

# Available TTS models and languages
TTS_MODELS = {
    "fastpitch_hifigan": ["en-US", "es-ES", "es-US", "it-IT", "de-DE", "zh-CN"],
    "magpie": ["multi"],
    "radtts_hifigan": ["en-US"]
}

# Default model and language selections
DEFAULT_ASR_MODEL = "conformer"
DEFAULT_ASR_LANGUAGE = "en-US"

# Create a dictionary to store client instances per model/language combo
riva_clients = {}
default_client = RivaClient(RIVA_SERVER)

# Store active streaming sessions
active_sessions = {}

# Mapping of language codes to specific voice names required by the server
VOICE_NAME_MAP = {
    "en-US": ["English-US-Female-1", "English-US-Male-1"],
    "es-ES": ["Spanish-ES-Female-1", "Spanish-ES-Male-1"],
    "es-US": ["Spanish-US-Female-1", "Spanish-US-Male-1"],
    "it-IT": ["Italian-IT-Female-1", "Italian-IT-Male-1"],
    "de-DE": ["German-DE-Female-1", "German-DE-Male-1"],
    "zh-CN": ["Chinese-CN-Female-1", "Chinese-CN-Male-1"]
}

# Configure TTS voices based on the fastpitch_hifigan model
# tts_models_languages_map["fastpitch_hifigan"]="en-US es-ES es-US it-IT de-DE zh-CN"
VOICES = {}  # Will be populated with working voice configurations

def initialize_voices():
    """Initialize voice map with supported languages for fastpitch_hifigan model"""
    global VOICES
    
    # Languages supported by fastpitch_hifigan
    languages = ["en-US", "es-ES", "es-US", "it-IT", "de-DE", "zh-CN"]
    
    # For each language, create voice entries with different formats to try
    for lang in languages:
        # Start with empty list for this language
        VOICES[lang] = []
        
        # Format 1: Just the language code (primary format that usually works)
        VOICES[lang].append(lang)
        
        # Format 2: Language-specific naming in Riva
        if lang == "en-US":
            VOICES[lang].extend(["english", "en-US-FastPitch", "english_us"])
        elif lang == "es-ES":
            VOICES[lang].extend(["spanish", "es-ES-FastPitch", "spanish_es"])
        elif lang == "es-US":
            VOICES[lang].extend(["spanish-us", "es-US-FastPitch", "spanish_us"])
        elif lang == "it-IT":
            VOICES[lang].extend(["italian", "it-IT-FastPitch", "italian_it"])
        elif lang == "de-DE":
            VOICES[lang].extend(["german", "de-DE-FastPitch", "german_de"])
        elif lang == "zh-CN":
            VOICES[lang].extend(["chinese", "zh-CN-FastPitch", "chinese_cn"])
    
    print(f"Initialized TTS voices: {VOICES}")

# Initialize voices on startup
initialize_voices()

def test_voice_configuration():
    """Test voice configurations to find working ones"""
    global VOICES
    tested_voices = {}
    
    # Create a test client
    test_client = RivaClient(RIVA_SERVER)
    
    # Test each language with its voice candidates
    for lang, voices in VOICES.items():
        working_voices = []
        
        for voice in voices:
            try:
                # Test with a short text
                print(f"Testing voice '{voice}' for language '{lang}'...")
                audio = test_client.synthesize_speech(
                    text="Test",
                    language_code=lang,
                    voice_name=voice
                )
                
                if audio:
                    print(f"Voice '{voice}' works for language '{lang}'")
                    working_voices.append(voice)
            except Exception as e:
                print(f"Voice '{voice}' failed for language '{lang}': {e}")
        
        # Update the language with only working voices
        if working_voices:
            tested_voices[lang] = working_voices
            print(f"Working voices for {lang}: {working_voices}")
        else:
            # Keep the first voice as a potential option even if it failed
            tested_voices[lang] = [voices[0]]
            print(f"No working voices found for {lang}, keeping {voices[0]} as fallback")
    
    # Update the global VOICES dictionary
    VOICES = tested_voices
    return VOICES

@app.route('/tts/test_voices', methods=['POST'])
def test_voices():
    """Test and find working TTS voice configurations."""
    try:
        voices = test_voice_configuration()
        return jsonify({
            'success': True,
            'voices': voices
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html', tts_available=tts_available)

@app.route('/get_models', methods=['GET'])
def get_models():
    """Return available ASR and TTS models and languages."""
    return jsonify({
        'asr_models': ASR_MODELS,
        'tts_models': TTS_MODELS,
        'default_asr_model': DEFAULT_ASR_MODEL,
        'default_asr_language': DEFAULT_ASR_LANGUAGE
    })

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe uploaded audio file."""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400
    
    audio_file = request.files['audio']
    
    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        tmp_filename = tmp_file.name
        audio_file.save(tmp_filename)
    
    try:
        # Process audio file in chunks to simulate streaming
        def audio_chunks():
            chunk_size = 4096  # 4KB chunks
            with open(tmp_filename, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        
        # Get sample rate from request or use default
        sample_rate = int(request.form.get('sample_rate', 16000))
        
        # Get transcription
        results = []
        final_text = ""
        
        for result in riva_client.transcribe_stream(
            audio_chunks(), 
            sample_rate_hz=sample_rate
        ):
            if result['is_final']:
                final_text = result['transcript']
                results.append(final_text)
        
        return jsonify({'transcription': ' '.join(results) if results else final_text})
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_filename):
            os.unlink(tmp_filename)

@app.route('/stream_start', methods=['POST'])
def stream_start():
    """Initialize a streaming session."""
    session_id = str(uuid.uuid4())
    
    # Get sample rate from request or use default
    sample_rate = int(request.args.get('sample_rate', 16000))
    
    # Create queues for audio data and results
    audio_queue = queue.Queue()
    results_queue = queue.Queue()
    
    # Store session info
    active_sessions[session_id] = {
        'created_at': time.time(),
        'audio_queue': audio_queue,
        'results_queue': results_queue,
        'results': [],
        'complete': False,
        'sample_rate': sample_rate
    }
    
    # Start a dedicated thread for this streaming session
    def session_thread():
        try:
            riva_client.create_streaming_session(
                audio_queue=audio_queue,
                results_queue=results_queue,
                sample_rate_hz=sample_rate
            )
        except Exception as e:
            print(f"Error in session thread {session_id}: {e}")
        finally:
            # Mark session as complete when the thread ends
            if session_id in active_sessions:
                active_sessions[session_id]['complete'] = True
    
    # Start the session thread
    thread = threading.Thread(target=session_thread)
    thread.daemon = True
    thread.start()
    
    # Store thread in session
    active_sessions[session_id]['thread'] = thread
    
    return jsonify({'session_id': session_id})

@app.route('/stream_audio/<session_id>', methods=['POST'])
def stream_audio(session_id):
    """Add audio chunk to an existing streaming session."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = active_sessions[session_id]
    
    # Check for data - handle empty requests as result polling
    is_polling = not request.data or len(request.data) == 0
    
    # Only add audio to queue if there's actual data
    if not is_polling:
        try:
            session['audio_queue'].put(request.data)
        except Exception as e:
            print(f"Error queuing audio chunk: {e}")
            return jsonify({'error': f'Failed to process audio: {str(e)}'}), 500
    
    # Collect any new results
    try:
        while not session['results_queue'].empty():
            result = session['results_queue'].get_nowait()
            session['results'].append(result)
            session['results_queue'].task_done()
    except Exception as e:
        print(f"Error collecting results: {e}")
    
    # Return the latest results
    latest_results = [r['transcript'] for r in session['results'] if r.get('is_final', False)]
    
    # If no final results, get latest interim result
    if not latest_results and session['results']:
        latest_results = [session['results'][-1]['transcript']]
    
    return jsonify({
        'transcription': ' '.join(latest_results) if latest_results else '',
        'is_final': any(r.get('is_final', False) for r in session['results']) if session['results'] else False,
        'num_results': len(session['results'])
    })

@app.route('/stream_stop/<session_id>', methods=['POST'])
def stream_stop(session_id):
    """Finalize a streaming session and get the complete transcription."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = active_sessions[session_id]
    
    # Signal the streaming thread to stop by putting None in the queue
    try:
        session['audio_queue'].put(None)
        
        # Wait for any final results (with timeout)
        end_time = time.time() + 2.0  # 2 second timeout
        while time.time() < end_time:
            try:
                if not session['results_queue'].empty():
                    result = session['results_queue'].get_nowait()
                    session['results'].append(result)
                    session['results_queue'].task_done()
                else:
                    # No more results, break out
                    break
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error collecting final results: {e}")
                break
        
        # Mark session as complete
        session['complete'] = True
    except Exception as e:
        print(f"Error stopping session {session_id}: {e}")
    
    # Get final transcription
    final_results = [r['transcript'] for r in session['results'] if r.get('is_final', False)]
    final_transcription = ' '.join(final_results) if final_results else ''
    
    # Cleanup session after a delay
    def cleanup_session():
        time.sleep(60)  # Keep session for 1 minute
        if session_id in active_sessions:
            del active_sessions[session_id]
    
    threading.Thread(target=cleanup_session).start()
    
    return jsonify({'final_transcription': final_transcription})

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    cert_exists = os.path.exists(SSL_CERT_FILE)
    key_exists = os.path.exists(SSL_KEY_FILE)
    
    return jsonify({
        'status': 'healthy', 
        'server': 'Riva Flask API',
        'ssl': {
            'cert_path': SSL_CERT_FILE,
            'cert_exists': cert_exists,
            'key_path': SSL_KEY_FILE,
            'key_exists': key_exists
        }
    })

@app.route('/ssl-check')
def ssl_check():
    """Endpoint to check SSL configuration."""
    cert_exists = os.path.exists(SSL_CERT_FILE)
    key_exists = os.path.exists(SSL_KEY_FILE)
    
    return jsonify({
        'ssl_configured': cert_exists and key_exists,
        'cert_file': SSL_CERT_FILE,
        'cert_exists': cert_exists,
        'key_file': SSL_KEY_FILE,
        'key_exists': key_exists,
        'checked_cert_paths': SSL_CERT_PATHS,
        'checked_key_paths': SSL_KEY_PATHS
    })

@app.route('/tts/available', methods=['GET'])
def check_tts_available():
    """Check if TTS functionality is available."""
    return jsonify({'available': tts_available})

@app.route('/tts/refresh_voices', methods=['POST'])
def refresh_tts_voices():
    """Force a refresh of available TTS voices."""
    try:
        voices = query_available_tts_voices()
        return jsonify({
            'success': True,
            'voices': voices
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/tts/voices', methods=['GET'])
def get_tts_voices():
    """Get available TTS voices for a language."""
    if not tts_available:
        return jsonify({
            'voices': VOICES.get('en-US', []),
            'default_voice': VOICES.get('en-US', [])[0] if VOICES.get('en-US', []) else None,
            'error': 'TTS functionality not available'
        })
    
    language = request.args.get('language', 'en-US')
    
    # Return the pre-queried voices from our global dictionary
    voices = VOICES.get(language, [])
    if not voices and language in TTS_MODELS.get("fastpitch_hifigan", []):
        # Fallback: Use language code as voice name
        voices = [language]
        VOICES[language] = voices
    
    return jsonify({
        'voices': voices,
        'default_voice': voices[0] if voices else None
    })

@app.route('/tts/synthesize', methods=['POST'])
def synthesize_speech():
    """Synthesize speech from text."""
    if not tts_available:
        return jsonify({'error': 'TTS functionality not available'}), 503
    
    data = request.json
    
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']
    language = data.get('language', 'en-US')
    
    # Get voice for this language from our global dictionary
    voices = VOICES.get(language, [language])  # Fallback to language code as voice
    voice = data.get('voice', voices[0] if voices else language)
    
    try:
        # Generate audio
        audio_data = default_client.synthesize_speech(
            text=text,
            language_code=language,
            voice_name=voice
        )
        
        if not audio_data:
            return jsonify({'error': 'Failed to synthesize speech'}), 500
        
        # Create a unique filename
        filename = f"tts_{uuid.uuid4().hex}.wav"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        
        # Write audio to WAV file
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)  # Sample rate
            wav_file.writeframes(audio_data)
        
        # Return file path (to be used for playback)
        return jsonify({
            'audio_file': filename,
            'text': text,
            'voice': voice
        })
        
    except Exception as e:
        return jsonify({'error': f'TTS error: {str(e)}'}, 500)

@app.route('/tts/audio/<filename>', methods=['GET'])
def get_tts_audio(filename):
    """Serve synthesized audio file."""
    filepath = os.path.join(tempfile.gettempdir(), filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Audio file not found'}), 404
    
    try:
        return send_file(
            filepath,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': f'Error serving audio file: {str(e)}'}), 500

@app.route('/tts/stream', methods=['POST'])
def stream_tts():
    """Stream synthesized speech."""
    data = request.json
    
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']
    language = data.get('language', 'en-US')
    voice = data.get('voice', VOICES.get(language, [])[0] if VOICES.get(language, []) else "English-US-Female-1")
    
    def generate():
        try:
            # Use default_client instead of undefined riva_client
            for audio_chunk in default_client.stream_synthesize_speech(
                text=text,
                language_code=language,
                voice_name=voice
            ):
                if audio_chunk:
                    yield audio_chunk
        except Exception as e:
            print(f"Error streaming TTS: {e}")
    
    return Response(
        stream_with_context(generate()),
        mimetype='audio/wav'
    )

def check_ssl_config():
    """Check if SSL certificates exist and are valid."""
    if not os.path.exists(SSL_CERT_FILE):
        print(f"Warning: SSL certificate not found at {SSL_CERT_FILE}")
        print(f"Checked paths: {SSL_CERT_PATHS}")
        print("Running without SSL (not secure).")
        return False
    
    if not os.path.exists(SSL_KEY_FILE):
        print(f"Warning: SSL key not found at {SSL_KEY_FILE}")
        print(f"Checked paths: {SSL_KEY_PATHS}")
        print("Running without SSL (not secure).")
        return False
    
    try:
        # Try to create an SSL context with the certificates
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=SSL_CERT_FILE, keyfile=SSL_KEY_FILE)
        
        # Print certificate details for debugging
        with open(SSL_CERT_FILE, 'r') as f:
            cert_content = f.read()
            print(f"Certificate details: {cert_content[:100]}...")
        
        print(f"SSL certificates loaded successfully from:")
        print(f"  - Certificate: {SSL_CERT_FILE}")
        print(f"  - Private key: {SSL_KEY_FILE}")
        return context
    except Exception as e:
        print(f"Error loading SSL certificates: {e}")
        print("Running without SSL (not secure).")
        return False

if __name__ == '__main__':
    # Create a proper SSL context if certificates exist
    ssl_context = check_ssl_config()
    
    if ssl_context:
        # Run with SSL
        print("Starting Flask app with SSL on port 5000")
        app.run(host='0.0.0.0', port=5000, ssl_context=ssl_context)
    else:
        # Run without SSL
        print("Starting Flask app WITHOUT SSL on port 5000")
        app.run(host='0.0.0.0', port=5000)
