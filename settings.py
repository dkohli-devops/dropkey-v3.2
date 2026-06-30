"""
settings.py — DropKey v3.2 Enterprise Configuration (Pydantic BaseSettings)

FEATURES:
  [VALIDATION] Pydantic models for configuration validation
  [TYPED] Full type hints and validation
  [ENVIRONMENT] Environment variable support with prefixes
  [SECRETS] Secure secret handling
  [PROFILES] Environment profiles (dev, test, prod)
  [DEFAULTS] Sensible defaults for all settings
  [DOCUMENTATION] Comprehensive field documentation

USAGE:
  from settings import Settings
  settings = Settings()  # Automatically loads from environment
"""

from typing import List, Optional
#from pydantic import BaseSettings, Field, validator, AnyHttpUrl, PostgresDsn
import os
from pydantic import Field, AnyHttpUrl, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Enterprise configuration for DropKey v3.2.
    
    Configuration is loaded from:
    1. Environment variables (DROPKEY_* prefix)
    2. .env file (if present)
    3. Default values
    
    Use `Settings.schema()` to see all available configuration options.
    """

    # ════════════════════════════════════════════════════════════════════════════
    # ENVIRONMENT & DEPLOYMENT
    # ════════════════════════════════════════════════════════════════════════════

    ENVIRONMENT: str = Field(
        "development",
        description="Environment profile: development, testing, production",
        regex="^(development|testing|production)$"
    )
    """
    Environment profile controlling default behaviors:
    - development: Debug enabled, verbose logging
    - testing: Memory stores, fast cleanup
    - production: Optimized performance, strict validation
    """

    DEBUG: bool = Field(False, description="Enable debug mode")
    """Enable detailed error messages and logging"""

    APP_NAME: str = Field("DropKey", description="Application name")
    APP_VERSION: str = Field("3.2-enterprise", description="Application version")
    APP_DESCRIPTION: str = Field(
        "Enterprise P2P file transfer with WebRTC",
        description="Application description"
    )

    # ════════════════════════════════════════════════════════════════════════════
    # SERVER CONFIGURATION
    # ════════════════════════════════════════════════════════════════════════════

    HOST: str = Field("0.0.0.0", description="Server bind address")
    PORT: int = Field(8000, ge=1, le=65535, description="Server port")
    WORKERS: int = Field(4, ge=1, le=16, description="Number of worker processes")

    # ════════════════════════════════════════════════════════════════════════════
    # LOGGING CONFIGURATION
    # ════════════════════════════════════════════════════════════════════════════

    LOG_LEVEL: str = Field(
        "INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )

    LOG_DIR: str = Field("./logs", description="Directory for log files")
    LOG_FILE_MAX_BYTES: int = Field(
        50 * 1024 * 1024,
        ge=1024,
        description="Maximum log file size in bytes"
    )
    LOG_FILE_BACKUP_COUNT: int = Field(
        5, ge=1, le=20, description="Number of log file backups to keep"
    )

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — TRANSFER SESSION
    # ════════════════════════════════════════════════════════════════════════════

    KEY_LENGTH: int = Field(
        16,
        ge=12,
        le=32,
        description="Length of transfer key (12-32 characters)"
    )
    """Transfer key length for share URLs"""

    MAX_FILE_SIZE_BYTES: int = Field(
        5 * 1024 * 1024 * 1024,
        ge=1024 * 1024,
        description="Maximum file size (5GB default)"
    )
    """Maximum individual file size in bytes"""

    MAX_FILES_PER_SESSION: int = Field(
        100, ge=1, le=1000, description="Maximum files per session"
    )
    """Maximum number of files per transfer session"""

    BLOCKED_EXTENSIONS: List[str] = Field(
        default_factory=lambda: [
            ".exe", ".dll", ".bat", ".sh", ".com", ".msi", ".scr",
            ".ps1", ".psc1", ".psc2", ".msh", ".msh1", ".msh2",
            ".cmd", ".jar", ".zip", ".rar", ".7z",
        ],
        description="Blocked file extensions"
    )
    """List of blocked file extensions"""

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — SESSION MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════

    SESSION_TTL_DEFAULT: int = Field(
        3600, ge=60, description="Default session TTL in seconds (1 hour)"
    )
    """Default session time-to-live"""

    SESSION_TTL_TRANSFER: int = Field(
        7200, ge=300, description="Extended TTL during active transfer (2 hours)"
    )
    """Extended TTL for active transfers"""

    SESSION_CLEANUP_INTERVAL: int = Field(
        30, ge=10, description="Session cleanup interval in seconds"
    )
    """How often to cleanup expired sessions"""

    MAX_MEMORY_SESSIONS: int = Field(
        10000, ge=100, description="Max in-memory sessions"
    )
    """Hard cap on in-memory sessions (memory store)"""

    ONE_TIME_KEY_ENABLED: bool = Field(
        True, description="Enforce one-time key usage"
    )
    """Enforce one-time key semantics (burn-after-reading)"""

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — JWT & AUTHENTICATION
    # ════════════════════════════════════════════════════════════════════════════

    JWT_ENABLED: bool = Field(True, description="Enable JWT authentication")
    """Enable JWT-based authentication"""

    JWT_SECRET_KEY: Optional[str] = Field(
        None,
        description="JWT secret key (min 32 chars, stored in secrets manager)"
    )
    """Secret key for JWT signing - NEVER hardcode in production"""

    JWT_ALGORITHM: str = Field(
        "HS256",
        description="JWT signing algorithm: HS256, RS256, ES256",
        regex="^(HS256|HS512|RS256|ES256)$"
    )
    """JWT signing algorithm"""

    JWT_EXPIRATION_HOURS: int = Field(
        24, ge=1, le=720, description="JWT token expiration in hours"
    )
    """JWT token expiration time"""

    JWT_REFRESH_EXPIRATION_HOURS: int = Field(
        168, ge=24, le=2160, description="JWT refresh token expiration (7 days)"
    )
    """JWT refresh token expiration time"""

    JWT_REFRESH_ENABLED: bool = Field(
        True, description="Allow token refresh"
    )
    """Enable token refresh mechanism"""

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — RATE LIMITING
    # ════════════════════════════════════════════════════════════════════════════

    RATE_LIMITING_ENABLED: bool = Field(
        True, description="Enable rate limiting"
    )
    """Enable rate limiting"""

    RATE_LIMIT_RPM: int = Field(
        60, ge=10, description="Rate limit: requests per minute"
    )
    """Requests per minute limit"""

    RATE_LIMIT_STORAGE: str = Field(
        "memory",
        description="Rate limit storage: memory, redis",
        regex="^(memory|redis)$"
    )
    """Where to store rate limit counters"""

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — CORS
    # ════════════════════════════════════════════════════════════════════════════

    CORS_ENABLED: bool = Field(True, description="Enable CORS")
    """Enable Cross-Origin Resource Sharing"""

    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8000",
        ],
        description="CORS allowed origins"
    )
    """List of allowed CORS origins"""

    CORS_CREDENTIALS: bool = Field(
        True, description="Allow credentials in CORS"
    )
    """Allow cookies and credentials in CORS requests"""

    CORS_METHODS: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods"
    )
    """Allowed HTTP methods"""

    CORS_HEADERS: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS headers"
    )
    """Allowed CORS headers"""

    # ════════════════════════════════════════════════════════════════════════════
    # SECURITY — HTTPS & HEADERS
    # ════════════════════════════════════════════════════════════════════════════

    ENABLE_HSTS: bool = Field(
        True, description="Enable HTTP Strict-Transport-Security"
    )
    """Enable HSTS header (HTTPS only)"""

    HSTS_MAX_AGE: int = Field(
        31536000, ge=0, description="HSTS max age in seconds (1 year)"
    )
    """HSTS max age"""

    AUDIT_LOG_ENABLED: bool = Field(
        True, description="Enable audit logging"
    )
    """Enable structured audit logging"""

    # ════════════════════════════════════════════════════════════════════════════
    # DATABASE — POSTGRESQL (FUTURE)
    # ════════════════════════════════════════════════════════════════════════════

    DATABASE_ENABLED: bool = Field(
        False, description="Enable database (PostgreSQL)"
    )
    """Enable database backend"""

    DATABASE_URL: Optional[PostgresDsn] = Field(
        None,
        description="PostgreSQL connection URL"
    )
    """PostgreSQL connection string"""

    DATABASE_POOL_SIZE: int = Field(
        10, ge=1, le=100, description="Database connection pool size"
    )
    """Database connection pool size"""

    DATABASE_POOL_RECYCLE: int = Field(
        3600, ge=60, description="Connection pool recycle time (seconds)"
    )
    """Connection pool recycle time"""

    DATABASE_ECHO: bool = Field(
        False, description="Echo SQL queries (development only)"
    )
    """Echo SQL queries for debugging"""

    # ════════════════════════════════════════════════════════════════════════════
    # CACHE — REDIS
    # ════════════════════════════════════════════════════════════════════════════

    REDIS_ENABLED: bool = Field(False, description="Enable Redis")
    """Enable Redis caching/session store"""

    REDIS_URL: Optional[str] = Field(
        None,
        description="Redis connection URL"
    )
    """Redis connection string (redis://host:port/db)"""

    REDIS_PREFIX: str = Field(
        "dropkey:", description="Redis key prefix"
    )
    """Prefix for all Redis keys"""

    REDIS_POOL_SIZE: int = Field(
        10, ge=1, le=100, description="Redis connection pool size"
    )
    """Redis connection pool size"""

    REDIS_CONNECTION_TIMEOUT: int = Field(
        5, ge=1, le=30, description="Redis connection timeout (seconds)"
    )
    """Redis connection timeout"""

    REDIS_SOCKET_TIMEOUT: int = Field(
        5, ge=1, le=30, description="Redis socket timeout (seconds)"
    )
    """Redis socket/read timeout"""

    REDIS_MAX_RETRIES: int = Field(
        3, ge=1, le=10, description="Redis max retry attempts"
    )
    """Maximum retry attempts for transient failures"""

    REDIS_RETRY_BACKOFF_FACTOR: float = Field(
        0.1, ge=0.01, le=1.0, description="Redis retry backoff factor"
    )
    """Exponential backoff factor for retries"""

    # ════════════════════════════════════════════════════════════════════════════
    # WEBRTC CONFIGURATION
    # ════════════════════════════════════════════════════════════════════════════

    STUN_URLS: List[str] = Field(
        default_factory=lambda: [
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302",
        ],
        description="STUN server URLs"
    )
    """STUN server URLs for NAT traversal"""

    TURN_URLS: List[str] = Field(
        default_factory=list,
        description="TURN server URLs"
    )
    """TURN server URLs for relay"""

    TURN_USERNAME: Optional[str] = Field(
        None, description="TURN server username"
    )
    """TURN server authentication username"""

    TURN_CREDENTIAL: Optional[str] = Field(
        None, description="TURN server password"
    )
    """TURN server authentication password"""

    # ════════════════════════════════════════════════════════════════════════════
    # MONITORING & OBSERVABILITY
    # ════════════════════════════════════════════════════════════════════════════

    METRICS_ENABLED: bool = Field(
        True, description="Enable Prometheus metrics"
    )
    """Enable metrics collection"""

    METRICS_PORT: int = Field(
        9090, ge=1024, le=65535, description="Metrics server port"
    )
    """Port for metrics endpoint"""

    HEALTH_CHECK_ENABLED: bool = Field(
        True, description="Enable health checks"
    )
    """Enable health check endpoints"""

    # ════════════════════════════════════════════════════════════════════════════
    # ERROR TRACKING
    # ════════════════════════════════════════════════════════════════════════════

    SENTRY_ENABLED: bool = Field(
        False, description="Enable Sentry error tracking"
    )
    """Enable Sentry integration"""

    SENTRY_DSN: Optional[AnyHttpUrl] = Field(
        None, description="Sentry DSN"
    )
    """Sentry Data Source Name for error tracking"""

    SENTRY_SAMPLE_RATE: float = Field(
        1.0, ge=0.0, le=1.0, description="Sentry sample rate"
    )
    """Sentry transaction sample rate"""

    # ════════════════════════════════════════════════════════════════════════════
    # AWS INTEGRATION
    # ════════════════════════════════════════════════════════════════════════════

    AWS_ENABLED: bool = Field(False, description="Enable AWS integration")
    """Enable AWS services integration"""

    AWS_REGION: str = Field(
        "us-east-1", description="AWS region"
    )
    """AWS region for services"""

    AWS_PROFILE: Optional[str] = Field(
        None, description="AWS profile name"
    )
    """AWS profile for credentials"""

    CLOUDWATCH_ENABLED: bool = Field(
        False, description="Send logs to CloudWatch"
    )
    """Enable CloudWatch logging"""

    CLOUDWATCH_LOG_GROUP: str = Field(
        "/dropkey/application", description="CloudWatch log group"
    )
    """CloudWatch log group name"""

    SECRETS_MANAGER_ENABLED: bool = Field(
        False, description="Load secrets from Secrets Manager"
    )
    """Load secrets from AWS Secrets Manager"""

    SECRETS_MANAGER_SECRET_NAME: Optional[str] = Field(
        None, description="Secrets Manager secret name"
    )
    """AWS Secrets Manager secret name"""

    # ════════════════════════════════════════════════════════════════════════════
    # DOCKER & DEPLOYMENT
    # ════════════════════════════════════════════════════════════════════════════

    DOCKER_ENABLED: bool = Field(
        False, description="Running in Docker"
    )
    """Indicate if running in Docker container"""

    # ════════════════════════════════════════════════════════════════════════════
    # VALIDATORS
    # ════════════════════════════════════════════════════════════════════════════

    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret(cls, v, values):
        """Validate JWT secret key if JWT is enabled."""
        jwt_enabled = values.get("JWT_ENABLED", True)
        if jwt_enabled and v:
            if len(v) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @validator("SESSION_TTL_TRANSFER")
    def validate_session_ttl(cls, v, values):
        """Validate transfer TTL >= default TTL."""
        default_ttl = values.get("SESSION_TTL_DEFAULT", 3600)
        if v < default_ttl:
            raise ValueError("SESSION_TTL_TRANSFER must be >= SESSION_TTL_DEFAULT")
        return v

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [url.strip() for url in v.split(",")]
        return v

    @validator("BLOCKED_EXTENSIONS", pre=True)
    def parse_blocked_extensions(cls, v):
        """Parse blocked extensions from comma-separated string."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @validator("DEBUG")
    def set_debug_from_environment(cls, v, values):
        """Set DEBUG based on environment."""
        if not v:
            env = values.get("ENVIRONMENT", "development")
            return env in ("development", "testing")
        return v

    @validator("LOG_LEVEL")
    def validate_log_level_from_environment(cls, v, values):
        """Adjust log level based on environment."""
        if not v or v == "INFO":
            env = values.get("ENVIRONMENT", "development")
            if env == "development":
                return "DEBUG"
            elif env == "testing":
                return "WARNING"
        return v

    # ════════════════════════════════════════════════════════════════════════════
    # COMPUTED PROPERTIES
    # ════════════════════════════════════════════════════════════════════════════

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.ENVIRONMENT == "testing"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def database_configured(self) -> bool:
        """Check if database is properly configured."""
        return self.DATABASE_ENABLED and self.DATABASE_URL is not None

    @property
    def redis_configured(self) -> bool:
        """Check if Redis is properly configured."""
        return self.REDIS_ENABLED and self.REDIS_URL is not None

    @property
    def jwt_configured(self) -> bool:
        """Check if JWT is properly configured."""
        return self.JWT_ENABLED and (self.JWT_SECRET_KEY is not None or self.is_development)

    # ════════════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ════════════════════════════════════════════════════════════════════════════

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_prefix = "DROPKEY_"
        case_sensitive = True
        arbitrary_types_allowed = True

        # Custom settings
        extra = "allow"  # Allow extra fields


# Singleton instance (lazy loaded)
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create Settings instance (singleton pattern).
    
    Returns:
        Settings instance with environment variables loaded
        
    Raises:
        ValidationError if configuration is invalid
    """
    global _settings_instance
    
    if _settings_instance is None:
        _settings_instance = Settings()
    
    return _settings_instance


def reload_settings() -> Settings:
    """
    Reload settings from environment (useful for testing).
    
    Returns:
        New Settings instance
    """
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance
