# 🎼 Lyrics Collection (Personal Archive)

This repository contains a curated collection of **TTML (Timed Text Markup Language) lyric files**, manually timed and formatted by me.  
The primary purpose of this repo is **archival, experimentation, and integration** with personal tooling and projects (such as lyric players, subtitle engines, custom websites, etc.).

> ⚠️ **Disclaimer:** This repository is not intended for redistribution of copyrighted lyric text. All lyrics remain the property of their respective rights holders. These files are archived here strictly for personal research, development, and non-commercial use.

---

## Spotify Synced Lyrics Terminal (`spotify-lyrics.py`)

A terminal-based synced lyrics player that follows your currently playing Spotify track and scrolls local TTML/JSON lyrics in real time.

### Features
- **Automatic Song Tracking**: Dynamically tracks play/pause, seeks, and skip actions on your Spotify player.
- **Real-time Live Offset**: Fine-tune lyric timing offset by `±0.1s` steps on the fly.
- **Fuzzy Track Matching**: Matches Spotify track names and artists to local indexed lyrics file structure.
- **Flicker-free Rendering**: Custom double-buffering terminal engine updating smoothly at 50 FPS.
- **Self-contained**: Pure Python implementation using standard libraries (no external packages except `python-dotenv`).

### How to Run
Ensure you run using the Python virtual environment:
```bash
./venv/bin/python spotify-lyrics.py
```

### Keyboard Controls (Interactive)
While the lyrics display is active:
* **`=` / `+`** or **`]`** : **Speed up lyrics** (increase offset by `+0.1s`). Use this if the lyrics appear **too late**.
* **`-`** or **`[`** : **Slow down lyrics** (decrease offset by `-0.1s`). Use this if the lyrics appear **too early**.
* **`q`** or **`Ctrl+C`** : **Exit** the player cleanly and restore terminal layout.

### Configuration Settings
On the first run, the script will request your Spotify credentials:
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an App.
2. In the App settings, register the Redirect URI as: `http://127.0.0.1:8888/callback`.
3. Check the **Web API** box under API/SDKs options.
4. Input the Client ID and Client Secret into the script, which automatically appends them to your `.env` file.

---

## Credits
This repository makes use of **amll-ttml-tool** (https://github.com/Steve-xmh/amll-ttml-tool) to generate and edit TTML lyric files.


