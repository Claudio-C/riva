document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const startRecordButton = document.getElementById('startRecording');
    const stopRecordButton = document.getElementById('stopRecording');
    const recordingStatus = document.getElementById('recordingStatus');
    const transcriptionDiv = document.getElementById('transcription');
    const ttsInput = document.getElementById('ttsInput');
    const synthesizeButton = document.getElementById('synthesize');
    const audioPlayer = document.getElementById('audioPlayer');
    
    // Global variables
    let mediaRecorder;
    let audioChunks = [];
    
    // ASR functionality
    startRecordButton.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });
            
            mediaRecorder.addEventListener('stop', async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                
                // Create FormData to send the audio
                const formData = new FormData();
                formData.append('audio', audioBlob);
                
                // Show loading state
                transcriptionDiv.textContent = 'Processing...';
                
                try {
                    // Send to server for ASR processing
                    const response = await fetch('/api/asr', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        transcriptionDiv.textContent = result.text || 'No text recognized';
                    } else {
                        transcriptionDiv.textContent = 'Error: ' + (result.error || 'Unknown error');
                    }
                } catch (error) {
                    transcriptionDiv.textContent = 'Error: ' + error.message;
                }
                
                // Reset UI
                startRecordButton.disabled = false;
                stopRecordButton.disabled = true;
                recordingStatus.style.display = 'none';
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            });
            
            // Start recording
            mediaRecorder.start();
            
            // Update UI
            startRecordButton.disabled = true;
            stopRecordButton.disabled = false;
            recordingStatus.style.display = 'inline';
            transcriptionDiv.textContent = 'Ready to record...';
            
        } catch (error) {
            alert('Error accessing microphone: ' + error.message);
        }
    });
    
    stopRecordButton.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    });
    
    // TTS functionality
    synthesizeButton.addEventListener('click', async () => {
        const text = ttsInput.value.trim();
        
        if (!text) {
            alert('Please enter some text to synthesize');
            return;
        }
        
        synthesizeButton.disabled = true;
        synthesizeButton.textContent = 'Processing...';
        
        try {
            const response = await fetch('/api/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Convert base64 to blob
                const byteCharacters = atob(result.audio);
                const byteNumbers = new Array(byteCharacters.length);
                
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                
                const byteArray = new Uint8Array(byteNumbers);
                const audioBlob = new Blob([byteArray], { type: result.content_type });
                
                // Set audio source and play
                const audioUrl = URL.createObjectURL(audioBlob);
                audioPlayer.src = audioUrl;
                audioPlayer.style.display = 'block';
                audioPlayer.play();
            } else {
                alert('Error: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            synthesizeButton.disabled = false;
            synthesizeButton.textContent = 'Convert to Speech';
        }
    });
});
