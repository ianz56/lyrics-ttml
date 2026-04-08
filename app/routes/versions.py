"""
Version Control API Endpoints

GET  /songs/{id}/versions           — List all versions for a song
GET  /songs/{id}/versions/{ver}     — Get full snapshot of a specific version
POST /songs/{id}/versions/snapshot  — Manually create a snapshot
POST /songs/{id}/versions/rollback  — Rollback to a previous version
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    VersionListItem,
    VersionListResponse,
    VersionDetailResponse,
    RollbackRequest,
    RollbackResponse,
    SnapshotRequest,
)
from app.services.versioning import (
    create_version,
    get_versions,
    get_version,
    rollback_version,
)

router = APIRouter(prefix="/songs/{song_id}/versions", tags=["versions"])


# ─── GET /songs/{id}/versions ────────────────────────────────────────────────


@router.get("", response_model=VersionListResponse)
async def list_versions(
    song_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all version snapshots for a song (metadata only, no snapshot data)."""
    try:
        versions = await get_versions(db, song_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return VersionListResponse(
        song_id=song_id,
        total=len(versions),
        versions=[VersionListItem.model_validate(v) for v in versions],
    )


# ─── GET /songs/{id}/versions/{ver} ─────────────────────────────────────────


@router.get("/{ver}", response_model=VersionDetailResponse)
async def get_version_detail(
    song_id: int,
    ver: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the full snapshot data for a specific version."""
    version = await get_version(db, song_id, ver)

    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"Version {ver} not found for song {song_id}",
        )

    return VersionDetailResponse.model_validate(version)


# ─── POST /songs/{id}/versions/snapshot ──────────────────────────────────────


@router.post("/snapshot", response_model=VersionDetailResponse, status_code=201)
async def create_snapshot(
    song_id: int,
    body: SnapshotRequest = SnapshotRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Manually create a snapshot of the current lyric lines."""
    try:
        version = await create_version(db, song_id, body.change_note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return VersionDetailResponse.model_validate(version)


# ─── POST /songs/{id}/versions/rollback ──────────────────────────────────────


@router.post("/rollback", response_model=RollbackResponse)
async def rollback_to_version(
    song_id: int,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback lyrics to a previous version.

    This will:
    1. Create a backup snapshot of the current state
    2. Replace all lyric_lines with the target version's snapshot
    """
    try:
        backup = await rollback_version(db, song_id, body.version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return RollbackResponse(
        message=f"Rolled back to version {body.version}. "
                f"Current state backed up as version {backup.version}.",
        backup_version=backup.version,
        rolled_back_to=body.version,
    )
