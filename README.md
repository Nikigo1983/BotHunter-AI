# BotHunter AI

Production-ready scaffold for a Telegram bot detection and analysis platform.

## Stack

- Python 3.12
- FastAPI + Swagger
- Aiogram 3
- PostgreSQL + SQLAlchemy + Alembic
- Redis
- Docker & Docker Compose

## Quick start

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

## Endpoints

| URL                        | Description        |
|----------------------------|--------------------|
| `/docs`                    | Swagger UI         |
| `/api/v1/health`           | Health check       |

See [docs/architecture.md](docs/architecture.md) for project structure details.
