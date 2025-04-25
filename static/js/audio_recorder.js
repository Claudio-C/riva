document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const uploadForm = document.getElementById('uploadForm');
    const uploadResult = document.getElementById('uploadResult');
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const liveResult = document.getElementById('liveResult');
    
    // Handle file upload form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        uploadResult.textContent = 'Processing...';
        
        fetch('/transcribe', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                uploadResult.textContent = `Error: ${data.error}`;
            } else {
                uploadResult.textContent = data.transcription || 'No transcription available';
            }
        })
        .catch(error => {
            uploadResult.textContent = `Error: ${error.message}`;
        });
    });
    
    // Audio recording variables
    let mediaRecorder;
    let audioChunks = [];
    let sessionId = null;
    let audioContext;
    let processor;
    let input;
    
    // Start recording
    startRecordingBtn.addEventListener('click', async function() {
        audioChunks = [];
        liveResult.textContent = 'Initializing...';
        
        try {
            // Start a new session with the server
            const response = await fetch('/stream_start', { method: 'POST' });
            const data = await response.json();
            sessionId = data.session_id;
            
            // Request permission to use microphone
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Set up audio context for Web Audio API
            audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000 // Match Riva's expected sample rate
            });
            
            // Update UI
            startRecordingBtn.disabled = true;
            stopRecordingBtn.disabled = false;
            liveResult.textContent = 'Recording... Speak now.';
            
            // Connect the audio nodes
            input = audioContext.createMediaStreamSource(stream);
            processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            // Set up the recording pipeline
            input.connect(processor);
            processor.connect(audioContext.destination);
            
            // Process audio data
            processor.onaudioprocess = function(e) {
                // Get raw audio data
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Convert to 16-bit PCM
                const pcmData = convertFloat32ToInt16(inputData);
                
                // Send to server
                sendAudioChunk(pcmData);
            };
            
        } catch (error) {
            liveResult.textContent = `Error: ${error.message}`;
            resetRecording();
        }
    });
    
    // Convert Float32Array to Int16Array for PCM
    function convertFloat32ToInt16(buffer) {
        const l = buffer.length;
        const buf = new Int16Array(l);
        
        for (let i = 0; i < l; i++) {
            buf[i] = Math.min(1, Math.max(-1, buffer[i])) * 0x7FFF;
        }
        
        return buf.buffer;
    }
    
    // Send audio chunk to server
    async function sendAudioChunk(audioChunk) {
        if (!sessionId) return;
        
        try {
            const response = await fetch(`/stream_audio/${sessionId}?sample_rate=16000`, {
                method: 'POST',
                body: audioChunk
            });
            
            const data = await response.json();
            if (data.transcription) {
                liveResult.textContent = data.transcription;
            }
        } catch (error) {
            console.error('Error sending audio chunk:', error);
        }
    }
    
    // Stop recording
    stopRecordingBtn.addEventListener('click', async function() {
        if (sessionId) {
            try {
                // Disconnect audio processing
                if (processor && input) {
                    input.disconnect();
                    processor.disconnect();
                }
                
                // Close audio context
                if (audioContext && audioContext.state !== 'closed') {
                    await audioContext.close();
                }
                
                // Get final transcription
                const response = await fetch(`/stream_stop/${sessionId}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.error) {
                    liveResult.textContent = `Error: ${data.error}`;
                } else {
                    liveResult.textContent = data.final_transcription || 'Transcription complete';
                }
            } catch (error) {
                liveResult.textContent = `Error finalizing transcription: ${error.message}`;
            }
            
            resetRecording();
        }
    });
    
    function resetRecording() {
        startRecordingBtn.disabled = false;
        stopRecordingBtn.disabled = true;
        sessionId = null;
        
        // Clean up audio resources
        if (processor && input) {
            try {
                input.disconnect();
                processor.disconnect();
            } catch (e) {
                console.error('Error disconnecting audio nodes:', e);
            }
        }
        
        if (audioContext && audioContext.state !== 'closed') {
            audioContext.close().catch(e => console.error('Error closing AudioContext:', e));
        }
    }
});
