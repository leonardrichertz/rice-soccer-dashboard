"""SAML2 SSO routes (SP side) and the session-gate middleware that protects
the dashboard behind them.

Rice IAM is SAML2-only (confirmed: their IAM SSO service doesn't do OAuth),
so this is a standard SP-initiated SAML2 flow using python3-saml:

  1. Unauthenticated request -> AuthGateMiddleware redirects to /saml/login
  2. /saml/login -> redirects to Rice IAM's SSO URL with a SAMLRequest
  3. User authenticates at Rice IAM, which POSTs a SAMLResponse to /saml/acs
  4. /saml/acs validates the response, stores the user in the session,
     and redirects back to whatever page was originally requested
"""
from urllib.parse import quote, unquote

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.websockets import WebSocket

from .saml_config import prepare_request, saml_settings

# Paths reachable without an authenticated session. Everything else is gated.
PUBLIC_PATHS = {"/saml/login", "/saml/acs", "/saml/metadata", "/saml/slo"}


async def _build_auth(request, post_data=None):
    req = await prepare_request(request, post_data)
    return OneLogin_Saml2_Auth(req, old_settings=saml_settings())


def _safe_next(next_path):
    """Only ever redirect back into this same app, never to an attacker-supplied
    external URL (open-redirect guard on the `next` query param)."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


async def saml_login(request: Request) -> Response:
    auth = await _build_auth(request)
    next_path = _safe_next(unquote(request.query_params.get("next", "/")))
    return RedirectResponse(auth.login(return_to=next_path))


async def saml_acs(request: Request) -> Response:
    form = await request.form()
    auth = await _build_auth(request, dict(form))
    auth.process_response()

    if auth.get_errors():
        detail = auth.get_last_error_reason() or ", ".join(auth.get_errors())
        return PlainTextResponse(f"SAML login failed: {detail}", status_code=401)

    attributes = auth.get_attributes()
    request.session["user"] = {
        "name_id": auth.get_nameid(),
        "email": (attributes.get("email") or attributes.get("mail") or [auth.get_nameid()])[0],
        "attributes": attributes,
    }

    relay_state = form.get("RelayState")
    return RedirectResponse(_safe_next(relay_state), status_code=303)


async def saml_metadata(request: Request) -> Response:
    """SP metadata XML to hand to Rice IAM so they can register this app as
    a service provider."""
    settings = OneLogin_Saml2_Settings(saml_settings(), sp_validation_only=True)
    errors = settings.validate_metadata(settings.get_sp_metadata())
    if errors:
        return PlainTextResponse(f"Invalid SP metadata: {', '.join(errors)}", status_code=500)
    return Response(settings.get_sp_metadata(), media_type="application/xml")


async def saml_slo(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse("/")


routes = [
    Route("/saml/login", saml_login, methods=["GET"]),
    Route("/saml/acs", saml_acs, methods=["POST"]),
    Route("/saml/metadata", saml_metadata, methods=["GET"]),
    Route("/saml/slo", saml_slo, methods=["GET"]),
]


class AuthGateMiddleware:
    """Raw ASGI middleware (not BaseHTTPMiddleware) so it can gate Shiny's
    websocket connection too, not just the initial HTTP page load."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or scope["path"] in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        if scope.get("session", {}).get("user"):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            websocket = WebSocket(scope, receive, send)
            await websocket.close(code=1008)
            return

        request = Request(scope, receive)
        next_path = quote(str(request.url.path) + (f"?{request.url.query}" if request.url.query else ""))
        response = RedirectResponse(f"/saml/login?next={next_path}")
        await response(scope, receive, send)
