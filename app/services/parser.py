"""
TTML Parser Service

Refactored from ttml_to_json.py — extracts the core TTML-to-dict parsing logic
into importable functions for use by the API and import scripts.

The original ttml_to_json.py is preserved as-is for standalone CLI usage.
"""

import re
from pathlib import Path
from xml.etree import ElementTree as ET


# ─── Time Parsing Helpers ────────────────────────────────────────────────────


def parse_time(time_str: str) -> float:
    """Convert TTML timestamp (MM:SS.mmm or HH:MM:SS.mmm) to seconds."""
    if not time_str:
        return 0.0

    parts = time_str.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 1:
        return float(parts[0])
    return 0.0


def format_time(seconds: float) -> str:
    """Format seconds to timestamp MM:SS.mmm."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:06.3f}"


# ─── Span & Paragraph Parsing ───────────────────────────────────────────────


def _parse_span(span_elem, namespaces: dict) -> dict:
    """Parse a span element to extract word and timing data."""
    text = span_elem.text or ""
    begin = span_elem.get("begin", "")
    end = span_elem.get("end", "")

    role = span_elem.get(f'{{{namespaces.get("ttm", "")}}}role', "")
    is_bg = role == "x-bg"
    is_translation = role == "x-translation"

    roman = span_elem.get("x-roman", "")

    has_leading_space = text[0].isspace() if text else False
    has_trailing_space = text[-1].isspace() if text else False

    result = {
        "text": text.strip() if text else "",
        "begin": parse_time(begin),
        "end": parse_time(end),
        "isBackground": is_bg,
        "isTranslation": is_translation,
        "hasLeadingSpace": has_leading_space,
        "hasTrailingSpace": has_trailing_space,
    }

    if roman:
        result["roman"] = roman

    return result


def _parse_paragraph(p_elem, namespaces: dict) -> dict:
    """Parse a <p> element to extract words, timing, translations, and background vocals."""
    begin = p_elem.get("begin", "")
    end = p_elem.get("end", "")
    agent = p_elem.get(f'{{{namespaces.get("ttm", "")}}}agent', "")
    key = p_elem.get(f'{{{namespaces.get("itunes", "")}}}key', "")

    words = []
    background_words = []
    translations = []
    bg_begin_time = None

    def process_spans(parent_elem, word_list, is_bg=False):
        nonlocal bg_begin_time
        for child in parent_elem:
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag_name == "span":
                role = child.get(f'{{{namespaces.get("ttm", "")}}}role', "")

                if role == "x-bg":
                    bg_begin_str = child.get("begin", "")
                    if bg_begin_str:
                        bg_begin_time = parse_time(bg_begin_str)

                    if list(child):
                        process_spans(child, background_words, is_bg=True)
                    else:
                        word_data = _parse_span(child, namespaces)
                        word_data["isBackground"] = True

                        raw_text = child.text or ""
                        if background_words and (
                            raw_text.startswith(" ")
                            or raw_text.startswith("\t")
                            or raw_text.startswith("\n")
                        ):
                            background_words[-1]["hasSpaceAfter"] = True

                        tail = child.tail or ""
                        is_formatting = "\n" in tail or "\r" in tail
                        has_tail_space = bool(
                            tail.strip() == "" and tail != "" and not is_formatting
                        )
                        word_data["hasSpaceAfter"] = has_tail_space or word_data.get(
                            "hasTrailingSpace", False
                        )

                        if word_data["text"]:
                            background_words.append(word_data)

                elif role == "x-translation":
                    trans_text = child.text or ""
                    clean_trans = trans_text.strip()
                    if clean_trans:
                        if is_bg and not (
                            clean_trans.startswith("(") and clean_trans.endswith(")")
                        ):
                            clean_trans = f"({clean_trans})"
                        translations.append((is_bg, clean_trans))

                else:
                    raw_text = child.text or ""
                    if word_list and (
                        raw_text.startswith(" ")
                        or raw_text.startswith("\t")
                        or raw_text.startswith("\n")
                    ):
                        word_list[-1]["hasSpaceAfter"] = True

                    word_data = _parse_span(child, namespaces)
                    word_data["isBackground"] = is_bg

                    if word_data["isTranslation"]:
                        if word_data["text"]:
                            translations.append((is_bg, word_data["text"]))
                        continue

                    tail = child.tail or ""
                    is_formatting = "\n" in tail or "\r" in tail
                    has_tail_space = bool(
                        tail.strip() == "" and tail != "" and not is_formatting
                    )
                    word_data["hasSpaceAfter"] = has_tail_space or word_data.get(
                        "hasTrailingSpace", False
                    )

                    if word_data["text"]:
                        word_list.append(word_data)

    p_role = p_elem.get(f'{{{namespaces.get("ttm", "")}}}role', "")
    is_p_bg = p_role == "x-bg"
    p_roman = p_elem.get("x-roman", "")

    if is_p_bg:
        process_spans(p_elem, background_words, is_bg=True)
    else:
        process_spans(p_elem, words)

    def join_words(word_list):
        result_str = ""
        for i, w in enumerate(word_list):
            text = w["text"]
            if i == 0:
                result_str = text
            else:
                prev_word = word_list[i - 1]
                should_add_space = prev_word.get("hasSpaceAfter", True) or w.get(
                    "hasLeadingSpace", False
                )
                if should_add_space:
                    result_str += " " + text
                else:
                    result_str += text
        return result_str

    line_text = join_words([w for w in words if not w.get("isBackground")])
    bg_text = join_words(background_words)

    result = {
        "begin": parse_time(begin),
        "end": parse_time(end),
        "text": line_text,
        "words": words,
    }

    if p_roman:
        result["roman"] = p_roman

    if agent:
        result["agent"] = agent
    if key:
        result["key"] = key
    if background_words:
        bg_obj = {
            "text": bg_text,
            "words": background_words,
        }
        bg_roman_parts = [
            w.get("roman", "") for w in background_words if w.get("roman")
        ]
        if bg_roman_parts:
            bg_obj["roman"] = " ".join(bg_roman_parts)

        result["backgroundVocal"] = bg_obj

    if translations:
        main_begin = parse_time(begin)
        bg_translations = [t for is_bg, t in translations if is_bg]
        main_translations = [t for is_bg, t in translations if not is_bg]

        if bg_begin_time is not None and bg_begin_time < main_begin:
            ordered = bg_translations + main_translations
        else:
            ordered = main_translations + bg_translations

        result["translation"] = " ".join(ordered)

    return result


# ─── Main TTML Parsing Functions ─────────────────────────────────────────────


def parse_ttml_content(content: str, source_filename: str = "") -> dict:
    """
    Parse TTML XML content string into a structured dictionary.

    Args:
        content: Raw TTML XML string
        source_filename: Optional filename for metadata extraction

    Returns:
        Dictionary with metadata, duration, and lines
    """
    root = ET.fromstring(content)

    # Detect main namespace
    if "}" in root.tag:
        tt_ns = root.tag.split("}")[0].strip("{")
    else:
        tt_ns = ""

    namespaces = {
        "tt": tt_ns,
        "ttm": "http://www.w3.org/ns/ttml#metadata",
        "amll": "http://www.example.com/ns/amll",
        "itunes": "http://music.apple.com/lyric-ttml-internal",
    }

    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    result = {
        "metadata": {},
        "duration": None,
        "lines": [],
    }

    # Parse metadata from head
    head = root.find(f'{{{namespaces["tt"]}}}head')
    if head is not None:
        metadata = head.find(f'{{{namespaces["tt"]}}}metadata')
        if metadata is not None:
            agents = metadata.findall(f'{{{namespaces["ttm"]}}}agent')
            result["metadata"]["agents"] = []
            for agent in agents:
                agent_info = {
                    "id": agent.get(
                        "{http://www.w3.org/XML/1998/namespace}id", ""
                    ),
                    "type": agent.get("type", ""),
                }
                result["metadata"]["agents"].append(agent_info)

    # Parse body
    body = root.find(f'{{{namespaces["tt"]}}}body')
    if body is not None:
        dur = body.get("dur", "")
        if dur:
            result["duration"] = parse_time(dur)

        for div in body.findall(f'{{{namespaces["tt"]}}}div'):
            for p in div.findall(f'{{{namespaces["tt"]}}}p'):
                line_data = _parse_paragraph(p, namespaces)
                result["lines"].append(line_data)

        # Post-process: merge background-only lines into overlapping main lines
        lines = result["lines"]
        indices_to_remove = set()

        for i, line in enumerate(lines):
            text = line.get("text", "").strip()
            bg_data = line.get("backgroundVocal")

            if not text and bg_data:
                bg_begin = line["begin"]
                bg_end = line["end"]
                best_match_idx = -1
                max_overlap = 0

                for j, target_line in enumerate(lines):
                    if i == j:
                        continue
                    if j in indices_to_remove:
                        continue

                    target_text = target_line.get("text", "").strip()
                    if not target_text:
                        continue

                    target_begin = target_line["begin"]
                    target_end = target_line["end"]

                    overlap_start = max(bg_begin, target_begin)
                    overlap_end = min(bg_end, target_end)
                    overlap = max(0, overlap_end - overlap_start)

                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_match_idx = j

                if best_match_idx != -1 and max_overlap > 0:
                    target_line = lines[best_match_idx]

                    if "backgroundVocal" not in target_line:
                        target_line["backgroundVocal"] = bg_data
                    else:
                        target_line["backgroundVocal"]["text"] += " " + bg_data["text"]
                        bg_roman = bg_data.get("roman", "")
                        if bg_roman:
                            if "roman" not in target_line["backgroundVocal"]:
                                target_line["backgroundVocal"]["roman"] = bg_roman
                            else:
                                target_line["backgroundVocal"]["roman"] += " " + bg_roman
                        target_line["backgroundVocal"]["words"].extend(bg_data["words"])

                    indices_to_remove.add(i)

        new_lines = [
            line for i, line in enumerate(lines) if i not in indices_to_remove
        ]
        result["lines"] = new_lines

    # Extract metadata from filename
    if source_filename:
        stem = Path(source_filename).stem
        parts = stem.split(" - ")
        if len(parts) >= 2:
            result["metadata"]["artist"] = parts[0]
            result["metadata"]["title"] = parts[1]
        else:
            result["metadata"]["title"] = stem

        result["metadata"]["sourceFile"] = source_filename

    result["totalLines"] = len(result["lines"])
    return result


def parse_ttml_file(file_path: str) -> dict:
    """
    Parse a TTML file from disk into a structured dictionary.

    Args:
        file_path: Path to the TTML file

    Returns:
        Dictionary with metadata, duration, and lines
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = Path(file_path).name
    return parse_ttml_content(content, source_filename=filename)
