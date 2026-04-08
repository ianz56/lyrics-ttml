"""
TTML Import Service

Provides functions to import TTML files into the database,
creating Song, LyricLine, and Translation records.
"""

import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Song, LyricLine, Translation
from app.services.parser import parse_ttml_file


# Mapping of folder names to language codes
LANGUAGE_MAP = {
    "ENG": "en",
    "KOR": "ko",
    "IND": "id",
    "MYS": "ms",
    "SUN": "su",
    "ELRC": "en",  # Default to English; ELRC files may vary
}


def _clean_word_data(word: dict) -> dict:
    """Clean a word dict to only keep relevant fields for JSONB storage."""
    return {
        "text": word.get("text", ""),
        "begin": word.get("begin", 0.0),
        "end": word.get("end", 0.0),
        "hasSpaceAfter": word.get("hasSpaceAfter", False),
        "isBackground": word.get("isBackground", False),
        **({"roman": word["roman"]} if word.get("roman") else {}),
    }


def import_ttml_file(
    db: Session,
    file_path: str,
    language: str,
    skip_existing: bool = True,
) -> Song | None:
    """
    Parse a single TTML file and import it into the database.

    Args:
        db: SQLAlchemy sync session
        file_path: Path to the TTML file
        language: Language code (e.g., 'en', 'ko')
        skip_existing: If True, skip if a song with the same artist/title/lang exists

    Returns:
        The created Song object, or None if skipped
    """
    parsed = parse_ttml_file(file_path)
    metadata = parsed.get("metadata", {})

    artist = metadata.get("artist", "Unknown Artist")
    title = metadata.get("title", Path(file_path).stem)
    source_file = metadata.get("sourceFile", Path(file_path).name)

    # Check for existing
    if skip_existing:
        existing = (
            db.query(Song)
            .filter_by(artist=artist, title=title, language=language)
            .first()
        )
        if existing:
            return None

    # Create Song
    song = Song(
        artist=artist,
        title=title,
        language=language,
        source_file=source_file,
        duration=parsed.get("duration"),
        metadata_json=metadata,
    )
    db.add(song)
    db.flush()  # Get the song.id

    # Create LyricLines
    for idx, line_data in enumerate(parsed.get("lines", [])):
        # Clean words for JSONB
        words_json = [_clean_word_data(w) for w in line_data.get("words", [])]

        # Background vocal data
        bg_vocal = line_data.get("backgroundVocal")
        bg_vocal_json = None
        if bg_vocal:
            bg_vocal_json = {
                "text": bg_vocal.get("text", ""),
                "words": [_clean_word_data(w) for w in bg_vocal.get("words", [])],
                **({"roman": bg_vocal["roman"]} if bg_vocal.get("roman") else {}),
            }

        lyric_line = LyricLine(
            song_id=song.id,
            line_index=idx,
            begin_time=line_data.get("begin", 0.0),
            end_time=line_data.get("end", 0.0),
            text=line_data.get("text", ""),
            agent=line_data.get("agent"),
            key=line_data.get("key"),
            words_json=words_json if words_json else None,
            bg_vocal_json=bg_vocal_json,
            romanization=line_data.get("roman"),
        )
        db.add(lyric_line)
        db.flush()

        # Create Translation if present
        translation_text = line_data.get("translation")
        if translation_text:
            translation = Translation(
                lyric_line_id=lyric_line.id,
                language_code="id",  # Default to Indonesian based on TTML content
                text=translation_text,
            )
            db.add(translation)

    return song


def bulk_import_folder(
    db: Session,
    folder_path: str,
    language: str,
    skip_existing: bool = True,
) -> dict:
    """
    Import all TTML files from a folder into the database.

    Args:
        db: SQLAlchemy sync session
        folder_path: Path to folder containing .ttml files
        language: Language code
        skip_existing: If True, skip files with existing artist/title/lang

    Returns:
        Dict with counts: {"imported": int, "skipped": int, "errors": list}
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return {"imported": 0, "skipped": 0, "errors": [f"Not a directory: {folder_path}"]}

    ttml_files = sorted(folder.glob("*.ttml"))
    imported = 0
    skipped = 0
    errors = []

    for ttml_file in ttml_files:
        try:
            song = import_ttml_file(
                db, str(ttml_file), language, skip_existing=skip_existing
            )
            if song:
                imported += 1
                print(f"  ✓ Imported: {ttml_file.name}")
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"{ttml_file.name}: {str(e)}")
            print(f"  ✗ Error: {ttml_file.name} — {str(e)[:80]}")

    return {"imported": imported, "skipped": skipped, "errors": errors}
