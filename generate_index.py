import os
import json

OUTPUT_FILE = "index.json"

index = []

for root, dirs, files in os.walk("."):
    # skip root
    if root == ".":
        continue
    folder = os.path.basename(root)

    for file in files:
        if file.lower().endswith(".ttml"):
            path = os.path.join(root, file).replace("\\", "/")

            name = os.path.splitext(file)[0]
            parts = name.split(" - ")
            artist = parts[0] if len(parts) > 1 else ""
            title = parts[1] if len(parts) > 1 else name

            entry = {
                "artist": artist,
                "title": title,
                "lang": folder,
                "path": path
            }
            index.append(entry)

index = sorted(index, key=lambda x: (x["artist"].lower(), x["title"].lower()))

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

print(f"Generated {OUTPUT_FILE} with {len(index)} entries.")
