#!/usr/bin/env python3
import os
import sys
import subprocess
import urllib.request
import tempfile
import shutil

def download_tts_proto_files(target_dir):
    """
    Download Riva TTS proto files from NVIDIA's GitHub repository.
    """
    print("Downloading Riva TTS proto files...")
    proto_files_dir = os.path.join(target_dir, "riva", "proto")
    os.makedirs(proto_files_dir, exist_ok=True)
    
    # URLs for the TTS proto file
    proto_url = "https://raw.githubusercontent.com/nvidia-riva/common/main/riva/proto/riva_tts.proto"
    
    target_path = os.path.join(proto_files_dir, "riva_tts.proto")
    print(f"Downloading riva_tts.proto from {proto_url}")
    
    try:
        urllib.request.urlretrieve(proto_url, target_path)
        print(f"Downloaded riva_tts.proto")
        return True
    except Exception as e:
        print(f"Error downloading riva_tts.proto: {e}")
        return False

def generate_tts_protos():
    """
    Generate Python gRPC client code for Riva TTS proto files.
    """
    # Create proper Python package structure
    current_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
    
    # Create __init__.py files for package structure
    for pkg_dir in ["riva", "riva/proto"]:
        os.makedirs(os.path.join(current_dir, pkg_dir), exist_ok=True)
        with open(os.path.join(current_dir, pkg_dir, "__init__.py"), "w") as f:
            pass
    
    # Define the TTS proto file
    tts_proto_file = "riva/proto/riva_tts.proto"
    
    # Check if proto file exists locally and download if needed
    if not os.path.exists(tts_proto_file):
        temp_dir = tempfile.mkdtemp()
        try:
            if download_tts_proto_files(temp_dir):
                print("TTS Proto file downloaded successfully")
                
                # Copy downloaded proto file to current directory
                src_path = os.path.join(temp_dir, tts_proto_file)
                os.makedirs(os.path.dirname(tts_proto_file), exist_ok=True)
                shutil.copy(src_path, tts_proto_file)
                print(f"Copied riva_tts.proto to {tts_proto_file}")
            else:
                print("Failed to download TTS proto file")
                return
        finally:
            shutil.rmtree(temp_dir)
    
    # Generate Python code for the TTS proto file
    try:
        if not os.path.exists(tts_proto_file):
            print(f"Error: TTS proto file {tts_proto_file} not found.")
            return
            
        print(f"Generating gRPC code for {tts_proto_file}")
        
        # Generate directly in the proto directory
        cmd = [
            sys.executable, "-m", "grpc_tools.protoc",
            "--proto_path=.",
            f"--python_out={current_dir}",
            f"--grpc_python_out={current_dir}",
            tts_proto_file
        ]
        subprocess.check_call(cmd)
        
        # Find the generated files and print their locations
        pb2_file = tts_proto_file.replace(".proto", "_pb2.py")
        pb2_grpc_file = tts_proto_file.replace(".proto", "_pb2_grpc.py")
        
        for file_path in [pb2_file, pb2_grpc_file]:
            if os.path.exists(file_path):
                print(f"Generated: {file_path}")
            else:
                print(f"Warning: Expected file {file_path} not found")
        
        print("Successfully generated TTS proto code")
    except Exception as e:
        print(f"Error generating TTS proto code: {e}")

if __name__ == "__main__":
    generate_tts_protos()
