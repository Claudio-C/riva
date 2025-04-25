document.addEventListener('DOMContentLoaded', () => {
    // ASR (Speech-to-Text) functionality
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const asrResultBox = document.getElementById('asrResult');
    const audioFileInput = document.getElementById('audioFile');
    
    let mediaRecorder;
    let audioChunks = [];
    
    // Initialize media recorder
    async function setupMediaRecorder() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });
            
            mediaRecorder.addEventListener('stop', () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                processAudioBlob(audioBlob);
                audioChunks = [];
            });
            
            return true;
        } catch (err) {
            console.error('Error accessing microphone:', err);
            asrResultBox.textContent = 'Error accessing microphone. Please check permissions.';
            return false;
        }
    }
    
    startRecordingBtn.addEventListener('click', async () => {
        asrResultBox.textContent = 'Recording...';
        if (!mediaRecorder) {
            const initialized = await setupMediaRecorder();
            if (!initialized) return;
        }
        
        audioChunks = [];
        mediaRecorder.start();
        startRecordingBtn.disabled = true;
        stopRecordingBtn.disabled = false;
    });
    
    stopRecordingBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
            asrResultBox.textContent = 'Processing audio...';
        }
    });
    
    audioFileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            asrResultBox.textContent = 'Processing audio file...';
            processAudioBlob(file);
        }
    });
    
    async function processAudioBlob(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob);
        
        try {
            const response = await fetch('/asr', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (data.success) {
                let resultText = '';
                data.results.forEach(result => {
                    resultText += `${result.transcript} (Confidence: ${(result.confidence * 100).toFixed(2)}%)\n\n`;
                });
                asrResultBox.textContent = resultText || 'No speech detected';
            } else {
                asrResultBox.textContent = `Error: ${data.error}`;
            }
        } catch (error) {
            console.error('Error processing audio:', error);
            asrResultBox.textContent = 'Error processing audio. Please try again.';
        }
    }
    
    // TTS (Text-to-Speech) functionality
    const ttsText = document.getElementById('ttsText');
    const ttsButton = document.getElementById('ttsButton');
    const ttsStreamButton = document.getElementById('ttsStreamButton');
    const ttsAudio = document.getElementById('ttsAudio');
    const voiceSelect = document.getElementById('voiceSelect');
    
    ttsButton.addEventListener('click', async () => {
        const text = ttsText.value.trim();
        if (!text) {
            alert('Please enter text to synthesize');
            return;
        }
        
        ttsButton.disabled = true;
        ttsButton.textContent = 'Generating...';
        
        try {
            const response = await fetch('/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text,
                    voice: voiceSelect.value
                })
            });
            
            if (response.ok) {
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                ttsAudio.src = audioUrl;
                ttsAudio.play();
            } else {
                const error = await response.json();
                alert(`Error: ${error.error}`);
            }
        } catch (error) {
            console.error('Error generating speech:', error);
            alert('Error generating speech. Please try again.');
        } finally {
            ttsButton.disabled = false;
            ttsButton.textContent = 'Generate Speech';
        }
    });
    
    ttsStreamButton.addEventListener('click', async () => {
        const text = ttsText.value.trim();
        if (!text) {
            alert('Please enter text to synthesize');
            return;
        }
        
        ttsStreamButton.disabled = true;
        ttsStreamButton.textContent = 'Streaming...';
        
        try {
            const response = await fetch('/tts-stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text,
                    voice: voiceSelect.value
                })
            });
            
            if (response.ok) {
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                ttsAudio.src = audioUrl;
                ttsAudio.play();
            } else {
                const error = await response.json();
                alert(`Error: ${error.error}`);
            }
        } catch (error) {
            console.error('Error streaming speech:', error);
            alert('Error streaming speech. Please try again.');
        } finally {
            ttsStreamButton.disabled = false;
            ttsStreamButton.textContent = 'Stream Speech';
        }
    });
});
