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
    # Create proper Python package structure
    current_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
    
    # Create __init__.py files for package structure
    for pkg_dir in ["riva", "riva/proto"]:
        os.makedirs(os.path.join(current_dir, pkg_dir), exist_ok=True)
        with open(os.path.join(current_dir, pkg_dir, "__init__.py"), "w") as f:
            pass
    
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
            
            # Generate directly in the proto directory instead of current directory
            cmd = [
                "python3", "-m", "grpc_tools.protoc",
                "--proto_path=.",
                f"--python_out={current_dir}",
                f"--grpc_python_out={current_dir}",
                proto_file
            ]
            subprocess.check_call(cmd)
            
            # Find the generated files and print their locations
            base_name = os.path.basename(proto_file).replace(".proto", "")
            pb2_file = f"{base_name}_pb2.py"
            pb2_grpc_file = f"{base_name}_pb2_grpc.py"
            
            # Files might be generated in the current directory or with the full path structure
            possible_locations = [
                # With full path structure (likely location)
                os.path.join(current_dir, proto_file.replace(".proto", "_pb2.py")),
                os.path.join(current_dir, proto_file.replace(".proto", "_pb2_grpc.py")),
                # In the current directory
                os.path.join(current_dir, pb2_file),
                os.path.join(current_dir, pb2_grpc_file)
            ]
            
            for file_path in possible_locations:
                if os.path.exists(file_path):
                    print(f"Generated file found at: {file_path}")
            
            print(f"Successfully generated code for {proto_file}")
        except Exception as e:
            print(f"Error generating code for {proto_file}: {e}")
    
    print("gRPC code generation complete.")
    print("\nNow checking for generated files in the expected locations:")
    verify_files_exist()

def verify_files_exist():
    """Verify if the generated files exist in the expected locations."""
    current_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
    
    expected_files = [
        "riva/proto/riva_asr_pb2.py",
        "riva/proto/riva_asr_pb2_grpc.py",
        "riva/proto/riva_audio_pb2.py",
        "riva/proto/riva_audio_pb2_grpc.py",
        "riva/proto/riva_common_pb2.py",
        "riva/proto/riva_common_pb2_grpc.py"
    ]
    
    found_files = []
    missing_files = []
    
    for file_path in expected_files:
        full_path = os.path.join(current_dir, file_path)
        if os.path.exists(full_path):
            found_files.append(file_path)
        else:
            missing_files.append(file_path)
    
    print(f"Found files: {found_files}")
    print(f"Missing files: {missing_files}")
    
    # Search for the files elsewhere in the directory
    print("\nSearching for the missing files in other locations:")
    for root, dirs, files in os.walk(current_dir):
        for file in files:
            if any(file == os.path.basename(missing) for missing in missing_files):
                print(f"Found at: {os.path.join(root, file)}")
                
                # Copy to the expected location if missing
                for missing in missing_files:
                    if file == os.path.basename(missing):
                        dest_path = os.path.join(current_dir, missing)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy(os.path.join(root, file), dest_path)
                        print(f"Copied to: {dest_path}")

if __name__ == "__main__":
    generate_protos()
