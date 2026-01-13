import os
import json
import datetime
import re

OUTPUT_FILE = "index.json"
SITEMAP_FILE = "sitemap.xml"
INDEX_HTML = "index.html"
BASE_URL = "https://ianz56.github.io/lyrics-ttml"

def generate_html_card(item):
    return f"""<article class="card">
  <div class="card__title">{item['title']}</div>
  <div class="card__meta">{item['artist']} - {item['lang'].upper()}</div>
  <div class="card__links">
    <a class="card__link" href="{item['path']}" aria-label="Open {item['title']} TTML">TTML</a>
    <a class="card__link card__link--json" href="{item['jsonPath']}" aria-label="Open {item['title']} JSON">JSON</a>
  </div>
</article>"""

index = []

print("Scanning files...")
for root, dirs, files in os.walk("."):
    if root == ".":
        continue
    
    # Skip hidden directories like .git
    if os.path.basename(root).startswith("."):
        continue

    folder = os.path.basename(root)

    for file in files:
        if file.lower().endswith(".ttml"):
            # Use forward slashes for paths
            path = os.path.join(root, file).replace("\\", "/")
            
            # JSON path construction
            json_filename = os.path.splitext(file)[0] + ".json"
            json_path = f"./JSON/{folder}/{json_filename}"

            name = os.path.splitext(file)[0]
            parts = name.split(" - ")
            artist = parts[0] if len(parts) > 1 else ""
            title = parts[1] if len(parts) > 1 else name

            entry = {
                "artist": artist,
                "title": title,
                "lang": folder,
                "path": path,
                "jsonPath": json_path,
                "lastmod": datetime.date.today().isoformat() # Using today as approximation if file stat is not critical
            }
            index.append(entry)

# Sort index
index = sorted(index, key=lambda x: (x["artist"].lower(), x["title"].lower()))

# Write index.json
print(f"Writing {OUTPUT_FILE}...")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

# Write sitemap.xml
print(f"Writing {SITEMAP_FILE}...")
sitemap_content = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

# Add root
sitemap_content.append(f"""  <url>
    <loc>{BASE_URL}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>""")

for item in index:
    # URL encode path parts if necessary, though simple paths usually work. 
    # Better to act simple for now. 
    # Assuming relative paths like ./ENG/File.ttml
    # We need to strip ./ for the URL
    clean_path = item['path']
    if clean_path.startswith("./"):
        clean_path = clean_path[2:]
    
    url = f"{BASE_URL}/{clean_path}"
    
    sitemap_content.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{item['lastmod']}</lastmod>
    <changefreq>monthly</changefreq>
  </url>""")

sitemap_content.append('</urlset>')

with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(sitemap_content))


# Inject into index.html
print(f"Updating {INDEX_HTML}...")
with open(INDEX_HTML, "r", encoding="utf-8") as f:
    html_content = f.read()

# Generate HTML list
html_list_items = [generate_html_card(item) for item in index]
html_list_str = "\n".join(html_list_items)

# Update count
html_content = re.sub(r'<span id="count">.*?</span>', f'<span id="count">{len(index)}</span>', html_content)

# Update list content
# We look for the tag <section class="grid" id="list">...</section>
# Using regex to find the start and end of the tag is tricky with nested tags, 
# but this section is likely empty or contains previous build.
# We will match explicit start tag and closing tag for this specific section.

# Pattern: <section class="grid" id="list"> ... </section>
# Note: attributes order might vary if edited manually, but let's assume standard format or just id match
pattern = r'(<section class="grid" id="list">)(.*?)(</section>)'
replacement = f'\\1{html_list_str}\\3'

# Using DOTALL so . matches newlines
html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL)

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print("Done.")
