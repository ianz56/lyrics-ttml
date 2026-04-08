from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Song(Base):
    """A song with its metadata, parsed from a TTML file."""

    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artist = Column(String(500), nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    source_file = Column(String(1000), nullable=False)
    duration = Column(Float, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    lyric_lines = relationship(
        "LyricLine",
        back_populates="song",
        cascade="all, delete-orphan",
        order_by="LyricLine.line_index",
    )
    lyric_versions = relationship(
        "LyricVersion",
        back_populates="song",
        cascade="all, delete-orphan",
        order_by="LyricVersion.version",
    )

    __table_args__ = (
        UniqueConstraint("artist", "title", "language", name="uq_song_artist_title_lang"),
        Index(
            "ix_song_search",
            "artist",
            "title",
            postgresql_ops={"artist": "gin_trgm_ops", "title": "gin_trgm_ops"},
            postgresql_using="gin",
        ),
    )

    def __repr__(self):
        return f"<Song(id={self.id}, artist='{self.artist}', title='{self.title}')>"


class LyricLine(Base):
    """A single timed lyric line within a song."""

    __tablename__ = "lyric_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    song_id = Column(
        Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_index = Column(Integer, nullable=False)
    begin_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False, default="")
    agent = Column(String(50), nullable=True)
    key = Column(String(50), nullable=True)
    words_json = Column(JSONB, nullable=True)
    bg_vocal_json = Column(JSONB, nullable=True)
    romanization = Column(Text, nullable=True)

    # Relationships
    song = relationship("Song", back_populates="lyric_lines")
    translations = relationship(
        "Translation",
        back_populates="lyric_line",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_lyric_line_song_index", "song_id", "line_index"),
    )

    def __repr__(self):
        return f"<LyricLine(id={self.id}, song_id={self.song_id}, index={self.line_index})>"


class Translation(Base):
    """A translation of a lyric line in a specific language."""

    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lyric_line_id = Column(
        Integer,
        ForeignKey("lyric_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_code = Column(String(10), nullable=False)
    text = Column(Text, nullable=False)

    # Relationships
    lyric_line = relationship("LyricLine", back_populates="translations")

    def __repr__(self):
        return f"<Translation(id={self.id}, line_id={self.lyric_line_id}, lang='{self.language_code}')>"


class LyricVersion(Base):
    """A versioned snapshot of all lyric_lines for a song."""

    __tablename__ = "lyric_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    song_id = Column(
        Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False)
    change_note = Column(Text, nullable=True)
    snapshot = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    song = relationship("Song", back_populates="lyric_versions")

    __table_args__ = (
        UniqueConstraint("song_id", "version", name="uq_lyric_version_song_ver"),
    )

    def __repr__(self):
        return f"<LyricVersion(id={self.id}, song_id={self.song_id}, v={self.version})>"
