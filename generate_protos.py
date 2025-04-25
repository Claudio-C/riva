import os
import sys
import subprocess
from pathlib import Path
import urllib.request
import tempfile
import shutil
import tarfile
import io

def download_proto_files(target_dir):
    """
    Download Riva proto files from NVIDIA's GitHub repository.
    """
    print("Downloading Riva proto files...")
    proto_files_dir = os.path.join(target_dir, "riva", "proto")
    os.makedirs(proto_files_dir, exist_ok=True)
    
    # URLs for the proto files - updated to the correct repository
    proto_urls = {
        "riva_asr.proto": "https://raw.githubusercontent.com/nvidia-riva/common/refs/heads/main/riva/proto/riva_asr.proto",
        "riva_audio.proto": "https://raw.githubusercontent.com/nvidia-riva/common/refs/heads/main/riva/proto/riva_audio.proto",
        "riva_common.proto": "https://raw.githubusercontent.com/nvidia-riva/common/refs/heads/main/riva/proto/riva_common.proto"
    }
    
    for proto_file, url in proto_urls.items():
        target_path = os.path.join(proto_files_dir, proto_file)
        print(f"Downloading {proto_file} from {url}")
        try:
            urllib.request.urlretrieve(url, target_path)
            print(f"Downloaded {proto_file}")
        except Exception as e:
            print(f"Error downloading {proto_file}: {e}")
            return False
    
    return True

def generate_protos():
    """
    Generate Python gRPC client code from Riva proto files.
    """
    # We'll place the generated files directly in the current directory
    # This makes imports simpler
    
    # Define the proto files we need
    proto_files = [
        "riva/proto/riva_asr.proto",
        "riva/proto/riva_audio.proto",
        "riva/proto/riva_common.proto"
    ]
    
    # Check if proto files exist locally and download if needed
    missing_protos = [f for f in proto_files if not os.path.exists(f)]
    
    # If missing, try to download from NVIDIA GitHub
    if missing_protos:
        temp_dir = tempfile.mkdtemp()
        try:
            if download_proto_files(temp_dir):
                print("Proto files downloaded successfully")
            else:
                print("Failed to download proto files")
                return
                
            # Copy downloaded proto files to current directory
            for proto_file in proto_files:
                base_name = os.path.basename(proto_file)
                src_path = os.path.join(temp_dir, proto_file)
                dst_path = proto_file
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy(src_path, dst_path)
                print(f"Copied {base_name} to {dst_path}")
        finally:
            shutil.rmtree(temp_dir)
    
    # Generate Python code for each proto file
    for proto_file in proto_files:
        try:
            if not os.path.exists(proto_file):
                print(f"Warning: Proto file {proto_file} not found. Skipping.")
                continue
                
            print(f"Generating gRPC code for {proto_file}")
            
            # Use protoc to generate Python code directly in the current directory
            cmd = [
                "python3", "-m", "grpc_tools.protoc",
                f"--proto_path=.",
                f"--python_out=.",
                f"--grpc_python_out=.",
                proto_file
            ]
            subprocess.check_call(cmd)
            
            # The generated files are now directly in the current directory structure
            # No need to move them anywhere
            print(f"Successfully generated code for {proto_file}")
        except Exception as e:
            print(f"Error generating code for {proto_file}: {e}")
    
    print("gRPC code generation complete.")

if __name__ == "__main__":
    generate_protos()
