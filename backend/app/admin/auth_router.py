from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.router import ADMIN_TEMPLATES
from app.database.session import get_db_session
from app.services.dashboard_auth import DashboardAuthService, get_session_token_from_request

auth_router = APIRouter(prefix="/admin", tags=["admin-auth"])


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
) -> DashboardAuthService:
    return DashboardAuthService(session)


@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "/admin",
    error: str | None = None,
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> HTMLResponse:
    token = get_session_token_from_request(request)
    if token and await auth_service.resolve_session(token):
        return RedirectResponse(url=next or "/admin", status_code=303)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/login.html",
        {"next_url": next, "error": error},
    )


@auth_router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> RedirectResponse:
    user = await auth_service.authenticate(email, password)
    if user is None:
        return RedirectResponse(
            url=f"/admin/login?error=invalid&next={next}",
            status_code=303,
        )
    token, _session = await auth_service.create_session(
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    response = RedirectResponse(url=next or "/admin", status_code=303)
    auth_service.set_session_cookie(response, token)
    return response


@auth_router.get("/logout")
async def logout(
    request: Request,
    auth_service: DashboardAuthService = Depends(get_auth_service),
) -> RedirectResponse:
    token = get_session_token_from_request(request)
    if token:
        await auth_service.destroy_session(token)
    response = RedirectResponse(url="/admin/login", status_code=303)
    auth_service.clear_session_cookie(response)
    return response
