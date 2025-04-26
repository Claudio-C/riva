#!/usr/bin/env python3
import json
import argparse
import os
import subprocess
from query_riva_models import query_riva_asr_models

def update_models_config(server_address="localhost:50051", output_file="models.json"):
    """
    Update the models configuration file with the latest models from the server
    
    Args:
        server_address: Riva server address
        output_file: Output JSON file path
    """
    print(f"Querying Riva server at {server_address}...")
    
    # Query available ASR models
    asr_models = query_riva_asr_models(server_address)
    
    # For TTS, we'll just use defaults for now
    tts_models = {"fastpitch_hifigan": ["en-US"]}
    
    # Set default selections
    default_asr_model = next(iter(asr_models.keys())) if asr_models else "conformer-streaming"
    default_asr_language = asr_models.get(default_asr_model, ["en-US"])[0]
    
    default_tts_model = next(iter(tts_models.keys())) if tts_models else "fastpitch_hifigan"
    default_tts_language = tts_models.get(default_tts_model, ["en-US"])[0]
    
    # Create the models configuration
    models_config = {
        "asr_models": asr_models,
        "tts_models": tts_models,
        "default_asr_model": default_asr_model,
        "default_asr_language": default_asr_language,
        "default_tts_model": default_tts_model,
        "default_tts_language": default_tts_language
    }
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(models_config, f, indent=2)
    
    print(f"Models configuration updated in {output_file}")
    return models_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update models configuration")
    parser.add_argument('--server', default="localhost:50051", help="Riva server address")
    parser.add_argument('--output', default="models.json", help="Output file path")
    
    args = parser.parse_args()
    update_models_config(args.server, args.output)
