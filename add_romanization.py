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
        
    # Process body
    body = root.find(f'{{{namespaces["tt"]}}}body')
    if body:
        for div in body.findall(f'{{{namespaces["tt"]}}}div'):
            for p in div.findall(f'{{{namespaces["tt"]}}}p'):
                # Process paragraph (line)
                p_text = ""
                
                # Check for existing x-roman
                if 'x-roman' not in p.attrib:
                    # Construct full text from spans for paragraph-level romanization usually? 
                    # Or just romanize the constructed text?
                    # Since p often contains spans, we might want to romanize the full line representation or individual words.
                    # The user example shows:
                    # "text": "첫눈 오는 이런 오후에", "roman": "di sini romaja"
                    # "words": ... "roman": "..."
                    
                    # We should probably romanize the text content of spans individually, 
                    # AND the full line.
                    
                    # But wait, p text construction in ttml_to_json constructs it from spans.
                    # Here we might need to rely on the fact that we can iterate spans.
                    pass
                
                # Process spans
                line_roman_parts = []
                
                for span in p.findall(f'{{{namespaces["tt"]}}}span'):
                    text = span.text
                    if text:
                        # Romanize span
                        if 'x-roman' not in span.attrib:
                            roman = romanize_text(text)
                            if roman:
                                span.set('x-roman', roman)
                                line_roman_parts.append(roman)
                            else:
                                line_roman_parts.append(text) # Fallback or keep original if not korean
                        else:
                            line_roman_parts.append(span.get('x-roman'))
                
                # Update p x-roman if not exists
                if 'x-roman' not in p.attrib and line_roman_parts:
                    # Join with spaces, but careful about spacing logic.
                    # Ideally we re-construct from spans, but simple join is a good approximation for now.
                    p.set('x-roman', ' '.join(line_roman_parts))

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
