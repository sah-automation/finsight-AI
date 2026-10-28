"""Tesseract OCR adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from finsight.domain.value_objects.reader_result import ReaderResult

from .base_reader import BaseReader


class TesseractReader(BaseReader):
    """Read scanned PDFs/images with Tesseract OCR.

    PDF pages are rendered with ``pdf2image`` and OCR runs through
    ``pytesseract``. Word-level confidence is averaged into the result.
    Missing system binaries or supporting libraries raise only when ``read``
    is invoked, keeping construction and imports safe in CI.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._tesseract_cmd_override: str | None = None
        for key in ('tesseract_cmd', 'tesseract_path', 'cmd', 'binary', 'executable'):
            if key in kwargs:
                value = kwargs.pop(key)
                if value is not None:
                    self._tesseract_cmd_override = str(value)
                break

        self._languages_override: list[str] | None = None
        for key in ('languages', 'language', 'lang', 'langs', 'languages_list'):
            if key in kwargs:
                value = kwargs.pop(key)
                if value is None:
                    self._languages_override = None
                elif isinstance(value, str):
                    self._languages_override = [
                        part.strip() for part in value.split(',') if part.strip()
                    ]
                elif isinstance(value, (list, tuple)):
                    self._languages_override = [str(item) for item in value]
                else:
                    self._languages_override = [str(value)]
                break

        self._dpi_override: int | None = None
        for key in ('dpi', 'resolution', 'render_dpi'):
            if key in kwargs:
                value = kwargs.pop(key)
                if value is not None:
                    try:
                        self._dpi_override = int(value)
                    except (TypeError, ValueError):
                        self._dpi_override = None
                break

        self._config_override: str | None = None
        for key in ('ocr_config', 'psm'):
            if key in kwargs:
                value = kwargs.pop(key)
                if value is None:
                    self._config_override = None
                else:
                    self._config_override = str(value)

        passed_config = None
        if 'config' in kwargs:
            passed_config = kwargs.pop('config')
        if 'tesseract_config' in kwargs:
            tc_value = kwargs.pop('tesseract_config')
            if isinstance(tc_value, str):
                if self._config_override is None:
                    self._config_override = tc_value
            elif passed_config is None:
                passed_config = tc_value
        if 'settings' in kwargs and passed_config is None:
            passed_config = kwargs.pop('settings')

        if isinstance(passed_config, str):
            if self._config_override is None:
                self._config_override = passed_config
            config = None
        else:
            config = passed_config

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
    def _tesseract_config_section(self) -> Any:
        config = self._config
        if config is None:
            return None
        readers = getattr(config, 'readers', None)
        if readers is None and isinstance(config, dict):
            readers = config.get('readers')
        if readers is not None:
            value = (
                readers.get('tesseract')
                if isinstance(readers, dict)
                else getattr(readers, 'tesseract', None)
            )
            if value is not None:
                return value
        if hasattr(config, 'tesseract'):
            return config.tesseract
        if isinstance(config, dict):
            if 'tesseract' in config:
                return config.get('tesseract')
            # Allow a flattened tesseract config section.
            if any(key in config for key in ('languages', 'dpi', 'config', 'resolution')):
                return config
        # Flattened object config.
        if any(hasattr(config, attr) for attr in ('languages', 'dpi', 'config')) and not hasattr(
            config, 'readers'
        ):
            return config
        return None

    def _section_value(self, section: Any, *names: str) -> Any:
        if section is None:
            return None
        for name in names:
            if isinstance(section, dict):
                if name in section and section.get(name) is not None:
                    return section.get(name)
            else:
                value = getattr(section, name, None)
                if value is not None:
                    return value
        return None

    def _languages(self) -> list[str]:
        if self._languages_override is not None:
            return list(self._languages_override)
        section = self._tesseract_config_section()
        value = self._section_value(section, 'languages', 'language', 'langs')
        if value is None:
            config = self._config
            if isinstance(config, dict):
                value = config.get('languages')
            else:
                value = getattr(config, 'languages', None)
        if value is None:
            return ['eng']
        if isinstance(value, str):
            return [part.strip() for part in value.split(',') if part.strip()] or ['eng']
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value] or ['eng']
        return [str(value)]

    def _dpi(self) -> int:
        if self._dpi_override is not None:
            return int(self._dpi_override)
        section = self._tesseract_config_section()
        value = self._section_value(section, 'dpi', 'resolution', 'render_dpi')
        if value is None:
            return 300
        try:
            return int(value)
        except (TypeError, ValueError):
            return 300

    def _ocr_config(self) -> str:
        if self._config_override is not None:
            return self._config_override
        section = self._tesseract_config_section()
        value = self._section_value(section, 'config', 'ocr_config', 'tesseract_config')
        if value is None:
            return ''
        return str(value)

    def _tesseract_cmd(self) -> str | None:
        override = self._tesseract_cmd_override
        if override is None:
            override = getattr(self, 'tesseract_cmd', None)
        if override is not None:
            return str(override)
        return None

    # ------------------------------------------------------------------
    # Source helpers
    # ------------------------------------------------------------------
    def _is_pdf_source(
        self,
        source: Any,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> bool:
        info_name = ''
        if filename is not None:
            info_name = str(filename)
        elif file_name is not None:
            info_name = str(file_name)
        elif file_path is not None:
            info_name = str(file_path)
        ext = ''
        if '.' in info_name:
            ext = info_name.rsplit('.', 1)[-1].lower()
        ct = content_type
        if ct is None and source is not None:
            ct = getattr(source, 'content_type', None)
            if ct is None and isinstance(source, dict):
                ct = source.get('content_type')
        if isinstance(ct, str) and 'pdf' in ct.lower():
            return True
        if ext == 'pdf':
            return True
        data = self._as_bytes(source)
        return bool(isinstance(data, (bytes, bytearray)) and len(data) >= 4 and data[:4] == b'%PDF')

    def _load_images(
        self,
        source: Any,
        filename: Any = None,
        file_name: Any = None,
        file_path: Any = None,
        content_type: Any = None,
    ) -> list[Any]:
        if self._is_pdf_source(source, filename, file_name, file_path, content_type):
            import pdf2image

            data = self._as_bytes(source)
            if data is not None:
                return list(pdf2image.convert_from_bytes(data, dpi=self._dpi()))
            if isinstance(source, (str, Path)):
                return list(pdf2image.convert_from_path(str(source), dpi=self._dpi()))
            path = file_path or filename or file_name
            if path is not None:
                return list(pdf2image.convert_from_path(str(path), dpi=self._dpi()))
            raise ValueError('Unable to resolve a PDF source for Tesseract rendering')

        # Image handling.
        data = self._as_bytes(source)
        if data is not None:
            try:
                from PIL import Image

                image = Image.open(io.BytesIO(data))
                image.load()
            except (OSError, ValueError):
                pass
            else:
                return [image]
        if hasattr(source, 'save') and hasattr(source, 'size'):
            return [source]
        if isinstance(source, (str, Path)):
            try:
                from PIL import Image

                return [Image.open(str(source))]
            except Exception:
                pass
        raise ValueError('Unable to resolve an image source for Tesseract OCR')

    def _ocr_image(self, image: Any) -> tuple[str, float, list[float]]:
        import pytesseract  # type: ignore[import-untyped]

        cmd = self._tesseract_cmd()
        if cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = cmd

        languages = self._languages()
        lang = ','.join(languages) if languages else None
        config_str = self._ocr_config()

        kwargs: dict[str, Any] = {'output_type': pytesseract.Output.DICT}
        if lang:
            kwargs['lang'] = lang
        if config_str:
            kwargs['config'] = config_str

        data = pytesseract.image_to_data(image, **kwargs)
        if not isinstance(data, dict):
            data = {}
        texts = list(data.get('text', []) or [])
        confs_raw = list(data.get('conf', []) or [])

        words: list[str] = []
        confidences: list[float] = []
        for index, raw_text in enumerate(texts):
            word = '' if raw_text is None else str(raw_text).strip()
            if not word:
                continue
            words.append(word)
            conf_value = None
            if index < len(confs_raw):
                try:
                    conf_value = float(confs_raw[index])
                except (TypeError, ValueError):
                    conf_value = None
            if conf_value is not None and conf_value >= 0:
                confidences.append(conf_value)

        page_text = ' '.join(words)
        if confidences:
            page_confidence = sum(confidences) / len(confidences)
        else:
            page_confidence = 0.0
        return page_text, page_confidence, confidences

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

        # Empty-input safety.
        if self._is_empty_content(source):
            return self._empty_result()

        # Allow explicit overrides from kwargs.
        filename = filename if filename is not None else kwargs.get('filename')
        file_name = file_name if file_name is not None else kwargs.get('file_name')
        file_path = file_path if file_path is not None else kwargs.get('file_path')
        content_type = content_type if content_type is not None else kwargs.get('content_type')

        images = self._load_images(
            source,
            filename=filename,
            file_name=file_name,
            file_path=file_path,
            content_type=content_type,
        )

        text_parts: list[str] = []
        page_confidences: list[float] = []
        all_confidences: list[float] = []
        page_numbers: list[int] = []

        if not images:
            return self._empty_result()

        for page_number, image in enumerate(images, start=1):
            page_text, page_confidence, confidences = self._ocr_image(image)
            text_parts.append(page_text)
            page_numbers.append(page_number)
            page_confidences.append(page_confidence)
            all_confidences.extend(confidences)

        full_text = '\n\n'.join(part for part in text_parts if part.strip()).strip()
        if not full_text:
            full_text = '\n\n'.join(text_parts).strip()

        if all_confidences:
            confidence: Any = sum(all_confidences) / len(all_confidences)
        elif page_confidences:
            confidence = sum(page_confidences) / len(page_confidences)
        else:
            confidence = 0.0

        locators: list[dict[str, Any]] = [{'page': page, 'type': 'ocr'} for page in page_numbers]

        return ReaderResult(
            text=full_text,
            tables=[],
            page_numbers=page_numbers,
            confidence=confidence,
            locators=list(locators),
        )

    # Aliases.
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


__all__ = ['Tesseract', 'TesseractReader']
# Compatibility alias defined at module load (safe).
Tesseract = TesseractReader
