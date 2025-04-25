import grpc
import wave
import time
import threading
import os
import sys
from typing import Generator, List, Optional

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Create __init__.py files to make the directories proper Python packages
for pkg_dir in ["riva", "riva/proto"]:
    init_file = os.path.join(current_dir, pkg_dir, "__init__.py")
    if not os.path.exists(init_file):
        os.makedirs(os.path.dirname(init_file), exist_ok=True)
        with open(init_file, "w") as f:
            pass

# Now try to import the generated modules
try:
    from riva.proto import riva_asr_pb2 as rasr
    from riva.proto import riva_asr_pb2_grpc as rasr_srv
    from riva.proto import riva_audio_pb2 as ra
    print("Successfully imported Riva modules from package")
except ImportError as e:
    # Detailed error for debugging
    print(f"Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {current_dir}")
    print(f"Checking for generated files...")
    
    # List files in the proto directory
    proto_dir = os.path.join(current_dir, "riva", "proto")
    if os.path.exists(proto_dir):
        files = os.listdir(proto_dir)
        print(f"Files in {proto_dir}: {files}")
    else:
        print(f"Proto directory {proto_dir} does not exist")

    # Try direct imports as a last resort
    try:
        # Try to use a relative import path
        sys.path.insert(0, os.path.join(current_dir, "riva", "proto"))
        import riva_asr_pb2 as rasr
        import riva_asr_pb2_grpc as rasr_srv
        import riva_audio_pb2 as ra
        print("Imported using direct path")
    except ImportError as e2:
        print(f"Final import attempt failed: {e2}")
        raise ImportError("Could not import Riva proto modules. Please ensure they are generated correctly.")

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
                yield rasr.StreamingRecognizeRequest(audio_content=chunk)
        
        # Stream recognition
        responses = self.asr_client.StreamingRecognize(request_generator())
        
        for response in responses:
            for result in response.results:
                if result.alternatives:
                    yield {
                        'transcript': result.alternatives[0].transcript,
                        'is_final': result.is_final
                    }
    
    def close(self):
        """Close the gRPC channel."""
        self.channel.close()
