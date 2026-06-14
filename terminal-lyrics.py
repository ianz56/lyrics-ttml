import json, time, sys, shutil, os, math, termios, tty

if len(sys.argv) < 2:
    print("Usage: python script.py <file.json>")
    sys.exit(1)

PATH = sys.argv[1]

if not os.path.exists(PATH):
    print(f"File not found: {PATH}")
    sys.exit(1)
FPS = 50
WORD_OFFSET = 0.8   # detik, munculkan karakter lebih awal biar gak kerasa telat
LONG_WORD_THRESHOLD = 1.0
LONG_WORD_SCALE = 0.55

def get_reveal_duration(original_duration):
    original_duration = max(1e-6, original_duration)
    if original_duration <= LONG_WORD_THRESHOLD:
        return original_duration

    excess = original_duration - LONG_WORD_THRESHOLD
    return LONG_WORD_THRESHOLD + math.log1p(excess) * LONG_WORD_SCALE

def render_line(words, now):
    out = ""
    for w in words:
        b_orig = float(w["begin"]); e = float(w["end"])
        b = b_orig - WORD_OFFSET          # mulai reveal lebih awal
        t = w["text"]
        if now < b:
            continue

        dur = get_reveal_duration(e - b_orig)
        # Sisakan satu interval setelah huruf terakhir agar huruf terakhir
        # tidak muncul bersamaan dengan awal kata berikutnya.
        step_interval = dur / max(1, len(t))
        n = min(len(t), 1 + int(((now - b) + 1e-9) / step_interval))
        out += t[:n]
        if w.get("hasSpaceAfter") and n > 0:
            out += " "
    return out.rstrip()

def get_line_text(line):
    if line.get("text"):
        return line["text"].strip()

    return "".join(
        w["text"] + (" " if w.get("hasSpaceAfter") else "")
        for w in line.get("words", [])
    ).strip()

def select_start_line(lines):
    choices = [
        (index, get_line_text(line))
        for index, line in enumerate(lines)
        if line.get("words")
    ]
    if not choices:
        return None
    if not sys.stdin.isatty():
        return choices[0][0]

    selected = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    sys.stdout.write("\033[?1049h\033[?25l")
    try:
        tty.setraw(fd)
        while True:
            height = shutil.get_terminal_size(fallback=(120, 30)).lines
            page_size = max(1, height - 2)
            page_start = max(0, min(
                selected - page_size // 2,
                len(choices) - page_size,
            ))
            page_end = min(len(choices), page_start + page_size)

            buf = ["\033[H\033[2J"]
            buf.append("Pilih mulai lirik (↑/↓ atau j/k, Enter untuk play, q batal)\r\n")
            for position in range(page_start, page_end):
                marker = ">" if position == selected else " "
                number = position + 1
                text = choices[position][1]
                buf.append(f"{marker} {number:3}. {text}\033[K\r\n")
            sys.stdout.write("".join(buf))
            sys.stdout.flush()

            key = os.read(fd, 1)
            if key in (b"\r", b"\n"):
                return choices[selected][0]
            if key in (b"q", b"\x03"):
                return None
            if key == b"\x1b":
                sequence = os.read(fd, 2)
                if sequence == b"[A":
                    selected = max(0, selected - 1)
                elif sequence == b"[B":
                    selected = min(len(choices) - 1, selected + 1)
            elif key == b"k":
                selected = max(0, selected - 1)
            elif key == b"j":
                selected = min(len(choices) - 1, selected + 1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

events = []

def add_event_from_words(words, line_index):
    if not words:
        return
    b = min(float(w["begin"]) for w in words) - WORD_OFFSET
    e = max(float(w["end"]) for w in words)
    events.append({
        "begin": b,
        "end": e,
        "words": words,
        "line_index": line_index,
        "_assigned": False,
        "_row": None,
    })

# main + BG (backgroundVocal) jadi event masing-masing
for line_index, ln in enumerate(data["lines"]):
    add_event_from_words(ln.get("words", []), line_index)
    bv = ln.get("backgroundVocal")
    if bv and bv.get("words"):
        add_event_from_words(bv["words"], line_index)

events.sort(key=lambda x: x["begin"])

# kalau kosong, stop
if not events:
    print("No events found.")
    raise SystemExit(1)

selected_line = select_start_line(data["lines"])
if selected_line is None:
    raise SystemExit(0)

events = [ev for ev in events if ev["line_index"] >= selected_line]
selected_words = data["lines"][selected_line]["words"]
start_at = min(float(w["begin"]) for w in selected_words) - WORD_OFFSET
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
