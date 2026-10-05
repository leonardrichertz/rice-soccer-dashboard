"""Builds the python3-saml settings dict for this app's SP from env vars.

Rice IAM only exposes SAML2 SSO (no OAuth), so this is the SP side of a
SAML2 integration: Rice IAM is the IdP, this app is the SP.
"""
import os


def _bool_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def saml_settings():
    return {
        "strict": _bool_env("SAML_STRICT", True),
        "debug": _bool_env("SAML_DEBUG", False),
        "sp": {
            "entityId": os.environ["SAML_SP_ENTITY_ID"],
            "assertionConsumerService": {
                "url": os.environ["SAML_SP_ACS_URL"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": os.environ.get("SAML_SP_SLO_URL", ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": os.environ.get(
                "SAML_SP_NAMEID_FORMAT",
                "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            ),
            # Only needed if Rice IAM requires signed AuthnRequests/LogoutRequests.
            "x509cert": os.environ.get("SAML_SP_X509_CERT", ""),
            "privateKey": os.environ.get("SAML_SP_PRIVATE_KEY", ""),
        },
        "idp": {
            "entityId": os.environ["SAML_IDP_ENTITY_ID"],
            "singleSignOnService": {
                "url": os.environ["SAML_IDP_SSO_URL"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": os.environ.get("SAML_IDP_SLO_URL", ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": os.environ["SAML_IDP_X509_CERT"],
        },
    }


async def prepare_request(request, post_data=None):
    """Builds the request_data dict python3-saml needs, from a Starlette Request.

    python3-saml predates ASGI frameworks, so it wants a plain dict rather
    than a Request object -- and it signs/validates against the exact host
    and scheme, so this must reflect what the IdP actually sees (set
    SAML_FORCE_HTTPS=true behind a TLS-terminating load balancer/proxy).
    """
    url = request.url
    return {
        "https": "on" if (url.scheme == "https" or _bool_env("SAML_FORCE_HTTPS", False)) else "off",
        "http_host": url.hostname,
        "server_port": url.port,
        "script_name": url.path,
        "get_data": dict(request.query_params),
        "post_data": post_data if post_data is not None else {},
        "query_string": url.query.encode("utf-8"),
    }
