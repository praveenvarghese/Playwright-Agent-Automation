# upload_app_docs.py
"""
Utility script to upload application documentation to the vector database.
This script provides more advanced uploading options than the basic functionality in main.py.
"""

import os
import argparse
from document_retrieval import upload_application_document, upload_documents_from_directory

def main():
    parser = argparse.ArgumentParser(description='Upload application documentation to the vector database')
    parser.add_argument('--file', '-f', help='Upload a single file')
    parser.add_argument('--directory', '-d', help='Upload all files from a directory')
    parser.add_argument('--recursive', '-r', action='store_true', help='Recursively upload files from subdirectories')
    parser.add_argument('--extensions', '-e', type=str, default='.txt,.md,.py,.html,.js,.css,.json,.rst',
                        help='Comma-separated list of file extensions to upload (default: .txt,.md,.py,.html,.js,.css,.json,.rst)')
    parser.add_argument('--exclude', '-x', type=str, default='',
                        help='Comma-separated list of directory names to exclude (e.g., .git,__pycache__)')
    
    args = parser.parse_args()
    
    # Parse extensions and excluded directories
    allowed_extensions = tuple(args.extensions.split(','))
    excluded_dirs = args.exclude.split(',') if args.exclude else ['.git', '__pycache__', 'node_modules', 'venv', 'env']
    
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File {args.file} does not exist")
            return
        
        print(f"Uploading file: {args.file}")
        try:
            result = upload_application_document(args.file)
            print(f"✅ {result}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
    elif args.directory:
        if not os.path.exists(args.directory) or not os.path.isdir(args.directory):
            print(f"Error: Directory {args.directory} does not exist or is not a directory")
            return
        
        if args.recursive:
            # Recursive upload
            file_count = 0
            success_count = 0
            error_count = 0
            
            print(f"Starting recursive upload from directory: {args.directory}")
            print(f"Using file extensions: {args.extensions}")
            print(f"Excluding directories: {excluded_dirs}")
            
            for root, dirs, files in os.walk(args.directory):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs]
                
                for file in files:
                    if file.endswith(allowed_extensions):
                        file_path = os.path.join(root, file)
                        file_count += 1
                        print(f"[{file_count}] Uploading file: {file_path}")
                        try:
                            result = upload_application_document(file_path)
                            print(f"  ✅ {result}")
                            success_count += 1
                        except Exception as e:
                            print(f"  ❌ Error uploading {file_path}: {e}")
                            error_count += 1
            
            print(f"\nUpload summary:")
            print(f"  Total files processed: {file_count}")
            print(f"  Successfully uploaded: {success_count}")
            print(f"  Errors: {error_count}")
        else:
            # Non-recursive upload (use the existing function)
            print(f"Uploading files from directory: {args.directory}")
            try:
                results = upload_documents_from_directory(args.directory)
                success_count = sum(1 for r in results if not r.startswith("Error"))
                error_count = len(results) - success_count
                
                for result in results:
                    if result.startswith("Error"):
                        print(f"❌ {result}")
                    else:
                        print(f"✅ {result}")
                
                print(f"\nUpload summary:")
                print(f"  Total files processed: {len(results)}")
                print(f"  Successfully uploaded: {success_count}")
                print(f"  Errors: {error_count}")
            except Exception as e:
                print(f"❌ Error: {e}")
    else:
        print("Error: Please specify either a file (-f) or a directory (-d) to upload")
        parser.print_help()

if __name__ == "__main__":
    main()