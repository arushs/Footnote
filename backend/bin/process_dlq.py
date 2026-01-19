#!/usr/bin/env python3
"""Dead Letter Queue management CLI.

Usage:
    bin/process_dlq.py                    # List unresolved failed tasks
    bin/process_dlq.py --all              # List all failed tasks
    bin/process_dlq.py --task-id <id>     # Show details for a specific task
    bin/process_dlq.py --resolve <id>     # Mark a task as resolved
    bin/process_dlq.py --retry <id>       # Retry a failed task
    bin/process_dlq.py --stats            # Show failure statistics
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_url() -> str:
    """Get database URL from environment, converting to psycopg2 format."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        # Try loading from .env file
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Convert asyncpg URL to psycopg2 format
    url = re.sub(r"postgresql\+asyncpg://", "postgresql://", url)
    url = re.sub(r"postgres://", "postgresql://", url)
    return url


def list_tasks(conn, show_all: bool = False) -> None:
    """List failed tasks in the DLQ."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if show_all:
            cur.execute("""
                SELECT id, task_id, task_name, exception_type, retries,
                       failed_at, resolved_at, resolution_notes
                FROM failed_tasks
                ORDER BY failed_at DESC
                LIMIT 50
            """)
        else:
            cur.execute("""
                SELECT id, task_id, task_name, exception_type, retries, failed_at
                FROM failed_tasks
                WHERE resolved_at IS NULL
                ORDER BY failed_at DESC
                LIMIT 50
            """)

        rows = cur.fetchall()

        if not rows:
            print("No failed tasks found" if show_all else "No unresolved failed tasks")
            return

        print(f"\n{'ID':<36} {'Task Name':<30} {'Exception':<25} {'Retries':<8} {'Failed At'}")
        print("-" * 140)

        for row in rows:
            task_id = str(row["id"])[:8] + "..."
            task_name = (
                (row["task_name"][:27] + "...") if len(row["task_name"]) > 30 else row["task_name"]
            )
            exc_type = (
                (row["exception_type"][:22] + "...")
                if row["exception_type"] and len(row["exception_type"]) > 25
                else (row["exception_type"] or "N/A")
            )
            failed_at = row["failed_at"].strftime("%Y-%m-%d %H:%M") if row["failed_at"] else "N/A"
            status = " [RESOLVED]" if row.get("resolved_at") else ""

            print(
                f"{task_id:<36} {task_name:<30} {exc_type:<25} {row['retries']:<8} {failed_at}{status}"
            )

        print(f"\nTotal: {len(rows)} task(s)")


def show_task_details(conn, task_id: str) -> None:
    """Show detailed information about a specific failed task."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM failed_tasks
            WHERE id::text LIKE %s OR task_id LIKE %s
            LIMIT 1
        """,
            (f"{task_id}%", f"{task_id}%"),
        )

        row = cur.fetchone()

        if not row:
            print(f"Task not found: {task_id}")
            return

        print("\n" + "=" * 80)
        print("FAILED TASK DETAILS")
        print("=" * 80)
        print(f"ID:              {row['id']}")
        print(f"Celery Task ID:  {row['task_id']}")
        print(f"Task Name:       {row['task_name']}")
        print(f"Retries:         {row['retries']}")
        print(f"Failed At:       {row['failed_at']}")
        print(f"Resolved At:     {row['resolved_at'] or 'Not resolved'}")

        if row["resolution_notes"]:
            print(f"Resolution:      {row['resolution_notes']}")

        print("\n--- Arguments ---")
        print(f"Args:   {row['args']}")
        print(f"Kwargs: {row['kwargs']}")

        print("\n--- Exception ---")
        print(f"Type:    {row['exception_type']}")
        print(f"Message: {row['exception_message']}")

        if row["traceback"]:
            print("\n--- Traceback ---")
            print(row["traceback"])


def resolve_task(conn, task_id: str, notes: str = None) -> None:
    """Mark a task as resolved."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE failed_tasks
            SET resolved_at = NOW(),
                resolution_notes = %s
            WHERE (id::text LIKE %s OR task_id LIKE %s) AND resolved_at IS NULL
            RETURNING id
        """,
            (notes or "Manually resolved", f"{task_id}%", f"{task_id}%"),
        )

        result = cur.fetchone()
        conn.commit()

        if result:
            print(f"Task {result[0]} marked as resolved")
        else:
            print(f"Task not found or already resolved: {task_id}")


def retry_task(conn, task_id: str) -> None:
    """Retry a failed task by re-queuing it to Celery."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT task_name, args, kwargs
            FROM failed_tasks
            WHERE id::text LIKE %s OR task_id LIKE %s
            LIMIT 1
        """,
            (f"{task_id}%", f"{task_id}%"),
        )

        row = cur.fetchone()

        if not row:
            print(f"Task not found: {task_id}")
            return

        # Import Celery app to dispatch task
        try:
            from app.celery_app import celery_app

            task = celery_app.tasks.get(row["task_name"])
            if not task:
                print(f"Task {row['task_name']} not found in Celery app")
                return

            args = row["args"] or []
            kwargs = row["kwargs"] or {}

            result = task.delay(*args, **kwargs)
            print(f"Task requeued with new ID: {result.id}")

            # Mark original as resolved
            cur.execute(
                """
                UPDATE failed_tasks
                SET resolved_at = NOW(),
                    resolution_notes = %s
                WHERE id::text LIKE %s OR task_id LIKE %s
            """,
                (f"Retried as {result.id}", f"{task_id}%", f"{task_id}%"),
            )
            conn.commit()

        except ImportError as e:
            print(f"Could not import Celery app: {e}")
            print("Make sure you're running from the backend directory")


def show_stats(conn) -> None:
    """Show failure statistics."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Overall counts
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE resolved_at IS NULL) as unresolved,
                COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) as resolved
            FROM failed_tasks
        """)
        totals = cur.fetchone()

        print("\n" + "=" * 50)
        print("DLQ STATISTICS")
        print("=" * 50)
        print(f"Total Failed Tasks:    {totals['total']}")
        print(f"Unresolved:            {totals['unresolved']}")
        print(f"Resolved:              {totals['resolved']}")

        # By task name
        cur.execute("""
            SELECT task_name, COUNT(*) as count
            FROM failed_tasks
            WHERE resolved_at IS NULL
            GROUP BY task_name
            ORDER BY count DESC
            LIMIT 10
        """)
        by_task = cur.fetchall()

        if by_task:
            print("\n--- Unresolved by Task Name ---")
            for row in by_task:
                print(f"  {row['task_name']}: {row['count']}")

        # By exception type
        cur.execute("""
            SELECT exception_type, COUNT(*) as count
            FROM failed_tasks
            WHERE resolved_at IS NULL AND exception_type IS NOT NULL
            GROUP BY exception_type
            ORDER BY count DESC
            LIMIT 10
        """)
        by_exc = cur.fetchall()

        if by_exc:
            print("\n--- Unresolved by Exception Type ---")
            for row in by_exc:
                print(f"  {row['exception_type']}: {row['count']}")

        # Recent failures (last 24h)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM failed_tasks
            WHERE failed_at > NOW() - INTERVAL '24 hours'
        """)
        recent = cur.fetchone()
        print(f"\nFailures (last 24h):   {recent['count']}")


def main():
    parser = argparse.ArgumentParser(description="Dead Letter Queue management")
    parser.add_argument("--all", action="store_true", help="Show all tasks (including resolved)")
    parser.add_argument("--task-id", type=str, help="Show details for a specific task")
    parser.add_argument("--resolve", type=str, metavar="TASK_ID", help="Mark a task as resolved")
    parser.add_argument("--notes", type=str, help="Resolution notes (used with --resolve)")
    parser.add_argument("--retry", type=str, metavar="TASK_ID", help="Retry a failed task")
    parser.add_argument("--stats", action="store_true", help="Show failure statistics")

    args = parser.parse_args()

    url = get_database_url()

    try:
        conn = psycopg2.connect(url)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    try:
        if args.task_id:
            show_task_details(conn, args.task_id)
        elif args.resolve:
            resolve_task(conn, args.resolve, args.notes)
        elif args.retry:
            retry_task(conn, args.retry)
        elif args.stats:
            show_stats(conn)
        else:
            list_tasks(conn, show_all=args.all)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
