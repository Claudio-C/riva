document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const uploadForm = document.getElementById('uploadForm');
    const uploadResult = document.getElementById('uploadResult');
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const liveResult = document.getElementById('liveResult');
    const asrModelSelect = document.getElementById('asrModel');
    const asrLanguageSelect = document.getElementById('asrLanguage');
    
    // TTS Elements
    const ttsVoiceSelect = document.getElementById('ttsVoice');
    const ttsTextArea = document.getElementById('ttsText');
    const ttsSynthesizeBtn = document.getElementById('ttsSynthesize');
    const ttsPlayBtn = document.getElementById('ttsPlay');
    const ttsStopBtn = document.getElementById('ttsStop');
    const ttsDownloadBtn = document.getElementById('ttsDownload');
    const ttsStatus = document.getElementById('ttsStatus');
    const ttsPlayer = document.getElementById('ttsPlayer');
    
    // TTS variables
    let currentTtsAudioFile = null;
    let audioPlayer = null;
    
    // Model and language variables
    let availableModels = {};
    let currentModel = '';
    let currentLanguage = '';
    
    // Fetch available models from server
    fetch('/get_models')
        .then(response => response.json())
        .then(data => {
            availableModels = data.asr_models;
            
            // Populate ASR model dropdown
            for (const model in availableModels) {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                asrModelSelect.appendChild(option);
            }
            
            // Set default model
            if (data.default_asr_model) {
                asrModelSelect.value = data.default_asr_model;
                currentModel = data.default_asr_model;
            }
            
            // Update languages for selected model
            updateLanguageOptions(currentModel);
            
            // Set default language if available
            if (data.default_asr_language) {
                currentLanguage = data.default_asr_language;
                if (isLanguageSupported(currentModel, currentLanguage)) {
                    asrLanguageSelect.value = currentLanguage;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching models:', error);
        });
    
    // Update language options when model changes
    asrModelSelect.addEventListener('change', function() {
        currentModel = this.value;
        updateLanguageOptions(currentModel);
    });
    
    // Update current language when selection changes
    asrLanguageSelect.addEventListener('change', function() {
        currentLanguage = this.value;
    });
    
    // Function to update language dropdown based on selected model
    function updateLanguageOptions(modelName) {
        // Clear existing options
        asrLanguageSelect.innerHTML = '';
        
        if (availableModels[modelName]) {
            availableModels[modelName].forEach(language => {
                const option = document.createElement('option');
                option.value = language;
                option.textContent = language;
                asrLanguageSelect.appendChild(option);
                
                // Select the current language if it's supported
                if (language === currentLanguage) {
                    asrLanguageSelect.value = currentLanguage;
                }
            });
            
            // If current language isn't supported, select the first one
            if (!isLanguageSupported(modelName, currentLanguage)) {
                currentLanguage = availableModels[modelName][0];
                asrLanguageSelect.value = currentLanguage;
            }
        }
    }
    
    // Check if a language is supported for a given model
    function isLanguageSupported(modelName, language) {
        return availableModels[modelName] && 
               (availableModels[modelName].includes(language) || 
                availableModels[modelName][0] === 'multi');
    }
    
    // Handle file upload form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        // Add model and language to form data
        formData.append('asr_model', currentModel);
        formData.append('asr_language', currentLanguage);
        
        uploadResult.textContent = `Processing with ${currentModel} (${currentLanguage})...`;
        
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
                uploadResult.innerHTML += `<p class="model-info">Model: ${data.model}, Language: ${data.language}</p>`;
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
    let streamInterval;
    
    // Start recording
    startRecordingBtn.addEventListener('click', async function() {
        audioChunks = [];
        liveResult.textContent = `Initializing ${currentModel} (${currentLanguage})...`;
        
        try {
            // Start a new session with the server
            const response = await fetch('/stream_start', { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    asr_model: currentModel,
                    asr_language: currentLanguage
                })
            });
            const data = await response.json();
            
            if (data.error) {
                liveResult.textContent = `Error: ${data.error}`;
                return;
            }
            
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
            liveResult.textContent = `Recording with ${data.model} (${data.language})... Speak now.`;
            
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
            
            // Set up polling for results
            streamInterval = setInterval(() => {
                getTranscriptionResults();
            }, 1000);
            
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
            // Only send if there's actual audio data
            if (audioChunk && audioChunk.byteLength > 0) {
                await fetch(`/stream_audio/${sessionId}?sample_rate=16000`, {
                    method: 'POST',
                    body: audioChunk
                });
            }
        } catch (error) {
            console.error('Error sending audio chunk:', error);
        }
    }
    
    // Get latest transcription results
    async function getTranscriptionResults() {
        if (!sessionId) return;
        
        try {
            // Send an empty POST request to get latest results without sending audio
            const response = await fetch(`/stream_audio/${sessionId}?sample_rate=16000`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': '0'
                }
            });
            
            if (!response.ok) {
                console.error('Error getting results:', response.status);
                return;
            }
            
            const data = await response.json();
            if (data.transcription) {
                liveResult.textContent = data.transcription;
            }
        } catch (error) {
            console.error('Error getting transcription results:', error);
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
                
                // Clear polling interval
                clearInterval(streamInterval);
                
                // Get final transcription
                const response = await fetch(`/stream_stop/${sessionId}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.error) {
                    liveResult.textContent = `Error: ${data.error}`;
                } else {
                    liveResult.textContent = data.final_transcription || 'Transcription complete';
                    liveResult.innerHTML += `<p class="model-info">Model: ${data.model}, Language: ${data.language}</p>`;
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
        
        if (streamInterval) {
            clearInterval(streamInterval);
        }
        
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
    
    // TTS Functions
    
    // Load available TTS voices for selected language
    function loadTtsVoices(language) {
        fetch(`/tts/voices?language=${language}`)
            .then(response => response.json())
            .then(data => {
                // Clear existing options
                ttsVoiceSelect.innerHTML = '';
                
                // Add available voices or defaults
                const voices = data.voices || ['English-US-Female-1', 'English-US-Male-1'];
                
                voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice;
                    option.textContent = formatVoiceName(voice);
                    ttsVoiceSelect.appendChild(option);
                });
                
                // Set default voice
                if (data.default_voice) {
                    ttsVoiceSelect.value = data.default_voice;
                }
            })
            .catch(error => {
                console.error('Error loading TTS voices:', error);
                // Add default voices as fallback
                ttsVoiceSelect.innerHTML = '';
                
                ['English-US-Female-1', 'English-US-Male-1'].forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice;
                    option.textContent = formatVoiceName(voice);
                    ttsVoiceSelect.appendChild(option);
                });
            });
    }
    
    // Format voice name for display
    function formatVoiceName(voice) {
        // Convert names like "English-US-Female-1" to "English Female 1"
        const parts = voice.split('-');
        if (parts.length >= 3) {
            const language = parts[0];
            const gender = parts[2];
            const number = parts.length > 3 ? parts[3] : '';
            return `${language} ${gender} ${number}`.trim();
        }
        return voice;
    }
    
    // Handle TTS synthesis
    ttsSynthesizeBtn.addEventListener('click', function() {
        const text = ttsTextArea.value.trim();
        
        if (!text) {
            ttsStatus.textContent = 'Please enter text to synthesize';
            return;
        }
        
        // Clear previous audio
        if (audioPlayer) {
            audioPlayer.pause();
            audioPlayer.remove();
            audioPlayer = null;
        }
        
        ttsStatus.textContent = 'Synthesizing speech...';
        ttsPlayBtn.disabled = true;
        ttsStopBtn.disabled = true;
        ttsDownloadBtn.disabled = true;
        
        // Send synthesis request
        fetch('/tts/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: text,
                language: currentLanguage,
                voice: ttsVoiceSelect.value
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                ttsStatus.textContent = `Error: ${data.error}`;
                return;
            }
            
            // Store audio file reference
            currentTtsAudioFile = data.audio_file;
            
            // Create audio player
            audioPlayer = new Audio(`/tts/audio/${data.audio_file}`);
            ttsPlayer.innerHTML = '';
            ttsPlayer.appendChild(audioPlayer);
            
            // Update UI
            ttsStatus.textContent = 'Speech synthesized successfully.';
            ttsPlayBtn.disabled = false;
            ttsDownloadBtn.disabled = false;
            
            // Add event listeners to audio player
            audioPlayer.addEventListener('ended', function() {
                ttsPlayBtn.textContent = 'Play';
                ttsStopBtn.disabled = true;
            });
            
            audioPlayer.addEventListener('play', function() {
                ttsPlayBtn.textContent = 'Pause';
                ttsStopBtn.disabled = false;
            });
            
            audioPlayer.addEventListener('pause', function() {
                ttsPlayBtn.textContent = 'Play';
            });
        })
        .catch(error => {
            ttsStatus.textContent = `Error: ${error.message}`;
        });
    });
    
    // Handle play/pause button
    ttsPlayBtn.addEventListener('click', function() {
        if (!audioPlayer) return;
        
        if (audioPlayer.paused) {
            audioPlayer.play();
            ttsPlayBtn.textContent = 'Pause';
            ttsStopBtn.disabled = false;
        } else {
            audioPlayer.pause();
            ttsPlayBtn.textContent = 'Play';
        }
    });
    
    // Handle stop button
    ttsStopBtn.addEventListener('click', function() {
        if (!audioPlayer) return;
        
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        ttsPlayBtn.textContent = 'Play';
        ttsStopBtn.disabled = true;
    });
    
    // Handle download button
    ttsDownloadBtn.addEventListener('click', function() {
        if (!currentTtsAudioFile) return;
        
        // Create a download link
        const downloadLink = document.createElement('a');
        downloadLink.href = `/tts/audio/${currentTtsAudioFile}`;
        downloadLink.download = `riva_tts_${Date.now()}.wav`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    });
    
    // Initial setup
    // Load TTS voices for default language (en-US)
    loadTtsVoices('en-US');
    
    // Update TTS voices when language changes
    asrLanguageSelect.addEventListener('change', function() {
        // This ensures TTS voices match the selected language
        loadTtsVoices(this.value);
    });
});
