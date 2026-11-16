# ruff: noqa: PLC0415
"""Remote model-gateway embedding transport (issue #330).

When ``switches.llm_transport == 'remote_gateway'`` the composition root injects
``build_remote_embedding_func(settings)`` as the embedding adapter's
``embedding_func``: it receives litellm-shaped kwargs (``model``, ``input``,
``timeout``, optional ``dimensions``) and returns a litellm-shaped dict response
(``data[i].embedding`` vectors) produced by the gateway function, so the
app-side extraction, dimension checks, and metering stay untouched.

The HTTP layer is injectable (``post_json``/``signer``) — the defaults use
``httpx`` and AWS SigV4 for the Lambda function URL's ``AWS_IAM`` auth. This
module never reads ``os.environ``: settings arrive as plain values from
``finsight.core.config.model_gateway_settings``.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_TIMEOUT_SECONDS = 30.0
HTTP_ERROR_MIN_STATUS = 300

EMBEDDINGS_PATH = '/v1/embeddings'


class RemoteGatewayError(RuntimeError):
    """Raised when the model gateway call fails (non-2xx or transport error)."""


def _sigv4_sign(  # noqa: PLR0913, PLR0917 - signer mirror of the SigV4 credential/region pair
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    region: str,
    credentials: Any = None,
) -> dict[str, str]:
    """Return SigV4-signed headers for a Lambda function URL invocation."""
    from botocore.auth import SigV4Auth  # type: ignore[import-untyped]
    from botocore.awsrequest import AWSRequest  # type: ignore[import-untyped]
    from botocore.credentials import Credentials  # type: ignore[import-untyped]

    resolved = credentials
    if resolved is None:
        from botocore.session import get_session  # type: ignore[import-untyped]

        resolved = get_session().get_credentials()
        if resolved is None:
            raise ValueError(
                'remote_gateway transport could not resolve AWS credentials for SigV4 signing'
            )
    if not isinstance(resolved, Credentials):
        resolved = Credentials(
            resolved.access_key,
            resolved.secret_key,
            resolved.token,
        )

    signed = dict(headers)
    signed['X-Amz-Content-Sha256'] = hashlib.sha256(body).hexdigest()
    request = AWSRequest(method=method, url=url, data=body, headers=dict(signed))
    SigV4Auth(resolved, 'lambda', region).add_auth(request)
    return {str(name): str(value) for name, value in request.headers.items()}


def _signed_headers(settings: Mapping[str, Any], signer: Any, body: bytes) -> dict[str, str]:
    """Build request headers: content type, optional master key, SigV4.

    The SigV4 signature lives in ``Authorization``; the optional shared key
    travels in ``X-Gateway-Master-Key`` so the two auth layers never collide.
    """
    headers: dict[str, str] = {'Content-Type': 'application/json'}
    auth_token = settings.get('auth_token')
    if auth_token:
        headers['X-Gateway-Master-Key'] = auth_token
    if signer is not None:
        return dict(signer('POST', str(settings['base_url']), dict(headers), body))
    region = settings.get('region')
    if not region:
        raise ValueError(
            'remote_gateway transport requires a signing region (AWS_REGION) for SigV4; '
            'inject an explicit signer for non-AWS endpoints'
        )
    return _sigv4_sign('POST', str(settings['base_url']), headers, body, region=region)


async def _httpx_post_json(
    url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
) -> dict[str, Any]:
    """Default HTTP layer: buffered JSON response (embeddings are not streamed)."""
    import httpx

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, headers=headers, content=body)
    if response.status_code >= HTTP_ERROR_MIN_STATUS:
        raise RemoteGatewayError(
            f'gateway POST {url} failed: HTTP {response.status_code}: {response.text[:200]!r}'
        )
    return response.json()  # type: ignore[no-any-return]


def _validated_base_url(settings: Mapping[str, Any], signer: Any) -> str:
    """Return the gateway base URL, failing loudly on missing URL or region."""
    base_url = str(settings.get('base_url') or '')
    if not base_url:
        raise ValueError(
            'remote_gateway transport requires MODEL_GATEWAY_URL (settings["base_url"])'
        )
    if signer is None and not settings.get('region'):
        raise ValueError(
            'remote_gateway transport requires a signing region (AWS_REGION) for SigV4; '
            'inject an explicit signer for non-AWS endpoints'
        )
    return base_url


def build_remote_embedding_func(
    settings: Mapping[str, Any], *, post_json: Any = None, signer: Any = None
) -> Any:
    """Return an async ``embedding_func(**litellm_kwargs)`` calling the gateway.

    ``settings`` carries ``base_url`` (required), an optional shared
    ``auth_token`` key, and the SigV4 ``region``. ``post_json(url, headers,
    body, timeout_seconds)`` must return the parsed JSON response.
    """
    base_url = _validated_base_url(settings, signer)
    json_fn = post_json if post_json is not None else _httpx_post_json

    async def remote_embedding(**kwargs: Any) -> Any:
        url = base_url.rstrip('/') + EMBEDDINGS_PATH
        body: dict[str, Any] = {'model': kwargs.get('model'), 'input': kwargs.get('input')}
        if kwargs.get('dimensions'):
            body['dimensions'] = kwargs['dimensions']
        timeout_seconds = float(kwargs.get('timeout') or DEFAULT_TIMEOUT_SECONDS)
        body_bytes = json.dumps(body, default=str).encode('utf-8')
        headers = _signed_headers(settings, signer, body_bytes)
        return await json_fn(url, headers, body_bytes, timeout_seconds)

    return remote_embedding


__all__ = ['RemoteGatewayError', 'build_remote_embedding_func']
