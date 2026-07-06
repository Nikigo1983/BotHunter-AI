import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, get_request_redis, require_dashboard_auth, validate_post_csrf
from app.repositories.deps import get_dashboard_session_repository
from app.services.dashboard_auth import DashboardAuthContext
from app.services.dashboard_workspace_cache import DashboardWorkspaceCache
from app.database.session import get_db_session

tenant_router = APIRouter(
    prefix="/admin",
    tags=["admin-tenant"],
    dependencies=[Depends(attach_dashboard_auth)],
)


@tenant_router.post("/switch-workspace", dependencies=[Depends(validate_post_csrf)])
async def switch_workspace(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    organization_id: uuid.UUID = Form(...),
    workspace_id: uuid.UUID = Form(...),
) -> RedirectResponse:
    session_repo = get_dashboard_session_repository(session)
    db_session = auth.session
    db_session.active_organization_id = organization_id
    db_session.active_workspace_id = workspace_id
    await session_repo.update(db_session)
    await DashboardWorkspaceCache.invalidate(get_request_redis(request), auth.user.id)
    return RedirectResponse("/admin", status_code=303)
