import os
from flask import Flask, request, jsonify, render_template_string
from nvidia_riva.client import ASRService
from nvidia_riva.client.audio_io import AudioChunkFileStream

SSL_CERT_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem"
SSL_KEY_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem"

RIVA_SERVER = "localhost:50051"  # Default Riva server address

app = Flask(__name__)

# Initialize Riva ASR client
asr_service = ASRService(
    riva_uri=RIVA_SERVER,
    ssl_cert=None,  # Not needed for localhost unless Riva is using SSL
)

HTML_FORM = """
<!doctype html>
<title>NVIDIA Riva ASR Demo</title>
<h2>Upload or Record Audio (16kHz WAV, PCM)</h2>
<form id="uploadForm" method=post enctype=multipart/form-data>
  <input type=file name=audio accept="audio/wav">
  <input type=submit value=Transcribe>
</form>
<br>
<button id="recordBtn">Record</button>
<button id="stopBtn" disabled>Stop</button>
<audio id="audioPlayback" controls style="display:none"></audio>
<script>
let mediaRecorder;
let audioChunks = [];
const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const audioPlayback = document.getElementById('audioPlayback');
const uploadForm = document.getElementById('uploadForm');

recordBtn.onclick = async function(e) {
  e.preventDefault();
  audioChunks = [];
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.start();
  recordBtn.disabled = true;
  stopBtn.disabled = false;
  mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };
  mediaRecorder.onstop = e => {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    audioPlayback.src = URL.createObjectURL(audioBlob);
    audioPlayback.style.display = 'block';
    // Auto-upload after recording
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');
    fetch('/', { method: 'POST', body: formData })
      .then(response => response.text())
      .then(html => document.documentElement.innerHTML = html);
  };
};

stopBtn.onclick = function(e) {
  e.preventDefault();
  mediaRecorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
};
</script>
{% if transcript is defined %}
  <h3>Transcript:</h3>
  <pre>{{ transcript }}</pre>
{% endif %}
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    transcript = None
    if request.method == 'POST':
        if 'audio' not in request.files:
            transcript = 'No audio file provided'
        else:
            audio_file = request.files['audio']
            audio_path = '/tmp/' + audio_file.filename
            audio_file.save(audio_path)
            with AudioChunkFileStream(audio_path, chunk_size=16000) as stream:
                responses = asr_service.streaming_recognize(
                    audio_chunks=stream,
                    config={
                        "language_code": "en-US",
                        "sample_rate_hertz": 16000,
                        "encoding": "LINEAR_PCM",
                        "max_alternatives": 1,
                        "interim_results": False,
                        "automatic_punctuation": True,
                    }
                )
                transcript = ""
                for response in responses:
                    for result in response.results:
                        if result.alternatives:
                            transcript += result.alternatives[0].transcript
            os.remove(audio_path)
    return render_template_string(HTML_FORM, transcript=transcript)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    audio_path = '/tmp/' + audio_file.filename
    audio_file.save(audio_path)

    # Stream audio to Riva ASR
    with AudioChunkFileStream(audio_path, chunk_size=16000) as stream:
        responses = asr_service.streaming_recognize(
            audio_chunks=stream,
            config={
                "language_code": "en-US",
                "sample_rate_hertz": 16000,
                "encoding": "LINEAR_PCM",
                "max_alternatives": 1,
                "interim_results": False,
                "automatic_punctuation": True,
            }
        )
        transcript = ""
        for response in responses:
            for result in response.results:
                if result.alternatives:
                    transcript += result.alternatives[0].transcript

    os.remove(audio_path)
    return jsonify({'transcript': transcript})

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=8443,
        ssl_context=(SSL_CERT_FILE, SSL_KEY_FILE)
    )
