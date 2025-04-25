import grpc
import wave
import time
import threading
import os
import sys
import glob
import queue
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
import_success = False

# First strategy: standard import from package
try:
    print("Trying import from riva.proto package...")
    from riva.proto import riva_asr_pb2 as rasr
    from riva.proto import riva_asr_pb2_grpc as rasr_srv
    from riva.proto import riva_audio_pb2 as ra
    print("Success: Imported from riva.proto package")
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
        print("Success: Imported directly")
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
            print("Success: Imported after fixing file locations")
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
        
        # Create a gRPC channel
        self.channel = grpc.insecure_channel(server_address)
        
        # Create a stub (client)
        self.asr_client = rasr_srv.RivaSpeechRecognitionStub(self.channel)
    
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
    
    def close(self):
        """Close the gRPC channel."""
        self.channel.close()
