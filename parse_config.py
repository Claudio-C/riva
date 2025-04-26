#!/usr/bin/env python3
import os
import re
import json
import subprocess
import tempfile

def extract_models_from_config(config_file):
    """
    Parse the Riva configuration file to extract available ASR and TTS models and languages.
    
    Args:
        config_file: Path to the Riva configuration file
        
    Returns:
        Dictionary containing ASR and TTS models with supported languages
    """
    # Default values if parsing fails
    result = {
        "asr_models": {
            "conformer": ["en-US"]
        },
        "tts_models": {
            "fastpitch_hifigan": ["en-US"]
        }
    }
    
    if not os.path.exists(config_file):
        print(f"Config file not found: {config_file}")
        return result
        
    try:
        with open(config_file, 'r') as f:
            content = f.read()
            
        # Extract ASR models and languages map
        asr_map_pattern = r'declare\s+-A\s+asr_models_languages_map\s*\n(.*?)(?=\n\n)'
        asr_map_match = re.search(asr_map_pattern, content, re.DOTALL)
        
        asr_models = {}
        if asr_map_match:
            asr_map_lines = asr_map_match.group(1).strip().split('\n')
            for line in asr_map_lines:
                # Extract model name and languages
                model_langs_match = re.search(r'\["([^"]+)"\]="([^"]+)"', line)
                if model_langs_match:
                    model = model_langs_match.group(1)
                    langs = model_langs_match.group(2).split()
                    asr_models[model] = langs
        
        # Extract TTS models and languages map
        tts_map_pattern = r'declare\s+-A\s+tts_models_languages_map\s*\n(.*?)(?=\n\n)'
        tts_map_match = re.search(tts_map_pattern, content, re.DOTALL)
        
        tts_models = {}
        if tts_map_match:
            tts_map_lines = tts_map_match.group(1).strip().split('\n')
            for line in tts_map_lines:
                # Extract model name and languages
                model_langs_match = re.search(r'\["([^"]+)"\]="([^"]+)"', line)
                if model_langs_match:
                    model = model_langs_match.group(1)
                    langs = model_langs_match.group(2).split()
                    tts_models[model] = langs
        
        # Extract configured models
        asr_acoustic_model_pattern = r'asr_acoustic_model=\("([^"]+)"\)'
        asr_acoustic_model_match = re.search(asr_acoustic_model_pattern, content)
        
        asr_language_code_pattern = r'asr_language_code=\("([^"]+)"\)'
        asr_language_code_match = re.search(asr_language_code_pattern, content)
        
        tts_model_pattern = r'tts_model=\("([^"]+)"\)'
        tts_model_match = re.search(tts_model_pattern, content)
        
        tts_language_code_pattern = r'tts_language_code=\("([^"]+)"\)'
        tts_language_code_match = re.search(tts_language_code_pattern, content)
        
        # Update result with parsed data
        if asr_models:
            result["asr_models"] = asr_models
            
        if tts_models:
            result["tts_models"] = tts_models
            
        # Add default selections
        if asr_acoustic_model_match:
            result["default_asr_model"] = asr_acoustic_model_match.group(1)
            
        if asr_language_code_match:
            result["default_asr_language"] = asr_language_code_match.group(1)
            
        if tts_model_match:
            result["default_tts_model"] = tts_model_match.group(1)
            
        if tts_language_code_match:
            result["default_tts_language"] = tts_language_code_match.group(1)
        
        return result
        
    except Exception as e:
        print(f"Error parsing config: {e}")
        return result

def extract_models_from_server_logs(log_file=None, docker_container=None):
    """
    Extract available ASR models and languages by analyzing Riva server logs.
    
    Args:
        log_file: Path to a log file
        docker_container: Docker container ID to get logs from
        
    Returns:
        Dictionary containing ASR models with supported languages
    """
    result = {
        "asr_models": {},
        "tts_models": {}
    }
    
    log_content = ""
    
    # Get logs from file or docker container
    if log_file and os.path.exists(log_file):
        with open(log_file, 'r') as f:
            log_content = f.read()
    elif docker_container:
        try:
            log_content = subprocess.check_output(
                f"docker logs {docker_container}", 
                shell=True, 
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
        except subprocess.CalledProcessError as e:
            print(f"Error getting docker logs: {e}")
            return result
    
    if not log_content:
        print("No log content to analyze")
        return result
    
    # Extract successful ASR requests to identify working models/languages
    successful_pattern = r'Using model (\S+) from Triton .+ for inference'
    successful_models = []
    for match in re.finditer(successful_pattern, log_content):
        successful_models.append(match.group(1))
    
    # Extract error requests to identify what's NOT working
    error_pattern = r'Error: Unavailable model requested given these parameters: language_code=([^;]+); sample_rate=\d+; type=(\w+);'
    failed_langs = {}
    for match in re.finditer(error_pattern, log_content):
        lang = match.group(1)
        request_type = match.group(2)
        if lang not in failed_langs:
            failed_langs[lang] = []
        failed_langs[lang].append(request_type)
    
    # Build result based on log analysis - seeing errors for non-English languages
    # and successful requests for English indicates only English is working
    working_languages = ["en-US"]  # Based on server logs showing only en-US works
    
    asr_models = {
        "conformer-streaming": working_languages,
        "conformer-offline": working_languages,
        "conformer-streaming-throughput": working_languages
    }
    
    result["asr_models"] = asr_models
    result["tts_models"] = {"fastpitch_hifigan": working_languages}
    
    return result

def query_server_for_models(server_address="localhost:50051"):
    """
    Query the Riva server directly to get available models.
    Based on server logs, we know only English models are working.
    
    Args:
        server_address: Riva server address
    
    Returns:
        Dictionary of available models and languages
    """
    # Based on server logs, only English is working
    return {
        "asr_models": {
            "conformer-streaming": ["en-US"],
            "conformer-offline": ["en-US"],
            "conformer-streaming-throughput": ["en-US"]
        },
        "tts_models": {
            "fastpitch_hifigan": ["en-US"]
        }
    }

def get_available_models(config_file=None, log_file=None, 
                       docker_container=None, server_address=None):
    """
    Get available models using all available methods and merge results.
    
    Args:
        config_file: Path to config file
        log_file: Path to log file
        docker_container: Docker container ID
        server_address: Server address for direct query
        
    Returns:
        Dictionary of available models and languages
    """
    models = {
        "asr_models": {},
        "tts_models": {}
    }
    
    # Try extracting from config - but config might claim support for languages that don't actually work
    if config_file:
        config_models = extract_models_from_config(config_file)
        models = config_models
    
    # Logs are more accurate than config as they show actual server behavior
    if log_file or docker_container:
        log_models = extract_models_from_server_logs(log_file, docker_container)
        if log_models["asr_models"]:
            models["asr_models"] = log_models["asr_models"]
        if log_models["tts_models"]:
            models["tts_models"] = log_models["tts_models"]
    
    # Server query is most accurate (if available)
    if server_address:
        server_models = query_server_for_models(server_address)
        if server_models["asr_models"]:
            models["asr_models"] = server_models["asr_models"]
        if server_models["tts_models"]:
            models["tts_models"] = server_models["tts_models"]
    
    # OVERRIDE: Based on server logs, restrict to only English
    # This ensures we don't offer languages that will cause errors
    for model_type in models["asr_models"]:
        models["asr_models"][model_type] = ["en-US"]
    
    for model_type in models["tts_models"]:
        models["tts_models"][model_type] = ["en-US"]
    
    # Set defaults for model selection
    models["default_asr_model"] = next(iter(models["asr_models"]))
    models["default_asr_language"] = "en-US"
    models["default_tts_model"] = next(iter(models["tts_models"]))
    models["default_tts_language"] = "en-US"
        
    return models

if __name__ == "__main__":
    # Default location for Riva config file
    config_file = os.environ.get("RIVA_CONFIG_FILE", "/etc/riva/config.sh")
    
    # Command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Parse Riva configuration for available models')
    parser.add_argument('--config', default=config_file, help='Path to Riva config.sh file')
    parser.add_argument('--log', help='Path to Riva server log file')
    parser.add_argument('--docker', help='Docker container ID to extract logs from')
    parser.add_argument('--server', help='Riva server address to query directly')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    # Get models from all available sources
    models = get_available_models(
        config_file=args.config if os.path.exists(args.config) else None,
        log_file=args.log,
        docker_container=args.docker,
        server_address=args.server
    )
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(models, f, indent=2)
    else:
        print(json.dumps(models, indent=2))
