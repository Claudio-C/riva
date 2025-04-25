import os
import sys
import shutil

def fix_package_structure():
    """
    Create proper Python package structure for the Riva proto modules.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Ensure riva and riva/proto are proper Python packages
    for pkg_dir in ["riva", "riva/proto"]:
        pkg_path = os.path.join(current_dir, pkg_dir)
        os.makedirs(pkg_path, exist_ok=True)
        
        # Create an __init__.py file if it doesn't exist
        init_file = os.path.join(pkg_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass
            print(f"Created package init file: {init_file}")
    
    # Check if the generated proto files exist in the right location
    proto_files = [
        ("riva_asr_pb2.py", "riva/proto/riva_asr_pb2.py"),
        ("riva_asr_pb2_grpc.py", "riva/proto/riva_asr_pb2_grpc.py"),
        ("riva_audio_pb2.py", "riva/proto/riva_audio_pb2.py"),
        ("riva_common_pb2.py", "riva/proto/riva_common_pb2.py")
    ]
    
    for source, dest in proto_files:
        # First check if they exist directly in the riva/proto directory
        if os.path.exists(os.path.join(current_dir, dest)):
            print(f"Proto file already in correct location: {dest}")
            continue
            
        # Then check if they exist in the root directory
        source_path = os.path.join(current_dir, source)
        if os.path.exists(source_path):
            # Move to the correct location
            dest_path = os.path.join(current_dir, dest)
            shutil.copy2(source_path, dest_path)
            print(f"Copied {source} to {dest}")
    
    print("Package structure fixed. Try running your application now.")

if __name__ == "__main__":
    fix_package_structure()
