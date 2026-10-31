"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any, cast

from finsight.core.errors import TextractError
from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader

_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.bmp', '.webp'})
_CONFIDENCE_BLOCK_TYPES = frozenset({'CELL', 'TABLE', 'LINE', 'WORD'})


class TextractReader(BaseReader):
    """Read documents with AWS Textract.

    Synchronous ``AnalyzeDocument`` is used for images and single-page PDFs;
    asynchronous ``StartDocumentAnalysis`` is used for multi-page PDFs when
    configuration and file shape allow it. Missing AWS support fails loudly
    when ``read`` is invoked, not at construction or import time.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._client_override = None
        self._client: Any = None
        for key in ('client', 'textract_client', 'boto_client', 'aws_client', 'textract'):
            if key in kwargs:
                self._client_override = kwargs.pop(key)
                break

        self._client_factory = None
        for key in ('client_factory', 'factory', 'textract_factory', 'create_client'):
            if key in kwargs:
                self._client_factory = kwargs.pop(key)
                break

        self._region_override = None
        for key in ('region', 'aws_region', 'textract_region'):
            if key in kwargs:
                self._region_override = kwargs.pop(key)
                break

        self._async_override: bool | None = None
        for key in ('async_enabled', 'async_textract_enabled', 'use_async', 'async_mode'):
            if key in kwargs:
                value = kwargs.pop(key)
                if isinstance(value, str):
                    self._async_override = value.strip().lower() in {'async', '1', 'yes', 'true'}
                else:
                    self._async_override = bool(value)
                break

        self._confidence_threshold = None
        for key in ('confidence_threshold', 'min_confidence', 'threshold'):
            if key in kwargs:
                self._confidence_threshold = kwargs.pop(key)
                break

        config = kwargs.pop('config', kwargs.pop('settings', None))
        session = kwargs.pop('session', kwargs.pop('db_session', None))
        self._config = config
        self._session = session
        super().__init__(config=config, session=session)
        for key, value in kwargs.items():
            if key not in self.__dict__:
                setattr(self, key, value)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _readers_config(self) -> Any:
        config = self._config
        if config is None:
            return None
        if hasattr(config, 'readers'):
            return config.readers
        if isinstance(config, dict):
            return config.get('readers')
        return None

    def _textract_config(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_textract_config import _textract_config as _adapter_method

        return _adapter_method(self, *a, **k)

    def _switch_async_enabled(self) -> bool | None:
        tc = self._textract_config()
        if tc is not None:
            for attr in ('async_enabled', 'async_textract_enabled'):
                value = tc.get(attr) if isinstance(tc, dict) else getattr(tc, attr, None)
                if value is not None:
                    return bool(value)
        return None

    def _switches_async(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_switches_async import _switches_async as _adapter_method

        return _adapter_method(self, *a, **k)

    def _async_enabled(self) -> bool:
        if self._async_override is not None:
            return self._async_override
        switch = self._switch_async_enabled()
        if switch is not None:
            return switch
        switch = self._switches_async()
        if switch is not None:
            return cast('bool', switch)
        return True

    def _feature_types(self, *a: Any, **k: Any) -> Any:
        from ._textract_reader_feature_types import _feature_types as _m

        return _m(self, *a, **k)

    def _poll_interval(self, *a: Any, **k: Any) -> Any:
        from ._textract_reader_poll_interval import _poll_interval as _m

        return _m(self, *a, **k)

    def _max_poll_attempts(self, *a: Any, **k: Any) -> Any:
        from ._textract_reader_max_poll_attempts import _max_poll_attempts as _m

        return _m(self, *a, **k)

    def _region(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_region import _region as _adapter_method

        return _adapter_method(self, *a, **k)

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------
    def _create_client(self) -> Any:
        try:
            import boto3  # type: ignore[import-untyped]
        except Exception as exc:
            raise TextractError('boto3 is required for TextractReader') from exc
        region = self._region()
        if not region:
            raise TextractError('Textract region is not configured')
        return boto3.client('textract', region_name=region)

    def _get_client(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_get_client import _get_client as _adapter_method

        return _adapter_method(self, *a, **k)

    @property
    def client(self) -> Any:
        try:
            return self._get_client()
        except Exception:
            return getattr(self, '_client', None)

    @client.setter
    def client(self, value: Any) -> None:
        self._client_override = value

    # ------------------------------------------------------------------
    # Source helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_name(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_normalise_name import _normalise_name as _m

        return _m(*args, **kwargs)

    @staticmethod
    def _is_image_source(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_is_image_source import _is_image_source as _m

        return _m(*args, **kwargs)

    @staticmethod
    def _is_pdf_source(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_is_pdf_source import _is_pdf_source as _m

        return _m(*args, **kwargs)

    def _count_pages(self, *a: Any, **k: Any) -> Any:
        from ._textract_reader_count_pages import _count_pages as _m

        return _m(self, *a, **k)

    def _should_use_async(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_should_use_async import _should_use_async as _adapter_method

        return _adapter_method(self, *a, **k)

    # Mode aliases expected by some callers/tests.
    def _resolve_mode_source(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve_source(*args, **kwargs)

    def determine_mode(self, *args: Any, **kwargs: Any) -> str:
        src = self._resolve_source(*args, **kwargs)
        other = dict(kwargs)
        other.pop('content', None)
        use_async = self._should_use_async(src, **other)
        return 'async' if use_async else 'sync'

    def select_mode(self, *args: Any, **kwargs: Any) -> str:
        return self.determine_mode(*args, **kwargs)

    def get_mode(self, company_id: Any = None, *args: Any, **kwargs: Any) -> str:
        _ = company_id
        return self.determine_mode(*args, **kwargs)

    def mode(self, *args: Any, **kwargs: Any) -> str:
        return self.determine_mode(*args, **kwargs)

    _determine_mode = determine_mode
    _select_mode = select_mode
    _get_mode = get_mode
    _mode_for = determine_mode

    def should_use_async(self, *args: Any, **kwargs: Any) -> bool:
        src = self._resolve_source(*args, **kwargs)
        other = dict(kwargs)
        other.pop('content', None)
        return cast('bool', self._should_use_async(src, **other))

    def use_async(self, *args: Any, **kwargs: Any) -> bool:
        return self.should_use_async(*args, **kwargs)

    def async_use(self, *args: Any, **kwargs: Any) -> bool:
        return self.should_use_async(*args, **kwargs)

    # ------------------------------------------------------------------
    # Document argument resolution for Textract
    # ------------------------------------------------------------------
    def _document_arg(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_document_arg import _document_arg as _adapter_method

        return _adapter_method(self, *a, **k)

    # ------------------------------------------------------------------
    # Textract calls
    # ------------------------------------------------------------------
    def _analyze_sync(self, *a: Any, **k: Any) -> Any:
        from ._textract_reader_analyze_sync import _analyze_sync as _m

        return _m(self, *a, **k)

    def _start_async_job(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_start_async_job import _start_async_job as _adapter_method

        return _adapter_method(self, *a, **k)

    def _get_async_result(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_get_async_result import _get_async_result as _adapter_method

        return _adapter_method(self, *a, **k)

    def _analyze_async(self, source: Any) -> Any:
        job_id = self._start_async_job(source)
        return self._get_async_result(job_id)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _block_id(block: Any) -> Any:
        if isinstance(block, dict):
            return block.get('Id', block.get('ID'))
        return getattr(block, 'Id', getattr(block, 'ID', None))

    @staticmethod
    def _block_type(block: Any) -> str:
        value = (
            block.get('BlockType', block.get('blockType'))
            if isinstance(block, dict)
            else getattr(block, 'BlockType', getattr(block, 'blockType', None))
        )
        return str(value).upper() if value is not None else ''

    @staticmethod
    def _block_page(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_block_page import _block_page as _m

        return _m(*args, **kwargs)

    @staticmethod
    def _block_confidence(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_block_confidence import _block_confidence as _m

        return _m(*args, **kwargs)

    @staticmethod
    def _blocks(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_blocks import _blocks as _m

        return _m(*args, **kwargs)

    @staticmethod
    def _child_ids(*args: Any, **kwargs: Any) -> Any:
        from ._textract_reader_child_ids import _child_ids as _m

        return _m(*args, **kwargs)

    def _extract_cell_text(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_extract_cell_text import _extract_cell_text as _adapter_method

        return _adapter_method(self, *a, **k)

    def _parse_response(self: Any, *a: Any, **k: Any) -> Any:
        from ._textract_reader_parse_response import _parse_response as _adapter_method

        return _adapter_method(self, *a, **k)

    # ------------------------------------------------------------------
    # Read entry point
    # ------------------------------------------------------------------
    async def read(self, *args: Any, **kwargs: Any) -> ReaderResult:
        from typing import cast

        from ._textract_reader_read import _read as _adapter_read

        return cast('ReaderResult', await _adapter_read(self, *args, **kwargs))

    async def read_document(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def parse(self, company_id: Any, content: Any = None, **kwargs: Any) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    async def extract_text(
        self, company_id: Any, content: Any = None, **kwargs: Any
    ) -> ReaderResult:
        return await self.read(company_id, content, **kwargs)

    # Aliases used by the base/shared scaffolding.
    @staticmethod
    def _empty_result(*, confidence: Any = None) -> ReaderResult:
        return BaseReader._empty_result(confidence=confidence)

    def _as_bytes(self, source: Any) -> bytes | None:
        return super()._as_bytes(source)


# Compatibility alias
Textract = TextractReader

__all__ = ['Textract', 'TextractReader']
