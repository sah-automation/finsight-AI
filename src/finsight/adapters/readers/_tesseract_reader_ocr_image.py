"""Tesseract OCR adapter implementing :class:`DocumentReader`."""

from __future__ import annotations

from typing import Any


def _ocr_image(self: Any, image: Any) -> Any:
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
