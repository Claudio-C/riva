#!/usr/bin/env python3
import os
import sys
import wave
from riva_client import RivaClient

def test_tts(text, voice_name="English-US-Female-1", output_file="tts_output.wav"):
    """
    Test Text-to-Speech functionality with Riva
    
    Args:
        text: Text to synthesize
        voice_name: Voice to use
        output_file: Path to save the output audio file
    """
    print(f"Testing TTS with voice: {voice_name}")
    print(f"Text: {text}")
    
    # Create Riva client
    client = RivaClient("localhost:50051")
    
    try:
        # Get available voices
        voices = client.get_available_voices("en-US")
        print(f"Available voices: {', '.join(voices)}")
        
        # If specified voice is not available, use the first available voice
        if voice_name not in voices and voices:
            print(f"Voice {voice_name} not available, using {voices[0]} instead")
            voice_name = voices[0]
        
        # Synthesize speech
        audio_data = client.synthesize_speech(
            text=text,
            voice_name=voice_name
        )
        
        if not audio_data:
            print("Failed to synthesize speech")
            return False
        
        # Write audio data to WAV file
        with wave.open(output_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)  # Sample rate
            wav_file.writeframes(audio_data)
        
        print(f"Audio saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        client.close()

if __name__ == "__main__":
    text = "Hello, this is a test of the NVIDIA Riva Text-to-Speech system."
    
    if len(sys.argv) > 1:
        text = sys.argv[1]
    
    voice = "English-US-Female-1"
    if len(sys.argv) > 2:
        voice = sys.argv[2]
    
    output_file = "tts_output.wav"
    if len(sys.argv) > 3:
        output_file = sys.argv[3]
    
    test_tts(text, voice, output_file)
