#!/usr/bin/env python3
import os
import subprocess
import sys
import time

def run_command(command, error_message=None):
    """Run a command and print its output in real time."""
    print(f"Running: {command}")
    try:
        process = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Print output in real time
        for line in process.stdout:
            print(line.strip())
        
        process.wait()
        
        if process.returncode != 0 and error_message:
            print(f"\n{error_message}")
            return False
        return True
    except Exception as e:
        print(f"Error executing command: {e}")
        if error_message:
            print(error_message)
        return False

def check_proto_files():
    """Check if required proto files exist."""
    proto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "riva", "proto")
    required_files = [
        "riva_asr_pb2.py", 
        "riva_asr_pb2_grpc.py", 
        "riva_audio_pb2.py", 
        "riva_audio_pb2_grpc.py"
    ]
    
    # Check ASR proto files (required)
    missing_asr = [f for f in required_files if not os.path.exists(os.path.join(proto_dir, f))]
    if missing_asr:
        print(f"Missing required ASR proto files: {', '.join(missing_asr)}")
        return False
    
    # Check TTS proto files (optional)
    tts_files = [
        "riva_tts_pb2.py", 
        "riva_tts_pb2_grpc.py"
    ]
    missing_tts = [f for f in tts_files if not os.path.exists(os.path.join(proto_dir, f))]
    if missing_tts:
        print(f"Missing TTS proto files: {', '.join(missing_tts)}")
        print("TTS functionality will not be available")
        
    return True

def main():
    """Main function to run the Riva application."""
    # Change to the script's directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Check if proto files exist
    if not check_proto_files():
        print("Generating ASR proto files...")
        run_command("python generate_protos.py", "Failed to generate ASR proto files")
    
    # Always try to generate TTS proto files
    print("Generating TTS proto files...")
    run_command("python generate_tts_protos.py", "Failed to generate TTS proto files")
    
    # Wait a moment to make sure the files are fully written
    time.sleep(1)
    
    # Run the Flask app
    print("\nStarting Riva Flask Application...")
    run_command("python app.py", "Failed to start Flask application")

if __name__ == "__main__":
    main()
