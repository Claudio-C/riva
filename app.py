from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import os
import tempfile
import uuid
import threading
import json
import time
from riva_client import RivaClient

app = Flask(__name__, static_folder='static', template_folder='templates')

# SSL certificate paths
SSL_CERT_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem"
SSL_KEY_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem"

# Riva client configuration
RIVA_SERVER = "localhost:50051"  # Default Riva server address
riva_client = RivaClient(RIVA_SERVER)

# Store active streaming sessions
active_sessions = {}

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

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
    
    # Store session info
    active_sessions[session_id] = {
        'created_at': time.time(),
        'audio_chunks': [],
        'results': [],
        'complete': False
    }
    
    return jsonify({'session_id': session_id})

@app.route('/stream_audio/<session_id>', methods=['POST'])
def stream_audio(session_id):
    """Add audio chunk to an existing streaming session."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    if not request.data:
        return jsonify({'error': 'No audio data received'}), 400
    
    session = active_sessions[session_id]
    session['audio_chunks'].append(request.data)
    
    # Get sample rate from query params or use default
    sample_rate = int(request.args.get('sample_rate', 16000))
    
    # Process in separate thread to avoid blocking
    def process_audio():
        def audio_stream():
            yield request.data
        
        try:
            for result in riva_client.transcribe_stream(audio_stream(), sample_rate_hz=sample_rate):
                if session_id in active_sessions:  # Check if session still exists
                    session = active_sessions[session_id]
                    session['results'].append(result)
        except Exception as e:
            print(f"Error in stream processing: {e}")
    
    # Start processing thread
    threading.Thread(target=process_audio).start()
    
    # Return the latest results we have so far
    latest_results = [r['transcript'] for r in session['results'] if r['is_final']]
    if not latest_results and session['results']:
        # Return the latest interim result if no final results yet
        latest_results = [session['results'][-1]['transcript']]
    
    return jsonify({
        'transcription': ' '.join(latest_results) if latest_results else '',
        'is_final': any(r['is_final'] for r in session['results']) if session['results'] else False
    })

@app.route('/stream_stop/<session_id>', methods=['POST'])
def stream_stop(session_id):
    """Finalize a streaming session and get the complete transcription."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = active_sessions[session_id]
    session['complete'] = True
    
    # Get final transcription
    final_results = [r['transcript'] for r in session['results'] if r['is_final']]
    final_transcription = ' '.join(final_results) if final_results else ''
    
    # Cleanup session after a delay to allow final results to be retrieved
    def cleanup_session():
        time.sleep(60)  # Keep session for 1 minute
        if session_id in active_sessions:
            del active_sessions[session_id]
    
    threading.Thread(target=cleanup_session).start()
    
    return jsonify({'final_transcription': final_transcription})

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Check if SSL certificates exist
    if os.path.exists(SSL_CERT_FILE) and os.path.exists(SSL_KEY_FILE):
        # Run with SSL
        app.run(host='0.0.0.0', port=5000, ssl_context=(SSL_CERT_FILE, SSL_KEY_FILE))
    else:
        # Run without SSL (for development)
        print("Warning: SSL certificates not found. Running without SSL (not secure).")
        app.run(host='0.0.0.0', port=5000)
