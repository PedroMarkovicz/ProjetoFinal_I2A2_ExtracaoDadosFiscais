# src/agents/pdf_parser_agent.py
from __future__ import annotations
import io
import logging
from dataclasses import dataclass, asdict
import os
import json
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict

import fitz  # PyMuPDF

# OCR (ativado automaticamente quando não houver texto)
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None  # type: ignore

from src.agents.xml_parser_agent import XmlParseError
from src.domain.models import UfEnum, NFePayload  # usaremos nas validações futuras

# .env support
try:
    from dotenv import load_dotenv
    load_dotenv()  # carrega variáveis do arquivo .env se existir
except Exception:
    pass

# LLM / LangChain (multi-provedor)
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except Exception:  # pragma: no cover - import opcional
    ChatPromptTemplate = None  # type: ignore
    JsonOutputParser = None  # type: ignore

# OpenAI
try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - import opcional
    ChatOpenAI = None  # type: ignore

# Google Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - import opcional
    ChatGoogleGenerativeAI = None  # type: ignore

# Groq
try:
    from langchain_groq import ChatGroq
except Exception:  # pragma: no cover - import opcional
    ChatGroq = None  # type: ignore

logger = logging.getLogger(__name__)

# =========================
# Configurações (flags)
# =========================
ENABLE_LLM: bool = True            # ativada: usar LLM para extrair payload
ENABLE_OCR_AUTO: bool = True       # OCR habilitado automaticamente
STRICT_ITEMS: bool = True          # sem item sintético
ENFORCE_EXACT_SUM: bool = True     # soma dos itens deve bater com o total (sem tolerância)


# =========================
# Tipos auxiliares
# =========================
@dataclass
class PageTextBlock:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

@dataclass
class PdfTextExtraction:
    has_text_layer: bool
    plain_text: str
    blocks: List[PageTextBlock]  # blocos com posições (para reconstruir tabela/linhas)

@dataclass
class Word:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


# =========================
# Utilidades
# =========================
def _normalize_ptbr_number(s: str) -> str:
    """Converte número PT-BR para formato com ponto decimal."""
    s = (s or '').strip()
    s = s.replace('\u00A0', ' ').replace('R$', '').replace(' ', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    return s

def _only_digits(s: str) -> str:
    return ''.join(ch for ch in (s or '') if ch.isdigit())

def _is_valid_uf(token: str) -> bool:
    try:
        return token.upper() in {u.value for u in UfEnum}
    except Exception:
        return False


# =========================
# Extração por texto (PyMuPDF)
# =========================
def _extract_text_blocks(pdf_path: Path) -> PdfTextExtraction:
    if not pdf_path.exists():
        raise XmlParseError(f"Arquivo PDF não encontrado: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise XmlParseError(f"Falha ao abrir PDF: {e}")

    all_text_parts: List[str] = []
    blocks: List[PageTextBlock] = []

    try:
        for pno, page in enumerate(doc, start=1):
            txt = page.get_text('text') or ''
            if txt:
                all_text_parts.append(txt)

            for b in page.get_text('blocks') or []:
                if len(b) >= 5 and isinstance(b[4], str) and b[4].strip():
                    blocks.append(PageTextBlock(
                        page=pno,
                        x0=float(b[0]), y0=float(b[1]), x1=float(b[2]), y1=float(b[3]),
                        text=b[4],
                    ))

        plain_text = '\n'.join(all_text_parts).strip()
        has_text = len(plain_text) >= 20
        return PdfTextExtraction(has_text_layer=has_text, plain_text=plain_text, blocks=blocks)

    except Exception as e:
        logger.exception('Falha na extração de texto/blocks')
        raise XmlParseError(f'Falha ao extrair texto do PDF: {e}')


# =========================
# OCR (fallback automático)
# =========================
def _rasterize_page_to_png(page: fitz.Page, scale: float = 2.0) -> bytes:
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes('png')

def _ocr_png_bytes(png_bytes: bytes) -> str:
    if pytesseract is None or Image is None:
        raise XmlParseError('OCR necessário, mas pytesseract/Pillow não estão disponíveis (ERR_NO_TEXT_LAYER).')
    try:
        img = Image.open(io.BytesIO(png_bytes))
        return pytesseract.image_to_string(img, lang='por') or ''
    except Exception as e:
        logger.exception('Falha no OCR de uma página')
        raise XmlParseError(f'Falha ao realizar OCR: {e}')

def _extract_text_via_ocr(pdf_path: Path) -> str:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise XmlParseError(f'Falha ao abrir PDF para OCR: {e}')

    texts: List[str] = []
    for page in doc:
        png = _rasterize_page_to_png(page, scale=2.0)
        ocr_text = _ocr_png_bytes(png)
        if ocr_text:
            texts.append(ocr_text)

    out = '\n'.join(texts).strip()
    if not out:
        raise XmlParseError('OCR não retornou texto (ERR_NO_TEXT_LAYER).')
    return out


# =========================
# Word-level extraction
# =========================
def _extract_words(pdf_path: Path) -> List[Word]:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise XmlParseError(f'Falha ao abrir PDF: {e}')
    words: List[Word] = []
    for pno, page in enumerate(doc, start=1):
        try:
            for w in page.get_text('words'):
                if len(w) >= 5 and isinstance(w[4], str) and w[4].strip():
                    words.append(Word(pno, float(w[0]), float(w[1]), float(w[2]), float(w[3]), w[4]))
        except Exception:
            continue
    return words

# =========================
# Heuristics using words
# =========================
def _find_chave_acesso(text: str) -> Optional[str]:
    import re
    m = re.search(r'(?<!\d)(\d{44})(?!\d)', text)
    if m:
        return m.group(1)
    cleaned = ''.join(ch for ch in text if ch.isdigit())
    if len(cleaned) >= 44:
        for i in range(0, len(cleaned)-43):
            chunk = cleaned[i:i+44]
            if chunk.isdigit():
                return chunk
    return None

def _neighbors(words: List[Word], center_word: Word, radius_x: float = 150, radius_y: float = 20) -> List[Word]:
    cx = (center_word.x0 + center_word.x1)/2
    cy = (center_word.y0 + center_word.y1)/2
    out = []
    for w in words:
        wx = (w.x0 + w.x1)/2
        wy = (w.y0 + w.y1)/2
        if abs(wx - cx) <= radius_x and abs(wy - cy) <= radius_y and w.page == center_word.page:
            out.append(w)
    return out

def _find_valor_total(words: List[Word], fallback_text: str) -> Optional[float]:
    import re
    candidates: List[float] = []
    for w in words:
        if w.text.upper() == 'TOTAL':
            neigh = _neighbors(words, w, radius_x=300, radius_y=15)
            nums = []
            for n in neigh:
                s_norm = _normalize_ptbr_number(n.text)
                if re.match(r'^\d{1,3}(\.\d{3})*(,\d{2})?$', n.text) or re.match(r'^\d+(\.\d+)?$', s_norm):
                    try:
                        val = float(_normalize_ptbr_number(n.text))
                        nums.append(val)
                    except:
                        pass
            if nums:
                candidates.append(max(nums))
    if not candidates:
        m = re.search(r'(VALOR\s+TOTAL(?:\s+DA\s+NOTA)?|TOTAL\s+DA\s+NFC-?E)[^\d]{0,20}([\d\.\,]+)', fallback_text, flags=re.IGNORECASE)
        if m:
            try:
                return float(_normalize_ptbr_number(m.group(2)))
            except:
                return None
    if candidates:
        return max(candidates)
    return None

def _find_ufs(words: List[Word], fallback_text: str) -> Tuple[Optional[str], Optional[str]]:
    emit_uf = None
    dest_uf = None
    keywords_emit = {'EMITENTE','REMETENTE'}
    keywords_dest = {'DESTINATÁRIO','DESTINATARIO','CONSUMIDOR'}
    for w in words:
        token = w.text.upper()
        if token in keywords_emit and emit_uf is None:
            neigh = _neighbors(words, w, radius_x=300, radius_y=40)
            for n in neigh:
                if _is_valid_uf(n.text):
                    emit_uf = n.text.upper()
                    break
        if token in keywords_dest and dest_uf is None:
            neigh = _neighbors(words, w, radius_x=300, radius_y=40)
            for n in neigh:
                if _is_valid_uf(n.text):
                    dest_uf = n.text.upper()
                    break
    if emit_uf is None or dest_uf is None:
        import re
        ufs = re.findall(r'\b([A-Z]{2})\b', fallback_text)
        ufs = [u for u in ufs if _is_valid_uf(u)]
        if len(ufs) >= 2:
            if emit_uf is None: emit_uf = ufs[0]
            if dest_uf is None: dest_uf = ufs[1] if ufs[1]!=emit_uf else (ufs[2] if len(ufs)>2 else None)
    return emit_uf, dest_uf

def _find_cfops(words: List[Word]) -> List[str]:
    cfops: List[str] = []
    headers = [w for w in words if w.text.upper() == 'CFOP']
    if not headers:
        return cfops
    h = sorted(headers, key=lambda w:(w.page,w.y0,w.x0))[0]
    hx = (h.x0 + h.x1)/2
    for w in words:
        if w.page != h.page: 
            continue
        wy_center = (w.y0 + w.y1)/2
        if wy_center <= h.y1 + 5:
            continue
        wx_center = (w.x0 + w.x1)/2
        if abs(wx_center - hx) <= 25:
            s = _only_digits(w.text)
            if len(s)==4 and s[0] in '1256':
                cfops.append(s)
    seen=set(); out=[]
    for c in cfops:
        if c not in seen:
            out.append(c); seen.add(c)
    return out


# =========================
# Orquestrador (ainda sem montar NFePayload)
# =========================
def parse_pdf_prepare(pdf_path: str | Path) -> Tuple[str, Optional[List[PageTextBlock]], bool]:
    path = Path(pdf_path)
    ext = path.suffix.lower()
    if ext != '.pdf':
        raise XmlParseError(f'Extensão não suportada para este parser: {ext}')
    extraction = _extract_text_blocks(path)
    if not extraction.has_text_layer and ENABLE_OCR_AUTO:
        logger.info('PDF sem camada de texto. Ativando OCR automático.')
        ocr_text = _extract_text_via_ocr(path)
        return (ocr_text, None, True)
    return (extraction.plain_text, extraction.blocks, False)


# =========================
# Placeholders para o Passo 2
# =========================
def _ensure_llm_available(provider: str) -> None:
    if ChatPromptTemplate is None or JsonOutputParser is None:
        raise XmlParseError('Componentes básicos do LangChain indisponíveis.')
    p = (provider or 'openai').lower()
    if p == 'openai' and ChatOpenAI is None:
        raise XmlParseError('langchain-openai não instalado. Adicione ao requirements.txt e sincronize.')
    if p == 'gemini' and ChatGoogleGenerativeAI is None:
        raise XmlParseError('langchain-google-genai não instalado. Adicione ao requirements.txt e sincronize.')
    if p == 'groq' and ChatGroq is None:
        raise XmlParseError('langchain-groq não instalado. Adicione ao requirements.txt e sincronize.')


def _get_llm() -> Any:
    """Cria o cliente de LLM via LangChain conforme provedor.

    Variáveis:
    - PDF_LLM_PROVIDER: openai | gemini | groq (default: openai)
    - PDF_LLM_MODEL: nome do modelo (default depende do provedor)
    - PDF_LLM_TEMPERATURE: float (default: 0.0)
    - OPENAI_API_KEY | GOOGLE_API_KEY | GROQ_API_KEY conforme o provedor
    """
    provider = os.getenv('PDF_LLM_PROVIDER', 'openai').lower()
    try:
        temperature = float(os.getenv('PDF_LLM_TEMPERATURE', '0'))
    except Exception:
        temperature = 0.0

    defaults = {
        'openai': 'gpt-4o-mini',
        'gemini': 'gemini-1.5-pro',
        'groq': 'llama-3.1-70b-versatile',
    }
    model = os.getenv('PDF_LLM_MODEL', defaults.get(provider, 'gpt-4o-mini'))

    _ensure_llm_available(provider)

    if provider == 'openai':
        if not os.getenv('OPENAI_API_KEY'):
            raise XmlParseError('OPENAI_API_KEY não configurada.')
        return ChatOpenAI(model=model, temperature=temperature)

    if provider == 'gemini':
        if not os.getenv('GOOGLE_API_KEY'):
            raise XmlParseError('GOOGLE_API_KEY não configurada.')
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    if provider == 'groq':
        if not os.getenv('GROQ_API_KEY'):
            raise XmlParseError('GROQ_API_KEY não configurada.')
        return ChatGroq(model=model, temperature=temperature)

    raise XmlParseError(f"Provedor LLM desconhecido: {provider}")


def _build_prompt() -> Any:
    # _get_llm valida o provider e dependências
    ufs = ', '.join(sorted(u.value for u in UfEnum))
    schema_hint = {
        "type": "object",
        "properties": {
            "cfop": {"type": "string", "pattern": "^\\d{4}$"},
            "emitente_uf": {"type": "string", "enum": [u.value for u in UfEnum]},
            "destinatario_uf": {"type": "string", "enum": [u.value for u in UfEnum]},
            "valor_total": {"type": "number"},
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "xProd": {"type": "string"},
                        "NCM": {"type": ["string", "null"], "pattern": "^\\d{8}$"},
                        "vProd": {"type": ["number", "string"]},
                    },
                    "required": ["xProd", "vProd"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["cfop", "emitente_uf", "destinatario_uf", "valor_total", "itens"],
        "additionalProperties": False
    }

    system = (
        "Você é um extrator de dados de DANFE (NF-e PDF) extremamente rigoroso. "
        "Extraia APENAS os campos solicitados e retorne um JSON VÁLIDO, sem comentários, sem markdown. "
        "Regras: "
        f"- 'cfop' deve ser string com 4 dígitos.\n"
        f"- 'emitente_uf' e 'destinatario_uf' devem ser uma destas UFs: {ufs}.\n"
        "- 'valor_total' número com ponto decimal.\n"
        "- 'itens' é uma lista com ao menos 1 item, cada item com: 'xProd' (string), 'NCM' (8 dígitos ou null), 'vProd' (número).\n"
        "- Se um valor não existir no documento, use null (quando permitido) ou uma string vazia para 'xProd'.\n"
        "- NUNCA inclua campos extras.\n"
        "- Saída: APENAS o JSON no formato solicitado."
    )

    template = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", (
            "Documento DANFE (texto extraído a seguir).\n"
            "Por favor, gere o JSON final no formato especificado:\n\n"
            "Esquema (apenas referência de formato): {schema}\n\n"
            "Texto:\n{document}\n\n"
            "Responda somente com o JSON."
        )),
    ])
    return template, schema_hint


def _extract_with_llm(plain_text: str) -> NFePayload:
    llm = _get_llm()
    template, schema_hint = _build_prompt()
    parser = JsonOutputParser()
    chain = template | llm | parser
    try:
        result = chain.invoke({
            'document': plain_text[:150000],  # proteção leve de contexto
            'schema': json.dumps(schema_hint, ensure_ascii=False),
        })
        if not isinstance(result, dict):
            raise ValueError('LLM não retornou JSON object.')
        # Sanitização leve antes de validar
        sanitized = _sanitize_llm_payload(result)
        # Validação rigorosa via Pydantic
        payload = NFePayload.model_validate(sanitized)
        return payload
    except Exception as e:
        logger.exception('Falha ao extrair payload com LLM')
        raise XmlParseError(f'Falha na extração via LLM: {e}')


def _build_payload_from_text(text: str,
                             blocks: Optional[List[PageTextBlock]]) -> Any:
    if not ENABLE_LLM:
        raise XmlParseError('LLM desativada. Ative ENABLE_LLM para usar a extração por modelo de linguagem.')
    if not text or len(text.strip()) < 20:
        raise XmlParseError('Texto insuficiente para extração via LLM.')
    return _extract_with_llm(text)


def parse_pdf(pdf_path: str | Path) -> NFePayload:
    text, blocks, used_ocr = parse_pdf_prepare(pdf_path)
    logger.info('Preparação PDF concluída | used_ocr=%s | text_len=%d | blocks=%s',
                used_ocr, len(text or ''), 'yes' if blocks else 'no')
    return _build_payload_from_text(text, blocks)


# Verificação defensiva: garantir que o módulo correto do PyMuPDF esteja carregado
def _assert_pymupdf_ok() -> None:
    if not hasattr(fitz, 'open'):
        raise XmlParseError(
            "O módulo 'fitz' importado não é o do PyMuPDF. Desinstale o pacote 'fitz' (uv pip uninstall -y fitz) "
            "e mantenha apenas 'PyMuPDF' no requirements."
        )

# Chame a verificação no início dos fluxos que usam PyMuPDF
_assert_pymupdf_ok()


def _sanitize_llm_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza o dicionário retornado pela LLM para aderir aos modelos.

    - cfop: mantém somente dígitos; tenta limitar para 4 caracteres
    - UFs: caixa alta; se inválida, mantém como está para falhar claramente
    - valor_total: converte vírgula para ponto
    - itens: garante dict; xProd obrigatório com fallback; NCM= None se não for 8 dígitos; vProd normalizado
    """
    out: Dict[str, Any] = {}
    # cfop
    cfop_val = str(raw.get('cfop', '') or '')
    cfop_digits = ''.join(ch for ch in cfop_val if ch.isdigit())
    if len(cfop_digits) >= 4:
        cfop_val = cfop_digits[:4]
    out['cfop'] = cfop_val

    # UFs
    emit_uf = (raw.get('emitente_uf') or '')
    dest_uf = (raw.get('destinatario_uf') or '')
    out['emitente_uf'] = str(emit_uf).upper() if isinstance(emit_uf, str) else emit_uf
    out['destinatario_uf'] = str(dest_uf).upper() if isinstance(dest_uf, str) else dest_uf

    # valor_total
    vtot = raw.get('valor_total')
    if isinstance(vtot, str):
        try:
            vtot = float(_normalize_ptbr_number(vtot))
        except Exception:
            pass
    out['valor_total'] = vtot

    # itens
    items_in = raw.get('itens') or []
    norm_items: List[Dict[str, Any]] = []
    for item in items_in if isinstance(items_in, list) else []:
        itm = item if isinstance(item, dict) else {}
        xprod = itm.get('xProd')
        if not isinstance(xprod, str) or not xprod.strip():
            xprod = 'Item'
        ncm = itm.get('NCM')
        if isinstance(ncm, str):
            ncm_digits = ''.join(ch for ch in ncm if ch.isdigit())
            ncm = ncm_digits if len(ncm_digits) == 8 else None
        else:
            ncm = None if ncm not in (None, '') else None
        vprod = itm.get('vProd')
        if isinstance(vprod, str):
            try:
                vprod = _normalize_ptbr_number(vprod)
            except Exception:
                pass
        norm_items.append({'xProd': xprod, 'NCM': ncm, 'vProd': vprod})
    if not norm_items:
        # Minimiza falha criando um item sintético com valor 0 se LLM não retornou nada
        norm_items = [{'xProd': 'Item', 'NCM': None, 'vProd': 0}]
    out['itens'] = norm_items

    return out


# =========================
# Diagnostics for testing before payload
# =========================
def analyze_fields(pdf_path: str | Path) -> Dict[str, Any]:
    text, blocks, used_ocr = parse_pdf_prepare(pdf_path)
    words = _extract_words(Path(pdf_path)) if not used_ocr else []
    out: Dict[str, Any] = {
        'used_ocr': used_ocr,
        'text_len': len(text or ''),
        'blocks': 0 if blocks is None else len(blocks),
    }
    out['chave_acesso'] = _find_chave_acesso(text) or '-'
    out['valor_total_detected'] = _find_valor_total(words, text)
    out['cfops_detected'] = _find_cfops(words)
    emit, dest = _find_ufs(words, text)
    out['emitente_uf'] = emit
    out['destinatario_uf'] = dest
    return out
