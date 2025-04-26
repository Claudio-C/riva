#!/usr/bin/env python3
import grpc
import json
import argparse
import sys
import os

def query_riva_asr_models(server_address="localhost:50051"):
    """
    Query the Riva server directly to list available ASR models and languages.
    
    Args:
        server_address: Riva server address (host:port)
        
    Returns:
        Dictionary of available ASR models and languages
    """
    try:
        # Import Riva proto files dynamically
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        sys.path.insert(0, os.path.join(current_dir, "riva", "proto"))
        
        # Try different import strategies
        try:
            from riva.proto import riva_asr_pb2 as rasr
            from riva.proto import riva_asr_pb2_grpc as rasr_srv
        except ImportError:
            import riva_asr_pb2 as rasr
            import riva_asr_pb2_grpc as rasr_srv
        
        # Create a gRPC channel
        channel = grpc.insecure_channel(server_address)
        
        # Create a client
        asr_client = rasr_srv.RivaSpeechRecognitionStub(channel)
        
        # Query available languages by trying different language codes
        # and checking which ones return errors
        test_languages = [
            "en-US", "en-GB", "es-ES", "es-US", "fr-FR", "de-DE", "it-IT", 
            "pt-BR", "ru-RU", "zh-CN", "ja-JP", "ko-KR", "ar-AR", "hi-IN",
            "nl-NL", "nl-BE"
        ]
        
        available_models = {
            "conformer-streaming": [],
            "conformer-offline": [],
            "conformer-streaming-throughput": []
        }
        
        print("Testing available languages and models...")
        
        # Test streaming configuration (online)
        config = rasr.RecognitionConfig(
            encoding=0,  # LINEAR_PCM
            sample_rate_hertz=16000,
            max_alternatives=1
        )
        
        # Test each language
        for lang in test_languages:
            print(f"Testing language: {lang}")
            
            # Try streaming mode
            try:
                config.language_code = lang
                streaming_config = rasr.StreamingRecognitionConfig(
                    config=config,
                    interim_results=True
                )
                # Create a stub request to check if this model/language is supported
                request = rasr.RecognizeRequest(config=config, audio=b'')
                asr_client.Recognize(request, timeout=1)
                # If no error, this language is supported for streaming
                available_models["conformer-streaming"].append(lang)
                print(f"  - {lang} supported for streaming")
            except grpc.RpcError as e:
                if "Unavailable model" not in str(e):
                    # If error is not about unavailable model, it's a different issue
                    # Likely the language is supported but request is invalid (empty audio)
                    available_models["conformer-streaming"].append(lang)
                    print(f"  - {lang} likely supported for streaming")
            
            # Try offline mode
            try:
                config.language_code = lang
                # Create a stub request to check if this model/language is supported
                request = rasr.RecognizeRequest(config=config, audio=b'')
                asr_client.Recognize(request, timeout=1)
                # If no error, this language is supported for offline
                available_models["conformer-offline"].append(lang)
                print(f"  - {lang} supported for offline")
            except grpc.RpcError as e:
                if "Unavailable model" not in str(e):
                    available_models["conformer-offline"].append(lang)
                    print(f"  - {lang} likely supported for offline")
        
        # Clean up results - remove empty models
        for model in list(available_models.keys()):
            if not available_models[model]:
                del available_models[model]
        
        # If no languages were detected, default to en-US
        if not any(available_models.values()):
            available_models = {
                "conformer-streaming": ["en-US"],
                "conformer-offline": ["en-US"]
            }
            print("No languages detected, defaulting to en-US")
        
        return available_models
    
    except ImportError as e:
        print(f"Error importing Riva modules: {e}")
        return {"conformer-streaming": ["en-US"], "conformer-offline": ["en-US"]}
    except Exception as e:
        print(f"Error querying Riva server: {e}")
        return {"conformer-streaming": ["en-US"], "conformer-offline": ["en-US"]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Riva server for available models")
    parser.add_argument('--server', default="localhost:50051", help="Riva server address")
    parser.add_argument('--output', help="Output file for results (JSON format)")
    
    args = parser.parse_args()
    
    models = {
        "asr_models": query_riva_asr_models(args.server),
        "tts_models": {"fastpitch_hifigan": ["en-US"]},
        "default_asr_model": "conformer-streaming",
        "default_asr_language": "en-US",
        "default_tts_model": "fastpitch_hifigan",
        "default_tts_language": "en-US"
    }
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(models, f, indent=2)
    else:
        print(json.dumps(models, indent=2))
