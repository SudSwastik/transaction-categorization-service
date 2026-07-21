from celery import Celery
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("txcat", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("llm"),
        Queue("learning"),
        Queue("analytics"),
        Queue("maintenance"),
    ),
    task_routes={
        "app.tasks.statement_tasks.*": {"queue": "default"},
        "app.tasks.categorization_tasks.*": {"queue": "llm"},
        "app.tasks.learning_tasks.*": {"queue": "learning"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,
)
