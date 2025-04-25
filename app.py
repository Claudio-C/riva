import os
from flask import Flask, render_template, request, jsonify, Response
import riva.client
from riva.client.auth import Auth
from riva.client.asr import ASRService
from riva.client.tts import SpeechSynthesisService
from io import BytesIO

app = Flask(__name__)

# SSL certificate paths
SSL_CERT_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem"
SSL_KEY_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem"

# Riva client configuration
RIVA_API_URL = "localhost:50051"  # Default Riva API endpoint

# Initialize Riva client
auth = Auth(uri=RIVA_API_URL, use_ssl=False)  # Set to True if Riva server uses SSL

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/asr', methods=['POST'])
def speech_to_text():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No audio file selected'}), 400
    
    # Create ASR service
    asr_service = ASRService(auth)
    
    # Configure ASR parameters for streaming
    config = riva.client.StreamingRecognitionConfig(
        config=riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=16000,
            language_code="en-US",
            max_alternatives=1,
            profanity_filter=False,
            enable_automatic_punctuation=True,
            verbatim_transcripts=False,
        )
    )
    
    # Read audio data
    audio_data = audio_file.read()
    
    # Process audio in streaming mode
    responses = []
    for response in asr_service.streaming_recognize(config=config, audio_generator=[audio_data]):
        for result in response.results:
            if result.is_final:
                transcription = result.alternatives[0].transcript
                confidence = result.alternatives[0].confidence
                responses.append({
                    "transcript": transcription,
                    "confidence": confidence
                })
    
    return jsonify({
        'success': True,
        'results': responses
    })

@app.route('/tts', methods=['POST'])
def text_to_speech():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400

    text = data['text']
    voice = data.get('voice', 'English-US-Female-1')
    
    # Create TTS service
    tts_service = SpeechSynthesisService(auth)
    
    try:
        # Use streaming synthesis
        audio_chunks = []
        responses = tts_service.synthesize(
            text,
            voice_name=voice,
            sample_rate_hz=22050
        )
        
        for response in responses:
            audio_chunks.append(response.audio)
        
        audio_data = b''.join(audio_chunks)
        
        # Return audio as response
        return Response(audio_data, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tts-stream', methods=['POST'])
def text_to_speech_stream():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400

    text = data['text']
    voice = data.get('voice', 'English-US-Female-1')
    
    # Create TTS service
    tts_service = SpeechSynthesisService(auth)
    
    def generate():
        try:
            responses = tts_service.synthesize(
                text,
                voice_name=voice,
                sample_rate_hz=22050
            )
            
            for response in responses:
                yield response.audio
        except Exception as e:
            print(f"Error in TTS streaming: {e}")
    
    return Response(generate(), mimetype='audio/wav')

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        ssl_context=(SSL_CERT_FILE, SSL_KEY_FILE),
        debug=True
    )
