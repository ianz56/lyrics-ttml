"""
Song API Endpoints

GET    /songs           — List all songs (paginated, filterable)
GET    /songs/{id}      — Get full song with lyrics, translations
POST   /songs           — Upload a TTML file → parse & store
PATCH  /songs/{id}      — Update song metadata
DELETE /songs/{id}      — Delete a song
PUT    /songs/{id}/lines — Update lyric lines (auto-snapshots before update)
GET    /search          — Search songs by query string
"""

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Song, LyricLine, Translation
from app.schemas import (
    SongListItem,
    SongListResponse,
    SongDetailResponse,
    LyricLineResponse,
    SearchResponse,
    UpdateLyricsRequest,
    SongUpdateRequest,
)
from app.services.parser import parse_ttml_content
from app.services.versioning import create_version

router = APIRouter(prefix="/songs", tags=["songs"])


# ─── GET /songs ──────────────────────────────────────────────────────────────


@router.get("", response_model=SongListResponse)
async def list_songs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    artist: Optional[str] = Query(None, description="Filter by artist name"),
    db: AsyncSession = Depends(get_db),
):
    """List all songs with pagination and optional filters."""
    query = select(Song)

    if language:
        query = query.where(Song.language == language)
    if artist:
        query = query.where(Song.artist.ilike(f"%{artist}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = (
        query.order_by(Song.artist, Song.title)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    songs = result.scalars().all()

    return SongListResponse(
        total=total,
        page=page,
        per_page=per_page,
        songs=[SongListItem.model_validate(s) for s in songs],
    )


# ─── GET /songs/{id} ─────────────────────────────────────────────────────────


@router.get("/{song_id}", response_model=SongDetailResponse)
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)):
    """Get a song with all lyric lines and translations."""
    query = (
        select(Song)
        .where(Song.id == song_id)
        .options(
            selectinload(Song.lyric_lines).selectinload(LyricLine.translations)
        )
    )

    result = await db.execute(query)
    song = result.scalar_one_or_none()

    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    return SongDetailResponse(
        id=song.id,
        artist=song.artist,
        title=song.title,
        language=song.language,
        duration=song.duration,
        source_file=song.source_file,
        metadata_json=song.metadata_json,
        created_at=song.created_at,
        updated_at=song.updated_at,
        lines=[
            LyricLineResponse.model_validate(line) for line in song.lyric_lines
        ],
    )


# ─── POST /songs ─────────────────────────────────────────────────────────────


@router.post("", response_model=SongDetailResponse, status_code=201)
async def create_song(
    file: UploadFile = File(..., description="TTML file to upload"),
    language: str = Form("en", description="Language code (e.g., en, ko, id)"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a TTML file, parse it, and store in the database."""
    if not file.filename or not file.filename.endswith(".ttml"):
        raise HTTPException(status_code=400, detail="Only .ttml files are accepted")

    content = await file.read()
    content_str = content.decode("utf-8")

    # Parse TTML
    try:
        parsed = parse_ttml_content(content_str, source_filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse TTML: {str(e)}")

    metadata = parsed.get("metadata", {})
    artist = metadata.get("artist", "Unknown Artist")
    title = metadata.get("title", file.filename)
    source_file = metadata.get("sourceFile", file.filename)

    # Check for duplicate
    existing_query = select(Song).where(
        Song.artist == artist,
        Song.title == title,
        Song.language == language,
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Song already exists: {artist} - {title} ({language})",
        )

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
    await db.flush()

    # Create LyricLines + Translations
    for idx, line_data in enumerate(parsed.get("lines", [])):
        words = line_data.get("words", [])
        words_json = [
            {
                "text": w.get("text", ""),
                "begin": w.get("begin", 0.0),
                "end": w.get("end", 0.0),
                "hasSpaceAfter": w.get("hasSpaceAfter", False),
                "isBackground": w.get("isBackground", False),
                **({"roman": w["roman"]} if w.get("roman") else {}),
            }
            for w in words
        ] if words else None

        bg_vocal = line_data.get("backgroundVocal")
        bg_vocal_json = None
        if bg_vocal:
            bg_vocal_json = {
                "text": bg_vocal.get("text", ""),
                "words": [
                    {
                        "text": w.get("text", ""),
                        "begin": w.get("begin", 0.0),
                        "end": w.get("end", 0.0),
                        "hasSpaceAfter": w.get("hasSpaceAfter", False),
                        "isBackground": w.get("isBackground", False),
                        **({"roman": w["roman"]} if w.get("roman") else {}),
                    }
                    for w in bg_vocal.get("words", [])
                ],
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
            words_json=words_json,
            bg_vocal_json=bg_vocal_json,
            romanization=line_data.get("roman"),
        )
        db.add(lyric_line)
        await db.flush()

        translation_text = line_data.get("translation")
        if translation_text:
            translation = Translation(
                lyric_line_id=lyric_line.id,
                language_code="id",
                text=translation_text,
            )
            db.add(translation)

    # Re-fetch with eager loading for response
    await db.flush()
    full_query = (
        select(Song)
        .where(Song.id == song.id)
        .options(
            selectinload(Song.lyric_lines).selectinload(LyricLine.translations)
        )
    )
    full_result = await db.execute(full_query)
    full_song = full_result.scalar_one()

    return SongDetailResponse(
        id=full_song.id,
        artist=full_song.artist,
        title=full_song.title,
        language=full_song.language,
        duration=full_song.duration,
        source_file=full_song.source_file,
        metadata_json=full_song.metadata_json,
        created_at=full_song.created_at,
        updated_at=full_song.updated_at,
        lines=[
            LyricLineResponse.model_validate(line) for line in full_song.lyric_lines
        ],
    )


# ─── PATCH /songs/{id} ───────────────────────────────────────────────────


@router.patch("/{song_id}", response_model=SongListItem)
async def update_song(
    song_id: int,
    body: SongUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update song metadata (artist, title, language)."""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if body.artist is not None:
        song.artist = body.artist
    if body.title is not None:
        song.title = body.title
    if body.language is not None:
        song.language = body.language

    await db.flush()
    return SongListItem.model_validate(song)


# ─── DELETE /songs/{id} ──────────────────────────────────────────────────


@router.delete("/{song_id}", status_code=204)
async def delete_song(
    song_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a song and all its lyric lines, translations, and versions."""
    result = await db.execute(select(Song).where(Song.id == song_id))
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    await db.delete(song)
    await db.flush()


# ─── PUT /songs/{id}/lines ───────────────────────────────────────────────────


@router.put("/{song_id}/lines", response_model=SongDetailResponse)
async def update_lyrics(
    song_id: int,
    body: UpdateLyricsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update all lyric lines for a song. Automatically snapshots the current state first."""
    # Ensure song exists
    song_query = select(Song).where(Song.id == song_id)
    result = await db.execute(song_query)
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    # Auto-snapshot current state before applying update
    change_note = body.change_note or "Auto-snapshot before lyric update"
    try:
        await create_version(db, song_id, change_note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Delete existing lyric_lines (CASCADE deletes translations)
    await db.execute(delete(LyricLine).where(LyricLine.song_id == song_id))
    await db.flush()

    # Create new lines from request body
    for line_data in body.lines:
        lyric_line = LyricLine(
            song_id=song_id,
            line_index=line_data.line_index,
            begin_time=line_data.begin_time,
            end_time=line_data.end_time,
            text=line_data.text,
            agent=line_data.agent,
            key=line_data.key,
            words_json=line_data.words_json,
            bg_vocal_json=line_data.bg_vocal_json,
            romanization=line_data.romanization,
        )
        db.add(lyric_line)
        await db.flush()

        # Create translations if provided
        if line_data.translations:
            for trans in line_data.translations:
                translation = Translation(
                    lyric_line_id=lyric_line.id,
                    language_code=trans.get("language_code", "en"),
                    text=trans.get("text", ""),
                )
                db.add(translation)

    await db.flush()

    # Re-fetch full song for response
    full_query = (
        select(Song)
        .where(Song.id == song_id)
        .options(
            selectinload(Song.lyric_lines).selectinload(LyricLine.translations)
        )
    )
    full_result = await db.execute(full_query)
    full_song = full_result.scalar_one()

    return SongDetailResponse(
        id=full_song.id,
        artist=full_song.artist,
        title=full_song.title,
        language=full_song.language,
        duration=full_song.duration,
        source_file=full_song.source_file,
        metadata_json=full_song.metadata_json,
        created_at=full_song.created_at,
        updated_at=full_song.updated_at,
        lines=[
            LyricLineResponse.model_validate(line) for line in full_song.lyric_lines
        ],
    )


# ─── GET /search ─────────────────────────────────────────────────────────────


search_router = APIRouter(tags=["search"])


@search_router.get("/search", response_model=SearchResponse)
async def search_songs(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    """Search songs by artist, title, or lyric text using ILIKE."""
    search_term = f"%{q}%"

    # Search in songs (artist + title)
    song_query = (
        select(Song)
        .where(
            or_(
                Song.artist.ilike(search_term),
                Song.title.ilike(search_term),
            )
        )
        .order_by(Song.artist, Song.title)
        .limit(limit)
    )

    result = await db.execute(song_query)
    songs = list(result.scalars().all())

    # If not enough results, also search in lyric text
    if len(songs) < limit:
        remaining = limit - len(songs)
        song_ids = [s.id for s in songs]

        lyric_query = (
            select(Song)
            .join(LyricLine, LyricLine.song_id == Song.id)
            .where(
                LyricLine.text.ilike(search_term),
            )
            .group_by(Song.id)
            .order_by(Song.artist, Song.title)
            .limit(remaining)
        )

        if song_ids:
            lyric_query = lyric_query.where(Song.id.notin_(song_ids))

        lyric_result = await db.execute(lyric_query)
        songs.extend(lyric_result.scalars().all())

    return SearchResponse(
        query=q,
        total=len(songs),
        songs=[SongListItem.model_validate(s) for s in songs],
    )
