#!/usr/bin/env python3
"""
CLI script to bulk-import all TTML files from language folders into the database.

Usage:
    python import_ttml.py                  # Import all folders
    python import_ttml.py --folder ENG     # Import only ENG folder
    python import_ttml.py --force          # Re-import (skip existing is disabled)

Requires:
    - PostgreSQL running and accessible via DATABASE_URL_SYNC in .env
    - Tables created via `alembic upgrade head`
"""

import argparse
import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_sync_session_factory
from app.services.importer import bulk_import_folder, LANGUAGE_MAP


# Default folders to scan (relative to project root)
DEFAULT_FOLDERS = ["ENG", "KOR", "IND", "MYS", "SUN", "ELRC"]


def main():
    parser = argparse.ArgumentParser(
        description="Bulk-import TTML lyric files into the PostgreSQL database"
    )
    parser.add_argument(
        "--folder",
        help="Import only a specific folder (e.g., ENG, KOR)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-import all files (do not skip existing)",
    )
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    if args.folder:
        folders = [args.folder.upper()]
    else:
        folders = DEFAULT_FOLDERS

    session_factory = get_sync_session_factory()

    total_imported = 0
    total_skipped = 0
    total_errors = []

    for folder_name in folders:
        folder_path = base_dir / folder_name
        if not folder_path.is_dir():
            print(f"⚠ Folder not found, skipping: {folder_name}")
            continue

        language = LANGUAGE_MAP.get(folder_name, "unknown")
        ttml_count = len(list(folder_path.glob("*.ttml")))

        print(f"\n{'─' * 60}")
        print(f"📂 {folder_name}/ ({ttml_count} TTML files, language={language})")
        print(f"{'─' * 60}")

        session = session_factory()
        try:
            result = bulk_import_folder(
                session,
                str(folder_path),
                language,
                skip_existing=not args.force,
            )
            session.commit()

            total_imported += result["imported"]
            total_skipped += result["skipped"]
            total_errors.extend(result["errors"])

            print(
                f"  → Imported: {result['imported']} | "
                f"Skipped: {result['skipped']} | "
                f"Errors: {len(result['errors'])}"
            )
        except Exception as e:
            session.rollback()
            print(f"  ✗ Fatal error on {folder_name}: {e}")
            total_errors.append(f"{folder_name}: {str(e)}")
        finally:
            session.close()

    # Summary
    print(f"\n{'═' * 60}")
    print(f"  IMPORT COMPLETE")
    print(f"{'═' * 60}")
    print(f"  Imported: {total_imported}")
    print(f"  Skipped:  {total_skipped}")
    print(f"  Errors:   {len(total_errors)}")

    if total_errors:
        print(f"\n  Error details:")
        for err in total_errors:
            print(f"    ✗ {err}")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
