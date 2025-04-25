#!/usr/bin/env python3
import os
import sys
import glob
import shutil

def locate_and_fix_proto_files():
    """Find and fix the location of proto generated files."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Print Python info for debugging
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {current_dir}")
    
    # Search for proto files
    print("\nSearching for *_pb2*.py files:")
    all_found_files = []
    
    # Search in various locations
    for root, _, files in os.walk(current_dir):
        for file in files:
            if file.endswith('_pb2.py') or file.endswith('_pb2_grpc.py'):
                file_path = os.path.join(root, file)
                all_found_files.append(file_path)
                print(f"Found: {file_path}")
    
    if not all_found_files:
        print("No proto files found!")
        return
    
    # Create the riva/proto directory if it doesn't exist
    proto_dir = os.path.join(current_dir, "riva", "proto")
    os.makedirs(proto_dir, exist_ok=True)
    
    # Create __init__.py files
    with open(os.path.join(current_dir, "riva", "__init__.py"), "w") as f:
        pass
    with open(os.path.join(proto_dir, "__init__.py"), "w") as f:
        pass
    
    # Copy proto files to the expected location
    print("\nCopying files to riva/proto directory:")
    for file_path in all_found_files:
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(proto_dir, file_name)
        shutil.copy(file_path, dest_path)
        print(f"Copied {file_name} to {dest_path}")
    
    print("\nProto files should now be correctly located in riva/proto directory.")
    print("Try importing them using: from riva.proto import riva_asr_pb2")

if __name__ == "__main__":
    locate_and_fix_proto_files()
