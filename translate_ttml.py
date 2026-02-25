#!/usr/bin/env python3
import sys
import os
import argparse
import re

# Add current dir to path to import lint_ttml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from lint_ttml import parse_ttml, XMLNode, detect_prefix, format_node
except ImportError:
    print("Error: Could not import lint_ttml.py. Make sure it exists in the same directory.")
    sys.exit(1)

def extract_original_text(node):
    """
    Extract lyrics text from a node (ignoring translation).
    For a <p> tag, we also ignore <span ttm:role="x-bg"> since it's a separate unit.
    """
    text = ""
    is_p = (node.tag == "p" or node.tag == "tt:p")
    for child in node.children:
        if isinstance(child, str):
            if "\n" in child and child.strip() == "":
                continue
            text += child
        elif isinstance(child, XMLNode):
            role = next((v for k, v in child.attrs if k == "ttm:role"), None)
            
            if role == "x-translation":
                continue
                
            if is_p and role == "x-bg":
                continue
                
            text += extract_original_text(child)
    
    # We simply replace formatting newlines and multiple spaces with a single space.
    # We do NOT run strip() on the entire string because it trims valid trailing spaces.
    text = re.sub(r'\n\s+', '', text) # Remove structural newlines entirely
    text = text.replace('\n', '')
    
    # Do not strip(), otherwise "knees " becomes "knees" and misses joining context.
    # However we do want to strip leading/trailing spaces for the *final* string output,
    # but ONLY on the fully combined unit, not during recursive calls.
    return text

def find_translation_node(node):
    for child in node.children:
        if isinstance(child, XMLNode):
            role = next((v for k, v in child.attrs if k == "ttm:role"), None)
            if role == "x-translation":
                return child
    return None

def get_translation_text(node):
    trans_node = find_translation_node(node)
    if trans_node:
        return "".join(c for c in trans_node.children if isinstance(c, str)).strip()
    return ""

def set_translation_text(node, text, uses_prefix):
    # Remove existing translation node
    trans_node = find_translation_node(node)
    if trans_node:
        node.children.remove(trans_node)
    
    if text:
        span_tag = "tt:span" if uses_prefix else "span"
        new_node = XMLNode(tag=span_tag, attrs=[("ttm:role", "x-translation"), ("xml:lang", "id-ID")])
        new_node.children.append(text)
        node.children.append(new_node)

def get_units(node_list, uses_prefix):
    units = []
    p_tag = "tt:p" if uses_prefix else "p"
    span_tag = "tt:span" if uses_prefix else "span"
    
    for n in node_list:
        if isinstance(n, XMLNode):
            if n.tag == p_tag:
                units.append(n)
                # Look for background vocals
                for c in n.children:
                    if isinstance(c, XMLNode) and c.tag == span_tag:
                        c_role = next((v for k, v in c.attrs if k == "ttm:role"), None)
                        if c_role == "x-bg":
                            units.append(c)
            elif n.tag != span_tag:
                units.extend(get_units(n.children, uses_prefix))
    return units

def serialize_nodes(nodes, uses_prefix):
    lines = []
    has_xml_decl = False
    for node in nodes:
        if isinstance(node, XMLNode) and node.is_processing_instruction:
            has_xml_decl = True
        node_lines = format_node(node, 0, uses_prefix, inside_p=False)
        lines.extend(node_lines)
    
    if not has_xml_decl:
        lines.insert(0, '<?xml version="1.0" encoding="utf-8"?>')
        
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description="Interactive TTML Translator CLI")
    parser.add_argument("file", help="Path to TTML file")
    args = parser.parse_args()

    filepath = args.file
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    nodes = parse_ttml(content)
    if not nodes:
        print("Failed to parse TTML.")
        sys.exit(1)

    uses_prefix = detect_prefix(nodes)
    units = get_units(nodes, uses_prefix)

    if not units:
        print("No <p> elements or translation units found.")
        sys.exit(0)

    translation_memory = {}
    for unit in units:
        orig = extract_original_text(unit).strip()
        trans = get_translation_text(unit)
        if trans:
            translation_memory[orig] = trans

    i = 0
    save = False

    while True:
        if i >= len(units):
            print("\n" + "="*50)
            print("                END OF FILE REACHED")
            print("="*50)
            prompt = "Enter [line number] to edit, 's' to save & exit, 'q' to quit: "
            try:
                user_input = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting without saving.")
                break
            
            if user_input.lower() == 's':
                save = True
                break
            elif user_input.lower() == 'q':
                save = False
                break
            elif user_input.isdigit():
                target = int(user_input) - 1
                if 0 <= target < len(units):
                    i = target
                else:
                    print("Invalid line number.")
            else:
                print("Invalid command. Input a number, 's', or 'q'.")
            continue

        unit = units[i]
        orig = extract_original_text(unit).strip()
        current_trans = get_translation_text(unit)
        
        is_bg = next((v for k, v in unit.attrs if k == "ttm:role"), None) == "x-bg"
        prefix = "[BG] " if is_bg else "[Main] "
        
        print("\n" + "-"*50)
        print(f"Line {i+1} / {len(units)}")
        print(f"Original : {prefix}{orig}")
        
        if orig in translation_memory and not current_trans:
            suggested = translation_memory[orig]
            print(f"Auto-fill: {suggested}")
            set_translation_text(unit, suggested, uses_prefix)
            current_trans = suggested
        
        if current_trans:
            print(f"Current  : {current_trans}")
            
        prompt = "Translation (Enter: keep, [number]: jump, '-': delete, 'q': quit): "
        try:
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting without saving.")
            break
        
        if user_input.lower() == 'q':
            save = False
            break
        elif user_input == '-':
            set_translation_text(unit, "", uses_prefix)
        elif user_input.isdigit():
            target = int(user_input) - 1
            if 0 <= target < len(units):
                i = target
                continue
            else:
                print("Invalid line number.")
                continue
        elif user_input == '':
            pass
        else:
            set_translation_text(unit, user_input, uses_prefix)
            translation_memory[orig] = user_input
            
        i += 1

    if save:
        formatted_xml = serialize_nodes(nodes, uses_prefix)
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(formatted_xml)
        print(f"\nSaved changes to {filepath}")
    else:
        print("\nChanges discarded.")

if __name__ == "__main__":
    main()
