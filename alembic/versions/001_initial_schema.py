"""initial schema - songs, lyric_lines, translations

Revision ID: 001
Revises:
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── songs table ──────────────────────────────────────────────────────
    op.create_table(
        "songs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artist", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("source_file", sa.String(length=1000), nullable=False),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artist", "title", "language", name="uq_song_artist_title_lang"),
    )

    # Indexes for songs
    op.create_index("ix_songs_artist", "songs", ["artist"])
    op.create_index("ix_songs_title", "songs", ["title"])
    op.create_index("ix_songs_language", "songs", ["language"])

    # Trigram GIN index for fuzzy search
    op.execute(
        "CREATE INDEX ix_song_search ON songs "
        "USING gin (artist gin_trgm_ops, title gin_trgm_ops)"
    )

    # ── lyric_lines table ────────────────────────────────────────────────
    op.create_table(
        "lyric_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("begin_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("agent", sa.String(length=50), nullable=True),
        sa.Column("key", sa.String(length=50), nullable=True),
        sa.Column("words_json", JSONB(), nullable=True),
        sa.Column("bg_vocal_json", JSONB(), nullable=True),
        sa.Column("romanization", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_lyric_lines_song_id", "lyric_lines", ["song_id"])
    op.create_index(
        "ix_lyric_line_song_index", "lyric_lines", ["song_id", "line_index"]
    )

    # ── translations table ───────────────────────────────────────────────
    op.create_table(
        "translations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lyric_line_id", sa.Integer(), nullable=False),
        sa.Column("language_code", sa.String(length=10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lyric_line_id"], ["lyric_lines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_translations_lyric_line_id", "translations", ["lyric_line_id"]
    )


def downgrade() -> None:
    op.drop_table("translations")
    op.drop_table("lyric_lines")
    op.drop_table("songs")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
