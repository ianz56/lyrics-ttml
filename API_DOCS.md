# 🎵 Lyrics TTML API Documentation

REST API server for TTML (Timed Text Markup Language) lyric files. Provides word-level timed lyrics with background vocals, translations, and romanization support.

**Base URL:** `http://localhost:8001`  
**Interactive Docs:** `http://localhost:8001/docs` (Swagger UI)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Endpoints](#endpoints)
  - [GET /songs](#get-songs)
  - [GET /songs/{id}](#get-songsid)
  - [POST /songs](#post-songs)
  - [GET /search](#get-search)
  - [GET /health](#get-health)
- [Data Models](#data-models)
  - [Song](#song)
  - [Lyric Line](#lyric-line)
  - [Word Timing](#word-timing)
  - [Background Vocal](#background-vocal)
  - [Translation](#translation)
- [Language Codes](#language-codes)
- [Database Schema](#database-schema)
- [Running the Server](#running-the-server)
- [Import Script](#import-script)

---

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start with Docker
docker compose up --build

# 3. Test the API
curl http://localhost:8001/songs
```

---

## Endpoints

### GET /songs

List all songs with pagination and optional filters.

**Query Parameters:**

| Parameter  | Type   | Default | Description                        |
|-----------|--------|---------|-------------------------------------|
| `page`     | int    | `1`     | Page number (min: 1)               |
| `per_page` | int    | `20`    | Items per page (min: 1, max: 100)  |
| `language` | string | —       | Filter by language code (`en`, `id`, `ko`, etc.) |
| `artist`   | string | —       | Filter by artist name (partial match, case-insensitive) |

**Example — List all songs (paginated):**

```bash
curl "http://localhost:8001/songs?per_page=3"
```

```json
{
  "total": 137,
  "page": 1,
  "per_page": 3,
  "songs": [
    {
      "id": 1,
      "artist": "Alan Walker",
      "title": "Old Habits (From Delta Force Game)",
      "language": "en",
      "duration": 161.914,
      "source_file": "Alan Walker - Old Habits (From Delta Force Game).ttml",
      "created_at": "2026-04-08T03:46:37.120691Z"
    },
    {
      "id": 3,
      "artist": "Alan Walker, Emma Steinbakken",
      "title": "Not You",
      "language": "en",
      "duration": 125.701,
      "source_file": "Alan Walker, Emma Steinbakken - Not You.ttml",
      "created_at": "2026-04-08T03:46:37.212001Z"
    },
    {
      "id": 2,
      "artist": "Alan Walker, Emma Steinbakken",
      "title": "Not You (Restrung Performance)",
      "language": "en",
      "duration": 152.438,
      "source_file": "Alan Walker, Emma Steinbakken - Not You (Restrung Performance).ttml",
      "created_at": "2026-04-08T03:46:37.174808Z"
    }
  ]
}
```

**Example — Filter by language:**

```bash
curl "http://localhost:8001/songs?language=ko"
```

```json
{
  "total": 2,
  "page": 1,
  "per_page": 20,
  "songs": [
    {
      "id": 41,
      "artist": "Exo",
      "title": "The First Snow",
      "language": "ko",
      "duration": 207.74,
      "source_file": "Exo - The First Snow.ttml",
      "created_at": "2026-04-08T03:46:38.770942Z"
    }
  ]
}
```

**Example — Filter by artist:**

```bash
curl "http://localhost:8001/songs?artist=for+revenge"
```

```json
{
  "total": 8,
  "page": 1,
  "per_page": 20,
  "songs": [
    {
      "id": 70,
      "artist": "For Revenge",
      "title": "Bandung Hari Ini",
      "language": "id",
      "duration": 207.552,
      "source_file": "For Revenge - Bandung Hari Ini.ttml",
      "created_at": "2026-04-08T03:46:39.592320Z"
    },
    {
      "id": 71,
      "artist": "For Revenge",
      "title": "Kala Luka Berpesta",
      "language": "id",
      "duration": 225.807,
      "source_file": "For Revenge - Kala Luka Berpesta.ttml",
      "created_at": "2026-04-08T03:46:39.617971Z"
    }
  ]
}
```

---

### GET /songs/{id}

Get full song detail with all lyric lines, word-level timing, background vocals, and translations.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Song ID     |

**Example — Song with translations:**

```bash
curl "http://localhost:8001/songs/27"
```

```json
{
  "id": 27,
  "artist": "Rachel Grae",
  "title": "It'll Be Okay (Transalted)",
  "language": "en",
  "duration": 223.157,
  "source_file": "Rachel Grae - It'll Be Okay (Transalted).ttml",
  "metadata_json": {
    "title": "It'll Be Okay (Transalted)",
    "agents": [
      { "id": "v1", "type": "person" }
    ],
    "artist": "Rachel Grae",
    "sourceFile": "Rachel Grae - It'll Be Okay (Transalted).ttml"
  },
  "created_at": "2026-04-08T03:46:38.165521Z",
  "updated_at": "2026-04-08T03:46:38.165540Z",
  "lines": [
    {
      "id": 1169,
      "line_index": 0,
      "begin_time": 6.462,
      "end_time": 9.567,
      "text": "Hmm-mmm",
      "agent": "v1",
      "key": "L1",
      "words_json": [
        { "text": "Hmm-", "begin": 6.462, "end": 8.922, "hasSpaceAfter": false, "isBackground": false },
        { "text": "mmm",  "begin": 8.922, "end": 9.567, "hasSpaceAfter": false, "isBackground": false }
      ],
      "bg_vocal_json": null,
      "romanization": null,
      "translations": []
    },
    {
      "id": 1170,
      "line_index": 1,
      "begin_time": 13.397,
      "end_time": 17.222,
      "text": "Are we gonna make it?",
      "agent": "v1",
      "key": "L2",
      "words_json": [
        { "text": "Are",  "begin": 13.397, "end": 14.897, "hasSpaceAfter": true,  "isBackground": false },
        { "text": "we",   "begin": 14.897, "end": 15.280, "hasSpaceAfter": true,  "isBackground": false },
        { "text": "gon",  "begin": 15.280, "end": 15.640, "hasSpaceAfter": false, "isBackground": false },
        { "text": "na",   "begin": 15.640, "end": 16.030, "hasSpaceAfter": true,  "isBackground": false },
        { "text": "make", "begin": 16.030, "end": 16.840, "hasSpaceAfter": true,  "isBackground": false },
        { "text": "it?",  "begin": 16.840, "end": 17.222, "hasSpaceAfter": false, "isBackground": false }
      ],
      "bg_vocal_json": null,
      "romanization": null,
      "translations": [
        {
          "id": 186,
          "language_code": "id",
          "text": "Apa kita bakal bertahan?"
        }
      ]
    }
  ]
}
```

**Example — Song with background vocals (The 1975 - About You):**

```bash
curl "http://localhost:8001/songs/34"
```

A line with background vocals will include `bg_vocal_json`:

```json
{
  "id": 1457,
  "line_index": 7,
  "begin_time": 104.276,
  "end_time": 107.829,
  "text": "You and I",
  "agent": "v1",
  "key": "L8",
  "words_json": [
    { "text": "You", "begin": 104.276, "end": 104.526, "hasSpaceAfter": true,  "isBackground": false },
    { "text": "and", "begin": 104.526, "end": 104.810, "hasSpaceAfter": true,  "isBackground": false },
    { "text": "I",   "begin": 104.810, "end": 105.809, "hasSpaceAfter": true,  "isBackground": false }
  ],
  "bg_vocal_json": {
    "text": "(Don't let go)",
    "words": [
      { "text": "(Don't", "begin": 105.727, "end": 106.241, "hasSpaceAfter": true,  "isBackground": true },
      { "text": "let",    "begin": 106.658, "end": 107.042, "hasSpaceAfter": true,  "isBackground": true },
      { "text": "go)",    "begin": 107.276, "end": 107.829, "hasSpaceAfter": false, "isBackground": true }
    ]
  },
  "romanization": null,
  "translations": []
}
```

**Error — Song not found:**

```bash
curl "http://localhost:8001/songs/99999"
```

```json
{
  "detail": "Song not found"
}
```

> HTTP 404

---

### POST /songs

Upload a TTML file to parse and store in the database.

**Request:** `multipart/form-data`

| Field      | Type   | Required | Description                        |
|-----------|--------|----------|-------------------------------------|
| `file`     | file   | ✅       | TTML file (`.ttml` extension only) |
| `language` | string | No       | Language code (default: `en`)      |

**Example — Upload a TTML file with curl:**

```bash
curl -X POST "http://localhost:8001/songs" \
  -F "file=@ENG/Calum Scott - You Are The Reason.ttml" \
  -F "language=en"
```

```json
{
  "id": 138,
  "artist": "Calum Scott",
  "title": "You Are The Reason",
  "language": "en",
  "duration": 198.5,
  "source_file": "Calum Scott - You Are The Reason.ttml",
  "lines": [
    {
      "line_index": 0,
      "begin_time": 12.345,
      "end_time": 15.678,
      "text": "There goes my heart beating...",
      "words_json": [ ... ],
      "translations": []
    }
  ]
}
```

> HTTP 201 Created

**Example — Upload with Python requests:**

```python
import requests

url = "http://localhost:8001/songs"

with open("IND/Mahalini - Sial.ttml", "rb") as f:
    response = requests.post(
        url,
        files={"file": ("Mahalini - Sial.ttml", f, "application/xml")},
        data={"language": "id"}
    )

print(response.status_code)  # 201
print(response.json()["id"]) # 139
```

**Error — Duplicate song:**

```json
{
  "detail": "Song already exists: Mahalini - Sial (id)"
}
```

> HTTP 409 Conflict

**Error — Invalid file type:**

```json
{
  "detail": "Only .ttml files are accepted"
}
```

> HTTP 400 Bad Request

---

### GET /search

Search songs by artist name, song title, or lyric text content. Searches artist and title first, then falls back to searching within lyric lines.

**Query Parameters:**

| Parameter | Type   | Default | Description                |
|-----------|--------|---------|----------------------------|
| `q`       | string | —       | Search query (required, min 1 char) |
| `limit`   | int    | `20`    | Max results (min: 1, max: 100)      |

**Example — Search by artist:**

```bash
curl "http://localhost:8001/search?q=mahalini"
```

```json
{
  "query": "mahalini",
  "total": 9,
  "songs": [
    {
      "id": 93,
      "artist": "Mahalini",
      "title": "Batasi Rasa",
      "language": "id",
      "duration": 239.687,
      "source_file": "Mahalini - Batasi Rasa.ttml",
      "created_at": "2026-04-08T03:46:40.284595Z"
    },
    {
      "id": 94,
      "artist": "Mahalini",
      "title": "Kemarilah Tenang",
      "language": "id",
      "duration": 230.746,
      "source_file": "Mahalini - Kemarilah Tenang.ttml",
      "created_at": "2026-04-08T03:46:40.316456Z"
    },
    {
      "id": 99,
      "artist": "Mahalini",
      "title": "Sial",
      "language": "id",
      "duration": 234.627,
      "source_file": "Mahalini - Sial.ttml",
      "created_at": "2026-04-08T03:46:40.472153Z"
    }
  ]
}
```

**Example — Search by lyric content:**

Searching for `"cinta"` (Indonesian word for "love") finds songs that contain the word in their lyrics, even if it's not in the title:

```bash
curl "http://localhost:8001/search?q=cinta"
```

```json
{
  "query": "cinta",
  "total": 20,
  "songs": [
    {
      "id": 67,
      "artist": "Elma Dae",
      "title": "Cinta Terindah",
      "language": "id",
      "duration": 225.433
    },
    {
      "id": 128,
      "artist": "Virgoun",
      "title": "Surat Cinta Untuk Starla (New Version)",
      "language": "id",
      "duration": 254.919
    },
    {
      "id": 42,
      "artist": "Aldo Sagala",
      "title": "Rodok Rodok",
      "language": "id",
      "duration": 264.704
    }
  ]
}
```

> Note: "Aldo Sagala - Rodok Rodok" doesn't have "cinta" in the title — it was found by searching the lyric text content.

**Example — Limit results:**

```bash
curl "http://localhost:8001/search?q=love&limit=5"
```

---

### GET /health

Health check endpoint.

```bash
curl "http://localhost:8001/health"
```

```json
{
  "status": "ok"
}
```

---

## Data Models

### Song

| Field          | Type      | Description                                  |
|---------------|-----------|----------------------------------------------|
| `id`           | integer   | Unique song ID                               |
| `artist`       | string    | Artist name                                  |
| `title`        | string    | Song title                                   |
| `language`     | string    | Language code (`en`, `ko`, `id`, `ms`, `su`) |
| `duration`     | float     | Song duration in seconds                     |
| `source_file`  | string    | Original TTML filename                       |
| `metadata_json`| object    | Full metadata from TTML header (agents, etc.)|
| `created_at`   | datetime  | Import timestamp                             |
| `updated_at`   | datetime  | Last update timestamp                        |
| `lines`        | array     | Array of [Lyric Line](#lyric-line) objects (detail endpoint only) |

### Lyric Line

| Field          | Type      | Description                                  |
|---------------|-----------|----------------------------------------------|
| `id`           | integer   | Unique line ID                               |
| `line_index`   | integer   | Position in song (0-indexed)                 |
| `begin_time`   | float     | Start time in seconds                        |
| `end_time`     | float     | End time in seconds                          |
| `text`         | string    | Full line text                               |
| `agent`        | string    | Vocal agent (`v1`, `v2`, etc.)               |
| `key`          | string    | iTunes line key (`L1`, `L2`, etc.)           |
| `words_json`   | array     | Array of [Word Timing](#word-timing) objects |
| `bg_vocal_json`| object    | [Background Vocal](#background-vocal) data (null if none) |
| `romanization` | string    | Romanized line text (null if not available)  |
| `translations` | array     | Array of [Translation](#translation) objects |

### Word Timing

Each word in `words_json` has precise timing for karaoke-style display:

| Field          | Type    | Description                                  |
|---------------|---------|----------------------------------------------|
| `text`         | string  | Word text (may be a syllable fragment)       |
| `begin`        | float   | Word start time in seconds                   |
| `end`          | float   | Word end time in seconds                     |
| `hasSpaceAfter`| boolean | Whether a space follows this word            |
| `isBackground` | boolean | Whether this is a background vocal word      |
| `roman`        | string  | Romanized word text (optional, for non-Latin scripts) |

> **Note:** Words may be split into syllables (e.g., `"gon"` + `"na"` = `"gonna"`). Use `hasSpaceAfter` to reconstruct the full text correctly.

### Background Vocal

When a lyric line has an overlapping background vocal (e.g., backup singers), the `bg_vocal_json` contains:

| Field   | Type   | Description                                 |
|---------|--------|---------------------------------------------|
| `text`  | string | Full background vocal text                  |
| `words` | array  | Array of [Word Timing](#word-timing) objects with `isBackground: true` |
| `roman` | string | Romanized background text (optional)        |

### Translation

| Field           | Type   | Description                        |
|----------------|--------|------------------------------------|
| `id`            | integer| Translation ID                     |
| `language_code` | string | Translation language (e.g., `id` for Indonesian) |
| `text`          | string | Translated line text               |

---

## Language Codes

| Code | Language   | Folder | Song Count |
|------|-----------|--------|------------|
| `en` | English   | `ENG/` | ~40        |
| `id` | Indonesian| `IND/` | ~94        |
| `ko` | Korean    | `KOR/` | ~2         |
| `ms` | Malay     | `MYS/` | ~1         |
| `su` | Sundanese | `SUN/` | ~1         |

---

## Database Schema

```
┌─────────────────────┐
│       songs          │
├─────────────────────┤
│ id (PK)             │
│ artist              │──┐
│ title               │  │ UNIQUE(artist, title, language)
│ language            │──┘
│ source_file         │
│ duration            │
│ metadata_json       │
│ created_at          │
│ updated_at          │
└────────┬────────────┘
         │ 1:N
┌────────▼────────────┐
│    lyric_lines       │
├─────────────────────┤
│ id (PK)             │
│ song_id (FK)        │
│ line_index          │
│ begin_time          │
│ end_time            │
│ text                │
│ agent               │
│ key                 │
│ words_json (JSONB)  │
│ bg_vocal_json (JSONB)│
│ romanization        │
└────────┬────────────┘
         │ 1:N
┌────────▼────────────┐
│   translations       │
├─────────────────────┤
│ id (PK)             │
│ lyric_line_id (FK)  │
│ language_code       │
│ text                │
└─────────────────────┘
```

---

## Running the Server

### With Docker (recommended)

```bash
# Start PostgreSQL + API
cp .env.example .env
docker compose up --build

# Runs migrations + imports all TTML files automatically
# API available at http://localhost:8001
# Swagger docs at http://localhost:8001/docs
```

### Without Docker

```bash
# 1. Setup
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Start PostgreSQL (must be running separately)
# Update DATABASE_URL in .env if needed

# 3. Run migrations
alembic upgrade head

# 4. Import TTML files
python import_ttml.py              # Import all folders
python import_ttml.py --folder ENG # Import only English
python import_ttml.py --force      # Re-import (overwrite existing)

# 5. Start server
uvicorn app.main:app --reload --port 8001
```

---

## Import Script

The `import_ttml.py` script batch-imports TTML files from language folders into the database.

```bash
# Import all folders (ENG, KOR, IND, MYS, SUN, ELRC)
python import_ttml.py

# Import a specific folder
python import_ttml.py --folder IND

# Force re-import (do not skip existing songs)
python import_ttml.py --force
```

**Output:**

```
────────────────────────────────────────────────────────────
📂 ENG/ (40 TTML files, language=en)
────────────────────────────────────────────────────────────
  ✓ Imported: Alan Walker - Old Habits (From Delta Force Game).ttml
  ✓ Imported: Backstreet Boys - Drowning.ttml
  ...
  → Imported: 40 | Skipped: 0 | Errors: 0

════════════════════════════════════════════════════════════
  IMPORT COMPLETE
════════════════════════════════════════════════════════════
  Imported: 137
  Skipped:  0
  Errors:   0
```
