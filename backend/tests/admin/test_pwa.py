import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_pwa_manifest_and_service_worker() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manifest = await client.get("/manifest.webmanifest")
        assert manifest.status_code == 200
        assert "application/manifest+json" in manifest.headers["content-type"]
        assert '"name": "BotHunter AI"' in manifest.text

        sw = await client.get("/sw.js")
        assert sw.status_code == 200
        assert "bothunter-admin-v1" in sw.text
        assert sw.headers.get("service-worker-allowed") == "/"

        icon = await client.get("/pwa/icons/icon-192.png")
        assert icon.status_code == 200
        assert icon.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_login_page_includes_pwa_meta() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/login")
        assert response.status_code == 200
        assert 'rel="manifest"' in response.text
        assert "/manifest.webmanifest" in response.text
        assert 'navigator.serviceWorker.register("/sw.js"' in response.text
