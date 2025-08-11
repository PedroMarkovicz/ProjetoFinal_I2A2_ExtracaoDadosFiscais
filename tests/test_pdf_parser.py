from __future__ import annotations

from pathlib import Path
import pytest

from src.agents.pdf_parser_agent import parse_pdf_prepare
from src.agents.xml_parser_agent import XmlParseError

SAMPLE = Path("data/exemplos/pdf/35240361412110067225650530000913141224108397-nfe.pdf")


def test_parse_pdf_prepare_default_sample():
    if not SAMPLE.exists():
        pytest.skip(f"Sample PDF não encontrado: {SAMPLE}")

    try:
        text, blocks, used_ocr = parse_pdf_prepare(SAMPLE)
    except XmlParseError as e:
        msg = str(e)
        # Skip se não houver camada de texto e OCR não estiver disponível
        if "OCR necessário" in msg or "ERR_NO_TEXT_LAYER" in msg:
            pytest.skip("OCR exigido, mas pytesseract/Pillow/Tesseract não disponíveis.")
        raise

    assert isinstance(text, str) and len(text) > 10
    assert isinstance(used_ocr, bool)
    if used_ocr:
        assert blocks is None
    else:
        assert blocks is None or isinstance(blocks, list)