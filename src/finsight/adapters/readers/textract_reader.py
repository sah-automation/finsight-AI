"""AWS Textract adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
import time
from typing import Any

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

    def _textract_config(self) -> Any:
        readers = self._readers_config()
        if readers is not None:
            for attr in ('textract',):
                value = (
                    readers.get(attr) if isinstance(readers, dict) else getattr(readers, attr, None)
                )
                if value is not None:
                    return value
        config = self._config
        if config is None:
            return None
        if hasattr(config, 'textract'):
            return config.textract
        if isinstance(config, dict):
            return config.get('textract')
        return None

    def _switch_async_enabled(self) -> bool | None:
        tc = self._textract_config()
        if tc is not None:
            for attr in ('async_enabled', 'async_textract_enabled'):
                value = tc.get(attr) if isinstance(tc, dict) else getattr(tc, attr, None)
                if value is not None:
                    return bool(value)
        return None

    def _switches_async(self) -> bool | None:
        config = self._config
        switches = None
        if config is not None:
            switches = (
                getattr(config, 'switches', None)
                if not isinstance(config, dict)
                else config.get('switches')
            )
            readers = self._readers_config()
            if switches is None and isinstance(readers, dict):
                switches = readers.get('switches')
        if switches is None:
            return None
        for key in ('async_textract_enabled', 'textract_async_enabled', 'async_enabled'):
            value = (
                switches.get(key) if isinstance(switches, dict) else getattr(switches, key, None)
            )
            if value is not None:
                return bool(value)
        return None

    def _async_enabled(self) -> bool:
        if self._async_override is not None:
            return self._async_override
        switch = self._switch_async_enabled()
        if switch is not None:
            return switch
        switch = self._switches_async()
        if switch is not None:
            return switch
        return True

    def _feature_types(self) -> list[str]:
        tc = self._textract_config()
        if tc is not None:
            value = (
                tc.get('feature_types')
                if isinstance(tc, dict)
                else getattr(tc, 'feature_types', None)
            )
            if value is not None:
                return list(value)
        return ['TABLES', 'FORMS']

    def _poll_interval(self) -> int:
        tc = self._textract_config()
        if tc is not None:
            value = (
                tc.get('poll_interval_seconds')
                if isinstance(tc, dict)
                else getattr(tc, 'poll_interval_seconds', None)
            )
            if value is not None:
                return int(value)
        return 5

    def _max_poll_attempts(self) -> int:
        tc = self._textract_config()
        if tc is not None:
            value = (
                tc.get('max_poll_attempts')
                if isinstance(tc, dict)
                else getattr(tc, 'max_poll_attempts', None)
            )
            if value is not None:
                return int(value)
        return 100

    def _region(self) -> str | None:
        if self._region_override is not None:
            return str(self._region_override)
        tc = self._textract_config()
        if tc is not None:
            value = tc.get('region') if isinstance(tc, dict) else getattr(tc, 'region', None)
            if value is not None:
                return str(value)
        config = self._config
        if config is not None:
            for section_name in ('aws', 'storage', 'textract'):
                section = (
                    getattr(config, section_name, None)
                    if not isinstance(config, dict)
                    else config.get(section_name)
                )
                if section is None:
                    continue
                value = (
                    section.get('region')
                    if isinstance(section, dict)
                    else getattr(section, 'region', None)
                )
                if value is not None:
                    return str(value)
        return None

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

    def _get_client(self) -> Any:
        if self._client_override is not None:
            return self._client_override
        if getattr(self, '_client', None) is not None:
            return self._client
        if self._client_factory is not None:
            if not callable(self._client_factory):
                raise TextractError('Textract client factory is not callable')
            client = self._client_factory()
            if client is None:
                raise TextractError('Textract client factory returned None')
            self._client = client
            return client
        try:
            client = self._create_client()
        except Exception as exc:
            raise TextractError(str(exc) or 'Failed to construct Textract client') from exc
        self._client = client
        return client

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
    def _normalise_name(
        source: Any,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> dict[str, Any]:
        name = ''
        if filename is not None:
            name = str(filename)
        elif file_name is not None:
            name = str(file_name)
        elif file_path is not None:
            name = str(file_path)
        ext = ''
        if '.' in name:
            ext = name.rsplit('.', 1)[-1].lower()
        ct = content_type
        if ct is None and source is not None:
            ct = getattr(source, 'content_type', None)
        return {'name': name, 'ext': ext, 'content_type': ct}

    @staticmethod
    def _is_image_source(
        source: Any,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> bool:
        info = TextractReader._normalise_name(source, filename, file_name, file_path, content_type)
        ct = info['content_type']
        if isinstance(ct, str) and ct.lower().startswith('image/'):
            return True
        if info['ext'] in _IMAGE_EXTENSIONS:
            return True
        # Rely on bytes sniffing for common image signatures when available.
        try:
            raw = source if isinstance(source, (bytes, bytearray)) else None
            if raw is None and hasattr(source, 'read'):
                raw = source.read()
                if hasattr(source, 'seek'):
                    source.seek(0)
            if isinstance(raw, (bytes, bytearray)):
                if raw[:4] == b'\x89PNG' or raw[:3] == b'\xff\xd8\xff':
                    return True
                if raw[:6] in (b'GIF87a', b'GIF89a'):
                    return True
                if raw[:2] == b'BM':
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _is_pdf_source(
        source: Any,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> bool:
        info = TextractReader._normalise_name(source, filename, file_name, file_path, content_type)
        ct = info['content_type']
        if isinstance(ct, str) and 'pdf' in ct.lower():
            return True
        if info['ext'] == 'pdf':
            return True
        try:
            raw = source if isinstance(source, (bytes, bytearray)) else None
            if raw is None and hasattr(source, 'read'):
                raw = source.read()
                if hasattr(source, 'seek'):
                    source.seek(0)
            if isinstance(raw, (bytes, bytearray)) and raw[:4] == b'%PDF':
                return True
        except Exception:
            pass
        return False

    def _count_pages(self, source: Any) -> int | None:
        data = self._as_bytes(source)
        if data is None:
            return None
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return len(pdf.pages)
        except Exception:
            return None

    def _should_use_async(  # noqa: PLR0917
        self,
        source: Any,
        page_count: Any = None,
        pages: Any = None,
        content_type: Any = None,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        **kwargs: Any,
    ) -> bool:
        # Explicit override always wins.
        if 'async_mode' in kwargs or 'use_async' in kwargs or 'mode' in kwargs:
            mode_kw = kwargs.get('mode', kwargs.get('async_mode', kwargs.get('use_async')))
            if isinstance(mode_kw, str):
                return mode_kw.strip().lower() in {'async', '1', 'yes', 'true'}
            if mode_kw is not None:
                return bool(mode_kw)

        count = page_count if page_count is not None else pages
        if count is None:
            count = kwargs.get('page_count', kwargs.get('pages'))
        if count is None:
            if self._is_image_source(source, filename, file_name, file_path, content_type):
                return False
            if self._is_pdf_source(source, filename, file_name, file_path, content_type):
                counted = self._count_pages(source)
                count = counted if counted is not None else 1
            else:
                return False
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        if count <= 1:
            return False
        return self._async_enabled()

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
        return self._should_use_async(src, **other)

    def use_async(self, *args: Any, **kwargs: Any) -> bool:
        return self.should_use_async(*args, **kwargs)

    def async_use(self, *args: Any, **kwargs: Any) -> bool:
        return self.should_use_async(*args, **kwargs)

    # ------------------------------------------------------------------
    # Document argument resolution for Textract
    # ------------------------------------------------------------------
    def _document_arg(self, source: Any) -> Any:
        if isinstance(source, dict):
            for key in ('bucket', 'Bucket'):
                bucket = source.get(key)
                if bucket:
                    key_name = source.get('key', source.get('Key', source.get('object_key')))
                    if key_name:
                        return {'S3Object': {'Bucket': bucket, 'Name': key_name}}
            if source.get('Bytes') is not None:
                return {'Bytes': source['Bytes']}
            if source.get('S3Object') is not None:
                return {'S3Object': source['S3Object']}
            for key in ('content', 'data', 'bytes', 'body', 'file'):
                if source.get(key) is not None:
                    return self._document_arg(source.get(key))
        if isinstance(source, str):
            if source.lower().startswith('s3://'):
                parts = source[5:].split('/', 1)
                if len(parts) == 2:
                    return {'S3Object': {'Bucket': parts[0], 'Name': parts[1]}}
            path_bytes = self._as_bytes(source)
            if path_bytes is not None:
                return {'Bytes': path_bytes}
            raise TextractError('Unable to resolve a Textract document source')
        raw = self._as_bytes(source)
        if raw is not None:
            return {'Bytes': raw}
        bucket = getattr(source, 'bucket', None) or getattr(source, 'Bucket', None)
        key_value: Any = (
            getattr(source, 'key', None)
            or getattr(source, 'Key', None)
            or getattr(source, 'object_key', None)
        )
        if bucket and key_value:
            return {'S3Object': {'Bucket': bucket, 'Name': key_value}}
        raise TextractError('Unable to resolve a Textract document source')

    # ------------------------------------------------------------------
    # Textract calls
    # ------------------------------------------------------------------
    def _analyze_sync(self, source: Any) -> Any:
        client = self._get_client()
        document = self._document_arg(source)
        feature_types = self._feature_types()
        kwargs = {'Document': document}
        if feature_types:
            kwargs['FeatureTypes'] = feature_types
        try:
            return client.analyze_document(**kwargs)
        except Exception as exc:
            raise TextractError('Textract synchronous analysis failed') from exc

    def _start_async_job(self, source: Any) -> str:
        client = self._get_client()
        document = self._document_arg(source)
        feature_types = self._feature_types()
        kwargs = {'Document': document}
        if feature_types:
            kwargs['FeatureTypes'] = feature_types
        try:
            result = client.start_document_analysis(**kwargs)
        except Exception as exc:
            raise TextractError('Textract asynchronous analysis failed to start') from exc
        job_id = None
        if isinstance(result, dict):
            job_id = result.get('JobId', result.get('JobID'))
        else:
            job_id = getattr(result, 'JobId', getattr(result, 'JobID', None))
        if not job_id:
            raise TextractError('Textract asynchronous analysis did not return a job id')
        return str(job_id)

    def _get_async_result(self, job_id: str) -> Any:
        client = self._get_client()
        collected_blocks: list[Any] = []
        metadata: dict[str, Any] = {}
        next_token = None
        attempts = 0
        max_attempts = self._max_poll_attempts()
        while attempts < max_attempts:
            attempts += 1
            kwargs = {'JobId': job_id}
            if next_token:
                kwargs['NextToken'] = next_token
            try:
                response = client.get_document_analysis(**kwargs)
            except Exception as exc:
                raise TextractError('Textract asynchronous analysis failed') from exc
            status = None
            if isinstance(response, dict):
                status = response.get('JobStatus')
                md = response.get('DocumentMetadata') or response.get('documentMetadata')
                if md and not metadata:
                    metadata = md
                page_meta = response.get('DocumentMetadata') or metadata
                if page_meta and isinstance(page_meta, dict):
                    metadata = page_meta
                blocks = response.get('Blocks') or response.get('blocks') or []
                collected_blocks.extend(blocks if isinstance(blocks, (list, tuple)) else [blocks])
                next_token = response.get('NextToken') or response.get('nextToken')
            else:
                status = getattr(response, 'JobStatus', None)
                md = getattr(response, 'DocumentMetadata', None) or getattr(
                    response, 'documentMetadata', None
                )
                if md and not metadata:
                    metadata = md
                if md:
                    metadata = md
                blocks = (
                    getattr(response, 'Blocks', None) or getattr(response, 'blocks', None) or []
                )
                collected_blocks.extend(blocks if isinstance(blocks, (list, tuple)) else [blocks])
                next_token = getattr(response, 'NextToken', None) or getattr(
                    response, 'nextToken', None
                )
            status_text = str(status).upper() if status is not None else ''
            if status_text in {'SUCCEEDED', 'SUCCESS', 'PARTIAL_SUCCESS', 'COMPLETED', 'COMPLETE'}:
                if next_token:
                    time.sleep(0)
                    continue
                return {'Blocks': collected_blocks, 'DocumentMetadata': metadata}
            if status_text in {'FAILED', 'ERROR'}:
                raise TextractError('Textract asynchronous analysis failed')
            if (
                status_text in {'IN_PROGRESS', 'RUNNING', 'PROCESSING', 'STARTED'}
                or not status_text
            ):
                time.sleep(self._poll_interval())
                continue
            # Unknown status: wait briefly then continue.
            time.sleep(self._poll_interval())
        raise TextractError('Textract asynchronous analysis timed out')

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
    def _block_page(block: Any) -> int:
        page = None
        if isinstance(block, dict):
            page = block.get('Page', block.get('page'))
        else:
            page = getattr(block, 'Page', getattr(block, 'page', None))
        if page is None:
            return 1
        try:
            value = int(page)
        except (TypeError, ValueError):
            return 1
        if isinstance(page, bool):
            return 1
        return value if value >= 1 else 1

    @staticmethod
    def _block_confidence(block: Any) -> Any:
        if isinstance(block, dict):
            for key in ('Confidence', 'confidence'):
                if key in block:
                    return block.get(key)
            return None
        for key in ('Confidence', 'confidence'):
            value = getattr(block, key, None)
            if value is not None:
                return value
        return getattr(block, 'Confidence', None)

    @staticmethod
    def _blocks(response: Any) -> list[Any]:
        if isinstance(response, dict):
            blocks = response.get('Blocks', response.get('blocks'))
        else:
            blocks = getattr(response, 'Blocks', None) or getattr(response, 'blocks', None)
        if isinstance(blocks, (list, tuple)):
            return list(blocks)
        if blocks is None:
            return []
        return [blocks]

    @staticmethod
    def _child_ids(block: Any, relation_type: str = 'CHILD') -> list[Any]:
        relations = (
            block.get('Relationships', block.get('relationships'))
            if isinstance(block, dict)
            else getattr(block, 'Relationships', getattr(block, 'relationships', None))
        )
        if not isinstance(relations, (list, tuple)):
            return []
        ids: list[Any] = []
        for rel in relations:
            rtype = (
                rel.get('Type', rel.get('type'))
                if isinstance(rel, dict)
                else getattr(rel, 'Type', getattr(rel, 'type', None))
            )
            if str(rtype).upper() != relation_type.upper():
                continue
            raw_ids = (
                rel.get('Ids', rel.get('ids'))
                if isinstance(rel, dict)
                else getattr(rel, 'Ids', getattr(rel, 'ids', None))
            )
            if isinstance(raw_ids, (list, tuple)):
                ids.extend(raw_ids)
        return ids

    def _extract_cell_text(self, cell_block: Any, by_id: dict[Any, Any]) -> str:
        words: list[str] = []
        queue = list(self._child_ids(cell_block, 'CHILD'))
        visited: set[Any] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            child = by_id.get(current)
            if not child:
                continue
            btype = self._block_type(child).upper()
            if btype == 'WORD':
                value = (
                    child.get('Text', child.get('text'))
                    if isinstance(child, dict)
                    else getattr(child, 'Text', getattr(child, 'text', None))
                )
                if value is not None:
                    words.append(str(value))
            elif btype == 'SELECTION_ELEMENT':
                sel = (
                    child.get('SelectionStatus', child.get('selectionStatus'))
                    if isinstance(child, dict)
                    else getattr(child, 'SelectionStatus', getattr(child, 'selectionStatus', None))
                )
                if sel:
                    words.append(str(sel))
            queue.extend(self._child_ids(child, 'CHILD'))
        if words:
            return ' '.join(words).strip()
        value = (
            cell_block.get('Text', cell_block.get('text'))
            if isinstance(cell_block, dict)
            else getattr(cell_block, 'Text', getattr(cell_block, 'text', None))
        )
        if value is not None:
            return str(value).strip()
        return ''

    def _parse_response(
        self,
        response: Any,
        source: Any = None,
        content_type: Any = None,
    ) -> ReaderResult:
        blocks = self._blocks(response)
        by_id: dict[Any, Any] = {}
        for block in blocks:
            bid = self._block_id(block)
            if bid is not None:
                by_id[bid] = block

        text_by_page: dict[Any, list[str]] = {}
        page_set: set[int] = set()
        confidences: list[float] = []
        tables: list[dict[str, Any]] = []
        locators: list[dict[str, Any]] = []

        # Metadata page count (optional, does not drive page numbers).
        metadata = (
            response.get('DocumentMetadata', response.get('documentMetadata'))
            if isinstance(response, dict)
            else getattr(response, 'DocumentMetadata', getattr(response, 'documentMetadata', None))
        )
        metadata_pages = None
        if isinstance(metadata, dict):
            metadata_pages = metadata.get('Pages', metadata.get('pages'))

        table_index = 0
        for table_block in (b for b in blocks if self._block_type(b) == 'TABLE'):
            table_index += 1
            page = self._block_page(table_block)
            page_set.add(page)
            cell_ids = self._child_ids(table_block, 'CHILD')
            cell_blocks: list[Any] = [
                by_id[cid]
                for cid in cell_ids
                if cid in by_id and self._block_type(by_id[cid]) == 'CELL'
            ]
            # Collect any nested cell blocks as well.
            if not cell_blocks:
                cell_blocks = [by_id[cid] for cid in cell_ids if cid in by_id]

            cell_map: dict[tuple[int, int], Any] = {}
            max_row = 0
            max_col = 0
            for cell in cell_blocks:
                if self._block_type(cell) != 'CELL':
                    continue
                row_idx = (
                    cell.get('RowIndex', cell.get('rowIndex'))
                    if isinstance(cell, dict)
                    else getattr(cell, 'RowIndex', getattr(cell, 'rowIndex', 0))
                )
                col_idx = (
                    cell.get('ColumnIndex', cell.get('columnIndex'))
                    if isinstance(cell, dict)
                    else getattr(cell, 'ColumnIndex', getattr(cell, 'columnIndex', 0))
                )
                try:
                    row_idx = int(row_idx)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    row_idx = 0
                try:
                    col_idx = int(col_idx)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    col_idx = 0
                row_idx = max(row_idx, 1)
                col_idx = max(col_idx, 1)
                cell_map[(row_idx, col_idx)] = cell
                max_row = max(max_row, row_idx)
                max_col = max(max_col, col_idx)

            cell_confidences: list[float] = []
            rows: list[list[str]] = []
            for r in range(1, max_row + 1):
                row: list[str] = []
                for c in range(1, max_col + 1):
                    cell = cell_map.get((r, c))
                    if cell is not None:
                        text = self._extract_cell_text(cell, by_id)
                        row.append(text)
                        conf = self._block_confidence(cell)
                        if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                            cell_confidences.append(float(conf))
                    else:
                        row.append('')
                rows.append(row)

            if cell_confidences:
                table_confidence: Any = sum(cell_confidences) / len(cell_confidences)
            else:
                conf = self._block_confidence(table_block)
                table_confidence = (
                    float(conf)
                    if isinstance(conf, (int, float)) and not isinstance(conf, bool)
                    else None
                )

            geometry = (
                table_block.get('Geometry', table_block.get('geometry'))
                if isinstance(table_block, dict)
                else getattr(table_block, 'Geometry', getattr(table_block, 'geometry', None))
            )
            bbox = None
            if isinstance(geometry, dict):
                bbox = geometry.get(
                    'BoundingBox', geometry.get('boundingBox', geometry.get('BoundingBox'))
                )

            table_obj = {
                'page': page,
                'page_number': page,
                'rows': rows,
                'table': rows,
                'data': rows,
                'cells': rows,
                'confidence': table_confidence,
                'bbox': bbox,
                'bounding_box': bbox,
                'boundaries': bbox,
                'table_index': table_index,
            }
            tables.append(table_obj)
            locators.append(
                {
                    'page': page,
                    'type': 'table',
                    'index': table_index,
                    'rows': max_row,
                    'columns': max_col,
                    'confidence': table_confidence,
                }
            )

        # Text/confidence extraction (canonical: append confidence for
        # CELL/TABLE/LINE/WORD blocks).
        for block in blocks:
            btype = self._block_type(block)
            page = self._block_page(block)
            page_set.add(page)
            conf = self._block_confidence(block)
            if conf is not None and btype in _CONFIDENCE_BLOCK_TYPES:
                if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                    confidences.append(float(conf))
            if btype != 'LINE':
                continue
            if isinstance(block, dict):
                line_text = block.get('Text', block.get('text'))
            else:
                line_text = getattr(block, 'Text', getattr(block, 'text', None))
            if line_text is None:
                continue
            text_str = str(line_text)
            if not text_str.strip():
                continue
            text_by_page.setdefault(page, []).append(text_str)

        if not page_set:
            page_set.add(1)
        ordered_pages = sorted(page_set) if page_set else []
        if not ordered_pages and metadata_pages:
            try:
                ordered_pages = list(range(1, int(metadata_pages) + 1))
            except (TypeError, ValueError):
                ordered_pages = [1]
        if not page_set and not ordered_pages:
            ordered_pages = [1]
            page_set.add(1)

        page_texts: list[str] = []
        for page in ordered_pages:
            parts = text_by_page.get(page, [])
            page_texts.append('\n'.join(parts).strip() if parts else '')
        # Build full text
        if any(page_texts):
            full_text = '\n\n'.join(part for part in page_texts)
        else:
            full_text = ''
        # clean empty joins
        full_text = '\n\n'.join(part for part in page_texts).strip() if any(page_texts) else ''

        if confidences:
            confidence: Any = sum(confidences) / len(confidences)
        else:
            full_text_stripped = full_text.strip() if isinstance(full_text, str) else ''
            confidence = 1.0 if (full_text_stripped or tables) else 0.0

        page_numbers = ordered_pages if ordered_pages else [1]

        # Remove duplicate integer pages while preserving order.
        deduped: list[int] = []
        for page in page_numbers:
            page_int = int(page)
            if page_int not in deduped:
                deduped.append(page_int)
        page_numbers = deduped

        for page in page_numbers:
            locators.append({'page': page, 'type': 'text'})

        return ReaderResult(
            text=full_text,
            tables=list(tables),
            page_numbers=page_numbers,
            confidence=confidence,
            locators=list(locators),
        )

    # ------------------------------------------------------------------
    # Read entry point
    # ------------------------------------------------------------------
    async def read(
        self,
        company_id: Any,
        content: Any = None,
        *,
        file_path: Any = None,
        filename: Any = None,
        file_name: Any = None,
        content_type: Any = None,
        **kwargs: Any,
    ) -> ReaderResult:
        self._require_company_id(company_id)
        source = self._resolve_source(
            content, file_path=file_path, filename=filename, file_name=file_name, **kwargs
        )
        if self._is_empty_content(source) and not kwargs:
            # Keep empty content handling safe even when only metadata is passed.
            if source is None and all(
                v is None for v in (file_path, filename, file_name, content_type)
            ):
                return self._empty_result()

        # Mode overrides.
        mode_override = None
        for key in ('mode', 'reader_mode', 'textract_mode'):
            if key in kwargs:
                mode_override = kwargs.pop(key)
        async_override_kw = None
        for key in ('async_', 'async_mode', 'use_async'):
            if key in kwargs:
                async_override_kw = kwargs.pop(key)

        force_async = False
        if isinstance(async_override_kw, str):
            force_async = async_override_kw.strip().lower() in {'async', '1', 'yes', 'true'}
        elif async_override_kw is not None:
            force_async = bool(async_override_kw)
        if isinstance(mode_override, str):
            force_async = mode_override.strip().lower() == 'async'

        empty = self._is_empty_content(source)
        if empty:
            return self._empty_result()

        pages_kw = kwargs.get('pages', kwargs.get('page_count'))
        try:
            use_async = force_async or self._should_use_async(
                source,
                page_count=pages_kw,
                content_type=content_type or kwargs.get('content_type'),
                filename=filename or kwargs.get('filename'),
                file_name=file_name or kwargs.get('file_name'),
                file_path=file_path or kwargs.get('file_path'),
                **{k: v for k, v in kwargs.items() if k not in {'page_count', 'pages'}},
            )
        except Exception:
            use_async = force_async

        try:
            if use_async:
                response = self._analyze_async(source)
            else:
                response = self._analyze_sync(source)
        except TextractError:
            raise
        except Exception as exc:
            raise TextractError('Textract read failed') from exc

        ct = content_type or kwargs.get('content_type')
        if 'content_type' in kwargs:
            ct = kwargs.get('content_type')
        return self._coerce_result(self._parse_response(response, source, ct))

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
