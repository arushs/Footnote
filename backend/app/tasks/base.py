"""Base Celery task class with Dead Letter Queue support."""

import logging
from datetime import datetime

from celery import Task

from app.db import celery_session_scope
from app.models.failed_task import FailedTask

logger = logging.getLogger(__name__)


class DLQTask(Task):
    """Base task class that captures failures to a Dead Letter Queue.

    When a task exhausts all retries, this captures the failure details
    to the failed_tasks table for debugging and manual retry.

    Usage:
        @celery_app.task(base=DLQTask, bind=True, max_retries=5)
        def my_task(self, arg1, arg2):
            ...
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Capture failed task to DLQ after all retries exhausted."""
        logger.error(
            f"Task {self.name} ({task_id}) failed permanently after {self.request.retries} retries",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "retries": self.request.retries,
            },
        )

        try:
            failed_task = FailedTask(
                task_id=task_id,
                task_name=self.name,
                args=list(args) if args else None,
                kwargs=dict(kwargs) if kwargs else None,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                traceback=str(einfo.traceback) if einfo else None,
                retries=self.request.retries,
                failed_at=datetime.utcnow(),
            )

            with celery_session_scope() as session:
                # Check if task already exists (avoid duplicates on retry storms)
                existing = session.query(FailedTask).filter_by(task_id=task_id).first()
                if existing:
                    # Update existing record
                    existing.exception_type = failed_task.exception_type
                    existing.exception_message = failed_task.exception_message
                    existing.traceback = failed_task.traceback
                    existing.retries = failed_task.retries
                    existing.failed_at = failed_task.failed_at
                    logger.info(f"Updated existing DLQ entry for task {task_id}")
                else:
                    session.add(failed_task)
                    logger.info(f"Added task {task_id} to DLQ")

        except Exception as e:
            # Don't let DLQ failures affect the main task flow
            logger.error(f"Failed to save task {task_id} to DLQ: {e}")

        super().on_failure(exc, task_id, args, kwargs, einfo)
