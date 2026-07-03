from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

PWA_DIR = Path(__file__).resolve().parent / "static" / "pwa"

pwa_router = APIRouter(tags=["pwa"])


@pwa_router.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest() -> FileResponse:
    return FileResponse(
        PWA_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@pwa_router.get("/sw.js", include_in_schema=False)
async def pwa_service_worker() -> FileResponse:
    return FileResponse(
        PWA_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


def mount_pwa_static(app) -> None:
    icons_dir = PWA_DIR / "icons"
    if icons_dir.is_dir():
        app.mount("/pwa/icons", StaticFiles(directory=icons_dir), name="pwa-icons")
