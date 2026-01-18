"""Celery application configuration for background task processing."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "footnote",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.indexing"],
)

celery_app.conf.update(
    # Serialization (security-focused)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task tracking and reliability
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Worker settings (tuned for I/O-bound tasks)
    worker_prefetch_multiplier=4,
    # Result expiration
    result_expires=86400,  # 24 hours
    # Visibility timeout for long-running OCR/embedding tasks
    broker_transport_options={
        "visibility_timeout": 900,  # 15 min
    },
    # Graceful shutdown configuration
    task_soft_time_limit=840,  # Raise SoftTimeLimitExceeded at 14 min
    task_time_limit=900,  # Hard kill after 15 min
    worker_cancel_long_running_tasks_on_connection_loss=True,
)
