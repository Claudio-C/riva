#!/usr/bin/env python3
import os
import re
import json

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

if __name__ == "__main__":
    # Default location for Riva config file
    config_file = os.environ.get("RIVA_CONFIG_FILE", "/etc/riva/config.sh")
    
    # Allow command line argument to specify config file
    import sys
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    models = extract_models_from_config(config_file)
    print(json.dumps(models, indent=2))
