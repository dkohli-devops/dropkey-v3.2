# ═════════════════════════════════════════════════════════════════════════════
# logging_config.py — Structured Logging Configuration for DropKey v3.2
#
# Features:
#   • JSON structured logging
#   • Context propagation
#   • Performance tracking
#   • Error tracking with Sentry
#   • Log level configuration
# ═════════════════════════════════════════════════════════════════════════════

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import pythonjsonlogger.jsonlogger


class StructuredLogFormatter(pythonjsonlogger.jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add service info
        log_record['service'] = 'dropkey'
        log_record['version'] = '3.2.0'
        
        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        
        # Add performance metrics
        if hasattr(record, 'duration_ms'):
            log_record['duration_ms'] = record.duration_ms
        
        # Add environment
        log_record['env'] = record.name
        
        # Add hostname
        import socket
        log_record['hostname'] = socket.gethostname()


def get_logging_config(log_level: str = 'INFO') -> Dict[str, Any]:
    """Get comprehensive logging configuration."""
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': (
                    '{levelname} {asctime} {name} {funcName} '
                    '{lineno} {message}'
                ),
                'style': '{',
            },
            'json': {
                '()': StructuredLogFormatter,
                'fmt': '%(timestamp)s %(level)s %(name)s %(message)s',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'filters': {
            'request_id': {
                '()': 'logging_config.RequestIdFilter',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'json',
                'stream': 'ext://sys.stdout',
                'filters': ['request_id'],
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'json',
                'filename': 'logs/dropkey.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'filters': ['request_id'],
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'verbose',
                'filename': 'logs/errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'filters': ['request_id'],
            },
            'sentry': {
                'level': 'ERROR',
                'class': 'sentry_sdk.integrations.logging.EventHandler',
            },
        },
        'loggers': {
            'dropkey': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            'dropkey.api': {
                'level': log_level,
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'dropkey.database': {
                'level': log_level,
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'dropkey.security': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False,
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
        },
        'root': {
            'level': log_level,
            'handlers': ['console', 'file'],
        },
    }


class RequestIdFilter(logging.Filter):
    """Add request ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id from context if available."""
        # This would be populated from FastAPI context
        # For now, it's a placeholder
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        return True


class StructuredLogger:
    """Wrapper for structured logging with context."""

    def __init__(self, name: str):
        """Initialize logger."""
        self.logger = logging.getLogger(name)

    def bind(self, **context: Any) -> 'StructuredLogger':
        """Bind context to logger."""
        # Create a logger adapter with context
        adapter = logging.LoggerAdapter(self.logger, context)
        return self

    def info(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log info message with context."""
        self.logger.info(message, extra=kwargs)

    def warning(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log warning message with context."""
        self.logger.warning(message, extra=kwargs)

    def error(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log error message with context."""
        self.logger.error(message, extra=kwargs)

    def debug(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log debug message with context."""
        self.logger.debug(message, extra=kwargs)

    def critical(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log critical message with context."""
        self.logger.critical(message, extra=kwargs)


def setup_logging(log_level: str = 'INFO') -> None:
    """Setup structured logging."""
    config = get_logging_config(log_level)
    logging.config.dictConfig(config)


# Example usage in FastAPI
# 
# logger = StructuredLogger(__name__)
#
# @app.get('/api/users/{user_id}')
# async def get_user(user_id: str, request: Request):
#     start_time = time.time()
#     
#     logger.info(
#         'Fetching user',
#         user_id=user_id,
#         path=request.url.path,
#     )
#     
#     try:
#         user = await db.fetch_user(user_id)
#         duration_ms = (time.time() - start_time) * 1000
#         
#         logger.info(
#             'User fetched successfully',
#             user_id=user_id,
#             duration_ms=duration_ms,
#         )
#         return user
#     
#     except Exception as e:
#         duration_ms = (time.time() - start_time) * 1000
#         logger.error(
#             'Error fetching user',
#             user_id=user_id,
#             duration_ms=duration_ms,
#             error=str(e),
#             exc_info=True,
#         )
#         raise


if __name__ == '__main__':
    setup_logging('DEBUG')
    logger = StructuredLogger(__name__)
    
    logger.info('Application started', version='3.2.0')
    logger.debug('Debug message', context='example')
    logger.warning('Warning message', severity='medium')
    logger.error('Error message', severity='high')
