# BotHunter AI — Architecture

## Overview

BotHunter AI follows clean architecture with clear separation of concerns.

## Layers

```
Presentation   →  api/, bot/
Application    →  services/, schemas/
Domain         →  models/
Infrastructure →  database/, config/, ai/, utils/
```

## Backend structure

| Folder      | Responsibility                          |
|-------------|-----------------------------------------|
| `api/`      | FastAPI routes and HTTP dependencies    |
| `bot/`      | Aiogram handlers and bot lifecycle      |
| `ai/`       | AI/ML integrations                      |
| `services/` | Business logic                          |
| `models/`   | SQLAlchemy ORM entities                 |
| `schemas/`  | Pydantic request/response models        |
| `database/` | DB engine, sessions, base model         |
| `config/`   | Environment-based settings              |
| `utils/`    | Cross-cutting utilities (logging, etc.) |

## Running locally

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Start API: `cd backend && python run.py`
4. Start bot: `cd backend && python -c "from run import run_bot; run_bot()"`

## Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```
