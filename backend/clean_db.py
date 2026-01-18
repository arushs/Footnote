#!/usr/bin/env python3
"""
Database cleanup script for local testing.

Cleans folders, files, chunks, conversations, messages, and indexing jobs.
By default, preserves users and sessions for authentication continuity.

Usage:
    uv run python clean_db.py           # Clean data, preserve auth
    uv run python clean_db.py --all     # Clean everything including auth
    uv run python clean_db.py --dry-run # Show what would be deleted
"""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def get_table_counts(conn) -> dict[str, int]:
    """Get row counts for all tables."""
    tables = [
        "users",
        "sessions",
        "folders",
        "files",
        "chunks",
        "conversations",
        "messages",
        "indexing_jobs",
    ]
    counts = {}
    for table in tables:
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = result.scalar() or 0
    return counts


async def clean_database(preserve_auth: bool = True, dry_run: bool = False):
    """
    Clean the database tables.

    Args:
        preserve_auth: If True, keep users and sessions tables intact
        dry_run: If True, only show what would be deleted without actually deleting
    """
    database_url = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/footnote"
    )
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        # Get current counts
        print("\nCurrent table counts:")
        print("-" * 40)
        counts = await get_table_counts(conn)
        for table, count in counts.items():
            print(f"  {table}: {count} rows")

        if dry_run:
            print("\n[DRY RUN] Would delete:")
        else:
            print("\nCleaning tables...")

        # Order matters due to foreign key constraints
        # Delete in order: messages -> conversations -> indexing_jobs -> chunks -> files -> folders
        tables_to_clean = [
            ("messages", "conversations, folders"),
            ("conversations", "folders"),
            ("indexing_jobs", "folders, files"),
            ("chunks", "files, folders"),
            ("files", "folders"),
            ("folders", "users"),
        ]

        if not preserve_auth:
            tables_to_clean.extend(
                [
                    ("sessions", "users"),
                    ("users", None),
                ]
            )

        for table, _ in tables_to_clean:
            count = counts.get(table, 0)
            if dry_run:
                print(f"  {table}: {count} rows")
            else:
                await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                print(f"  Cleaned {table} ({count} rows)")

        if not dry_run:
            # Verify cleanup
            print("\nVerifying cleanup...")
            new_counts = await get_table_counts(conn)
            all_clean = True
            for table, count in new_counts.items():
                if preserve_auth and table in ("users", "sessions"):
                    continue
                if count > 0:
                    print(f"  WARNING: {table} still has {count} rows")
                    all_clean = False

            if all_clean:
                print("  All targeted tables are empty.")

            print("\nFinal table counts:")
            print("-" * 40)
            for table, count in new_counts.items():
                print(f"  {table}: {count} rows")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Clean database tables for local testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python clean_db.py           # Clean data, preserve users/sessions
  uv run python clean_db.py --all     # Clean everything
  uv run python clean_db.py --dry-run # Preview what would be deleted
        """,
    )
    parser.add_argument("--all", action="store_true", help="Also clean users and sessions tables")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    preserve_auth = not args.all

    if not args.dry_run:
        if args.all:
            msg = "This will DELETE ALL DATA including users and sessions."
        else:
            msg = "This will delete all folders, files, chunks, conversations, and messages."

        print(f"\nWARNING: {msg}")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return

    asyncio.run(clean_database(preserve_auth=preserve_auth, dry_run=args.dry_run))
    print("\nDone!")


if __name__ == "__main__":
    main()
