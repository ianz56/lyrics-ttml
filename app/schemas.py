from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Lyric Line Schemas ──────────────────────────────────────────────────────


class TranslationResponse(BaseModel):
    id: int
    language_code: str
    text: str

    model_config = {"from_attributes": True}


class LyricLineResponse(BaseModel):
    id: int
    line_index: int
    begin_time: float
    end_time: float
    text: str
    agent: Optional[str] = None
    key: Optional[str] = None
    words_json: Optional[Any] = None
    bg_vocal_json: Optional[Any] = None
    romanization: Optional[str] = None
    translations: list[TranslationResponse] = []

    model_config = {"from_attributes": True}


# ─── Song Schemas ─────────────────────────────────────────────────────────────


class SongBase(BaseModel):
    artist: str
    title: str
    language: str


class SongListItem(BaseModel):
    """Compact representation for listing songs."""

    id: int
    artist: str
    title: str
    language: str
    duration: Optional[float] = None
    source_file: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SongDetailResponse(BaseModel):
    """Full song with all lyric lines and translations."""

    id: int
    artist: str
    title: str
    language: str
    duration: Optional[float] = None
    source_file: str
    metadata_json: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    lines: list[LyricLineResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SongListResponse(BaseModel):
    """Paginated list of songs."""

    total: int
    page: int
    per_page: int
    songs: list[SongListItem]


class SearchResponse(BaseModel):
    """Search results."""

    query: str
    total: int
    songs: list[SongListItem]


# ─── Version Schemas ──────────────────────────────────────────────────────────


class VersionListItem(BaseModel):
    """Compact version info without full snapshot."""

    id: int
    version: int
    change_note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionDetailResponse(BaseModel):
    """Full version with snapshot data."""

    id: int
    version: int
    change_note: Optional[str] = None
    snapshot: Any
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    """List of versions for a song."""

    song_id: int
    total: int
    versions: list[VersionListItem]


class RollbackRequest(BaseModel):
    """Request body for rollback."""

    version: int


class SnapshotRequest(BaseModel):
    """Request body for manual snapshot."""

    change_note: Optional[str] = None


class RollbackResponse(BaseModel):
    """Response after rollback."""

    message: str
    backup_version: int
    rolled_back_to: int


# ─── Update Lyrics Schemas ───────────────────────────────────────────────────


class LyricLineUpdate(BaseModel):
    """A single lyric line in an update request."""

    line_index: int
    begin_time: float
    end_time: float
    text: str = ""
    agent: Optional[str] = None
    key: Optional[str] = None
    words_json: Optional[Any] = None
    bg_vocal_json: Optional[Any] = None
    romanization: Optional[str] = None
    translations: Optional[list[dict]] = None  # [{"language_code": "id", "text": "..."}]


class UpdateLyricsRequest(BaseModel):
    """Request body for updating all lyric lines of a song."""

    lines: list[LyricLineUpdate]
    change_note: Optional[str] = None
