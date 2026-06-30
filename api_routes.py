"""
api_routes.py — DropKey v3.2 FastAPI Routes with Enterprise Security Integration

FEATURES:
  [JWT] JWT authentication endpoints
  [RBAC] Role-based access control on sensitive operations
  [SECURITY] Integrated file screening, rate limiting, key validation
  [AUDIT] All security events logged to audit trail
  [ERROR] Comprehensive error handling with proper HTTP status codes

USAGE:
  app = FastAPI()
  app.include_router(auth_routes)
  app.include_router(transfer_routes)
  app.include_router(health_routes)
"""

import time
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import get_settings
from security import (
    SecurityLayer,
    SecurityLogger,
    SecureHeadersFactory,
    InvalidKeyError,
    FileBlockedError,
    MessageBlockedError,
    RateLimitError,
    JWTError,
    SecurityException,
)
from logger import app_logger, security_logger, log_duration

# ═════════════════════════════════════════════════════════════════════════════
# INITIALIZATION
# ═════════════════════════════════════════════════════════════════════════════

settings = get_settings()
security = SecurityLayer(settings)

# Response headers (applied to all responses)
SECURITY_HEADERS = SecureHeadersFactory.get_security_headers()


# ═════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)


class LoginResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TransferInitiateRequest(BaseModel):
    """Initiate file transfer request."""
    key: str = Field(..., min_length=12, max_length=20)
    files: list[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class TransferInitiateResponse(BaseModel):
    """Transfer initiation response."""
    transfer_id: str
    key: str
    expires_at: str
    ice_servers: list[Dict[str, Any]]


class MessageRequest(BaseModel):
    """WebRTC signaling message."""
    type: str
    data: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    if request.headers.get("x-forwarded-for"):
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def create_error_response(status_code: int, message: str) -> JSONResponse:
    """Create a standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=SECURITY_HEADERS,
    )


def create_success_response(data: Any, status_code: int = 200) -> JSONResponse:
    """Create a standardized success response."""
    return JSONResponse(
        status_code=status_code,
        content=data,
        headers=SECURITY_HEADERS,
    )


# ═════════════════════════════════════════════════════════════════════════════
# ROUTER 1: AUTHENTICATION
# ═════════════════════════════════════════════════════════════════════════════

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """
    User login endpoint.
    
    Validates credentials and returns JWT token.
    """
    client_ip = get_client_ip(req)
    
    try:
        # Rate limit login attempts
        security.check_rate_limit(f"login:{client_ip}", endpoint="/auth/login")
        
        # TODO: Validate credentials against user database
        # This is a placeholder; implement with your auth system
        if request.username == "demo" and request.password == "password123":
            # Create session token
            token = security.create_session_token(
                user_id=request.username,
                roles=["user"]
            )
            
            SecurityLogger.authentication_success(request.username, client_ip)
            
            return LoginResponse(
                access_token=token,
                expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
            )
        else:
            SecurityLogger.authentication_failed(request.username, "Invalid credentials", client_ip)
            raise HTTPException(status_code=401, detail="Invalid credentials")
    
    except RateLimitError:
        SecurityLogger.rate_limited(client_ip, "/auth/login")
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    except SecurityException as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@auth_router.post("/refresh")
async def refresh_token(authorization: str = Header(None), req: Request = None):
    """
    Refresh JWT token.
    
    Requires valid JWT in Authorization header.
    """
    client_ip = get_client_ip(req)
    
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = authorization.replace("Bearer ", "").strip()
        new_token = security.jwt_manager.refresh_token(token)
        
        if not new_token:
            raise HTTPException(status_code=401, detail="Could not refresh token")
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRATION_HOURS * 3600,
        }
    
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e.message))


@auth_router.post("/logout")
async def logout(authorization: str = Header(None)):
    """
    User logout endpoint.
    
    In a real implementation, this would invalidate the JWT token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # TODO: Implement token blacklist or similar mechanism
    return {"status": "success", "message": "Logged out successfully"}


# ═════════════════════════════════════════════════════════════════════════════
# ROUTER 2: FILE TRANSFER
# ═════════════════════════════════════════════════════════════════════════════

transfer_router = APIRouter(prefix="/api/transfer", tags=["Transfers"])


@transfer_router.post("/initiate", response_model=TransferInitiateResponse)
async def initiate_transfer(
    payload: TransferInitiateRequest,
    authorization: Optional[str] = Header(None),
    req: Request = None,
):
    """
    Initiate a file transfer.
    
    Performs comprehensive security checks:
    - Rate limiting
    - Key validation
    - File screening
    - Authorization (optional JWT)
    
    Returns transfer ID and ICE servers for WebRTC setup.
    """
    client_ip = get_client_ip(req)
    request_id = str(uuid.uuid4())
    
    with log_duration("transfer_initiate"):
        try:
            # 1. Rate limit check
            security.check_rate_limit(client_ip, endpoint="/transfer/initiate")
            
            # 2. Validate key format
            security.validate_key(payload.key, ip=client_ip)
            
            # 3. Validate message
            msg_dict = {
                "type": "file-manifest",
                "files": payload.files,
            }
            security.validate_message(msg_dict, ip=client_ip, rid=request_id)
            
            # 4. Get RBAC context (with JWT if provided)
            token = authorization.replace("Bearer ", "") if authorization else None
            rbac_ctx = security.get_rbac_context(token=token)
            
            if rbac_ctx.authenticated:
                SecurityLogger.authentication_success(rbac_ctx.user_id, client_ip)
            
            # 5. Check permission to send files
            if not rbac_ctx.has_permission("transfer.send"):
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions to initiate transfers"
                )
            
            # 6. Screen file manifest
            security.screen_manifest(payload.files, key=payload.key, ip=client_ip)
            
            # 7. Generate transfer ID
            transfer_id = f"xfr_{int(time.time())}_{str(uuid.uuid4())[:8]}"
            
            # 8. Get ICE servers
            ice_servers = security.get_ice_servers()
            
            app_logger.info(
                f"Transfer initiated: {transfer_id}",
                extra={
                    "transfer_id": transfer_id,
                    "key": payload.key[:4] + "****",
                    "files_count": len(payload.files),
                    "user": rbac_ctx.user_id,
                    "ip": client_ip,
                }
            )
            
            # 9. Return success response
            return TransferInitiateResponse(
                transfer_id=transfer_id,
                key=payload.key,
                expires_at=(
                    datetime.utcnow() +
                    timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
                ).isoformat(),
                ice_servers=ice_servers,
            )
        
        except RateLimitError as e:
            SecurityLogger.rate_limited(client_ip, "/transfer/initiate")
            return create_error_response(429, "Too many requests. Please try again later.")
        
        except InvalidKeyError as e:
            SecurityLogger.invalid_key_format(payload.key[:8], client_ip)
            return create_error_response(400, f"Invalid key: {e.message}")
        
        except FileBlockedError as e:
            return create_error_response(400, f"File rejected: {e.message}")
        
        except MessageBlockedError as e:
            return create_error_response(400, f"Invalid message: {e.message}")
        
        except HTTPException:
            raise
        
        except SecurityException as e:
            SecurityLogger.log_exception(e, context={"endpoint": "/transfer/initiate"})
            return create_error_response(400, "Security validation failed")
        
        except Exception as e:
            app_logger.error(f"Unexpected error in transfer initiate: {e}", exc_info=True)
            return create_error_response(500, "Internal server error")


@transfer_router.post("/{transfer_id}/message")
async def send_message(
    transfer_id: str,
    payload: MessageRequest,
    authorization: Optional[str] = Header(None),
    req: Request = None,
):
    """
    Send WebRTC signaling message.
    
    Validates message type and content.
    """
    client_ip = get_client_ip(req)
    
    try:
        # Rate limit WebRTC messages
        security.check_rate_limit(f"msg:{transfer_id}", endpoint="/transfer/message")
        
        # Validate message
        msg_dict = {
            "type": payload.type,
            "data": payload.data or {},
        }
        security.validate_message(msg_dict, ip=client_ip, rid=transfer_id)
        
        # TODO: Process WebRTC message
        
        return {"status": "ok", "transfer_id": transfer_id}
    
    except RateLimitError:
        SecurityLogger.rate_limited(client_ip, "/transfer/message")
        return create_error_response(429, "Too many requests")
    
    except MessageBlockedError as e:
        SecurityLogger.message_blocked(transfer_id, e.msg_type, e.message, client_ip)
        return create_error_response(400, f"Message rejected: {e.message}")
    
    except Exception as e:
        app_logger.error(f"Error sending message: {e}", exc_info=True)
        return create_error_response(500, "Failed to process message")


@transfer_router.get("/{transfer_id}/status")
async def get_transfer_status(transfer_id: str, req: Request = None):
    """
    Get transfer status.
    
    Returns current state of transfer.
    """
    client_ip = get_client_ip(req)
    
    try:
        security.check_rate_limit(client_ip, endpoint="/transfer/status")
        
        # TODO: Fetch transfer status from database/cache
        
        return {
            "transfer_id": transfer_id,
            "status": "active",
            "progress": 50,
            "bytes_transferred": 1024 * 1024 * 512,  # 512 MB
        }
    
    except RateLimitError:
        return create_error_response(429, "Too many requests")
    except Exception as e:
        app_logger.error(f"Error getting transfer status: {e}", exc_info=True)
        return create_error_response(500, "Failed to get transfer status")


# ═════════════════════════════════════════════════════════════════════════════
# ROUTER 3: HEALTH & DIAGNOSTICS
# ═════════════════════════════════════════════════════════════════════════════

health_router = APIRouter(prefix="/api", tags=["Health"])


@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.APP_VERSION,
    )


@health_router.get("/config")
async def get_config_info():
    """
    Get non-sensitive configuration info.
    
    Useful for debugging/monitoring.
    """
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "jwt_enabled": settings.JWT_ENABLED,
        "rate_limiting_enabled": settings.RATE_LIMITING_ENABLED,
        "rate_limit_rpm": settings.RATE_LIMIT_RPM,
        "max_file_size_gb": settings.MAX_FILE_SIZE_BYTES / (1024**3),
        "max_files_per_session": settings.MAX_FILES_PER_SESSION,
    }


# ═════════════════════════════════════════════════════════════════════════════
# EXCEPTION HANDLERS
# ═════════════════════════════════════════════════════════════════════════════

async def security_exception_handler(request: Request, exc: SecurityException):
    """Handle security exceptions."""
    client_ip = get_client_ip(request)
    SecurityLogger.log_exception(exc, context={"path": request.url.path, "ip": client_ip})
    
    return create_error_response(400, f"Security error: {exc.message}")


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return create_error_response(exc.status_code, exc.detail)


# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION FACTORY
# ═════════════════════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
    )
    
    # Include routers
    app.include_router(auth_router)
    app.include_router(transfer_router)
    app.include_router(health_router)
    
    # Exception handlers
    app.add_exception_handler(SecurityException, security_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add security headers to all responses."""
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all requests."""
        client_ip = get_client_ip(request)
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        
        app_logger.info(
            f"{request.method} {request.url.path} {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration,
                "ip": client_ip,
            }
        )
        
        return response
    
    app_logger.info(f"Application created: {settings.APP_NAME} v{settings.APP_VERSION}")
    
    return app


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
