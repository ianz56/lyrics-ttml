#!/usr/bin/env python3
"""
TTML to JSON Converter
Mengkonversi file TTML lyrics ke format JSON yang terstruktur.
"""

import os
import json
import re
import sys
import argparse
from xml.etree import ElementTree as ET
from pathlib import Path


def parse_time(time_str: str) -> float:
    """Konversi timestamp TTML (MM:SS.mmm) ke detik."""
    if not time_str:
        return 0.0
    
    # Format: MM:SS.mmm atau HH:MM:SS.mmm
    parts = time_str.split(':')
    if len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    return 0.0


def format_time(seconds: float) -> str:
    """Format detik ke timestamp MM:SS.mmm."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:06.3f}"


def parse_span(span_elem, namespaces: dict) -> dict:
    """Parse elemen span untuk mendapatkan word dan timing."""
    text = span_elem.text or ""
    begin = span_elem.get('begin', '')
    end = span_elem.get('end', '')
    
    role = span_elem.get(f'{{{namespaces.get("ttm", "")}}}role', '')
    is_bg = role == 'x-bg'
    is_translation = role == 'x-translation'
    
    # Detect spaces before stripping
    has_leading_space = text[0].isspace() if text else False
    has_trailing_space = text[-1].isspace() if text else False
    
    return {
        "text": text.strip() if text else "",
        "begin": parse_time(begin),
        "end": parse_time(end),
        "isBackground": is_bg,
        "isTranslation": is_translation,
        "hasLeadingSpace": has_leading_space,
        "hasTrailingSpace": has_trailing_space
    }


def parse_paragraph(p_elem, namespaces: dict) -> dict:
    """Parse elemen <p> (paragraph/line) untuk mendapatkan words dan timing."""
    begin = p_elem.get('begin', '')
    end = p_elem.get('end', '')
    agent = p_elem.get(f'{{{namespaces.get("ttm", "")}}}agent', '')
    key = p_elem.get(f'{{{namespaces.get("itunes", "")}}}key', '')
    
    words = []
    background_words = []
    translations = []
    
    # Track apakah ada spasi sebelum span berikutnya
    # Spasi ditandai oleh 'tail' property dari elemen sebelumnya
    def process_spans(parent_elem, word_list, is_bg=False):
        """Process semua span dalam parent element dan track spasi."""
        for i, child in enumerate(parent_elem):
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag_name == 'span':
                role = child.get(f'{{{namespaces.get("ttm", "")}}}role', '')
                
                if role == 'x-bg':
                    # Background vocal - parse nested spans
                    process_spans(child, background_words, is_bg=True)
                elif role == 'x-translation':
                    # Translation - extract text directly, don't treat as lyric word
                    trans_text = child.text or ""
                    if trans_text.strip():
                        translations.append(trans_text.strip())
                else:
                    raw_text = child.text or ""
                    if word_list and (raw_text.startswith(" ") or raw_text.startswith("\t") or raw_text.startswith("\n")):
                         word_list[-1]["hasSpaceAfter"] = True

                    word_data = parse_span(child, namespaces)
                    word_data["isBackground"] = is_bg
                    
                    if word_data["isTranslation"]:
                         # Should have been caught by elif, but just in case
                         if word_data["text"]:
                            translations.append(word_data["text"])
                         continue
                    
                    tail = child.tail or ""
                    has_tail_space = bool(tail.strip() == "" and tail != "")
                    
                    # Combine tail space with internal trailing space from the text itself
                    word_data["hasSpaceAfter"] = has_tail_space or word_data.get("hasTrailingSpace", False)
                    
                    if word_data["text"]:
                        word_list.append(word_data)
    
    process_spans(p_elem, words)
    
    # Gabungkan teks untuk mendapatkan full line text
    def join_words(word_list):
        result = ""
        for i, w in enumerate(word_list):
            text = w["text"]
            if i == 0:
                result = text
            else:
                prev_word = word_list[i - 1]
                # Check for spaces:
                # 1. Previous word marked as having space after (tail or internal trailing)
                # 2. Current word has leading space
                should_add_space = prev_word.get("hasSpaceAfter", True) or w.get("hasLeadingSpace", False)
                
                if should_add_space:
                    result += " " + text
                else:
                    result += text
        return result
    
    line_text = join_words([w for w in words if not w.get("isBackground")])
    bg_text = join_words(background_words)
    
    result = {
        "begin": parse_time(begin),
        "end": parse_time(end),
        "text": line_text,
        "words": words
    }
    
    if agent:
        result["agent"] = agent
    if key:
        result["key"] = key
    if background_words:
        result["backgroundVocal"] = {
            "text": bg_text,
            "words": background_words
        }
    if translations:
        result["translation"] = " ".join(translations)
    
    return result


def ttml_to_json(ttml_path: str, output_path: str = None) -> dict:
    """
    Konversi file TTML ke JSON.
    
    Args:
        ttml_path: Path ke file TTML
        output_path: Path output JSON (optional)
        
    Returns:
        Dictionary hasil konversi
    """
    # Parse TTML file
    tree = ET.parse(ttml_path)
    root = tree.getroot()
    
    # Define namespaces
    namespaces = {
        'tt': 'http://www.w3.org/ns/ttml',
        'ttm': 'http://www.w3.org/ns/ttml#metadata',
        'amll': 'http://www.example.com/ns/amll',
        'itunes': 'http://music.apple.com/lyric-ttml-internal'
    }
    
    # Register namespaces untuk parsing
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    
    result = {
        "metadata": {},
        "duration": None,
        "lines": []
    }
    
    # Parse metadata dari head
    head = root.find(f'{{{namespaces["tt"]}}}head')
    if head is not None:
        metadata = head.find(f'{{{namespaces["tt"]}}}metadata')
        if metadata is not None:
            agents = metadata.findall(f'{{{namespaces["ttm"]}}}agent')
            result["metadata"]["agents"] = []
            for agent in agents:
                agent_info = {
                    "id": agent.get('{http://www.w3.org/XML/1998/namespace}id', ''),
                    "type": agent.get('type', '')
                }
                result["metadata"]["agents"].append(agent_info)
    
    # Parse body
    body = root.find(f'{{{namespaces["tt"]}}}body')
    if body is not None:
        dur = body.get('dur', '')
        if dur:
            result["duration"] = parse_time(dur)
        
        # Parse div elements
        for div in body.findall(f'{{{namespaces["tt"]}}}div'):
            div_begin = div.get('begin', '')
            div_end = div.get('end', '')
            
            # Parse paragraphs (lines)
            for p in div.findall(f'{{{namespaces["tt"]}}}p'):
                line_data = parse_paragraph(p, namespaces)
                result["lines"].append(line_data)
    
    # Extract metadata dari filename
    filename = Path(ttml_path).stem
    parts = filename.split(' - ')
    if len(parts) >= 2:
        result["metadata"]["artist"] = parts[0]
        result["metadata"]["title"] = parts[1]
    else:
        result["metadata"]["title"] = filename
    
    result["metadata"]["sourceFile"] = Path(ttml_path).name
    result["totalLines"] = len(result["lines"])
    
    # Save to JSON if output path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✓ Converted: {ttml_path} -> {output_path}")
    
    return result


def convert_folder(input_folder: str, output_folder: str = None):
    """Konversi semua file TTML dalam folder ke JSON."""
    input_path = Path(input_folder)
    output_path = Path(output_folder) if output_folder else input_path
    
    if not output_path.exists():
        output_path.mkdir(parents=True)
    
    converted = 0
    for ttml_file in input_path.rglob('*.ttml'):
        # Buat path output dengan struktur folder yang sama
        relative = ttml_file.relative_to(input_path)
        json_file = output_path / relative.with_suffix('.json')
        
        # Buat folder jika belum ada
        json_file.parent.mkdir(parents=True, exist_ok=True)
        
        ttml_to_json(str(ttml_file), str(json_file))
        converted += 1
    
    print(f"\n✓ Total converted: {converted} files")


def convert_all_to_json(base_dir: str = ".", force: bool = False):
    """
    Konversi semua file TTML ke struktur JSON/{Lang}/{filename}.json
    
    Args:
        base_dir: Direktori dasar project
        force: Jika True, convert ulang semua file. Jika False, skip file yang sudah ada dan tidak berubah.
    """
    base_path = Path(base_dir)
    json_output = base_path / "JSON"
    
    # Folder bahasa yang akan di-scan (ENG, IND, MISC, MYS, SUN, dll)
    lang_folders = [d for d in base_path.iterdir() 
                    if d.is_dir() and not d.name.startswith('.') 
                    and d.name not in ['JSON', 'node_modules', '__pycache__']]
    
    converted = 0
    skipped = 0
    errors = []
    
    for lang_folder in lang_folders:
        lang_name = lang_folder.name
        
        for ttml_file in lang_folder.glob('*.ttml'):
            # Output: JSON/{Lang}/{filename}.json
            output_dir = json_output / lang_name
            output_dir.mkdir(parents=True, exist_ok=True)
            
            json_file = output_dir / ttml_file.with_suffix('.json').name
            
            # Skip jika JSON sudah ada dan lebih baru dari TTML (kecuali force=True)
            if not force and json_file.exists():
                ttml_mtime = ttml_file.stat().st_mtime
                json_mtime = json_file.stat().st_mtime
                if json_mtime >= ttml_mtime:
                    skipped += 1
                    continue
            
            try:
                ttml_to_json(str(ttml_file), str(json_file))
                converted += 1
            except Exception as e:
                errors.append(f"  ✗ {ttml_file}: {str(e)}")
                print(f"✗ Error: {ttml_file.name} - {str(e)[:50]}")
    
    print(f"\n✓ Converted: {converted} files | Skipped: {skipped} files (unchanged)")
    if errors:
        print(f"✗ Errors ({len(errors)}):")
        for err in errors:
            print(err)


def main():
    parser = argparse.ArgumentParser(
        description='Konversi file TTML lyrics ke JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python ttml_to_json.py file.ttml                    # Konversi satu file
  python ttml_to_json.py file.ttml -o output.json     # Konversi dengan output spesifik
  python ttml_to_json.py --folder ./ENG               # Konversi semua TTML dalam folder
  python ttml_to_json.py --folder ./ENG -o ./json     # Konversi folder ke folder output
        """
    )
    
    parser.add_argument('input', nargs='?', help='Path ke file TTML')
    parser.add_argument('-o', '--output', help='Path output JSON atau folder')
    parser.add_argument('--folder', help='Path folder berisi file TTML untuk batch convert')
    parser.add_argument('--all', action='store_true', help='Konversi semua TTML ke JSON/{Lang}/{file}.json')
    parser.add_argument('--force', action='store_true', help='Force regenerate semua file (gunakan dengan --all)')
    parser.add_argument('--pretty', action='store_true', default=True, help='Pretty print JSON (default: True)')
    
    args = parser.parse_args()
    
    if args.all:
        # Konversi semua TTML ke struktur JSON/{Lang}/{filename}.json
        convert_all_to_json(".", force=args.force)
    elif args.folder:
        # Batch convert folder
        convert_folder(args.folder, args.output)
    elif args.input:
        # Single file convert
        output = args.output
        if not output:
            output = Path(args.input).with_suffix('.json')
        
        result = ttml_to_json(args.input, str(output))
        
        if not args.output:
            # Print preview
            print(f"\nPreview ({result['totalLines']} lines):")
            for i, line in enumerate(result['lines'][:5]):
                print(f"  {i+1}. [{format_time(line['begin'])}] {line['text']}")
            if result['totalLines'] > 5:
                print(f"  ... dan {result['totalLines'] - 5} baris lainnya")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
