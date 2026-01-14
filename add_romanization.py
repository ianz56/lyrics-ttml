import os
import argparse
import sys
from xml.etree import ElementTree as ET
from pathlib import Path

# Lazy import helpers
def get_romanizer(lang_code):
    """
    Returns a romanization function for the specified language code.
    Codes: kor, jpn, chi/zho, hin, urd, ara
    """
    lang = lang_code.lower()
    
    if lang == 'kor':
        try:
            from korean_romanizer.romanizer import Romanizer
            def romanize_kor(text):
                if not text or not text.strip(): return ""
                if not any('\uac00' <= char <= '\ud7a3' for char in text): return ""
                try:
                    return Romanizer(text).romanize()
                except: return ""
            return romanize_kor
        except ImportError:
            print("Error: 'korean-romanizer' not installed. pip install korean-romanizer")
            return None

    elif lang == 'jpn':
        try:
            import pykakasi
            kks = pykakasi.kakasi()
            def romanize_jpn(text):
                if not text: return ""
                result = kks.convert(text)
                return " ".join([item['hepburn'] for item in result])
            return romanize_jpn
        except ImportError:
            print("Error: 'pykakasi' not installed. pip install pykakasi")
            return None

    elif lang in ['chi', 'zho']:
        try:
            from pypinyin import pinyin, Style
            def romanize_chi(text):
                if not text: return ""
                # Normal pinyin with tone marks or without? Usually with tones is better, or numbers?
                # Using normal style (no tone marks) for "romanization" usually implies reading aid.
                # But typically romanization includes tones. User didn't specify.
                # Let's use Style.NORMAL (no tones) or Style.TONE.
                # TONE is safer for learning, NORMAL for "english-like".
                # Let's stick to Style.NORMAL for cleaner text, or maybe separate?
                # User asked for "roman", usually means readable.
                # Let's use Style.NORMAL (no tones) for now to be safe as 'roman'.
                res = pinyin(text, style=Style.NORMAL)
                return " ".join([item[0] for item in res])
            return romanize_chi
        except ImportError:
            print("Error: 'pypinyin' not installed. pip install pypinyin")
            return None

    elif lang == 'hin':
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import SchemeMap, SCHEMES, transliterate
            def romanize_hin(text):
                if not text: return ""
                return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
            return romanize_hin
        except ImportError:
            print("Error: 'indic-transliteration' not installed. pip install indic-transliteration")
            return None
            
    elif lang == 'urd':
        try:
            import urdu2roman
            def romanize_urd(text):
                if not text: return ""
                return urdu2roman.romanize(text)
            return romanize_urd
        except ImportError:
            print("Warning: 'urdu2roman' not found. Falling back to unidecode.")
            try:
                from unidecode import unidecode
                return lambda text: unidecode(text) if text else ""
            except ImportError:
                print("Error: 'unidecode' not installed. pip install unidecode")
                return None

    elif lang == 'ara':
        try:
            from unidecode import unidecode
            def romanize_ara(text):
                if not text: return ""
                return unidecode(text)
            return romanize_ara
        except ImportError:
             print("Error: 'unidecode' not installed. pip install unidecode")
             return None

    else:
        print(f"Warning: Unsupported language '{lang}'")
        return None

def detect_lang_from_path(path):
    """Detect language from file path (folder name)."""
    parts = path.parts
    
    # Check for known folder names
    map = {
        'KOR': 'kor',
        'JPN': 'jpn',
        'CHI': 'chi', 'ZHO': 'chi',
        'HIN': 'hin',
        'URD': 'urd',
        'ARA': 'ara',
        'MYS': 'mys', # Standard Malay? Usually Latin already.
        'IND': 'ind'  # Indonesian?
    }
    
    for part in parts:
        if part.upper() in map:
            return map[part.upper()]
    return None




def process_ttml(ttml_path, lang=None, overwrite=False):
    """
    Process TTML file and add x-roman attributes.
    """
    path = Path(ttml_path)
    if overwrite:
        output_path = path
    else:
        output_path = path.with_suffix('.romanized.ttml')

    
    # Determine language
    if not lang:
        lang = detect_lang_from_path(path)
    
    if not lang:
        print(f"Skipping {ttml_path}: Could not detect language. Use --lang.")
        return

    romanizer = get_romanizer(lang)
    if not romanizer:
        return

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
        for child in element:
            tag_name = child.tag.split('}')[-1]
            if tag_name == 'span':
                # Check for role
                # Try getting role with and without namespace to be safe
                role = child.get(f'{{{namespaces.get("ttm", "")}}}role', '')
                if not role:
                    role = child.get('role', '') # Sometimes it might be without ns if not strictly parsed?
                
                if role == 'x-translation':
                    continue

                text = child.text
                roman = ""
                if text and text.strip():
                    if 'x-roman' not in child.attrib:
                        roman = romanizer(text)
                        if roman:
                            child.set('x-roman', roman)
                    else:
                        roman = child.get('x-roman')
                
                if text:
                    roman_parts_accumulator.append(roman if roman else text)
                
                process_element_spans(child, roman_parts_accumulator)

    # Process body
    body = root.find(f'{{{namespaces["tt"]}}}body')
    if body is not None:
        for div in body.findall(f'{{{namespaces["tt"]}}}div'):
            for p in div.findall(f'{{{namespaces["tt"]}}}p'):
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
    print(f"✓ Processed [{lang}]: {ttml_path} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Add x-roman attributes to TTML files')
    parser.add_argument('input', help='Input TTML file or folder')
    parser.add_argument('--lang', help='Target language (kor, jpn, chi, hin, urd, ara)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite input file')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        process_ttml(input_path, lang=args.lang, overwrite=args.overwrite)
    elif input_path.is_dir():
        for ttml_file in input_path.rglob('*.ttml'):
            try:
                process_ttml(ttml_file, lang=args.lang, overwrite=args.overwrite)
            except Exception as e:
                print(f"✗ Error processing {ttml_file}: {e}")

if __name__ == '__main__':
    main()
