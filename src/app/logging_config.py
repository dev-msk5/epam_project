import contextvars
import logging
import logging.config
import os
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Logging defaults to a "logs" directory in the current working directory
LOG_DIR = os.getenv("LOG_DIR", "logs")

os.makedirs(LOG_DIR, exist_ok=True)

# Context variable to store trace IDs across async task boundaries
request_id_context = contextvars.ContextVar("request_id", default="-")


class CorrelationFilter(logging.Filter):
    """Filter that pulls the current trace ID from context
    and appends it to log records"""

    def filter(self, record):
        record.request_id = request_id_context.get()
        return True


# Logging config dictionary
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation": {
            # custom filter to inject request_id into log records
            "()": CorrelationFilter,
        }
    },
    "formatters": {
        "detailed": {
            # Injects the [req_id] placeholder into every log entry
            "format": "%(asctime)s [%(levelname)s] [id: %(request_id)s] %(name)s: %(message)s",  # noqa: E501
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "stderr": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "stream": "ext://sys.stderr",
            "filters": ["correlation"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed",
            "filename": os.path.join(LOG_DIR, "app.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 3,
            "encoding": "utf-8",
            "filters": ["correlation"],
        },
    },
    "loggers": {
        "app_logger": {
            "handlers": ["stderr", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Captures database session statements if SQL logging is turned on
        "sqlalchemy.engine": {
            "handlers": ["stderr", "file"],
            "level": "WARNING",  # Set to INFO to print all SQL queries in local dev
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["stderr", "file"],
        "level": "INFO",
    },
}

# dictionary configuration for logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger("app_logger")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that tracks request processing times and
    manages request-id lifecycles"""

    async def dispatch(self, request: Request, call_next):
        # Read incoming request ID or generate a new short tracker
        req_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:8]}")

        # Bind the request ID to the current context
        token = request_id_context.set(req_id)
        start_time = time.time()

        logger.info(f"Incoming: {request.method} {request.url.path}")

        try:
            # request passes through to actual app route
            response: Response = await call_next(request)
            duration = round(time.time() - start_time, 4)
            logger.info(
                f"Completed: {request.method} {request.url.path} | Status: {response.status_code} in {duration}s"  # noqa: E501
            )

            # The application has responded, now modify the response
            # Send the request ID back in response headers for client-side correlation
            response.headers["X-Request-ID"] = req_id

            # modified response back to the client
            return response

        except Exception as e:
            duration = round(time.time() - start_time, 4)
            logger.error(
                f"Failed: {request.method} {request.url.path} | Crash after {duration}s | Error: {str(e)}",  # noqa: E501
                exc_info=True,
            )
            raise e

        finally:
            # Clean up context to prevent trace leaking between worker tasks
            request_id_context.reset(token)
