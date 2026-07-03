from starlette.requests import Request

from app.admin.request_utils import public_base_url


def test_public_base_url_uses_forwarded_headers() -> None:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/admin/organization/members",
        "headers": [
            (b"x-forwarded-proto", b"https"),
            (b"x-forwarded-host", b"bothunter-ai-production.up.railway.app"),
        ],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert public_base_url(request) == "https://bothunter-ai-production.up.railway.app"
