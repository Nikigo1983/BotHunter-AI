from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.router import ADMIN_TEMPLATES
from app.database.session import get_db_session
from app.services.dashboard_auth import DashboardAuthService
from app.services.organization import OrganizationInviteService

invite_router = APIRouter(tags=["invite"])


async def get_invite_service(
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationInviteService:
    return OrganizationInviteService(session)


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
) -> DashboardAuthService:
    return DashboardAuthService(session)


@invite_router.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(
    token: str,
    request: Request,
    service: OrganizationInviteService = Depends(get_invite_service),
) -> HTMLResponse:
    context = await service.get_invite_context(token)
    if context is None:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    invite, organization = context
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/invite/accept.html",
        {
            "request": request,
            "invite": invite,
            "organization": organization,
            "error": None,
        },
    )


@invite_router.post("/invite/{token}")
async def invite_accept(
    token: str,
    request: Request,
    service: OrganizationInviteService = Depends(get_invite_service),
    auth_service: DashboardAuthService = Depends(get_auth_service),
    full_name: str = Form(...),
    password: str = Form(...),
):
    try:
        user = await service.accept_invite(token, full_name=full_name, password=password)
    except ValueError as exc:
        context = await service.get_invite_context(token)
        if context is None:
            raise HTTPException(status_code=404, detail="Invite not found or expired") from exc
        invite, organization = context
        return ADMIN_TEMPLATES.TemplateResponse(
            request,
            "dashboard/invite/accept.html",
            {
                "request": request,
                "invite": invite,
                "organization": organization,
                "error": str(exc),
            },
        )

    session_token, _ = await auth_service.create_session(
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    response = RedirectResponse("/admin", status_code=303)
    auth_service.set_session_cookie(response, session_token)
    return response
