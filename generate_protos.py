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
    
    # URLs for the proto files
    proto_urls = {
        "riva_asr.proto": "https://raw.githubusercontent.com/nvidia-riva/cpp-clients/main/proto/riva_asr.proto",
        "riva_audio.proto": "https://raw.githubusercontent.com/nvidia-riva/cpp-clients/main/proto/riva_audio.proto",
        "riva_common.proto": "https://raw.githubusercontent.com/nvidia-riva/cpp-clients/main/proto/riva_common.proto"
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
    # Create proto directory if it doesn't exist
    os.makedirs("riva_api", exist_ok=True)
    
    # Create an __init__.py file to make it a proper package
    init_file = os.path.join("riva_api", "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            pass
    
    # Create riva directory structure in riva_api
    os.makedirs(os.path.join("riva_api", "riva", "proto"), exist_ok=True)
    with open(os.path.join("riva_api", "riva", "__init__.py"), "w") as f:
        pass
    with open(os.path.join("riva_api", "riva", "proto", "__init__.py"), "w") as f:
        pass
    
    # Define the proto files we need
    proto_files = [
        "riva/proto/riva_asr.proto",
        "riva/proto/riva_audio.proto",
        "riva/proto/riva_common.proto"
    ]
    
    # Check if proto files exist locally
    proto_dir = "riva/proto"
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
            
            # Use protoc to generate Python code
            cmd = [
                "python3", "-m", "grpc_tools.protoc",
                f"--proto_path=.",
                f"--python_out=.",
                f"--grpc_python_out=.",
                proto_file
            ]
            subprocess.check_call(cmd)
            
            # Make sure import paths are correct in generated code
            generated_pb2 = proto_file.replace('.proto', '_pb2.py')
            generated_pb2_grpc = proto_file.replace('.proto', '_pb2_grpc.py')
            
            # Fix imports in generated files
            for gen_file in [generated_pb2, generated_pb2_grpc]:
                if os.path.exists(gen_file):
                    with open(gen_file, 'r') as f:
                        content = f.read()
                    
                    # Fix imports
                    content = content.replace('import riva.proto.', 'import riva_api.riva.proto.')
                    
                    with open(gen_file, 'w') as f:
                        f.write(content)
                    
                    # Move file to riva_api directory
                    target_dir = os.path.join("riva_api", os.path.dirname(gen_file))
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.move(gen_file, os.path.join("riva_api", gen_file))
            
            print(f"Successfully generated code for {proto_file}")
        except Exception as e:
            print(f"Error generating code for {proto_file}: {e}")
    
    print("gRPC code generation complete.")

if __name__ == "__main__":
    generate_protos()
