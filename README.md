# DropKey

> **Enterprise-grade peer-to-peer encrypted file transfer — zero server storage, production-ready architecture.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Session%20Store-DC382D?style=flat&logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy%202.0-4169E1?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Multi--stage%20Build-2496ED?style=flat&logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-AWS%20IaC-7B42BC?style=flat&logo=terraform&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-SAA--C03%20Certified-FF9900?style=flat&logo=amazonaws&logoColor=white)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red?style=flat)

---

## What is DropKey?

DropKey enables two parties to transfer files directly over a **WebRTC data channel** — fully encrypted, browser-to-browser. The backend handles only signaling, session management, and security enforcement. **File content never touches the server.**

Built with enterprise patterns: JWT authentication, Redis-backed sessions, structured observability, and a full Terraform blueprint for AWS.

---

## How It Works

```
Sender ──────────── WebRTC P2P (DTLS/SRTP encrypted) ──────────── Receiver
           ▲                                              ▲
           └──────────── Signaling only ──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │    FastAPI App     │
                    │   (api_routes)    │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────┴─────┐     ┌───────┴───────┐   ┌───────┴───────┐
    │ security  │     │    session    │   │  repository   │
    │ JWT, RBAC │     │ Redis + mem   │   │  SQLAlchemy   │
    │ rate limit│     │  fallback     │   │  data access  │
    └───────────┘     └───────────────┘   └───────────────┘
```

**Transfer flow:**
1. Sender generates a transfer session and receives a transfer code
2. Share the code with the recipient (any channel — email, chat, etc.)
3. Recipient enters the code; WebRTC handshake completes via backend signaling
4. Files stream directly peer-to-peer — server is no longer involved

---

## Security

Security is a first-class concern in DropKey, not an afterthought:

| Layer | Protection |
|---|---|
| Transport | WebRTC DTLS/SRTP end-to-end encryption |
| Auth | JWT tokens with configurable expiry + RBAC |
| File Validation | MIME cross-validation, double-extension attack detection, path traversal defense |
| Input | Strict sanitization on all user-supplied data |
| Rate Limiting | Per-IP and per-session throttling on all endpoints |
| Audit Trail | Structured JSON logs for all sensitive actions |
| Infrastructure | KMS encryption at rest (RDS, ElastiCache) via Terraform |
| Container | Non-root user, minimal base image, read-only filesystem mounts |

> The server never stores, buffers, or inspects transferred file content.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI, Uvicorn (ASGI) |
| Real-time Transfer | WebRTC (aiortc), WebSockets |
| Authentication | JWT (PyJWT), bcrypt / passlib |
| Session Store | Redis (with automatic in-memory fallback) |
| Database | PostgreSQL via SQLAlchemy 2.0 / SQLModel |
| Config & Validation | Pydantic v2 / pydantic-settings |
| Logging | Structured JSON, AWS CloudWatch (watchtower) |
| Monitoring | Prometheus metrics, Grafana dashboards, Sentry error tracking |
| Containerization | Docker (multi-stage build, non-root user, health checks) |
| Infrastructure as Code | Terraform — VPC, ALB, ASG, RDS Multi-AZ, ElastiCache, KMS |
| Orchestration | Kubernetes manifests (`k8s/`) |
| Testing | Pytest — unit, integration, security, performance |

---

## Project Structure

```
dropkey-v3.2/
├── main.py                  # FastAPI app factory + lifespan management
├── api_routes.py            # HTTP + WebSocket endpoints
├── security.py              # JWT, RBAC, file validation, sanitization
├── session_manager.py       # Redis/memory session backend with fallback
├── config.py / settings.py  # Pydantic-based configuration management
├── database.py              # SQLAlchemy engine + async session factory
├── logger.py                # Structured JSON logging interface
│
├── models/                  # SQLAlchemy ORM models
├── repository/              # Data access layer (repository pattern)
│
├── tests/                   # Pytest test suite
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── performance/
│
├── terraform/               # AWS infrastructure definitions
│   ├── vpc.tf
│   ├── alb.tf
│   ├── asg.tf
│   ├── rds.tf
│   ├── elasticache.tf
│   └── kms.tf
│
├── k8s/                     # Kubernetes manifests
├── Dockerfile               # Multi-stage production build
├── docker-compose.yml       # Local development stack
├── docker-compose.prod.yml  # Production compose configuration
├── docker-compose.monitoring.yml  # Prometheus + Grafana stack
└── requirements.txt
```

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required |
| Redis | Any | Optional — falls back to in-memory store |
| PostgreSQL | 14+ | Optional — required only for DB features |
| Docker | 24+ | For containerized setup |

### Local Setup (Python)

```bash
# 1. Clone the repository
git clone https://github.com/dkohli-devops/dropkey-v3.2.git
cd dropkey-v3.2

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Open .env and fill in your values — NEVER commit this file

# 5. Start the application
uvicorn main:app --reload
```

API server: `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

### Docker Setup (Recommended)

```bash
# Full stack (app + Redis + PostgreSQL)
docker compose up --build

# With monitoring (adds Prometheus + Grafana)
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up --build
```

Grafana dashboard: `http://localhost:3000`
Prometheus metrics: `http://localhost:9090`

---

## Environment Variables

All required variables are documented in `.env.example`. Copy to `.env` and populate before running.

```bash
cp .env.example .env
```

Key variables:

```env
SECRET_KEY=           # JWT signing key — generate with: openssl rand -hex 32
DATABASE_URL=         # postgresql+asyncpg://user:pass@host:5432/dbname
REDIS_URL=            # redis://localhost:6379 (omit to use in-memory fallback)
ALLOWED_ORIGINS=      # Comma-separated CORS origins
ENVIRONMENT=          # development | staging | production
```

> `.env` is git-ignored. Never commit secrets.

---

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run full test suite
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test category
pytest tests/security/
pytest tests/integration/
```

---

## Roadmap

- [ ] GitHub Actions CI/CD pipeline (ECR + EC2 deployment)
- [ ] EC2 production deployment — Docker Compose + Nginx + SSL
- [ ] Alembic database migrations
- [ ] AWS Secrets Manager integration *(Terraform groundwork already in place)*
- [ ] One-time transfer codes with automatic session expiry
- [ ] Admin dashboard — active sessions, transfer metrics, audit log viewer

---

## Author

**Deepak Kumar**
IT Infrastructure & DevOps Engineer | AWS Solutions Architect Associate

Building production-grade infrastructure at the intersection of networking, cloud, and security.

[![GitHub](https://img.shields.io/badge/GitHub-dkohli--devops-181717?style=flat&logo=github)](https://github.com/dkohli-devops)

---

## License

All rights reserved © Deepak Kumar. This project is not open-source. Unauthorized copying, distribution, or use is prohibited.
