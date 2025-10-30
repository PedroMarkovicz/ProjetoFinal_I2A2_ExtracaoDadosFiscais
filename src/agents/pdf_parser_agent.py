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

def _normalize_ptbr_number_safe(value: Any) -> Any:
    """Normaliza números com tratamento de erros, retorna None se falhar."""
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(_normalize_ptbr_number(value))
        except Exception:
            return None
    return None

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
            "emitente": {
                "type": "object",
                "properties": {
                    "xNome": {"type": "string", "description": "Razão social do emitente"},
                    "CNPJ": {"type": "string", "pattern": "^\\d{14}$", "description": "CNPJ (14 dígitos)"},
                    "IE": {"type": ["string", "null"], "description": "Inscrição Estadual"},
                    "uf": {"type": "string", "enum": [u.value for u in UfEnum], "description": "UF do emitente"},
                    "xMun": {"type": ["string", "null"], "description": "Município"},
                    "xBairro": {"type": ["string", "null"], "description": "Bairro"},
                    "xLgr": {"type": ["string", "null"], "description": "Logradouro (rua/avenida)"},
                    "nro": {"type": ["string", "null"], "description": "Número"},
                    "CEP": {"type": ["string", "null"], "pattern": "^\\d{8}$", "description": "CEP (8 dígitos)"},
                    "fone": {"type": ["string", "null"], "description": "Telefone"}
                },
                "required": ["xNome", "CNPJ", "uf"],
                "additionalProperties": False
            },
            "destinatario": {
                "type": "object",
                "properties": {
                    "xNome": {"type": "string", "description": "Razão social/nome do destinatário"},
                    "CNPJ": {"type": ["string", "null"], "pattern": "^\\d{14}$", "description": "CNPJ (14 dígitos) - pessoa jurídica"},
                    "CPF": {"type": ["string", "null"], "pattern": "^\\d{11}$", "description": "CPF (11 dígitos) - pessoa física"},
                    "IE": {"type": ["string", "null"], "description": "Inscrição Estadual do DESTINATÁRIO (localizada na seção DESTINATÁRIO/REMETENTE, geralmente ao lado do campo UF)"},
                    "indIEDest": {"type": ["string", "null"], "description": "Indicador IE (1=Contribuinte, 2=Isento, 9=Não Contribuinte)"},
                    "uf": {"type": "string", "enum": [u.value for u in UfEnum], "description": "UF do destinatário"},
                    "xMun": {"type": ["string", "null"], "description": "Município"},
                    "xBairro": {"type": ["string", "null"], "description": "Bairro"},
                    "xLgr": {"type": ["string", "null"], "description": "Logradouro (rua/avenida)"},
                    "nro": {"type": ["string", "null"], "description": "Número"},
                    "CEP": {"type": ["string", "null"], "pattern": "^\\d{8}$", "description": "CEP (8 dígitos)"},
                    "fone": {"type": ["string", "null"], "description": "Telefone"}
                },
                "required": ["xNome", "uf"],
                "additionalProperties": False
            },
            "valor_total": {"type": "number"},
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "xProd": {"type": "string", "description": "Descrição do produto"},
                        "NCM": {"type": ["string", "null"], "pattern": "^\\d{8}$", "description": "Código NCM (8 dígitos)"},
                        "CEST": {"type": ["string", "null"], "pattern": "^\\d{7}$", "description": "Código CEST de Substituição Tributária (7 dígitos, se presente)"},
                        "vProd": {"type": ["number", "string"], "description": "Valor total do produto"},
                        "qCom": {"type": ["number", "string", "null"], "description": "Quantidade comercial"},
                        "vUnCom": {"type": ["number", "string", "null"], "description": "Valor unitário comercial"},
                        "uCom": {"type": ["string", "null"], "description": "Unidade comercial (ex: UN, KG, MT)"},
                        "cProd": {"type": ["string", "null"], "description": "Código do produto"},
                        "impostos": {
                            "type": ["object", "null"],
                            "description": "Impostos do item (ICMS, IPI, PIS, COFINS) - extrair se disponível no PDF",
                            "properties": {
                                "icms": {
                                    "type": "object",
                                    "properties": {
                                        "CST": {"type": ["string", "null"], "description": "CST ICMS (2 dígitos) - para Regime Normal"},
                                        "CSOSN": {"type": ["string", "null"], "description": "CSOSN (3 dígitos) - para Simples Nacional. Usar CST OU CSOSN, não ambos"},
                                        "orig": {"type": ["string", "null"], "description": "Origem (0-8)"},
                                        "vBC": {"type": ["number", "string", "null"], "description": "Base de Cálculo ICMS"},
                                        "pICMS": {"type": ["number", "string", "null"], "description": "Alíquota ICMS (%)"},
                                        "vICMS": {"type": ["number", "string", "null"], "description": "Valor ICMS"}
                                    }
                                },
                                "ipi": {
                                    "type": ["object", "null"],
                                    "properties": {
                                        "CST": {"type": ["string", "null"], "description": "CST IPI (2 dígitos)"},
                                        "vBC": {"type": ["number", "string", "null"], "description": "Base de Cálculo IPI"},
                                        "pIPI": {"type": ["number", "string", "null"], "description": "Alíquota IPI (%)"},
                                        "vIPI": {"type": ["number", "string", "null"], "description": "Valor IPI"}
                                    }
                                },
                                "pis": {
                                    "type": "object",
                                    "properties": {
                                        "CST": {"type": ["string", "null"], "description": "CST PIS (2 dígitos)"},
                                        "vBC": {"type": ["number", "string", "null"], "description": "Base de Cálculo PIS"},
                                        "pPIS": {"type": ["number", "string", "null"], "description": "Alíquota PIS (%)"},
                                        "vPIS": {"type": ["number", "string", "null"], "description": "Valor PIS"}
                                    }
                                },
                                "cofins": {
                                    "type": "object",
                                    "properties": {
                                        "CST": {"type": ["string", "null"], "description": "CST COFINS (2 dígitos)"},
                                        "vBC": {"type": ["number", "string", "null"], "description": "Base de Cálculo COFINS"},
                                        "pCOFINS": {"type": ["number", "string", "null"], "description": "Alíquota COFINS (%)"},
                                        "vCOFINS": {"type": ["number", "string", "null"], "description": "Valor COFINS"}
                                    }
                                }
                            }
                        }
                    },
                    "required": ["xProd", "vProd"],
                    "additionalProperties": False
                }
            },
            "totais_impostos": {
                "type": ["object", "null"],
                "description": "Totais consolidados de impostos (geralmente no rodapé da nota)",
                "properties": {
                    "vBC": {"type": ["number", "string", "null"], "description": "Total Base de Cálculo ICMS"},
                    "vICMS": {"type": ["number", "string", "null"], "description": "Total ICMS"},
                    "vIPI": {"type": ["number", "string", "null"], "description": "Total IPI"},
                    "vPIS": {"type": ["number", "string", "null"], "description": "Total PIS"},
                    "vCOFINS": {"type": ["number", "string", "null"], "description": "Total COFINS"}
                }
            }
        },
        "required": ["cfop", "emitente", "destinatario", "valor_total", "itens"],
        "additionalProperties": False
    }

    system = (
        "Você é um extrator de dados de DANFE (NF-e PDF) extremamente rigoroso. "
        "Extraia APENAS os campos solicitados e retorne um JSON VÁLIDO, sem comentários, sem markdown. "
        "ATENÇÃO: A seção DESTINATÁRIO/REMETENTE contém campos específicos do destinatário. "
        "NÃO confunda a Inscrição Estadual (IE) do EMITENTE com a IE do DESTINATÁRIO. São campos separados! "
        "Regras: "
        f"- 'cfop' deve ser string com 4 dígitos.\n"
        f"- 'emitente' é um objeto com dados do emissor:\n"
        f"  - 'xNome': razão social (obrigatório)\n"
        f"  - 'CNPJ': 14 dígitos (obrigatório)\n"
        f"  - 'IE': inscrição estadual (opcional, use null se não encontrar)\n"
        f"  - 'uf': estado do emitente - uma destas UFs: {ufs} (obrigatório)\n"
        f"  - 'xMun': município (opcional)\n"
        f"  - 'xBairro': bairro (opcional)\n"
        f"  - 'xLgr': logradouro/rua (opcional)\n"
        f"  - 'nro': número do endereço (opcional)\n"
        f"  - 'CEP': 8 dígitos (opcional)\n"
        f"  - 'fone': telefone (opcional)\n"
        f"- 'destinatario' é um objeto com dados do receptor:\n"
        f"  - 'xNome': razão social ou nome (obrigatório)\n"
        f"  - 'CNPJ': 14 dígitos OU null (pessoa jurídica)\n"
        f"  - 'CPF': 11 dígitos OU null (pessoa física)\n"
        f"  - IMPORTANTE: Deve ter CPF OU CNPJ, nunca ambos! Se for pessoa física, CNPJ=null e CPF com 11 dígitos. Se jurídica, CPF=null e CNPJ com 14 dígitos.\n"
        f"  - 'IE': inscrição estadual do DESTINATÁRIO (opcional, geralmente aparece na seção 'DESTINATÁRIO/REMETENTE' ao lado ou próximo do campo UF)\n"
        f"  - 'indIEDest': indicador IE 1-9 (opcional)\n"
        f"  - 'uf': estado do destinatário - uma destas UFs: {ufs} (obrigatório)\n"
        f"  - 'xMun': município (opcional)\n"
        f"  - 'xBairro': bairro (opcional)\n"
        f"  - 'xLgr': logradouro/rua (opcional)\n"
        f"  - 'nro': número do endereço (opcional)\n"
        f"  - 'CEP': 8 dígitos (opcional)\n"
        f"  - 'fone': telefone (opcional)\n"
        "- 'valor_total' número com ponto decimal.\n"
        "- 'itens' é uma lista com ao menos 1 item. Cada item deve conter:\n"
        "  - 'xProd': descrição do produto (obrigatório)\n"
        "  - 'NCM': código NCM com 8 dígitos (opcional, use null se não encontrar)\n"
        "  - 'vProd': valor total do produto (obrigatório)\n"
        "  - 'qCom': quantidade comercial (opcional, geralmente aparece na coluna 'Qtde' ou 'Quantidade')\n"
        "  - 'vUnCom': valor unitário comercial (opcional, geralmente aparece na coluna 'Valor Unit.' ou 'Vlr. Unit.')\n"
        "  - 'uCom': unidade comercial (opcional, ex: UN, KG, MT, PC - geralmente aparece na coluna 'Unid.' ou 'UN')\n"
        "  - 'cProd': código do produto (opcional, geralmente aparece na coluna 'Código' ou antes da descrição)\n"
        "  - 'impostos': objeto com impostos do item (opcional, extrair se disponível no PDF):\n"
        "    - 'icms': CST, orig, vBC, pICMS, vICMS (buscar na tabela de impostos por item)\n"
        "    - 'ipi': CST, vBC, pIPI, vIPI (opcional, nem todas notas têm IPI)\n"
        "    - 'pis': CST, vBC, pPIS, vPIS (opcional, muitos PDFs não mostram PIS por item)\n"
        "    - 'cofins': CST, vBC, pCOFINS, vCOFINS (opcional, muitos PDFs não mostram COFINS por item)\n"
        "    ATENÇÃO: Muitos PDFs NÃO mostram impostos detalhados por item. Neste caso, deixe 'impostos': null para o item.\n"
        "    Se o PDF mostrar apenas ICMS e IPI, inclua apenas esses campos e deixe 'pis' e 'cofins' como null ou omita-os.\n"
        "- 'totais_impostos': objeto com totais de impostos (opcional, buscar no rodapé da nota):\n"
        "  - 'vBC': Total Base de Cálculo ICMS\n"
        "  - 'vICMS': Total ICMS\n"
        "  - 'vIPI': Total IPI\n"
        "  - 'vPIS': Total PIS\n"
        "  - 'vCOFINS': Total COFINS\n"
        "  Se os totais de impostos não estiverem visíveis no PDF, use null.\n"
        "- Se um valor opcional não existir no documento, use null.\n"
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
    - emitente: objeto completo com dados do emissor (razão social, CNPJ, endereço, etc.)
    - destinatario: objeto completo com dados do receptor (razão social, CNPJ/CPF, endereço, etc.)
    - valor_total: converte vírgula para ponto
    - itens: garante dict; xProd obrigatório com fallback; NCM=None se não for 8 dígitos; vProd normalizado
      Novos campos (Etapa 3): qCom, vUnCom (normalizados); uCom (uppercase); cProd (sanitizado)
    """
    out: Dict[str, Any] = {}
    # cfop
    cfop_val = str(raw.get('cfop', '') or '')
    cfop_digits = ''.join(ch for ch in cfop_val if ch.isdigit())
    if len(cfop_digits) >= 4:
        cfop_val = cfop_digits[:4]
    out['cfop'] = cfop_val

    # Emitente completo
    emitente_raw = raw.get('emitente') or {}
    if isinstance(emitente_raw, dict):
        emitente_sanitized: Dict[str, Any] = {}
        # xNome (obrigatório)
        emitente_sanitized['xNome'] = str(emitente_raw.get('xNome', '')).strip() or 'EMITENTE NAO IDENTIFICADO'
        # CNPJ (obrigatório) - apenas dígitos, limitado a 14
        cnpj_raw = str(emitente_raw.get('CNPJ', '') or '')
        cnpj_digits = ''.join(ch for ch in cnpj_raw if ch.isdigit())
        # Limitar a 14 dígitos (pegar os últimos 14 se houver mais)
        emitente_sanitized['CNPJ'] = cnpj_digits[-14:] if len(cnpj_digits) >= 14 else cnpj_digits
        # IE (opcional)
        ie_raw = emitente_raw.get('IE')
        emitente_sanitized['IE'] = str(ie_raw).strip().upper() if ie_raw and str(ie_raw).strip() else None
        # UF (obrigatório)
        uf_raw = emitente_raw.get('uf', '')
        emitente_sanitized['uf'] = str(uf_raw).upper() if isinstance(uf_raw, str) else uf_raw
        # Campos opcionais de endereço
        emitente_sanitized['xMun'] = str(emitente_raw.get('xMun', '') or '').strip() or None
        emitente_sanitized['xBairro'] = str(emitente_raw.get('xBairro', '') or '').strip() or None
        emitente_sanitized['xLgr'] = str(emitente_raw.get('xLgr', '') or '').strip() or None
        emitente_sanitized['nro'] = str(emitente_raw.get('nro', '') or '').strip() or None
        # CEP (opcional) - apenas dígitos
        cep_raw = emitente_raw.get('CEP')
        if cep_raw:
            cep_digits = ''.join(ch for ch in str(cep_raw) if ch.isdigit())
            emitente_sanitized['CEP'] = cep_digits if len(cep_digits) == 8 else None
        else:
            emitente_sanitized['CEP'] = None
        # Telefone (opcional) - apenas dígitos
        fone_raw = emitente_raw.get('fone')
        if fone_raw:
            emitente_sanitized['fone'] = ''.join(ch for ch in str(fone_raw) if ch.isdigit()) or None
        else:
            emitente_sanitized['fone'] = None

        out['emitente'] = emitente_sanitized
    else:
        # Fallback se emitente não for um dicionário
        out['emitente'] = {
            'xNome': 'EMITENTE NAO IDENTIFICADO',
            'CNPJ': '',
            'IE': None,
            'uf': '',
            'xMun': None,
            'xBairro': None,
            'xLgr': None,
            'nro': None,
            'CEP': None,
            'fone': None,
        }

    # Destinatario completo
    destinatario_raw = raw.get('destinatario') or {}
    if isinstance(destinatario_raw, dict):
        dest_sanitized: Dict[str, Any] = {}
        # xNome (obrigatório)
        dest_sanitized['xNome'] = str(destinatario_raw.get('xNome', '')).strip() or 'DESTINATARIO NAO IDENTIFICADO'

        # CNPJ ou CPF (mutuamente exclusivo)
        cnpj_raw = destinatario_raw.get('CNPJ')
        cpf_raw = destinatario_raw.get('CPF')

        # Extrair apenas dígitos de ambos
        cnpj_digits = ''.join(ch for ch in str(cnpj_raw) if ch.isdigit()) if cnpj_raw and str(cnpj_raw).strip() else ''
        cpf_digits = ''.join(ch for ch in str(cpf_raw) if ch.isdigit()) if cpf_raw and str(cpf_raw).strip() else ''

        # Limitar ao tamanho correto
        cnpj_digits = cnpj_digits[-14:] if len(cnpj_digits) >= 14 else cnpj_digits
        cpf_digits = cpf_digits[-11:] if len(cpf_digits) >= 11 else cpf_digits

        # Decidir qual usar baseado no tamanho e presença
        if cnpj_digits and len(cnpj_digits) >= 11:
            # Se tem 14 dígitos, é CNPJ. Se tem 11-13, assumir CNPJ também (dados incompletos)
            if len(cnpj_digits) == 14:
                dest_sanitized['CNPJ'] = cnpj_digits
                dest_sanitized['CPF'] = None
            elif len(cnpj_digits) == 11 and not cpf_digits:
                # Pode ser CPF, mas veio no campo CNPJ
                dest_sanitized['CPF'] = cnpj_digits
                dest_sanitized['CNPJ'] = None
            else:
                # 12-13 dígitos ou outros casos: assumir CNPJ incompleto
                dest_sanitized['CNPJ'] = cnpj_digits
                dest_sanitized['CPF'] = None
        elif cpf_digits and len(cpf_digits) == 11:
            # CPF válido
            dest_sanitized['CPF'] = cpf_digits
            dest_sanitized['CNPJ'] = None
        else:
            # Fallback: tentar qualquer número que temos
            if cnpj_digits:
                dest_sanitized['CNPJ'] = cnpj_digits
                dest_sanitized['CPF'] = None
            elif cpf_digits:
                dest_sanitized['CPF'] = cpf_digits
                dest_sanitized['CNPJ'] = None
            else:
                # Último recurso: criar um CNPJ dummy para não quebrar
                dest_sanitized['CNPJ'] = '00000000000000'
                dest_sanitized['CPF'] = None

        # IE (opcional)
        ie_raw = destinatario_raw.get('IE')
        dest_sanitized['IE'] = str(ie_raw).strip().upper() if ie_raw and str(ie_raw).strip() else None

        # indIEDest (opcional)
        ind_ie_raw = destinatario_raw.get('indIEDest')
        dest_sanitized['indIEDest'] = str(ind_ie_raw).strip() if ind_ie_raw and str(ind_ie_raw).strip() else None

        # UF (obrigatório)
        uf_raw = destinatario_raw.get('uf', '')
        dest_sanitized['uf'] = str(uf_raw).upper() if isinstance(uf_raw, str) else uf_raw

        # Campos opcionais de endereço
        dest_sanitized['xMun'] = str(destinatario_raw.get('xMun', '') or '').strip() or None
        dest_sanitized['xBairro'] = str(destinatario_raw.get('xBairro', '') or '').strip() or None
        dest_sanitized['xLgr'] = str(destinatario_raw.get('xLgr', '') or '').strip() or None
        dest_sanitized['nro'] = str(destinatario_raw.get('nro', '') or '').strip() or None

        # CEP (opcional) - apenas dígitos
        cep_raw = destinatario_raw.get('CEP')
        if cep_raw:
            cep_digits = ''.join(ch for ch in str(cep_raw) if ch.isdigit())
            dest_sanitized['CEP'] = cep_digits if len(cep_digits) == 8 else None
        else:
            dest_sanitized['CEP'] = None

        # Telefone (opcional) - apenas dígitos
        fone_raw = destinatario_raw.get('fone')
        if fone_raw:
            dest_sanitized['fone'] = ''.join(ch for ch in str(fone_raw) if ch.isdigit()) or None
        else:
            dest_sanitized['fone'] = None

        out['destinatario'] = dest_sanitized
    else:
        # Fallback se destinatario não for um dicionário
        out['destinatario'] = {
            'xNome': 'DESTINATARIO NAO IDENTIFICADO',
            'CNPJ': None,
            'CPF': None,
            'IE': None,
            'indIEDest': None,
            'uf': '',
            'xMun': None,
            'xBairro': None,
            'xLgr': None,
            'nro': None,
            'CEP': None,
            'fone': None,
        }

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

        # Novos campos (Etapa 3)
        qcom = itm.get('qCom')
        if isinstance(qcom, str):
            try:
                qcom = _normalize_ptbr_number(qcom)
            except Exception:
                qcom = None
        elif qcom is None or qcom == '':
            qcom = None

        vuncom = itm.get('vUnCom')
        if isinstance(vuncom, str):
            try:
                vuncom = _normalize_ptbr_number(vuncom)
            except Exception:
                vuncom = None
        elif vuncom is None or vuncom == '':
            vuncom = None

        ucom = itm.get('uCom')
        if isinstance(ucom, str) and ucom.strip():
            ucom = ucom.strip().upper()
        else:
            ucom = None

        cprod = itm.get('cProd')
        if isinstance(cprod, str) and cprod.strip():
            cprod = cprod.strip()
        else:
            cprod = None

        # Impostos (Etapa 4) - sanitizar se presentes
        impostos_raw = itm.get('impostos')
        impostos_sanitized = None
        if impostos_raw and isinstance(impostos_raw, dict):
            impostos_sanitized = {}

            # ICMS
            icms_raw = impostos_raw.get('icms')
            if icms_raw and isinstance(icms_raw, dict):
                impostos_sanitized['icms'] = {
                    'CST': str(icms_raw.get('CST', '')).strip() or None,
                    'orig': str(icms_raw.get('orig', '')).strip() or None,
                    'vBC': _normalize_ptbr_number_safe(icms_raw.get('vBC')),
                    'pICMS': _normalize_ptbr_number_safe(icms_raw.get('pICMS')),
                    'vICMS': _normalize_ptbr_number_safe(icms_raw.get('vICMS')),
                }

            # IPI (opcional)
            ipi_raw = impostos_raw.get('ipi')
            if ipi_raw and isinstance(ipi_raw, dict):
                impostos_sanitized['ipi'] = {
                    'CST': str(ipi_raw.get('CST', '')).strip() or None,
                    'vBC': _normalize_ptbr_number_safe(ipi_raw.get('vBC')),
                    'pIPI': _normalize_ptbr_number_safe(ipi_raw.get('pIPI')),
                    'vIPI': _normalize_ptbr_number_safe(ipi_raw.get('vIPI')),
                }

            # PIS
            pis_raw = impostos_raw.get('pis')
            if pis_raw and isinstance(pis_raw, dict):
                impostos_sanitized['pis'] = {
                    'CST': str(pis_raw.get('CST', '')).strip() or None,
                    'vBC': _normalize_ptbr_number_safe(pis_raw.get('vBC')),
                    'pPIS': _normalize_ptbr_number_safe(pis_raw.get('pPIS')),
                    'vPIS': _normalize_ptbr_number_safe(pis_raw.get('vPIS')),
                }

            # COFINS
            cofins_raw = impostos_raw.get('cofins')
            if cofins_raw and isinstance(cofins_raw, dict):
                impostos_sanitized['cofins'] = {
                    'CST': str(cofins_raw.get('CST', '')).strip() or None,
                    'vBC': _normalize_ptbr_number_safe(cofins_raw.get('vBC')),
                    'pCOFINS': _normalize_ptbr_number_safe(cofins_raw.get('pCOFINS')),
                    'vCOFINS': _normalize_ptbr_number_safe(cofins_raw.get('vCOFINS')),
                }

        item_dict = {
            'xProd': xprod,
            'NCM': ncm,
            'vProd': vprod,
            'qCom': qcom,
            'vUnCom': vuncom,
            'uCom': ucom,
            'cProd': cprod
        }

        # Adicionar impostos se presentes
        if impostos_sanitized:
            item_dict['impostos'] = impostos_sanitized

        norm_items.append(item_dict)
    if not norm_items:
        # Minimiza falha criando um item sintético com valor 0 se LLM não retornou nada
        norm_items = [{'xProd': 'Item', 'NCM': None, 'vProd': 0, 'qCom': None, 'vUnCom': None, 'uCom': None, 'cProd': None}]
    out['itens'] = norm_items

    # Totais de impostos (Etapa 4) - sanitizar se presentes
    totais_raw = raw.get('totais_impostos')
    if totais_raw and isinstance(totais_raw, dict):
        totais_sanitized = {
            'vBC': _normalize_ptbr_number_safe(totais_raw.get('vBC')),
            'vICMS': _normalize_ptbr_number_safe(totais_raw.get('vICMS')),
            'vIPI': _normalize_ptbr_number_safe(totais_raw.get('vIPI')),
            'vPIS': _normalize_ptbr_number_safe(totais_raw.get('vPIS')),
            'vCOFINS': _normalize_ptbr_number_safe(totais_raw.get('vCOFINS')),
        }
        # Só adicionar se pelo menos um valor estiver presente
        if any(v is not None for v in totais_sanitized.values()):
            out['totais_impostos'] = totais_sanitized

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
