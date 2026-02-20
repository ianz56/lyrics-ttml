import json, time, sys, shutil, os

if len(sys.argv) < 2:
    print("Usage: python script.py <file.json>")
    sys.exit(1)

PATH = sys.argv[1]

if not os.path.exists(PATH):
    print(f"File not found: {PATH}")
    sys.exit(1)
FPS = 50
WORD_OFFSET = 0.8   # detik, munculkan karakter lebih awal biar gak kerasa telat

def clamp(x, a, b): return max(a, min(b, x))

def render_line(words, now):
    out = ""
    for w in words:
        b_orig = float(w["begin"]); e = float(w["end"])
        b = b_orig - WORD_OFFSET          # mulai reveal lebih awal
        dur = max(1e-6, e - b_orig)        # kecepatan reveal = durasi asli
        t = w["text"]
        if now < b:
            continue
        p = clamp((now - b) / dur, 0.0, 1.0)
        n = int(len(t) * p)
        out += t[:n]
        if w.get("hasSpaceAfter") and n > 0:
            out += " "
    return out.rstrip()

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

events = []

def add_event_from_words(words):
    if not words:
        return
    b = min(float(w["begin"]) for w in words) - WORD_OFFSET
    e = max(float(w["end"]) for w in words)
    events.append({
        "begin": b,
        "end": e,
        "words": words,
        "_assigned": False,
        "_row": None,
    })

# main + BG (backgroundVocal) jadi event masing-masing
for ln in data["lines"]:
    add_event_from_words(ln.get("words", []))
    bv = ln.get("backgroundVocal")
    if bv and bv.get("words"):
        add_event_from_words(bv["words"])

events.sort(key=lambda x: x["begin"])

# kalau kosong, stop
if not events:
    print("No events found.")
    raise SystemExit(1)

start_at = min(ev["begin"] for ev in events)
end_at   = max(ev["end"]   for ev in events)

# alternate screen (biar command gak hilang)
sys.stdout.write("\033[?1049h\033[H\033[?25l\033[2J")
sys.stdout.flush()

t0 = time.time() - start_at
next_row = 1
first_visible_row = 1

try:
    while True:
        now = time.time() - t0
        if now > end_at + 0.75:
            break

        # assign row pas mulai (overlap => row baru)
        for ev in events:
            if (not ev["_assigned"]) and now >= ev["begin"]:
                ev["_assigned"] = True
                ev["_row"] = next_row
                next_row += 1

        H = shutil.get_terminal_size(fallback=(120, 30)).lines
        visible = max(3, H)  # minimal 3 baris biar ada debug

        last_row = next_row - 1
        if last_row - first_visible_row + 1 > (visible - 1):
            first_visible_row = last_row - (visible - 1) + 1

        # render — kumpulkan semua ke buffer, tulis sekali (anti flicker)
        W = shutil.get_terminal_size(fallback=(120, 30)).columns
        buf = []
        row_to_event = {ev["_row"]: ev for ev in events if ev["_assigned"]}
        for screen_row in range(visible):
            actual_row = first_visible_row + screen_row
            ev = row_to_event.get(actual_row)
            if ev:
                text = render_line(ev["words"], now)[:W]
            else:
                text = ""
            buf.append(f"\033[{screen_row + 1};1H\033[2K{text}")

        sys.stdout.write("".join(buf))
        sys.stdout.flush()
        time.sleep(1.0 / FPS)

finally:
    sys.stdout.write("\033[?25h\033[0m\033[?1049l")
    sys.stdout.flush()
