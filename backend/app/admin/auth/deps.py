from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.permissions import role_label
from app.database.session import get_db_session
from app.services.dashboard_auth import (
    DashboardAuthContext,
    DashboardAuthService,
    get_session_token_from_request,
)
from app.services.notification_service import NotificationService

AUTH_LOGIN_URL = "/admin/login"


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
) -> DashboardAuthService:
    return DashboardAuthService(session)


async def get_optional_dashboard_auth(
    request: Request,
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> DashboardAuthContext | None:
    token = get_session_token_from_request(request)
    return await auth_service.resolve_session(token)


async def require_dashboard_auth(
    request: Request,
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> DashboardAuthContext:
    token = get_session_token_from_request(request)
    auth = await auth_service.resolve_session(token)
    if auth is None:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"{AUTH_LOGIN_URL}?next={next_url}"},
        )
    return auth


async def validate_post_csrf(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
) -> DashboardAuthContext:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return auth
    token = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if token is None:
        form = await request.form()
        token = form.get("csrf_token")
    if token != auth.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return auth


async def attach_dashboard_auth(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardAuthContext:
    notifications = await NotificationService(session).get_active_alerts(limit=5)
    request.state.dashboard_auth = auth
    request.state.notifications = notifications
    request.state.current_user = auth.user
    request.state.csrf_token = auth.csrf_token
    return auth


async def require_api_dashboard_auth(
    request: Request,
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> DashboardAuthContext:
    token = get_session_token_from_request(request)
    auth = await auth_service.resolve_session(token)
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return auth


async def get_template_context(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    notifications = await NotificationService(session).get_active_alerts(limit=5)
    return {
        "request": request,
        "current_user": auth.user,
        "csrf_token": auth.csrf_token,
        "user_role_label": role_label(auth.user.role),
        "notifications": notifications,
        "has_critical_alerts": any(item.level == "critical" for item in notifications),
    }
