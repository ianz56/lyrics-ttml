import os
import re
import argparse
import sys

def minify_ttml(content):
    # Remove XML comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    # Remove all whitespace between tags
    content = re.sub(r'>\s+<', '><', content)
    return content.strip()

def process_directory(source_dir, target_dir):
    source_dir = os.path.abspath(source_dir)
    target_dir = os.path.abspath(target_dir)
    
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)
        
    count = 0
    for root, dirs, files in os.walk(source_dir):
        # Skip the target_dir to avoid recursive minification
        if root.startswith(target_dir) or '.git' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.ttml'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, source_dir)
                target_path = os.path.join(target_dir, rel_path)
                
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                with open(src_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                minified = minify_ttml(content)
                
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(minified)
                
                # print(f"Minified: {rel_path} -> {os.path.relpath(target_path, source_dir)}")
                count += 1
                
    print(f"\nTotal TTML files minified: {count}")
    print(f"Minified output saved to: {os.path.relpath(target_dir, source_dir)}")

def main():
    parser = argparse.ArgumentParser(description="Minify TTML files to a designated folder mapping original structure.")
    parser.add_argument("--src", default=".", help="Source directory (default: current directory)")
    parser.add_argument("--dest", default="minify", help="Destination directory (default: 'minify')")
    args = parser.parse_args()
    
    process_directory(args.src, args.dest)

if __name__ == "__main__":
    main()
