import re
import sys
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

def parse_time(time_str):
    """Parses mm:ss.xxx to seconds."""
    if not time_str:
        return 0.0
    minutes, seconds = time_str.split(':')
    return float(minutes) * 60 + float(seconds)

def format_time(seconds):
    """Formats seconds to mm:ss.xxx."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02}:{secs:06.3f}"

def clean_filename(filename):
    """Removes illegal characters from filename."""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def parse_elrc(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    metadata = {}
    lyrics_data = []
    
    # Regex for metadata: [key:value]
    meta_re = re.compile(r'\[(ar|ti|offset|by):(.*)\]')
    # Regex for standard line: [mm:ss.xxx]voice:content
    line_re = re.compile(r'\[(\d{2}:\d{2}\.\d{3})\](v1:|v2:|bg:)?(.*)')
    # Regex for bg line: [bg:content]
    bg_re = re.compile(r'\[bg:(.*)\]')
    # Regex for word: <mm:ss.xxx>word
    word_re = re.compile(r'<(\d{2}:\d{2}\.\d{3})>([^<]*)')

    for line in lines:
        line = line.strip()
        meta_match = meta_re.match(line)
        if meta_match:
            metadata[meta_match.group(1)] = meta_match.group(2).strip()
            continue

        start_time = 0.0
        agent = "v1"
        role = None
        content = ""
        
        line_match = line_re.match(line)
        bg_match = bg_re.match(line)
        
        if line_match:
            start_time_str = line_match.group(1)
            voice_tag = line_match.group(2)
            content = line_match.group(3)
            
            start_time = parse_time(start_time_str)
            
            if voice_tag:
                if "v2" in voice_tag:
                    agent = "v2"
                elif "bg" in voice_tag:
                    role = "x-bg"
                    agent = None
        elif bg_match:
            content = bg_match.group(1)
            role = "x-bg"
            agent = None # or "v1" / "v2" if we want to assign a default agent? Best to leave it just role x-bg.
            
            # For BG lines in this format, the line start time is effectively the start of the first word.
            # parsing words will extract it.
        else:
            continue
            
        # Parse words
        words = []
        # Find all word matches
        for wm in word_re.finditer(content):
            w_start_str = wm.group(1)
            w_text = wm.group(2)
            w_start = parse_time(w_start_str)
            words.append({
                'text': w_text,
                'start': w_start,
                'end': 0.0 # To be calculated
            })
        
        if words:
            # If line start was 0.0 (from bg line), set it to first word start
            if start_time == 0.0:
                start_time = words[0]['start']
                
            # Calculate word durations
            for i in range(len(words) - 1):
                words[i]['end'] = words[i+1]['start']
            
        lyrics_data.append({
            'start': start_time,
            'agent': agent,
            'role': role,
            'words': words
        })

    # Post-process to fix last word durations based on next line start
    for i in range(len(lyrics_data)):
        words = lyrics_data[i]['words']
        if not words:
            continue
            
        # Fix internal word durations (already done basically, but let's ensure)
        for j in range(len(words) - 1):
            words[j]['end'] = words[j+1]['start']
            
        # Fix last word duration
        # Fix last word duration
        if i < len(lyrics_data) - 1:
            # Find next non-bg line start
            next_start = None
            for k in range(i + 1, len(lyrics_data)):
                if lyrics_data[k].get('role') != 'x-bg':
                    next_start = lyrics_data[k]['start']
                    break
            
            # If no next main line found, or if next main line is earlier than word start (weird),
            # default to +3.0s or ensure validity
            if next_start and next_start > words[-1]['start']:
                 words[-1]['end'] = next_start
            else:
                 words[-1]['end'] = words[-1]['start'] + 3.0
        else:
            # Last line, last word. Arbitrary 'long enough' or +3 seconds?
             words[-1]['end'] = words[-1]['start'] + 3.0

    return metadata, lyrics_data

def generate_ttml(metadata, lyrics_data, output_path):
    # XML Construction
    NS = {
        None: "http://www.w3.org/ns/ttml",
        "ttm": "http://www.w3.org/ns/ttml#metadata",
        "amll": "http://www.example.com/ns/amll",
        "itunes": "http://music.apple.com/lyric-ttml-internal"
    }
    
    # Register namespaces
    for prefix, uri in NS.items():
        ET.register_namespace(prefix if prefix else "", uri)

    tt = ET.Element("tt", {
        "xmlns": "http://www.w3.org/ns/ttml",
        "xmlns:ttm": "http://www.w3.org/ns/ttml#metadata",
        "xmlns:amll": "http://www.example.com/ns/amll",
        "xmlns:itunes": "http://music.apple.com/lyric-ttml-internal"
    })
    
    head = ET.SubElement(tt, "head")
    meta = ET.SubElement(head, "metadata")
    ET.SubElement(meta, "ttm:agent", {"type": "person", "xml:id": "v1"})
    ET.SubElement(meta, "ttm:agent", {"type": "person", "xml:id": "v2"})
    
    # Calculate Total Duration
    last_end = 0.0
    if lyrics_data and lyrics_data[-1]['words']:
         last_end = lyrics_data[-1]['words'][-1]['end']
    
    body = ET.SubElement(tt, "body", {"dur": format_time(last_end)})
    
    # Main div
    # Find first start
    first_start = lyrics_data[0]['start'] if lyrics_data else 0.0
    div = ET.SubElement(body, "div", {"begin": format_time(first_start), "end": format_time(last_end)})
    
    for idx, line in enumerate(lyrics_data):
        if not line['words']:
            continue
            
        line_start = line['words'][0]['start']
        line_end = line['words'][-1]['end']
        
        p_attrib = {
            "begin": format_time(line_start),
            "end": format_time(line_end),
            "itunes:key": f"L{idx+1}"
        }
        
        if line['agent']:
            p_attrib["ttm:agent"] = line['agent']
        if line['role']:
            p_attrib["ttm:role"] = line['role']
            
        p = ET.SubElement(div, "p", p_attrib)
        
        for word in line['words']:
            span = ET.SubElement(p, "span", {
                "begin": format_time(word['start']),
                "end": format_time(word['end'])
            })
            span.text = word['text']
            
    # Prettify and Write
    xml_str = minidom.parseString(ET.tostring(tt, encoding='utf-8')).toprettyxml(indent="  ")
    
    # Post-process to remove whitespace between spans This fixes the issue where
    # ttml_to_json interprets whitespace between tags as a space between words.
    # We want 'fan' + 'ta' to be 'fanta', not 'fan ta'.
    xml_str = re.sub(r'</span>\s+<span', '</span><span', xml_str)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)

def main():
    if len(sys.argv) < 2:
        print("Usage: python elrc_to_ttml.py <input_file.lrc>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        sys.exit(1)

    metadata, lyrics_data = parse_elrc(input_path)
    
    artist = metadata.get('ar', 'Unknown Artist')
    title = metadata.get('ti', 'Unknown Title')
    
    output_filename = f"{artist} - {title}.ttml"
    output_filename = clean_filename(output_filename)
    
    # Determine output directory (same as input)
    output_dir = os.path.dirname(input_path)
    output_path = os.path.join(output_dir, output_filename)
    
    generate_ttml(metadata, lyrics_data, output_path)
    print(f"Generated: {output_path}")

if __name__ == "__main__":
    main()
