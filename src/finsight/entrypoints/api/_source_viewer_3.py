# ruff: noqa: BLE001, PLR2004, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

try:
    from finsight.entrypoints.api.documents import _Response
except Exception:  # pragma: no cover

    class _Response(dict[str, Any]):  # type: ignore[no-redef]
        pass


from ._source_viewer_0 import *
from ._source_viewer_1 import *
from ._source_viewer_2 import *


def handle_documents(*args: Any, **kwargs: Any) -> Any:
    return documents(*args, **kwargs)


def handle_source_viewer(*args: Any, **kwargs: Any) -> Any:
    return documents(*args, **kwargs)


async def http_source(
    document_id: str, citation_id: str, context: Any = None, **kwargs: Any
) -> Any:
    try:
        return await _handle(
            {'document_id': document_id, 'citation_id': citation_id},
            context=context,
            **kwargs,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={'status': 'not_available'})
        raise
    except Exception:
        return JSONResponse(status_code=404, content={'status': 'not_available'})


async def http_original(
    document_id: str, citation_id: str, context: Any = None, **kwargs: Any
) -> Any:
    try:
        return await _handle(
            {'document_id': document_id, 'citation_id': citation_id},
            context=context,
            original=True,
            **kwargs,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={'status': 'not_available'})
        raise
    except Exception:
        return JSONResponse(status_code=404, content={'status': 'not_available'})


__all__ = ['handle_documents', 'handle_source_viewer', 'http_original', 'http_source']
