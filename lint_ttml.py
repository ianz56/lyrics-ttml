#!/usr/bin/env python3
"""
TTML Linter & Formatter

Pretty-prints and validates TTML lyrics files.
Preserves existing namespace prefixes (tt: vs no-prefix) and text content.

Usage:
    python lint_ttml.py file.ttml              # lint, show diff
    python lint_ttml.py --fix file.ttml        # lint + rewrite in-place
    python lint_ttml.py --check file.ttml      # lint only, exit 1 if unformatted
    python lint_ttml.py --all                  # lint all .ttml recursively
    python lint_ttml.py --fix --all            # fix all
"""

import argparse
import glob
import os
import re
import sys
import difflib

# ─── Namespace handling ──────────────────────────────────────────────────────

TTML_NS = "http://www.w3.org/ns/ttml"
TTM_NS = "http://www.w3.org/ns/ttml#metadata"
ITUNES_NS = "http://music.apple.com/lyric-ttml-internal"
AMLL_NS = "http://www.example.com/ns/amll"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# Attribute ordering priority (lower = earlier)
ATTR_ORDER = {
    "begin": 0,
    "end": 1,
    "dur": 2,
    "ttm:agent": 3,
    "ttm:role": 4,
    "itunes:key": 5,
    "itunes:timing": 6,
    "type": 7,
    "xml:id": 8,
    "xml:lang": 9,
    "x-roman": 10,
    "for": 11,
}


def attr_sort_key(name):
    """Sort key: known attrs first by priority, rest alphabetically."""
    if name in ATTR_ORDER:
        return (0, ATTR_ORDER[name], name)
    return (1, 0, name)


# ─── Minimal XML parser (preserves text nodes exactly) ────────────────────

class XMLNode:
    """Minimal XML node for TTML formatting."""

    def __init__(self, tag=None, attrs=None, is_processing_instruction=False):
        self.tag = tag
        self.attrs = attrs or []  # list of (name, value) to preserve order
        self.children = []        # list of XMLNode or str (text nodes)
        self.is_self_closing = False
        self.is_processing_instruction = is_processing_instruction
        self.parent = None

    def __repr__(self):
        return f"XMLNode(tag={self.tag!r}, children={len(self.children)})"


def parse_ttml(content):
    """
    Parse TTML XML into a tree of XMLNode objects.
    Uses regex-based parsing to preserve exact text content and attribute values.
    """
    pos = 0
    root_nodes = []
    stack = []  # stack of parent XMLNodes

    def current_parent():
        return stack[-1] if stack else None

    def add_child(node):
        parent = current_parent()
        if parent:
            node.parent = parent
            parent.children.append(node)
        else:
            root_nodes.append(node)

    def add_text(text):
        if not text:
            return
        parent = current_parent()
        if parent:
            parent.children.append(text)
        else:
            if text.strip():
                root_nodes.append(text)

    while pos < len(content):
        # Find next tag
        next_lt = content.find("<", pos)
        if next_lt == -1:
            add_text(content[pos:])
            break

        # Text before tag
        if next_lt > pos:
            add_text(content[pos:next_lt])

        # Processing instruction
        if content[next_lt:next_lt + 2] == "<?":
            end = content.find("?>", next_lt)
            if end == -1:
                break
            pi_content = content[next_lt + 2:end].strip()
            pi_parts = pi_content.split(None, 1)
            pi_tag = pi_parts[0]
            pi_attrs = parse_attrs(pi_parts[1] if len(pi_parts) > 1 else "")
            node = XMLNode(tag=pi_tag, attrs=pi_attrs, is_processing_instruction=True)
            add_child(node)
            pos = end + 2
            continue

        # Comment
        if content[next_lt:next_lt + 4] == "<!--":
            end = content.find("-->", next_lt)
            if end == -1:
                break
            pos = end + 3
            continue

        # Closing tag
        if content[next_lt + 1:next_lt + 2] == "/":
            end = content.find(">", next_lt)
            if end == -1:
                break
            if stack:
                stack.pop()
            pos = end + 1
            continue

        # Opening tag
        # Find the end of the tag, accounting for attributes with > inside quotes
        tag_end = find_tag_end(content, next_lt)
        if tag_end == -1:
            break

        tag_content = content[next_lt + 1:tag_end]
        is_self_closing = tag_content.endswith("/")
        if is_self_closing:
            tag_content = tag_content[:-1]

        # Parse tag name and attributes
        tag_content = tag_content.strip()
        parts = tag_content.split(None, 1)
        tag_name = parts[0]
        attr_str = parts[1] if len(parts) > 1 else ""

        attrs = parse_attrs(attr_str)

        node = XMLNode(tag=tag_name, attrs=attrs)
        node.is_self_closing = is_self_closing
        add_child(node)

        if not is_self_closing:
            stack.append(node)

        pos = tag_end + 1

    return root_nodes


def find_tag_end(content, start):
    """Find the closing > of a tag, respecting quoted attribute values."""
    pos = start + 1
    in_quote = None
    while pos < len(content):
        ch = content[pos]
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
        elif ch == ">":
            return pos
        pos += 1
    return -1


def parse_attrs(attr_str):
    """Parse attribute string into list of (name, value) tuples."""
    attrs = []
    pattern = r'''([\w:.\-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')'''
    for m in re.finditer(pattern, attr_str):
        name = m.group(1)
        value = m.group(2) if m.group(2) is not None else m.group(3)
        attrs.append((name, value))
    return attrs


# ─── Formatter ───────────────────────────────────────────────────────────────

# Tags that should be on their own line (structural)
STRUCTURAL_TAGS_UNPREFIXED = {"tt", "head", "metadata", "body", "div", "p"}
STRUCTURAL_TAGS_PREFIXED = {f"tt:{t}" for t in STRUCTURAL_TAGS_UNPREFIXED}

# Tags whose children go inline (within the same parent line context)
INLINE_TAGS = {"span", "tt:span"}

# Tags that are leaf-level containers (content inside rendered inline if only text)
HEAD_SECTION_TAGS = {
    "ttm:agent", "ttm:name",
    "itunes:iTunesMetadata", "itunes:translations", "itunes:translation",
    "itunes:text", "itunes:songwriters", "itunes:songwriter",
}


def detect_prefix(nodes):
    """Detect whether the file uses tt: prefix or not."""
    for node in nodes:
        if isinstance(node, XMLNode):
            if node.tag and node.tag.startswith("tt:"):
                return True
            if detect_prefix(node.children):
                return True
    return False


def is_structural(tag, uses_prefix):
    """Check if a tag is structural (gets its own line + indented children)."""
    if uses_prefix:
        return tag in STRUCTURAL_TAGS_PREFIXED or tag in HEAD_SECTION_TAGS
    return tag in STRUCTURAL_TAGS_UNPREFIXED or tag in HEAD_SECTION_TAGS


def format_attrs(attrs):
    """Format attributes in sorted order."""
    sorted_attrs = sorted(attrs, key=lambda a: attr_sort_key(a[0]))
    parts = []
    for name, value in sorted_attrs:
        parts.append(f'{name}="{value}"')
    return " ".join(parts)


def format_node(node, indent, uses_prefix, inside_p=False, force_inline=False):
    """
    Recursively format a node into lines.

    Rules:
    - Structural tags (tt, head, body, div, p, metadata elements): each on own line, children indented
    - <p> children (spans + text): rendered inline within the <p> tag
    - Self-closing tags: single line
    - Processing instructions: single line
    """
    lines = []
    ind = "  " * indent

    if isinstance(node, str):
        # Text node
        if inside_p:
            return [node]
        if node.strip():
            return [f"{ind}{node}"]
        return []

    if node.is_processing_instruction:
        if node.tag == "xml":
            # Always output version before encoding for xml declaration
            lines.append(f'{ind}<?xml version="1.0" encoding="utf-8"?>')
        else:
            attr_str = format_attrs(node.attrs)
            if attr_str:
                lines.append(f"{ind}<?{node.tag} {attr_str}?>")
            else:
                lines.append(f"{ind}<?{node.tag}?>")
        return lines

    tag = node.tag
    attr_str = format_attrs(node.attrs)
    open_tag = f"{tag} {attr_str}".rstrip() if attr_str else tag

    # Force inline rendering
    if force_inline:
        inner = ""
        for child in node.children:
            if isinstance(child, str):
                text = child
                if "\n" in text:
                    text = re.sub(r'\s*\n\s*', ' ', text)
                inner += text
            elif isinstance(child, XMLNode):
                child_parts = format_node(child, 0, uses_prefix, inside_p=True, force_inline=True)
                inner += "".join(child_parts)
        
        # Collapse multiple spaces and clean up edges
        inner = re.sub(r'\s+', ' ', inner).strip()
        
        if node.is_self_closing or (not node.children):
            if inside_p:
                return [f"<{open_tag}/>"]
            return [f"{ind}<{open_tag}/>"]
        if inside_p:
            return [f"<{open_tag}>{inner}</{tag}>"]
        return [f"{ind}<{open_tag}>{inner}</{tag}>"]



    # Self-closing tag
    if node.is_self_closing or (not node.children):
        if inside_p:
            return [f"<{open_tag}/>"]
        lines.append(f"{ind}<{open_tag}/>")
        return lines

    # Check if this is a <p> tag (lyrics line) or inline tag like <span>
    p_tag = "tt:p" if uses_prefix else "p"
    span_tag = "tt:span" if uses_prefix else "span"

    is_p = (tag == p_tag)
    is_span = (tag == span_tag)
    is_bg_wrapper = (tag == span_tag and any(n == "ttm:role" and v == "x-bg" for n, v in node.attrs))

    # Inside a <p>: render spans inline (but not background wrappers)
    if (inside_p and not is_bg_wrapper) or (is_span and not is_bg_wrapper):
        # Inline rendering
        inner = ""
        for child in node.children:
            if isinstance(child, str):
                # Clean up newlines injected inside span text by corrupted formatting
                if "\n" in child:
                    child = re.sub(r'\n\s*', '', child)
                inner += child
            elif isinstance(child, XMLNode):
                # Pass inside_p=True unless child is a bg_wrapper
                c_is_bg = (child.tag == span_tag and any(n == "ttm:role" and v == "x-bg" for n, v in child.attrs))
                child_parts = format_node(child, indent, uses_prefix, inside_p=not c_is_bg)
                inner += "".join(child_parts)
        if node.is_self_closing or (not node.children):
            return [f"<{open_tag}/>"]
        return [f"<{open_tag}>{inner}</{tag}>"]

    # <p> tag or bg wrapper: each span on its own line, inter-span spaces merged into spans
    if is_p or is_bg_wrapper:
        def clean_double_parens(nodes):
            for n in nodes:
                if isinstance(n, str):
                    yield n.replace("((", "(").replace("))", ")")
                elif isinstance(n, XMLNode):
                    n.children = list(clean_double_parens(n.children))
                    yield n
                    
        children = list(node.children)
        if is_bg_wrapper:
            children = list(clean_double_parens(children))
            
        clean_children = []

        # 1. Strip structural indentation (newlines), keep actual spaces/text
        for child in children:
            if isinstance(child, str):
                if "\n" in child:
                    text = child.strip()
                    if text:
                        clean_children.append(text)
                elif child:
                    clean_children.append(child)
            else:
                clean_children.append(child)

        # 2. Merge loose text nodes into the PREVIOUS span if possible, else NEXT
        # This appends " " to the previous word, e.g. "Tak" + " " -> "Tak "
        merged_nodes = []
        pending_text = ""
        for child in clean_children:
            if isinstance(child, str):
                if merged_nodes and isinstance(merged_nodes[-1], XMLNode):
                    # Append text to the previous span's text content
                    merged_nodes[-1].children.append(child)
                else:
                    pending_text += child
            else:
                if pending_text:
                    # Prepend text to this span's text content
                    child.children.insert(0, pending_text)
                    pending_text = ""
                merged_nodes.append(child)

        if pending_text:
            if merged_nodes and isinstance(merged_nodes[-1], XMLNode):
                merged_nodes[-1].children.append(pending_text)
            else:
                merged_nodes.append(pending_text)

        lines.append(f"{ind}<{open_tag}>")
        child_ind = "  " * (indent + 1)
        for item in merged_nodes:
            if isinstance(item, str):
                if item.strip():
                    lines.append(f"{child_ind}{item}")
            else:
                is_item_bg = (item.tag == span_tag and any(n == "ttm:role" and v == "x-bg" for n, v in item.attrs))
                child_parts = format_node(item, indent + 1, uses_prefix, inside_p=not is_item_bg)
                
                # If child_parts returned multiple lines (e.g. from is_bg_wrapper), extend lines directly.
                # If it's a single line (inline span), append it with correct child indentation.
                if len(child_parts) > 1:
                    lines.extend(child_parts)
                else:
                    rendered = "".join(child_parts)
                    lines.append(f"{child_ind}{rendered}")
        lines.append(f"{ind}</{tag}>")
        return lines

    # If the tag ONLY contains text (no formatting elements), OR is an itunes:text tag, render completely inline
    # For example: <itunes:text>Some text <tt:span ttm:role="x-bg">(bg)</tt:span></itunes:text>
    is_text_only = all(isinstance(c, str) for c in node.children)
    is_itunes_text = (tag == "itunes:text")
    
    if (is_text_only or is_itunes_text) and not is_p and not is_bg_wrapper:
        inner = ""
        for child in node.children:
            if isinstance(child, str):
                text = child
                # Clean up corrupted newlines from old formatting
                if "\n" in text:
                    text = re.sub(r'\n\s*', ' ', text)
                inner += text
            elif isinstance(child, XMLNode):
                # Pass force_inline=True to ensure child spans don't get wrapped in multiline format
                child_parts = format_node(child, 0, uses_prefix, inside_p=True, force_inline=True)
                inner += "".join(child_parts)
                
        inner = inner.strip()
        
        if inner:
            return [f"{ind}<{open_tag}>{inner}</{tag}>"]
        elif not node.is_self_closing:
            return [f"{ind}<{open_tag}></{tag}>"]

    # Structural tag with children
    lines.append(f"{ind}<{open_tag}>")
    for child in node.children:
        if isinstance(child, str):
            text = child.strip()
            # Clean up corrupted newlines from old formatting
            if "\n" in text:
                text = re.sub(r'\n\s*', ' ', text)
            if text:
                lines.append(f"{'  ' * (indent + 1)}{text}")
        elif isinstance(child, XMLNode):
            child_lines = format_node(child, indent + 1, uses_prefix, inside_p=False)
            lines.extend(child_lines)
    lines.append(f"{ind}</{tag}>")
    return lines


def format_ttml(content):
    """Format TTML content into pretty-printed XML."""
    # Parse the XML
    nodes = parse_ttml(content)
    if not nodes:
        return content

    uses_prefix = detect_prefix(nodes)

    lines = []
    has_xml_decl = False

    for node in nodes:
        if isinstance(node, XMLNode) and node.is_processing_instruction:
            has_xml_decl = True

        node_lines = format_node(node, 0, uses_prefix, inside_p=False)
        lines.extend(node_lines)

    # Add XML declaration if not present
    if not has_xml_decl:
        lines.insert(0, '<?xml version="1.0" encoding="utf-8"?>')

    result = "\n".join(lines) + "\n"
    return result


# ─── Linter (warnings) ──────────────────────────────────────────────────────

def parse_timestamp(ts):
    """Parse a TTML timestamp (MM:SS.mmm or SS.mmm or H:MM:SS.mmm) to seconds."""
    if ts is None:
        return None
    ts = ts.strip()
    parts = ts.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


def lint_warnings(content, filepath):
    """Check for potential issues in a TTML file. Returns list of warning strings."""
    warnings = []
    nodes = parse_ttml(content)
    uses_prefix = detect_prefix(nodes)

    p_tag = "tt:p" if uses_prefix else "p"
    span_tag = "tt:span" if uses_prefix else "span"

    # Collect all <p> elements
    def collect_p_elements(node_list):
        result = []
        for n in node_list:
            if isinstance(n, XMLNode):
                if n.tag == p_tag:
                    result.append(n)
                result.extend(collect_p_elements(n.children))
        return result

    p_elements = collect_p_elements(nodes)

    # Check itunes:key sequencing
    keys = []
    for p in p_elements:
        key = dict(p.attrs).get("itunes:key")
        if key:
            keys.append(key)

    if keys:
        # Check for duplicates
        seen = set()
        for k in keys:
            if k in seen:
                warnings.append(f"  ⚠ Duplicate itunes:key: {k}")
            seen.add(k)

        # Check sequential numbering
        nums = []
        for k in keys:
            m = re.match(r"L(\d+)", k)
            if m:
                nums.append(int(m.group(1)))
        if nums:
            expected = list(range(1, max(nums) + 1))
            actual = sorted(set(nums))
            missing = set(expected) - set(actual)
            if missing and len(missing) <= 10:
                warnings.append(f"  ⚠ Missing itunes:key numbers: {sorted(missing)}")

    # Check spans in each <p>
    def collect_spans(node_list, tag):
        result = []
        for n in node_list:
            if isinstance(n, XMLNode):
                if n.tag == tag and not any(v == "x-bg" for _, v in n.attrs):
                    result.append(n)
                result.extend(collect_spans(n.children, tag))
        return result

    for p in p_elements:
        p_attrs = dict(p.attrs)
        p_begin = parse_timestamp(p_attrs.get("begin"))
        p_end = parse_timestamp(p_attrs.get("end"))
        p_key = p_attrs.get("itunes:key", p_attrs.get("begin", "?"))

        if p_begin is not None and p_end is not None:
            if p_begin >= p_end:
                warnings.append(f"  ⚠ [{p_key}] p begin >= end: {p_attrs.get('begin')} >= {p_attrs.get('end')}")

        spans = collect_spans(p.children, span_tag)
        for span in spans:
            s_attrs = dict(span.attrs)
            s_begin = parse_timestamp(s_attrs.get("begin"))
            s_end = parse_timestamp(s_attrs.get("end"))
            if s_begin is not None and s_end is not None:
                if s_begin > s_end:
                    text = "".join(c for c in span.children if isinstance(c, str))
                    warnings.append(f"  ⚠ [{p_key}] span begin > end: {s_attrs.get('begin')} > {s_attrs.get('end')} (text: {text!r})")

    return warnings


# ─── CLI ─────────────────────────────────────────────────────────────────────

def find_ttml_files(base_dir="."):
    """Find all .ttml files recursively, excluding test_*.ttml at root."""
    files = []
    for dirpath, _dirnames, filenames in os.walk(base_dir):
        for f in filenames:
            if f.endswith(".ttml"):
                full = os.path.join(dirpath, f)
                files.append(full)
    files.sort()
    return files


def process_file(filepath, fix=False, check=False):
    """
    Process a single TTML file.
    Returns: (has_changes: bool, warnings: list[str])
    """
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    # Normalize line endings
    original_normalized = original.replace("\r\n", "\n").replace("\r", "\n")

    formatted = format_ttml(original_normalized)
    warnings = lint_warnings(original_normalized, filepath)

    has_changes = original_normalized != formatted

    if has_changes:
        if fix:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(formatted)
        elif not check:
            # Show diff
            diff = difflib.unified_diff(
                original_normalized.splitlines(keepends=True),
                formatted.splitlines(keepends=True),
                fromfile=f"a/{filepath}",
                tofile=f"b/{filepath}",
                lineterm="",
            )
            diff_text = "".join(diff)
            if diff_text:
                # Limit diff output
                diff_lines = diff_text.split("\n")
                if len(diff_lines) > 80:
                    print("\n".join(diff_lines[:80]))
                    print(f"  ... ({len(diff_lines) - 80} more lines)")
                else:
                    print(diff_text)

    return has_changes, warnings


def main():
    parser = argparse.ArgumentParser(description="TTML Linter & Formatter")
    parser.add_argument("files", nargs="*", help="TTML files to lint")
    parser.add_argument("--fix", action="store_true", help="Rewrite files in-place")
    parser.add_argument("--check", action="store_true", help="Check only, exit 1 if unformatted")
    parser.add_argument("--all", action="store_true", help="Lint all .ttml files recursively")
    parser.add_argument("--warnings", action="store_true", help="Show lint warnings")

    args = parser.parse_args()

    if args.all:
        files = find_ttml_files(".")
    elif args.files:
        files = args.files
    else:
        parser.print_help()
        sys.exit(1)

    if not files:
        print("No .ttml files found.")
        sys.exit(0)

    total = len(files)
    changed = 0
    all_warnings = []

    for filepath in files:
        try:
            has_changes, warnings = process_file(filepath, fix=args.fix, check=args.check)
        except Exception as e:
            print(f"ERROR {filepath}: {e}")
            continue

        if has_changes:
            changed += 1
            if args.fix:
                print(f"  ✓ Fixed: {filepath}")
            elif args.check:
                print(f"  ✗ Needs formatting: {filepath}")
            else:
                print(f"  ~ Would change: {filepath}")

        if warnings:
            all_warnings.append((filepath, warnings))

    # Summary
    print()
    if args.fix:
        print(f"Fixed {changed}/{total} files.")
    elif args.check:
        print(f"{changed}/{total} files need formatting.")
    else:
        print(f"{changed}/{total} files would change.")

    # Show warnings
    if all_warnings and (args.warnings or not args.check):
        print()
        print("Lint warnings:")
        for filepath, warnings in all_warnings:
            print(f"\n  {filepath}:")
            for w in warnings:
                print(f"    {w}")

    if args.check and changed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
