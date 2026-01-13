import argparse
import re
import sys
import os
import xml.etree.ElementTree as ET

def parse_time(time_str):
    """Parses mm:ss.xxx to seconds."""
    if not time_str:
        return 0.0
    try:
        minutes, seconds = time_str.split(':')
        return float(minutes) * 60 + float(seconds)
    except ValueError:
        return 0.0

def format_time(seconds):
    """Formats seconds to mm:ss.xxx."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02}:{secs:06.3f}"

def parse_offset(offset_str):
    """
    Parses offset string to seconds.
    Supports 'ms' suffix for milliseconds (e.g., '100ms', '-50ms').
    Otherwise treats as seconds (e.g., '0.1', '-1.5').
    """
    offset_str = offset_str.strip().lower()
    if offset_str.endswith('ms'):
        try:
            val = float(offset_str[:-2])
            return val / 1000.0
        except ValueError:
            raise ValueError(f"Invalid millisecond format: {offset_str}")
    else:
        try:
            return float(offset_str)
        except ValueError:
            raise ValueError(f"Invalid seconds format: {offset_str}")

def apply_offset(element, offset_seconds):
    """Recursively applies offset to begin, end, and dur attributes."""
    for attr in ['begin', 'end', 'dur']:
        if attr in element.attrib:
            original_time = parse_time(element.attrib[attr])
            
            if attr in ['begin', 'end']:
                new_time = max(0.0, original_time + offset_seconds)
                element.attrib[attr] = format_time(new_time)

    for child in element:
        apply_offset(child, offset_seconds)

def main():
    # Manual argument parsing to handle negative numbers correctly (argparse can interpret -100ms as a flag)
    args = sys.argv[1:]
    
    # Handle help flag
    if not args or '-h' in args or '--help' in args:
        print("Usage: python offset_ttml.py input_file offset [output_file]")
        print("Example: python offset_ttml.py \"file.ttml\" 100ms")
        print("Example: python offset_ttml.py \"file.ttml\" -50ms")
        sys.exit(0)

    input_file = args[0]
    if len(args) < 2:
        print("Error: Offset argument is required.")
        print("Usage: python offset_ttml.py input_file offset [output_file]")
        sys.exit(1)
        
    offset_arg = args[1]
    output_file = args[2] if len(args) > 2 else None

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    try:
        offset_seconds = parse_offset(offset_arg)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
        
        # register namespaces to keep output clean
        try:
            namespaces = dict([node for _, node in ET.iterparse(input_file, events=['start-ns'])])
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)
        except:
            pass # continue if namespace parsing fails

        # Apply offset to all elements recursively
        apply_offset(root, offset_seconds)
        
        # Post-process: Update body 'dur' to match the very last end time found
        max_end = 0.0
        for elem in root.iter():
            if 'end' in elem.attrib:
                t = parse_time(elem.attrib['end'])
                if t > max_end:
                    max_end = t
        
        # Find body and update dur if exists. 
        # We try to find it with and without namespace just in case.
        body = root.find("{http://www.w3.org/ns/ttml}body")
        if body is None:
             body = root.find("body")
             
        if body is not None:
             body.attrib['dur'] = format_time(max_end)

        if output_file:
            output_path = output_file
        else:
            # Overwrite the input file by default as requested
            output_path = input_file

        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        print(f"Success! Offset by {offset_seconds}s. Output saved to: {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
