import grpc
import wave
import time
import threading
from typing import Generator, List, Optional
import os
import sys

# Add the current directory to the Python path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import generated proto classes - try different import paths
try:
    # First try direct import (files in current directory)
    import riva.proto.riva_asr_pb2 as rasr
    import riva.proto.riva_asr_pb2_grpc as rasr_srv
    import riva.proto.riva_audio_pb2 as ra
    print("Successfully imported Riva modules from current directory")
except ImportError:
    try:
        # Try absolute imports
        from riva.proto import riva_asr_pb2 as rasr
        from riva.proto import riva_asr_pb2_grpc as rasr_srv
        from riva.proto import riva_audio_pb2 as ra
        print("Successfully imported Riva modules using absolute paths")
    except ImportError:
        try:
            # Try direct imports of the generated files
            import riva_asr_pb2 as rasr
            import riva_asr_pb2_grpc as rasr_srv
            import riva_audio_pb2 as ra
            print("Successfully imported Riva modules directly")
        except ImportError:
            # Try to find the generated files
            proto_files = [
                "riva/proto/riva_asr_pb2.py",
                "riva/proto/riva_asr_pb2_grpc.py",
                "riva/proto/riva_audio_pb2.py",
                "riva_asr_pb2.py",
                "riva_asr_pb2_grpc.py", 
                "riva_audio_pb2.py"
            ]
            
            found_files = [f for f in proto_files if os.path.exists(f)]
            print(f"Found generated files: {found_files}")
            
            raise ImportError("Could not import Riva proto modules. Please run generate_protos.py first and check the output for errors.")

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
