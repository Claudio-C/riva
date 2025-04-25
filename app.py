import os
import json
import base64
from flask import Flask, request, jsonify, render_template, send_from_directory
import riva.client
from config import SSL_CERT_FILE, SSL_KEY_FILE, RIVA_SERVER, DEBUG

app = Flask(__name__)

# Initialize Riva client
def get_riva_client():
    auth = riva.client.Auth(uri=RIVA_SERVER)
    return riva.client.RivaClient(auth=auth)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/api/asr', methods=['POST'])
def speech_to_text():
    try:
        # Get audio data from request
        audio_data = request.files.get('audio')
        if not audio_data:
            audio_data = base64.b64decode(request.json.get('audio').split(',')[1])
        else:
            audio_data = audio_data.read()
            
        # Process with Riva ASR
        client = get_riva_client()
        config = riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=16000,
            language_code="en-US",
            max_alternatives=1,
            enable_automatic_punctuation=True
        )
        
        response = client.recognize(audio_data, config)
        
        # Return the transcription
        if response and response.results:
            transcript = response.results[0].alternatives[0].transcript
            return jsonify({'success': True, 'text': transcript})
        
        return jsonify({'success': False, 'error': 'No transcription found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    try:
        # Get text from request
        text = request.json.get('text', '')
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'})
        
        # Process with Riva TTS
        client = get_riva_client()
        
        # Configure TTS request
        req = riva.client.SynthesizeSpeechRequest(
            text=text,
            language_code="en-US",
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=22050,
            voice_name="English-US.Female-1"
        )
        
        # Get audio from Riva
        resp = client.synthesize_speech(req)
        
        # Return audio data as base64
        audio_b64 = base64.b64encode(resp.audio).decode('utf-8')
        return jsonify({
            'success': True, 
            'audio': audio_b64,
            'content_type': 'audio/wav'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    context = (SSL_CERT_FILE, SSL_KEY_FILE)
    app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=DEBUG)
