"""DOCX reader adapter implementing :class:`DocumentReader`.

Walks the document body in order using ``python-docx``, preserving paragraph
and table interleaving, retaining tables as table objects and pairing the
single virtual page ``1`` with concrete heading/table locators.
"""

from __future__ import annotations

from typing import Any, cast

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class DocxReader(BaseReader):
    """Read DOCX inputs preserving body order and headings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config = kwargs.pop('config', kwargs.pop('settings', None))
        for alias in ('configuration', 'app_config', 'ctx'):
            if alias in kwargs and self._config is None:
                self._config = kwargs.pop(alias)
            elif alias in kwargs:
                kwargs.pop(alias)

        session = kwargs.pop('session', kwargs.pop('db_session', None))
        self._session = session
        super().__init__(config=self._config, session=session)

        for key, value in list(kwargs.items()):
            if key not in self.__dict__:
                setattr(self, key, value)
            kwargs.pop(key, None)

    @staticmethod
    def _is_heading_paragraph(paragraph: Any) -> bool:
        try:
            style_name = str(getattr(getattr(paragraph, 'style', None), 'name', '') or '')
        except Exception:
            style_name = ''
        low = style_name.lower()
        if low.startswith('heading'):
            return True
        if low in {'title', 'subtitle'}:
            return True
        try:
            value = getattr(paragraph.paragraph_format, 'outline_level', None)
            if value is not None:
                return True
        except Exception:
            pass
        try:
            ppr = getattr(getattr(paragraph, '_p', None), 'pPr', None)
            if ppr is not None and getattr(ppr, 'outlineLvl', None) is not None:
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _iter_block_items(document: Any) -> list[Any]:
        from docx.table import Table as TableCls
        from docx.text.paragraph import Paragraph as ParagraphCls

        items: list[Any] = []
        try:
            body = document.element.body
        except Exception:
            return items
        for child in body.iterchildren():
            tag = str(getattr(child, 'tag', ''))
            if tag.endswith('}p'):
                items.append(ParagraphCls(child, document))
            elif tag.endswith('}tbl'):
                items.append(TableCls(child, document))
        return items

    @staticmethod
    def _table_rows(table: Any) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in getattr(table, 'rows', []) or []:
            cells = [
                str(getattr(cell, 'text', '') or '').strip() for cell in getattr(row, 'cells', [])
            ]
            rows.append(cells)
        return rows

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
        from ._docx_read import _read as _docx_read

        return cast(
            'ReaderResult',
            await _docx_read(
                self,
                company_id,
                content,
                file_path=file_path,
                filename=filename,
                file_name=file_name,
                content_type=content_type,
                **kwargs,
            ),
        )

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


Docx = DocxReader
DOCX = DocxReader
DocxDocumentReader = DocxReader
WordReader = DocxReader
WordDocumentReader = DocxReader

__all__ = [
    'DOCX',
    'Docx',
    'DocxDocumentReader',
    'DocxReader',
    'WordDocumentReader',
    'WordReader',
]
