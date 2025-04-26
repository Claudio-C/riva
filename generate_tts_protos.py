#!/usr/bin/env python3
import os
import sys
import subprocess
import urllib.request
import tempfile
import shutil

def download_proto_files(target_dir):
    """
    Download all required Riva proto files from NVIDIA's GitHub repository.
    """
    print("Downloading Riva proto files...")
    proto_files_dir = os.path.join(target_dir, "riva", "proto")
    os.makedirs(proto_files_dir, exist_ok=True)
    
    # All required proto files
    proto_files = {
        "riva_tts.proto": "https://raw.githubusercontent.com/nvidia-riva/common/main/riva/proto/riva_tts.proto",
        "riva_audio.proto": "https://raw.githubusercontent.com/nvidia-riva/common/main/riva/proto/riva_audio.proto",
        "riva_common.proto": "https://raw.githubusercontent.com/nvidia-riva/common/main/riva/proto/riva_common.proto"
    }
    
    success = True
    for proto_file, url in proto_files.items():
        target_path = os.path.join(proto_files_dir, proto_file)
        print(f"Downloading {proto_file} from {url}")
        
        try:
            urllib.request.urlretrieve(url, target_path)
            print(f"Downloaded {proto_file}")
        except Exception as e:
            print(f"Error downloading {proto_file}: {e}")
            success = False
    
    return success

def generate_proto_code():
    """
    Generate Python gRPC client code for Riva proto files.
    """
    # Create proper Python package structure
    current_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
    
    # Create __init__.py files for package structure
    for pkg_dir in ["riva", "riva/proto"]:
        pkg_path = os.path.join(current_dir, pkg_dir)
        os.makedirs(pkg_path, exist_ok=True)
        with open(os.path.join(pkg_path, "__init__.py"), "w") as f:
            pass
    
    # Download all required proto files
    if not download_proto_files(current_dir):
        print("Failed to download all required proto files")
        return False
    
    # Define the proto files
    proto_files = [
        "riva/proto/riva_audio.proto",  # Must be first as it's a dependency
        "riva/proto/riva_common.proto", # Must be second as it's a dependency
        "riva/proto/riva_tts.proto"
    ]
    
    # Generate Python code for all proto files
    success = True
    for proto_file in proto_files:
        try:
            if not os.path.exists(proto_file):
                print(f"Error: Proto file {proto_file} not found.")
                success = False
                continue
                
            print(f"Generating gRPC code for {proto_file}")
            
            cmd = [
                sys.executable, "-m", "grpc_tools.protoc",
                "--proto_path=.",
                f"--python_out={current_dir}",
                f"--grpc_python_out={current_dir}",
                proto_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error generating code for {proto_file}: {result.stderr}")
                success = False
            else:
                print(f"Successfully generated code for {proto_file}")
                
                # Find the generated files and print their paths
                pb2_file = proto_file.replace(".proto", "_pb2.py")
                pb2_grpc_file = proto_file.replace(".proto", "_pb2_grpc.py")
                
                for file_path in [pb2_file, pb2_grpc_file]:
                    if os.path.exists(file_path):
                        print(f"Generated: {file_path}")
                    else:
                        print(f"Warning: Expected file {file_path} not found")
            
        except Exception as e:
            print(f"Error processing {proto_file}: {e}")
            success = False
    
    return success

if __name__ == "__main__":
    if generate_proto_code():
        print("\nSuccessfully generated all proto code!")
        print("You can now use TTS functionality in the application.")
    else:
        print("\nThere were errors generating proto code.")
        print("TTS functionality may not be available.")
