"""
Lyric Versioning Service

Provides functions to create snapshots of lyric lines, list version history,
retrieve specific versions, and rollback to a previous version.
"""

from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Song, LyricLine, LyricVersion, Translation


def _serialize_line(line: LyricLine) -> dict:
    """Serialize a LyricLine ORM object to a dict suitable for JSONB storage."""
    return {
        "line_index": line.line_index,
        "begin_time": line.begin_time,
        "end_time": line.end_time,
        "text": line.text,
        "agent": line.agent,
        "key": line.key,
        "words_json": line.words_json,
        "bg_vocal_json": line.bg_vocal_json,
        "romanization": line.romanization,
        "translations": [
            {
                "language_code": t.language_code,
                "text": t.text,
            }
            for t in line.translations
        ],
    }


async def _get_song_or_raise(db: AsyncSession, song_id: int) -> Song:
    """Fetch a song by ID or raise ValueError if not found."""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise ValueError(f"Song with id {song_id} not found")
    return song


async def _get_next_version(db: AsyncSession, song_id: int) -> int:
    """Get the next version number for a song (max existing + 1, or 1 if none)."""
    result = await db.execute(
        select(func.max(LyricVersion.version)).where(
            LyricVersion.song_id == song_id
        )
    )
    max_ver = result.scalar()
    return (max_ver or 0) + 1


async def create_version(
    db: AsyncSession,
    song_id: int,
    change_note: Optional[str] = None,
) -> LyricVersion:
    """
    Snapshot the current lyric_lines of a song into a new lyric_version.

    Args:
        db: Async database session
        song_id: The song to snapshot
        change_note: Optional description of what changed

    Returns:
        The created LyricVersion object
    """
    # Ensure song exists
    await _get_song_or_raise(db, song_id)

    # Fetch current lyric lines with translations
    lines_query = (
        select(LyricLine)
        .where(LyricLine.song_id == song_id)
        .options(selectinload(LyricLine.translations))
        .order_by(LyricLine.line_index)
    )
    result = await db.execute(lines_query)
    lines = result.scalars().all()

    # Build snapshot
    snapshot = [_serialize_line(line) for line in lines]

    # Determine next version number
    next_ver = await _get_next_version(db, song_id)

    # Create version record
    version = LyricVersion(
        song_id=song_id,
        version=next_ver,
        change_note=change_note,
        snapshot=snapshot,
    )
    db.add(version)
    await db.flush()

    return version


async def get_versions(
    db: AsyncSession,
    song_id: int,
) -> list[LyricVersion]:
    """
    List all versions for a song, ordered by version number.

    Args:
        db: Async database session
        song_id: The song ID

    Returns:
        List of LyricVersion objects (without loading full snapshot)
    """
    await _get_song_or_raise(db, song_id)

    result = await db.execute(
        select(LyricVersion)
        .where(LyricVersion.song_id == song_id)
        .order_by(LyricVersion.version)
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession,
    song_id: int,
    version: int,
) -> LyricVersion | None:
    """
    Get a specific version of a song's lyrics.

    Args:
        db: Async database session
        song_id: The song ID
        version: The version number

    Returns:
        LyricVersion object or None if not found
    """
    result = await db.execute(
        select(LyricVersion).where(
            LyricVersion.song_id == song_id,
            LyricVersion.version == version,
        )
    )
    return result.scalar_one_or_none()


async def rollback_version(
    db: AsyncSession,
    song_id: int,
    version: int,
) -> LyricVersion:
    """
    Rollback a song's lyrics to a previous version.

    1. First creates a backup snapshot of the current state
    2. Deletes all current lyric_lines (and their translations via CASCADE)
    3. Recreates lyric_lines from the target version's snapshot

    Args:
        db: Async database session
        song_id: The song ID
        version: The target version number to rollback to

    Returns:
        The backup LyricVersion that was created before rolling back

    Raises:
        ValueError: If song or version not found
    """
    # Ensure song exists
    await _get_song_or_raise(db, song_id)

    # Get the target version
    target = await get_version(db, song_id, version)
    if not target:
        raise ValueError(f"Version {version} not found for song {song_id}")

    # Step 1: Backup current state
    backup = await create_version(
        db, song_id, change_note=f"Auto-backup before rollback to v{version}"
    )

    # Step 2: Delete current lyric_lines (CASCADE deletes translations too)
    await db.execute(
        delete(LyricLine).where(LyricLine.song_id == song_id)
    )
    await db.flush()

    # Step 3: Recreate from snapshot
    for line_data in target.snapshot:
        lyric_line = LyricLine(
            song_id=song_id,
            line_index=line_data["line_index"],
            begin_time=line_data["begin_time"],
            end_time=line_data["end_time"],
            text=line_data.get("text", ""),
            agent=line_data.get("agent"),
            key=line_data.get("key"),
            words_json=line_data.get("words_json"),
            bg_vocal_json=line_data.get("bg_vocal_json"),
            romanization=line_data.get("romanization"),
        )
        db.add(lyric_line)
        await db.flush()

        # Recreate translations
        for trans_data in line_data.get("translations", []):
            translation = Translation(
                lyric_line_id=lyric_line.id,
                language_code=trans_data["language_code"],
                text=trans_data["text"],
            )
            db.add(translation)

    await db.flush()
    return backup
