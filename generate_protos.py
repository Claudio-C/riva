import os
import sys
import subprocess
from pathlib import Path

def generate_protos():
    """
    Generate Python gRPC client code from Riva proto files.
    
    Assumes the Riva proto files are available in the expected locations.
    """
    # Create proto directory if it doesn't exist
    os.makedirs("riva_api", exist_ok=True)
    
    # Create an __init__.py file to make it a proper package
    with open(os.path.join("riva_api", "__init__.py"), "w") as f:
        pass
    
    # Define the proto files we need
    proto_files = [
        "riva/proto/riva_asr.proto",
        "riva/proto/riva_audio.proto",
        "riva/proto/riva_common.proto"
    ]
    
    # Define proto paths - adjust this if your proto files are in a different location
    proto_paths = [
        "/opt/nvidia/riva/proto",  # Default Riva proto location
        "."  # Current directory 
    ]
    
    # Convert to command line arguments
    proto_path_args = []
    for path in proto_paths:
        proto_path_args.extend(["-I", path])
    
    # Generate Python code for each proto file
    for proto_file in proto_files:
        try:
            # First try the default Riva location
            if os.path.exists(f"/opt/nvidia/riva/proto/{proto_file}"):
                proto_path = f"/opt/nvidia/riva/proto/{proto_file}"
            else:
                # If not found, assume it's in the current directory structure
                proto_path = proto_file
                
            if not os.path.exists(proto_path):
                print(f"Warning: Proto file {proto_path} not found. Skipping.")
                continue
                
            print(f"Generating gRPC code for {proto_path}")
            
            # Run the protoc compiler
            cmd = [
                "python", "-m", "grpc_tools.protoc",
                *proto_path_args,
                f"--python_out=.",
                f"--grpc_python_out=.",
                proto_path
            ]
            subprocess.check_call(cmd)
            
            print(f"Successfully generated code for {proto_file}")
        except Exception as e:
            print(f"Error generating code for {proto_file}: {e}")
    
    print("gRPC code generation complete.")

if __name__ == "__main__":
    generate_protos()
