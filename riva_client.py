import grpc
import wave
import time
import threading
import os
import sys
import glob
import queue
import shutil
from typing import Generator, List, Optional

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Helper function to find proto files
def find_proto_files():
    """Find and print location of generated proto files"""
    search_paths = [
        current_dir,
        os.path.join(current_dir, "riva", "proto"),
        os.path.join(current_dir, "riva"),
    ]
    
    for search_path in search_paths:
        proto_files = glob.glob(os.path.join(search_path, "*pb2*.py"))
        if proto_files:
            print(f"Found proto files in {search_path}:")
            for file in proto_files:
                print(f"  - {os.path.basename(file)}")
            return search_path
    
    print("No proto files found!")
    return None

# Create __init__.py files for proper package structure
for pkg_dir in ["riva", "riva/proto"]:
    init_file = os.path.join(current_dir, pkg_dir, "__init__.py")
    if not os.path.exists(init_file):
        os.makedirs(os.path.dirname(init_file), exist_ok=True)
        with open(init_file, "w") as f:
            pass

# Find where the proto files are actually located
proto_path = find_proto_files()
if proto_path:
    sys.path.insert(0, proto_path)

# Try different import strategies
rasr = rasr_srv = ra = None
tts_available = False  # Flag to track TTS availability
rtts = rtts_srv = None
import_success = False

# First strategy: standard import from package
try:
    print("Trying import from riva.proto package...")
    from riva.proto import riva_asr_pb2 as rasr
    from riva.proto import riva_asr_pb2_grpc as rasr_srv
    from riva.proto import riva_audio_pb2 as ra
    
    # Try to import TTS modules but continue if not available
    try:
        from riva.proto import riva_tts_pb2 as rtts
        from riva.proto import riva_tts_pb2_grpc as rtts_srv
        tts_available = True
        print("TTS modules successfully imported")
    except ImportError as e:
        print(f"TTS modules not available: {e}")
        print("TTS functionality will be disabled")
    
    print("Success: Imported ASR modules from riva.proto package")
    import_success = True
except ImportError as e:
    print(f"Error importing from riva.proto: {e}")

# Second strategy: direct import
if not import_success:
    try:
        print("Trying direct import...")
        import riva_asr_pb2 as rasr
        import riva_asr_pb2_grpc as rasr_srv
        import riva_audio_pb2 as ra
        
        # Try to import TTS modules but continue if not available
        try:
            import riva_tts_pb2 as rtts
            import riva_tts_pb2_grpc as rtts_srv
            tts_available = True
            print("TTS modules successfully imported")
        except ImportError as e:
            print(f"TTS modules not available: {e}")
            print("TTS functionality will be disabled")
        
        print("Success: Imported ASR modules directly")
        import_success = True
    except ImportError as e:
        print(f"Error with direct import: {e}")

# Third strategy: fix the generated files
if not import_success:
    try:
        print("Attempting to fix and locate proto files...")
        # Look for the generated files in the current directory
        pb2_files = glob.glob(os.path.join(current_dir, "*_pb2.py"))
        pb2_grpc_files = glob.glob(os.path.join(current_dir, "*_pb2_grpc.py"))
        
        # Copy to the right location if found
        if pb2_files or pb2_grpc_files:
            print(f"Found {len(pb2_files)} pb2 files and {len(pb2_grpc_files)} pb2_grpc files")
            for file_path in pb2_files + pb2_grpc_files:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(current_dir, "riva", "proto", file_name)
                shutil.copy(file_path, dest_path)
                print(f"Copied {file_name} to riva/proto/")
            
            # Try import again
            from riva.proto import riva_asr_pb2 as rasr
            from riva.proto import riva_asr_pb2_grpc as rasr_srv
            from riva.proto import riva_audio_pb2 as ra
            
            # Try to import TTS modules but continue if not available
            try:
                from riva.proto import riva_tts_pb2 as rtts
                from riva.proto import riva_tts_pb2_grpc as rtts_srv
                tts_available = True
                print("TTS modules successfully imported")
            except ImportError as e:
                print(f"TTS modules not available: {e}")
                print("TTS functionality will be disabled")
            
            print("Success: Imported ASR modules after fixing file locations")
            import_success = True
    except Exception as e:
        print(f"Error fixing proto files: {e}")

if not import_success:
    print("\nCould not import Riva proto modules. Please check the output for errors.")
    print("Make sure the proto files were generated correctly.")
    sys.exit(1)

class RivaClient:
    """Client class for Riva ASR service."""
    
    def __init__(self, server_address: str = "localhost:50051"):
        """
        Initialize Riva client with server address.
        
        Args:
            server_address: The address of the Riva server (host:port)
        """
        self.server_address = server_address
        self.tts_available = tts_available
        
        # Create a gRPC channel
        self.channel = grpc.insecure_channel(server_address)
        
        # Create a stub (client) for ASR
        self.asr_client = rasr_srv.RivaSpeechRecognitionStub(self.channel)
        
        # Create a stub for TTS if available
        if self.tts_available:
            self.tts_client = rtts_srv.RivaSpeechSynthesisStub(self.channel)
    
    def transcribe_stream(self, audio_stream: Generator[bytes, None, None], 
                         sample_rate_hz: int = 16000,
                         language_code: str = "en-US") -> Generator[dict, None, None]:
        """
        Transcribe streaming audio with Riva ASR.
        
        Args:
            audio_stream: Generator yielding chunks of audio data
            sample_rate_hz: Sample rate of the audio
            language_code: Language code for transcription
            
        Yields:
            Transcription text as it becomes available
        """
        # Create a streaming recognition config
        config = rasr.RecognitionConfig(
            encoding=ra.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate_hz,
            language_code=language_code,
            max_alternatives=1,
            enable_automatic_punctuation=True
        )
        
        streaming_config = rasr.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )
        
        # First request contains the config
        first_request = rasr.StreamingRecognizeRequest(streaming_config=streaming_config)
        
        def request_generator():
            yield first_request
            for chunk in audio_stream:
                if chunk:
                    yield rasr.StreamingRecognizeRequest(audio_content=chunk)
        
        try:
            # Stream recognition
            responses = self.asr_client.StreamingRecognize(request_generator())
            
            for response in responses:
                for result in response.results:
                    if result.alternatives:
                        yield {
                            'transcript': result.alternatives[0].transcript,
                            'is_final': result.is_final
                        }
        except Exception as e:
            print(f"Error in Riva transcribe_stream: {e}")
            yield {
                'transcript': f"Error: {str(e)}",
                'is_final': True,
                'error': True
            }
    
    def create_streaming_session(self, audio_queue, results_queue, 
                               sample_rate_hz=16000, 
                               language_code="en-US"):
        """
        Create a long-running streaming session that reads audio from a queue.
        
        Args:
            audio_queue: Queue to receive audio chunks
            results_queue: Queue to put transcription results
            sample_rate_hz: Audio sample rate
            language_code: Language code for transcription
        """
        # Create a streaming recognition config
        config = rasr.RecognitionConfig(
            encoding=ra.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate_hz,
            language_code=language_code,
            max_alternatives=1,
            enable_automatic_punctuation=True
        )
        
        streaming_config = rasr.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )
        
        # First request contains the config
        first_request = rasr.StreamingRecognizeRequest(streaming_config=streaming_config)
        
        def audio_generator():
            """Generate audio requests from queue."""
            # First yield the config request
            yield first_request
            
            while True:
                try:
                    # Get audio chunk from queue with timeout
                    chunk = audio_queue.get(timeout=2.0)
                    
                    # None is our signal to end the stream
                    if chunk is None:
                        print("Received end signal in audio generator")
                        break
                        
                    # Skip empty chunks
                    if not chunk or len(chunk) == 0:
                        audio_queue.task_done()
                        continue
                        
                    # Yield the audio chunk
                    yield rasr.StreamingRecognizeRequest(audio_content=chunk)
                    
                    # Mark task as done
                    audio_queue.task_done()
                    
                except queue.Empty:
                    # No data for a while, but keep the stream open
                    continue
                except Exception as e:
                    print(f"Error in audio generator: {e}")
                    break
            
            print("Audio generator finished")
        
        try:
            print("Starting streaming recognition session")
            # Start the streaming recognition
            responses = self.asr_client.StreamingRecognize(audio_generator())
            
            # Process responses and put results in the results queue
            for response in responses:
                for result in response.results:
                    if result.alternatives:
                        results_queue.put({
                            'transcript': result.alternatives[0].transcript,
                            'is_final': result.is_final,
                            'timestamp': time.time()
                        })
                        
            print("Streaming recognition completed")
        except Exception as e:
            print(f"Error in streaming session: {e}")
            results_queue.put({
                'transcript': f"Error in streaming: {str(e)}",
                'is_final': True,
                'error': True,
                'timestamp': time.time()
            })
    
    def synthesize_speech(self, 
                       text: str, 
                       language_code: str = "en-US",
                       voice_name: str = None,
                       sample_rate_hz: int = 22050) -> Optional[bytes]:
        """
        Synthesize speech from text using Riva TTS.
        
        Args:
            text: Text to synthesize
            language_code: Language code for synthesis
            voice_name: Voice to use for synthesis (or None to use default)
            sample_rate_hz: Output audio sample rate
            
        Returns:
            Audio data as bytes or None if TTS is unavailable
        """
        if not self.tts_available:
            print("TTS functionality is not available")
            return None
            
        try:
            # If voice_name is None, use language code directly
            if voice_name is None:
                voice_name = language_code
            
            print(f"Attempting TTS with voice: '{voice_name}', language: '{language_code}'")
            
            # Create synthesis request
            request = rtts.SynthesizeSpeechRequest(
                text=text,
                language_code=language_code,
                encoding=ra.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate_hz,
                voice_name=voice_name
            )
            
            # Call the service
            response = self.tts_client.Synthesize(request)
            
            # Return the audio data
            return response.audio
            
        except Exception as e:
            print(f"Error in Riva synthesize_speech: {e}")
            
            # If specified voice failed, try language code as voice name
            if voice_name != language_code:
                print(f"Retrying with voice name = language code: '{language_code}'")
                try:
                    request = rtts.SynthesizeSpeechRequest(
                        text=text,
                        language_code=language_code,
                        encoding=ra.AudioEncoding.LINEAR_PCM,
                        sample_rate_hz=sample_rate_hz,
                        voice_name=language_code
                    )
                    response = self.tts_client.Synthesize(request)
                    return response.audio
                except Exception as retry_e:
                    print(f"Retry also failed: {retry_e}")
            
            return None
    
    def get_available_voices(self, language_code: str = "en-US") -> List[str]:
        """
        Get available TTS voices for the specified language.
        
        Args:
            language_code: Language code to query voices for
            
        Returns:
            List of available voice names
        """
        if not self.tts_available:
            print("TTS functionality is not available")
            return ["English-US"] # Simplified voice name
            
        try:
            # Check if ListVoicesRequest is available
            if not hasattr(rtts, 'ListVoicesRequest'):
                print("ListVoicesRequest not available in proto")
                # Return simplified voice name without gender specification
                return [f"{language_code.split('-')[0]}-{language_code.split('-')[1]}"]
                
            # Create request
            request = rtts.ListVoicesRequest(language_code=language_code)
            
            # Call the service
            response = self.tts_client.ListVoices(request)
            
            # Return voice names
            return [voice.name for voice in response.voices]
            
        except Exception as e:
            print(f"Error getting available voices: {e}")
            # Return simplified voice name that matches Riva's expectation
            return [f"{language_code.split('-')[0]}-{language_code.split('-')[1]}"]
    
    def stream_synthesize_speech(self, 
                              text: str, 
                              language_code: str = "en-US",
                              voice_name: str = None,
                              sample_rate_hz: int = 22050) -> Generator[bytes, None, None]:
        """
        Stream synthesized speech from text using Riva TTS.
        
        Args:
            text: Text to synthesize
            language_code: Language code for synthesis
            voice_name: Voice to use for synthesis (or None to use default)
            sample_rate_hz: Output audio sample rate
            
        Yields:
            Audio data chunks as bytes
        """
        if not self.tts_available:
            print("TTS functionality is not available")
            yield None
            return
        
        try:
            # If voice_name is None or contains "Female/Male", use just the language code
            if voice_name is None or "Female" in voice_name or "Male" in voice_name:
                # Use simplified voice name format that should work with Riva
                voice_name = f"{language_code.split('-')[0]}-{language_code.split('-')[1]}"
            
            # Create synthesis request
            request = rtts.SynthesizeSpeechRequest(
                text=text,
                language_code=language_code,
                encoding=ra.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate_hz,
                voice_name=voice_name
            )
            
            # Call the service
            responses = self.tts_client.SynthesizeStreaming(request)
            
            # Yield audio chunks
            for response in responses:
                yield response.audio
                
        except Exception as e:
            print(f"Error in Riva stream_synthesize_speech: {e}")
            yield None
    
    def close(self):
        """Close the gRPC channel."""
        self.channel.close()
