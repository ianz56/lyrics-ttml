import os
import argparse
from xml.etree import ElementTree as ET
from pathlib import Path

# Try importing korean-romanizer
try:
    from korean_romanizer.romanizer import Romanizer
except ImportError:
    print("Module 'korean-romanizer' not found. Please install it using:")
    print("pip install korean-romanizer")
    exit(1)


def romanize_text(text):
    """Romanize Korean text."""
    if not text or not text.strip():
        return ""
    
    # Check if text contains Korean characters (Hangul)
    if not any('\uac00' <= char <= '\ud7a3' for char in text):
        return ""
        
    try:
        r = Romanizer(text)
        return r.romanize()
    except Exception as e:
        print(f"Warning: Failed to romanize '{text}': {e}")
        return ""


def process_ttml(ttml_path, output_path=None, overwrite=False):
    """
    Process TTML file and add x-roman attributes.
    """
    path = Path(ttml_path)
    if not output_path:
        output_path = path if overwrite else path.with_suffix('.romanized.ttml')
    
    tree = ET.parse(ttml_path)
    root = tree.getroot()
    
    # Register namespaces
    namespaces = {
        'tt': 'http://www.w3.org/ns/ttml',
        'ttm': 'http://www.w3.org/ns/ttml#metadata',
        'itunes': 'http://music.apple.com/lyric-ttml-internal'
    }
    
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
        
    def process_element_spans(element, roman_parts_accumulator):
        """Recursively process spans to add romanization."""
        # Check direct text of the element (unlikely for div/body, but possible for p/span)
        # In this specific simplified logic, we iterate children.
        
        for child in element:
            tag_name = child.tag.split('}')[-1]
            if tag_name == 'span':
                text = child.text
                roman = ""
                if text:
                    if 'x-roman' not in child.attrib:
                        roman = romanize_text(text)
                        if roman:
                            child.set('x-roman', roman)
                    else:
                        roman = child.get('x-roman')
                
                # Add to accumulator if we found something (text and/or roman)
                # We prioritize roman if available, else text (for non-korean parts)?
                # Or just accumulate roman parts? 
                # If we want to construct the parent's full romanization string, we need to know the order.
                # Recursive call for nested spans
                
                # If this span has text, we append its romanization (or text fallback)
                if text:
                    roman_parts_accumulator.append(roman if roman else text)
                
                process_element_spans(child, roman_parts_accumulator)

    # Process body
    body = root.find(f'{{{namespaces["tt"]}}}body')
    if body:
        for div in body.findall(f'{{{namespaces["tt"]}}}div'):
            for p in div.findall(f'{{{namespaces["tt"]}}}p'):
                p_text = ""
                
                # We need to capture line parts in order.
                # A simple recursive finder might lose order if we are not careful about mixing direct text and child nodes.
                # But TTML structure usually has text in leaf spans.
                
                line_roman_parts = []
                process_element_spans(p, line_roman_parts)
                
                # Update p x-roman if not exists
                if 'x-roman' not in p.attrib and line_roman_parts:
                     # Filter out empty strings
                    filtered_parts = [p for p in line_roman_parts if p and p.strip()]
                    if filtered_parts:
                        p.set('x-roman', ' '.join(filtered_parts))

    # Write output
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f"✓ Processed: {ttml_path} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Add x-roman attributes to TTML files')
    parser.add_argument('input', help='Input TTML file or folder')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite input file')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        process_ttml(input_path, overwrite=args.overwrite)
    elif input_path.is_dir():
        for ttml_file in input_path.rglob('*.ttml'):
            try:
                process_ttml(ttml_file, overwrite=args.overwrite)
            except Exception as e:
                print(f"✗ Error processing {ttml_file}: {e}")

if __name__ == '__main__':
    main()
