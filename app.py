import os
from flask import Flask, request, jsonify, render_template, Response
import riva.client
import riva.client.audio_io

app = Flask(__name__)

# Riva configuration
RIVA_API_URL = "localhost:50051"  # Default Riva server address
RIVA_CLIENT = None

# SSL Configuration
SSL_CERT_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem"
SSL_KEY_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem"

def get_riva_client():
    global RIVA_CLIENT
    if RIVA_CLIENT is None:
        RIVA_CLIENT = riva.client.RivaClient(RIVA_API_URL)
    return RIVA_CLIENT

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/asr-stream', methods=['POST'])
def asr_stream():
    """Endpoint for streaming ASR"""
    client = get_riva_client()
    
    # Configure ASR streaming
    config = riva.client.ASRConfig()
    config.enable_automatic_punctuation = True
    config.language_code = "en-US"  # Change as needed
    
    # Start streaming ASR session
    def generate():
        # Create ASR stream
        asr_service = client.streaming_asr(config)
        
        # Process incoming audio chunks
        for chunk in request.stream:
            resp = asr_service.send(chunk)
            
            # If we have results, return them
            if resp and resp.results:
                for result in resp.results:
                    if result.alternatives:
                        text = result.alternatives[0].transcript
                        is_final = result.is_final
                        yield f'data: {{"text": "{text}", "is_final": {str(is_final).lower()}}}\n\n'
        
        # Finish the stream
        final_resp = asr_service.finish()
        if final_resp and final_resp.results:
            for result in final_resp.results:
                if result.alternatives:
                    text = result.alternatives[0].transcript
                    yield f'data: {{"text": "{text}", "is_final": true}}\n\n'
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/tts', methods=['POST'])
def tts():
    """Endpoint for text-to-speech"""
    client = get_riva_client()
    
    data = request.json
    text = data.get('text', '')
    voice_name = data.get('voice', 'English-US.Female-1')
    
    # Configure TTS request
    req = riva.client.TTSRequest()
    req.text = text
    req.language_code = "en-US"  # Change as needed
    req.encoding = riva.client.AudioEncoding.LINEAR_PCM
    req.sample_rate_hz = 44100
    req.voice_name = voice_name
    
    # Stream audio chunks
    def generate():
        for resp in client.synthesize_online(req):
            yield resp.audio
    
    return Response(generate(), mimetype='audio/wav')

@app.route('/available-voices', methods=['GET'])
def available_voices():
    """Get available TTS voices"""
    client = get_riva_client()
    voices = client.get_available_voices()
    return jsonify(voices)

if __name__ == '__main__':
    context = (SSL_CERT_FILE, SSL_KEY_FILE)
    app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=True)
