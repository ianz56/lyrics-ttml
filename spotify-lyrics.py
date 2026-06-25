#!/usr/bin/env python3
import json
import time
import sys
import shutil
import os
import math
import re
import urllib.request
import urllib.parse
import http.server
import socketserver
import webbrowser
import threading
import tty
import termios
import select
from dotenv import load_dotenv


# Settings
PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"
TOKEN_FILE = ".spotify-token.json"
FPS = 50
WORD_OFFSET = 0.8   # detik, munculkan karakter lebih awal biar gak kerasa telat
LONG_WORD_THRESHOLD = 1.0
LONG_WORD_SCALE = 0.55

# ----------------- Spotify Authentication -----------------

class AuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            self.server.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <head>
                <title>Spotify Lyrics Connected</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #ffffff; text-align: center; padding-top: 100px; }
                    .card { background-color: #181818; border-radius: 8px; padding: 40px; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.5); max-width: 400px; }
                    h1 { color: #1DB954; margin-bottom: 20px; }
                    p { color: #b3b3b3; line-height: 1.5; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Authentication Successful!</h1>
                    <p>Spotify lyrics terminal is now authorized.</p>
                    <p>You can close this tab and return to your terminal.</p>
                </div>
            </body>
            </html>
            """)
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        # Override to suppress printing logs to stderr which messes with terminal UI
        pass

def get_auth_code(client_id):
    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "user-read-currently-playing user-read-playback-state",
        }, quote_via=urllib.parse.quote)
    )
    
    print("=" * 65)
    print(" SPOTIFY AUTHENTICATION REQUIRED")
    print("=" * 65)
    print("Please open the following URL in your browser to authorize:")
    print(auth_url)
    print("=" * 65)
    print("If you are accessing this terminal via SSH:")
    print("1. Open the URL on your Windows browser and log in.")
    print("2. The browser will fail to load a page (Connection Refused). THIS IS NORMAL.")
    print("3. Copy the ENTIRE URL from the browser's address bar.")
    print("   (It will look like: http://127.0.0.1:8888/callback?code=...)")
    print("4. Paste that URL here.")
    print("=" * 65)
    
    server_auth_code = [None]
    
    class ThreadedAuthHandler(AuthHandler):
        def do_GET(self):
            super().do_GET()
            if hasattr(self.server, 'auth_code') and self.server.auth_code:
                server_auth_code[0] = self.server.auth_code

    server = None
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("", PORT), ThreadedAuthHandler)
        server.auth_code = None
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("Listening for automatic callback on port 8888 (if port-forwarding)...")
    except OSError:
        print("Note: Could not start local callback server (port busy). Only manual paste is available.")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    try:
        user_input = input("\nPaste the redirect URL or authorization code here:\n> ").strip()
        
        if server:
            server.shutdown()
            server.server_close()
            
        if user_input:
            parsed = urllib.parse.urlparse(user_input)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                return params["code"][0]
            else:
                return user_input
        else:
            if server_auth_code[0]:
                print("Authenticated via background server!")
                return server_auth_code[0]
            else:
                print("No code provided and background server did not receive a callback.")
                return None
    except KeyboardInterrupt:
        print("\nAuth cancelled.")
        if server:
            server.shutdown()
            server.server_close()
        return None

def exchange_code_for_tokens(client_id, client_secret, code):
    url = "https://accounts.spotify.com/api/token"
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error exchanging authorization code: {e}")
        return None

def refresh_access_token(client_id, client_secret, refresh_token):
    url = "https://accounts.spotify.com/api/token"
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        # If refreshing fails, might be network error or revoked token
        return None

def get_tokens(client_id, client_secret):
    tokens = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                tokens = json.load(f)
        except Exception:
            pass
            
    if tokens:
        now = time.time()
        # If token is still valid (with a 60 seconds safety margin)
        if tokens.get("expires_at", 0) > now + 60:
            return tokens
        else:
            # Refresh token
            new_tokens = refresh_access_token(client_id, client_secret, tokens.get("refresh_token"))
            if new_tokens:
                tokens.update(new_tokens)
                tokens["expires_at"] = time.time() + new_tokens["expires_in"]
                try:
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        json.dump(tokens, f, indent=2)
                except Exception:
                    pass
                return tokens
    
    # Needs re-authentication
    code = get_auth_code(client_id)
    if not code:
        return None
        
    new_tokens = exchange_code_for_tokens(client_id, client_secret, code)
    if new_tokens:
        new_tokens["expires_at"] = time.time() + new_tokens["expires_in"]
        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(new_tokens, f, indent=2)
        except Exception:
            pass
        return new_tokens
    
    return None

# ----------------- Spotify Web API Helper -----------------

def spotify_get(url, access_token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 204:
                return None, 204
            return json.loads(response.read().decode("utf-8")), response.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 500

# ----------------- String Normalization & Matching -----------------

def clean_string(s):
    if not s:
        return ""
    s = s.lower()
    # Remove common song title decorations/suffixes
    s = re.sub(r'\(feat\..*?\)', '', s)
    s = re.sub(r'\(with.*?\)', '', s)
    s = re.sub(r'- remastered.*$', '', s)
    s = re.sub(r'\(remastered.*?\)', '', s)
    s = re.sub(r'\(from.*?\)', '', s)
    # Strip non-alphanumeric (keep spaces)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    # Simplify whitespaces
    return " ".join(s.split())

def find_matching_track(spotify_title, spotify_artists, index_data):
    clean_title = clean_string(spotify_title)
    clean_artists = [clean_string(a) for a in spotify_artists]
    
    best_match = None
    best_score = 0.0
    
    for entry in index_data:
        entry_title = clean_string(entry["title"])
        entry_artist = clean_string(entry["artist"])
        
        # Check title overlap
        title_match = False
        if entry_title == clean_title or entry_title in clean_title or clean_title in entry_title:
            title_match = True
            
        if title_match:
            # Check if any Spotify artist matches the index artist
            artist_match = False
            for sa in clean_artists:
                if sa in entry_artist or entry_artist in sa:
                    artist_match = True
                    break
            
            if artist_match:
                # Score based on length similarity to favor closer matches
                title_sim = len(entry_title) / max(1, len(clean_title))
                if title_sim > 1.0:
                    title_sim = 1.0 / title_sim
                
                score = title_sim
                if score > best_score:
                    best_score = score
                    best_match = entry
                    
    if best_score > 0.5:
        return best_match
    return None

# ----------------- Thread-safe Playback State -----------------

class PlaybackState:
    def __init__(self):
        self.lock = threading.Lock()
        self.track_id = None
        self.title = None
        self.artists = []
        self.is_playing = False
        self.spotify_progress = 0.0
        self.duration = 0.0
        self.last_update_time = 0.0
        
        self.song_changed = False
        self.connected = False
        self.error_msg = None
        self.idle = True
        self.non_track_type = None

    def update_track(self, track_id, title, artists, is_playing, progress, duration):
        with self.lock:
            if self.track_id != track_id:
                self.track_id = track_id
                self.title = title
                self.artists = artists
                self.song_changed = True
                self.duration = duration
                self.non_track_type = None
            self.is_playing = is_playing
            self.spotify_progress = progress
            self.last_update_time = time.time()
            self.idle = False
            self.connected = True
            self.error_msg = None

    def update_progress(self, is_playing, progress):
        with self.lock:
            self.is_playing = is_playing
            self.spotify_progress = progress
            self.last_update_time = time.time()
            self.idle = False
            self.connected = True
            self.error_msg = None

    def set_non_track(self, type_name):
        with self.lock:
            self.idle = False
            self.is_playing = False
            self.track_id = None
            self.connected = True
            self.title = f"Playing {type_name.capitalize()}"
            self.artists = ["Spotify"]
            self.duration = 0.0
            self.non_track_type = type_name
            self.error_msg = None

    def set_idle(self):
        with self.lock:
            self.idle = True
            self.is_playing = False
            self.track_id = None
            self.connected = True
            self.error_msg = None

    def set_api_error(self, err_msg):
        with self.lock:
            self.error_msg = err_msg

    def set_auth_failed(self, err_msg):
        with self.lock:
            self.connected = False
            self.error_msg = err_msg

    def get_snapshot(self):
        with self.lock:
            return {
                "track_id": self.track_id,
                "title": self.title,
                "artists": self.artists,
                "is_playing": self.is_playing,
                "spotify_progress": self.spotify_progress,
                "duration": self.duration,
                "last_update_time": self.last_update_time,
                "song_changed": self.song_changed,
                "connected": self.connected,
                "error_msg": self.error_msg,
                "idle": self.idle,
                "non_track_type": self.non_track_type
            }

    def clear_song_changed(self):
        with self.lock:
            self.song_changed = False

# ----------------- Polling Worker Thread -----------------

def spotify_polling_thread(client_id, client_secret, state):
    tokens = get_tokens(client_id, client_secret)
    if not tokens:
        state.set_auth_failed("Failed to authenticate with Spotify.")
        return
        
    access_token = tokens["access_token"]
    expires_at = tokens["expires_at"]
    
    while True:
        now = time.time()
        # Refresh tokens if expired
        if now + 60 > expires_at:
            new_tokens = refresh_access_token(client_id, client_secret, tokens.get("refresh_token"))
            if new_tokens:
                tokens.update(new_tokens)
                expires_at = time.time() + new_tokens["expires_in"]
                tokens["expires_at"] = expires_at
                access_token = tokens["access_token"]
                try:
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        json.dump(tokens, f, indent=2)
                except Exception:
                    pass
            else:
                state.set_api_error("Token refresh failed. Retrying...")
                time.sleep(5)
                continue
                
        # API request start time for latency calculation
        try:
            start_req = time.time()
            data, status = spotify_get("https://api.spotify.com/v1/me/player/currently-playing", access_token)
            latency = time.time() - start_req
            
            if status == 401:
                # Token expired unexpectedly, force refresh in next iteration
                expires_at = 0
                continue
            elif status == 204 or not data:
                state.set_idle()
            elif status == 200:
                item = data.get("item")
                playing_type = data.get("currently_playing_type")
                
                if playing_type == "track" and item:
                    track_id = item["id"]
                    title = item["name"]
                    artists = [a["name"] for a in item["artists"]]
                    is_playing = data["is_playing"]
                    duration_sec = item["duration_ms"] / 1000.0
                    
                    # Correct progress using half of latency to account for request delay
                    progress_sec = data["progress_ms"] / 1000.0
                    if is_playing:
                        progress_sec += latency
                        
                    state.update_track(track_id, title, artists, is_playing, progress_sec, duration_sec)
                elif playing_type in ("ad", "episode"):
                    state.set_non_track(playing_type)
                else:
                    state.set_idle()
            else:
                state.set_api_error(f"HTTP {status}")
        except Exception as e:
            state.set_api_error(f"Connection error: {e}")
            
        time.sleep(2)

# ----------------- Timing & Reveal Utilities -----------------

def get_reveal_duration(original_duration):
    original_duration = max(1e-6, original_duration)
    if original_duration <= LONG_WORD_THRESHOLD:
        return original_duration

    excess = original_duration - LONG_WORD_THRESHOLD
    return LONG_WORD_THRESHOLD + math.log1p(excess) * LONG_WORD_SCALE

def render_line(words, now, word_offset):
    out = ""
    for w in words:
        b_orig = float(w["begin"])
        e = float(w["end"])
        b = b_orig - word_offset
        t = w["text"]
        if now < b:
            continue

        dur = get_reveal_duration(e - b_orig)
        step_interval = dur / max(1, len(t))
        n = min(len(t), 1 + int(((now - b) + 1e-9) / step_interval))
        out += t[:n]
        if w.get("hasSpaceAfter") and n > 0:
            out += " "
    return out.rstrip()

def recompute_event_assignments(events, now):
    for ev in events:
        ev["_assigned"] = False
        ev["_row"] = None
        
    next_row = 1
    for ev in events:
        if ev["begin"] <= now:
            ev["_assigned"] = True
            ev["_row"] = next_row
            next_row += 1
    return next_row

def update_event_offsets(events, word_offset):
    for ev in events:
        ev["begin"] = ev["begin_orig"] - word_offset

def load_lyrics_events(lyrics_data):
    events = []
    
    def add_event_from_words(words, line_index):
        if not words:
            return
        b_orig = min(float(w["begin"]) for w in words)
        e_orig = max(float(w["end"]) for w in words)
        events.append({
            "begin_orig": b_orig,
            "begin": b_orig, # initialized to b_orig, will be updated by update_event_offsets
            "end": e_orig,
            "words": words,
            "line_index": line_index,
            "_assigned": False,
            "_row": None,
        })

    for line_index, ln in enumerate(lyrics_data.get("lines", [])):
        add_event_from_words(ln.get("words", []), line_index)
        bv = ln.get("backgroundVocal")
        if bv and bv.get("words"):
            add_event_from_words(bv["words"], line_index)

    events.sort(key=lambda x: x["begin_orig"])
    return events

# ----------------- UI Helpers -----------------

def format_time(seconds):
    if seconds is None or seconds < 0:
        return "00:00"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"

def get_progress_bar(current, total, width):
    if not total or total <= 0:
        return "░" * width
    percent = min(1.0, max(0.0, current / total))
    filled_len = int(width * percent)
    empty_len = width - filled_len
    return "█" * filled_len + "░" * empty_len

def truncate_str(text, max_len):
    if len(text) > max_len:
        return text[:max_len-3] + "..."
    return text

# ----------------- Main Entry Point -----------------

def main():
    load_dotenv()
    
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if client_id:
        client_id = client_id.strip()
    if client_secret:
        client_secret = client_secret.strip()
        
    if client_id and client_secret:
        print(f"Loaded credentials from .env: Client ID = {client_id[:4]}...{client_id[-4:]}, Secret = {client_secret[:4]}...{client_secret[-4:]}")
        
    if not client_id or not client_secret:
        print("=" * 65)
        print(" SPOTIFY CREDENTIALS MISSING")
        print("=" * 65)
        print("To sync with Spotify, you need a Spotify Developer Application:")
        print("1. Go to https://developer.spotify.com/dashboard and log in.")
        print("2. Create an App. Enter any app name and description.")
        print(f"3. IMPORTANT: Set the Redirect URI to exactly: {REDIRECT_URI}")
        print("4. Save the app, open Settings, and copy Client ID & Client Secret.")
        print("=" * 65)
        try:
            inp_id = input("Enter Client ID: ").strip()
            inp_secret = input("Enter Client Secret: ").strip()
            if inp_id and inp_secret:
                with open(".env", "a", encoding="utf-8") as f:
                    f.write(f"\n# Spotify Credentials\nSPOTIFY_CLIENT_ID={inp_id}\nSPOTIFY_CLIENT_SECRET={inp_secret}\n")
                client_id = inp_id
                client_secret = inp_secret
                print("Credentials saved to .env!")
            else:
                print("Invalid input. Exiting.")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(1)

    # ----------------- Synchronous Pre-Auth -----------------
    print("Checking Spotify credentials and tokens...")
    tokens = get_tokens(client_id, client_secret)
    if not tokens:
        print("Failed to authenticate with Spotify. Exiting.")
        sys.exit(1)
        
    print("Authentication successful! Initializing terminal...")
    time.sleep(0.5)

    state = PlaybackState()
    state.connected = True
    
    # Start polling thread
    poll_thread = threading.Thread(
        target=spotify_polling_thread, 
        args=(client_id, client_secret, state), 
        daemon=True
    )
    poll_thread.start()
    
    # Setup index cache
    index_data = []
    
    # Setup rendering timeline
    current_lyrics_file = None
    current_lyrics_events = []
    
    next_row = 1
    first_visible_row = 1
    last_now = None
    word_offset_var = WORD_OFFSET
    
    # Enter alternate terminal buffer and hide cursor
    sys.stdout.write("\033[?1049h\033[H\033[?25l\033[2J")
    sys.stdout.flush()
    
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    try:
        tty.setraw(fd)
        while True:
            # Read terminal size
            W, H = shutil.get_terminal_size(fallback=(120, 30))
            visible = H - 3 # leave bottom 3 lines for status area
            
            snapshot = state.get_snapshot()
            
            # Check connection (fatal auth error)
            if not snapshot["connected"]:
                buf = []
                for screen_row in range(H):
                    buf.append(f"\033[{screen_row + 1};1H\033[2K")
                msg1 = "🔌 Spotify Lyrics Terminal"
                msg2 = snapshot["error_msg"] or "Failed to connect to Spotify."
                msg3 = "Press q to exit"
                
                row1 = H // 2 - 1
                row2 = H // 2
                row3 = H // 2 + 1
                
                buf.append(f"\033[{row1};{(W - len(msg1))//2}H{msg1}")
                buf.append(f"\033[{row2};{(W - len(msg2))//2}H\033[91m{msg2[:W-4]}\033[0m")
                buf.append(f"\033[{row3};{(W - len(msg3))//2}H\033[90m{msg3}\033[0m")
                
                sys.stdout.write("".join(buf))
                sys.stdout.flush()
                
                # Check keys to allow exit
                rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
                if rlist:
                    key = os.read(fd, 1)
                    if key in (b"\x03", b"q", b"Q"):
                        break
                        
                time.sleep(0.1)
                continue
                
            # Check if idle
            if snapshot["idle"]:
                buf = []
                for screen_row in range(H):
                    buf.append(f"\033[{screen_row + 1};1H\033[2K")
                msg1 = "🎵 Spotify Lyrics Terminal"
                msg2 = "Play a song on Spotify to start syncing..."
                msg3 = "Press q to exit"
                
                row1 = H // 2 - 1
                row2 = H // 2
                row3 = H // 2 + 1
                
                buf.append(f"\033[{row1};{(W - len(msg1))//2}H{msg1}")
                buf.append(f"\033[{row2};{(W - len(msg2))//2}H{msg2}")
                buf.append(f"\033[{row3};{(W - len(msg3))//2}H\033[90m{msg3}\033[0m")
                
                sys.stdout.write("".join(buf))
                sys.stdout.flush()
                
                # Clear local cache since nothing is playing
                current_lyrics_file = None
                current_lyrics_events = []
                last_now = None
                
                # Check keys to allow exit
                rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
                if rlist:
                    key = os.read(fd, 1)
                    if key in (b"\x03", b"q", b"Q"):
                        break
                        
                time.sleep(0.2)
                continue
                
            # Track loaded - check if changed
            if snapshot["song_changed"]:
                state.clear_song_changed()
                
                # Reload index.json dynamically to support new songs added on the fly
                index_data = []
                if os.path.exists("index.json"):
                    try:
                        with open("index.json", "r", encoding="utf-8") as f:
                            index_data = json.load(f)
                    except Exception:
                        pass
                
                match = find_matching_track(snapshot["title"], snapshot["artists"], index_data)
                
                if match:
                    try:
                        with open(match["jsonPath"], "r", encoding="utf-8") as f:
                            lyrics_data = json.load(f)
                        current_lyrics_events = load_lyrics_events(lyrics_data)
                        update_event_offsets(current_lyrics_events, word_offset_var)
                        current_lyrics_file = match["path"]
                    except Exception:
                        current_lyrics_events = []
                        current_lyrics_file = None
                else:
                    current_lyrics_events = []
                    current_lyrics_file = None
                    
                # Reset layout state
                next_row = 1
                first_visible_row = 1
                last_now = None
                
            # Compute current playback position "now"
            elapsed = time.time() - snapshot["last_update_time"]
            if snapshot["is_playing"]:
                now = snapshot["spotify_progress"] + elapsed
            else:
                now = snapshot["spotify_progress"]
                
            # Limit now to duration
            if snapshot["duration"] > 0:
                now = min(now, snapshot["duration"])
                
            # Check keyboard input
            rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
            if rlist:
                key = os.read(fd, 1)
                # Check if user pressed Ctrl+C (x03) or q / Q to quit
                if key in (b"\x03", b"q", b"Q"):
                    break
                elif key in (b"-", b"["):
                    word_offset_var = max(-5.0, word_offset_var - 0.1)
                    if current_lyrics_events:
                        update_event_offsets(current_lyrics_events, word_offset_var)
                        next_row = recompute_event_assignments(current_lyrics_events, now)
                elif key in (b"=", b"+", b"]"):
                    word_offset_var = min(10.0, word_offset_var + 0.1)
                    if current_lyrics_events:
                        update_event_offsets(current_lyrics_events, word_offset_var)
                        next_row = recompute_event_assignments(current_lyrics_events, now)
                
            # Detect seeks or resets
            if last_now is not None and (now < last_now or (now - last_now) > 3.0):
                next_row = recompute_event_assignments(current_lyrics_events, now)
                
            last_now = now
            
            # Progress new lyrics row assignments
            for ev in current_lyrics_events:
                if (not ev["_assigned"]) and now >= ev["begin"]:
                    ev["_assigned"] = True
                    ev["_row"] = next_row
                    next_row += 1
                    
            # Compute visible view ranges
            last_row = next_row - 1
            if last_row - first_visible_row + 1 > (visible - 1):
                first_visible_row = last_row - (visible - 1) + 1
            elif last_row < first_visible_row:
                first_visible_row = max(1, last_row - (visible // 2))
                
            # Render Buffer
            buf = []
            
            if current_lyrics_events:
                # Render scrolling lyrics
                row_to_event = {ev["_row"]: ev for ev in current_lyrics_events if ev["_assigned"]}
                for screen_row in range(visible):
                    actual_row = first_visible_row + screen_row
                    ev = row_to_event.get(actual_row)
                    if ev:
                        text = render_line(ev["words"], now, word_offset_var)[:W]
                    else:
                        text = ""
                    buf.append(f"\033[{screen_row + 1};1H\033[2K{text}")
            else:
                # Render "No local lyrics" message
                for screen_row in range(visible):
                    buf.append(f"\033[{screen_row + 1};1H\033[2K")
                
                if snapshot["non_track_type"]:
                    msg1 = f"Currently Playing {snapshot['non_track_type'].capitalize()}"
                    msg2 = ""
                    msg3 = "Lyrics are only supported for musical tracks."
                else:
                    msg1 = "No local lyrics found for:"
                    msg2 = f"{', '.join(snapshot['artists'])} - {snapshot['title']}"
                    msg3 = "Create a TTML file and run generate_index.py to index it!"
                
                row1 = max(1, visible // 2 - 1)
                row2 = max(1, visible // 2)
                row3 = max(1, visible // 2 + 1)
                
                buf.append(f"\033[{row1};{max(1, (W - len(msg1))//2)}H{msg1}")
                if msg2:
                    buf.append(f"\033[{row2};{max(1, (W - len(msg2))//2)}H\033[1;36m{msg2[:W-4]}\033[0m")
                buf.append(f"\033[{row3};{max(1, (W - len(msg3))//2)}H\033[90m{msg3[:W-4]}\033[0m")
                
            # Render Status Area (Bottom 3 lines)
            # Line 1: separator
            sep = "─" * W
            buf.append(f"\033[{H-2};1H\033[2K\033[90m{sep}\033[0m")
            
            # Line 2: Play/Pause indicator & Title & Synced or Error status
            if snapshot["error_msg"]:
                status_text = f" ⚠️ Error: {snapshot['error_msg']}"
            else:
                play_indicator = "🟢 Playing" if snapshot["is_playing"] else "⏸️ Paused"
                status_text = f" {play_indicator}: {', '.join(snapshot['artists'])} - {snapshot['title']}"
                if current_lyrics_file:
                    status_text += " [Synced]"
                else:
                    status_text += " [Unsynced]"
            buf.append(f"\033[{H-1};1H\033[2K{truncate_str(status_text, W)}")
            
            # Line 3: Progress bar, Time markers, and Offset
            time_str = f" {format_time(now)} / {format_time(snapshot['duration'])}"
            offset_str = f" Offset: {word_offset_var:+.1f}s (Adjust: -/=)"
            hint_str = "Press q to Exit "
            
            # Calculate remaining space for progress bar
            reserved = len(time_str) + len(offset_str) + len(hint_str) + 6
            bar_width = max(10, min(30, W - reserved))
            p_bar = get_progress_bar(now, snapshot["duration"], bar_width)
            
            progress_line = f"{time_str}  {p_bar}  \033[90m{offset_str}\033[0m"
            
            # spacing based on plain string length
            plain_len = len(time_str) + 2 + bar_width + 2 + len(offset_str)
            spacing = W - plain_len - len(hint_str)
            if spacing > 0:
                progress_line += " " * spacing
            progress_line += f"\033[90m{hint_str}\033[0m"
            buf.append(f"\033[{H};1H\033[2K{progress_line}")
            
            # Print buffer all at once to avoid screen flicker
            sys.stdout.write("".join(buf))
            sys.stdout.flush()
            
            time.sleep(1.0 / FPS)
            
    finally:
        # Restore terminal window and show cursor
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[0m\033[?1049l\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
