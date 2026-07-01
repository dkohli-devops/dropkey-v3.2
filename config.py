"""
config.py — DropKey v3.2 Enterprise Configuration Interface

FEATURES:
  [INTERFACE] Main configuration interface and initialization
  [VALIDATION] Configuration validation and startup checks
  [INITIALIZATION] Component initialization with config
  [LOGGING] Logging setup based on configuration
  [AWS] AWS secrets manager integration
  [CONVENIENCE] Helper methods and computed properties

USAGE:
  from config import config, settings
  
  # Access settings
  print(config.settings.DATABASE_URL)
  print(config.is_production)
  
  # Initialize components
  await config.initialize()
  
  # Validate configuration
  config.validate()
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from settings import Settings, get_settings, reload_settings


class ConfigurationManager:
    """
    Main configuration manager for DropKey v3.2.
    
    Handles:
    - Settings loading and validation
    - AWS Secrets Manager integration
    - Logging initialization
    - Component initialization
    - Configuration validation
    """

    def __init__(self):
        """Initialize configuration manager."""
        self._settings: Optional[Settings] = None
        self._initialized = False
        self._logger: Optional[logging.Logger] = None

    # ════════════════════════════════════════════════════════════════════════════
    # SETTINGS ACCESS
    # ════════════════════════════════════════════════════════════════════════════

    @property
    def settings(self) -> Settings:
        """Get settings instance (lazy loaded)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def reload(self) -> Settings:
        """Reload settings from environment."""
        self._settings = reload_settings()
        return self._settings

    # ════════════════════════════════════════════════════════════════════════════
    # ENVIRONMENT CHECKS
    # ════════════════════════════════════════════════════════════════════════════

    @property
    def is_development(self) -> bool:
        """Check if development environment."""
        return self.settings.is_development

    @property
    def is_testing(self) -> bool:
        """Check if testing environment."""
        return self.settings.is_testing

    @property
    def is_production(self) -> bool:
        """Check if production environment."""
        return self.settings.is_production

    # ════════════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ════════════════════════════════════════════════════════════════════════════

    async def initialize(self) -> None:
        """
        Initialize configuration and components.
        
        Sets up:
        - AWS Secrets Manager (if enabled)
        - Logging
        - Validation
        
        Raises:
            ValueError if configuration is invalid
        """
        if self._initialized:
            return

        # Load secrets from AWS Secrets Manager if enabled
        if self.settings.SECRETS_MANAGER_ENABLED:
            await self._load_aws_secrets()

        # Initialize logging
        self._setup_logging()

        # Validate configuration
        self.validate()

        self._initialized = True

        self.logger.info(
            "Configuration initialized",
            extra={
                "environment": self.settings.ENVIRONMENT,
                "version": self.settings.APP_VERSION,
                "debug": self.settings.DEBUG,
            }
        )

    async def _load_aws_secrets(self) -> None:
        """Load secrets from AWS Secrets Manager."""
        try:
            import boto3
            import json

            client = boto3.client(
                "secretsmanager",
                region_name=self.settings.AWS_REGION,
            )

            secret_name = self.settings.SECRETS_MANAGER_SECRET_NAME
            if not secret_name:
                self.logger.warning("Secrets Manager enabled but secret name not set")
                return

            response = client.get_secret_value(SecretId=secret_name)
            secrets = json.loads(response.get("SecretString", "{}"))

            # Merge secrets into settings
            for key, value in secrets.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
                    self.logger.debug(f"Loaded secret: {key}")

            self.logger.info(f"Loaded {len(secrets)} secrets from AWS Secrets Manager")

        except Exception as e:
            self.logger.error(f"Failed to load AWS secrets: {e}", exc_info=True)
            if self.settings.is_production:
                raise

    # ════════════════════════════════════════════════════════════════════════════
    # LOGGING SETUP
    # ════════════════════════════════════════════════════════════════════════════

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        # Create logs directory
        log_dir = Path(self.settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.settings.LOG_LEVEL))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.settings.LOG_LEVEL))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (rotating)
        try:
            from logging.handlers import RotatingFileHandler

            log_file = log_dir / f"{self.settings.APP_NAME.lower()}.log"
            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=self.settings.LOG_FILE_MAX_BYTES,
                backupCount=self.settings.LOG_FILE_BACKUP_COUNT,
            )
            file_handler.setLevel(getattr(logging, self.settings.LOG_LEVEL))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"Failed to setup file logging: {e}")

        # CloudWatch handler (if enabled)
        if self.settings.CLOUDWATCH_ENABLED:
            try:
                import watchtower

                cw_handler = watchtower.CloudWatchLogHandler(
                    log_group=self.settings.CLOUDWATCH_LOG_GROUP,
                    stream_name=f"{self.settings.ENVIRONMENT}",
                    use_queues=True,
                )
                cw_handler.setLevel(logging.INFO)
                root_logger.addHandler(cw_handler)
            except Exception as e:
                root_logger.warning(f"Failed to setup CloudWatch logging: {e}")

        # Sentry handler (if enabled)
        if self.settings.SENTRY_ENABLED:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.logging import LoggingIntegration

                sentry_logging = LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                )

                sentry_sdk.init(
                    dsn=str(self.settings.SENTRY_DSN),
                    integrations=[sentry_logging],
                    traces_sample_rate=self.settings.SENTRY_SAMPLE_RATE,
                    environment=self.settings.ENVIRONMENT,
                )
            except Exception as e:
                root_logger.warning(f"Failed to setup Sentry: {e}")

        self._logger = logging.getLogger(self.settings.APP_NAME)

    @property
    def logger(self) -> logging.Logger:
        """Get configured logger."""
        if self._logger is None:
            self._logger = logging.getLogger(self.settings.APP_NAME)
        return self._logger

    # ════════════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════════════════

    def validate(self) -> List[str]:
        """
        Validate configuration for current environment.
        
        Returns:
            List of validation errors (empty if valid)
            
        Raises:
            ValueError if validation fails in production
        """
        errors = []

        # JWT validation
        if self.settings.JWT_ENABLED:
            if not self.settings.JWT_SECRET_KEY and self.is_production:
                errors.append("JWT_ENABLED=true but JWT_SECRET_KEY not set in production")
            if self.settings.JWT_SECRET_KEY and len(self.settings.JWT_SECRET_KEY) < 32:
                errors.append("JWT_SECRET_KEY must be at least 32 characters")

        # Database validation
        if self.settings.DATABASE_ENABLED:
            if not self.settings.DATABASE_URL and self.is_production:
                errors.append("DATABASE_ENABLED=true but DATABASE_URL not set in production")

        # Redis validation
        if self.settings.REDIS_ENABLED:
            if not self.settings.REDIS_URL and self.is_production:
                errors.append("REDIS_ENABLED=true but REDIS_URL not set in production")

        # Secrets Manager validation
        if self.settings.SECRETS_MANAGER_ENABLED:
            if not self.settings.SECRETS_MANAGER_SECRET_NAME:
                errors.append("SECRETS_MANAGER_ENABLED=true but SECRET_NAME not set")

        # Sentry validation
        if self.settings.SENTRY_ENABLED:
            if not self.settings.SENTRY_DSN and self.is_production:
                errors.append("SENTRY_ENABLED=true but SENTRY_DSN not set in production")

        # CORS validation
        if self.settings.CORS_ENABLED and not self.settings.CORS_ORIGINS:
            errors.append("CORS_ENABLED=true but CORS_ORIGINS is empty")

        # SSL/TLS validation
        if self.settings.ENABLE_HSTS and not self.is_production:
            self.logger.warning("ENABLE_HSTS is true but not in production (HTTPS may not be enforced)")

        # Log errors
        if errors:
            for error in errors:
                self.logger.error(f"Configuration error: {error}")

            if self.is_production:
                raise ValueError(f"Configuration invalid for production:\n" + "\n".join(errors))

        return errors

    # ════════════════════════════════════════════════════════════════════════════
    # CONFIGURATION UTILITIES
    # ════════════════════════════════════════════════════════════════════════════

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert settings to dictionary (sensitive values masked).
        
        Returns:
            Dictionary of configuration
        """
        data = self.settings.dict()

        # Mask sensitive values
        sensitive_keys = [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "TURN_CREDENTIAL",
            "SENTRY_DSN",
        ]

        for key in sensitive_keys:
            if key in data and data[key]:
                data[key] = "***" + data[key][-4:] if len(str(data[key])) > 4 else "***"

        return data

    def log_summary(self) -> None:
        """Log configuration summary."""
        self.logger.info(f"Application: {self.settings.APP_NAME} v{self.settings.APP_VERSION}")
        self.logger.info(f"Environment: {self.settings.ENVIRONMENT}")
        self.logger.info(f"Debug: {self.settings.DEBUG}")
        self.logger.info(f"Server: {self.settings.HOST}:{self.settings.PORT}")

        if self.settings.JWT_ENABLED:
            self.logger.info("JWT: enabled")
        if self.settings.DATABASE_ENABLED:
            self.logger.info("Database: enabled (PostgreSQL)")
        if self.settings.REDIS_ENABLED:
            self.logger.info("Redis: enabled")
        if self.settings.METRICS_ENABLED:
            self.logger.info(f"Metrics: enabled (port {self.settings.METRICS_PORT})")
        if self.settings.SENTRY_ENABLED:
            self.logger.info("Sentry: enabled")
        if self.settings.CLOUDWATCH_ENABLED:
            self.logger.info("CloudWatch: enabled")


# Global configuration instance
_config_instance: Optional[ConfigurationManager] = None


def get_config() -> ConfigurationManager:
    """
    Get or create global configuration manager.
    
    Returns:
        ConfigurationManager instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigurationManager()

    return _config_instance


# Convenience exports
config = get_config()
settings = config.settings

__all__ = ["config", "settings", "get_config", "ConfigurationManager", "Settings", "Config"]

class Config:
    """main.py ke liye shortcut class - Setting ko directly expose krta hai."""
    VERSION     = settings.APP_VERSION
    ENVIRONMENT = settings.ENVIRONMENT
    DEBUG       = settings.DEBUG
    PRODUCTION  = settings.ENVIRONMENT == "production"

    HOST        = settings.HOST
    PORT        = settings.PORT
    WORKERS     = settings.WORKERS

    LOG_LEVEL = settings.LOG_LEVEL

    DATABASE_ENABLED     = settings.DATABASE_ENABLED
    DATABASE_URL         = settings.DATABASE_URL
    DATABASE_POOL_SIZE   = settings.DATABASE_POOL_SIZE
    DATABASE_MAX_OVERFLOW= settings.DATABASE_MAX_OVERFLOW

    REDIS_ENABLED        = settings.REDIS_ENABLED
    REDIS_URL            = settings.REDIS_URL
    REDIS_DEFAULT_TTL    = settings.REDIS_DEFAULT_TTL
    REDIS_MAX_CONNECTIONS= settings.REDIS_MAX_CONNECTIONS

    SESSION_TIMEOUT      = settings.SESSION_TTL_DEFAULT
    MAX_SESSION_PER_USER = settings.MAX_MEMORY_SESSIONS

    CORS_ORIGINS         = settings.CORS_ORIGINS
    ALLOWED_HOSTS        = settings.ALLOWED_HOSTS 