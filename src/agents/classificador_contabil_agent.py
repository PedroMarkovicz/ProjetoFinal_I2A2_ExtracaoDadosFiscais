from __future__ import annotations
import csv
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from src.domain.models import NFePayload

logger = logging.getLogger(__name__)

DATA_DIR = Path("data_sources")
CSV_CFOP_PATH = DATA_DIR / "contas_por_cfop.csv"

# Limiar mínimo para aprovar automaticamente sem revisão
MIN_CONFIDENCE_FOR_AUTO_APPROVE = 0.75

REQUIRED_MAP_FIELDS = ("cfop", "regime", "conta_debito", "conta_credito", "justificativa_base", "confianca")

class ClassificacaoContabil(BaseModel):
    """Resultado da classificação contábil."""
    cfop: str = Field(min_length=4, max_length=4)
    natureza_operacao: str  # "interna" ou "interestadual"
    conta_debito: str
    conta_credito: str
    justificativa: str
    ncm_itens: List[Optional[str]] = []
    confianca: float = 0.60
    # Governança / Human-in-the-loop
    needs_human_review: bool = False
    review_reason: Optional[str] = None
    rule_version: str = "v0.4"

def _natureza(emit_uf: str, dest_uf: str) -> str:
    return "interna" if emit_uf == dest_uf else "interestadual"

@lru_cache(maxsize=1)
def _load_cfop_map() -> List[Dict[str, str]]:
    """Lê o CSV de mapeamentos CFOP→contas e cacheia em memória."""
    rows: List[Dict[str, str]] = []
    if not CSV_CFOP_PATH.exists():
        logger.warning("Arquivo de mapeamento não encontrado: %s", CSV_CFOP_PATH)
        return rows
    try:
        with CSV_CFOP_PATH.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({
                    "cfop": (r.get("cfop") or "").strip(),
                    "regime": (r.get("regime") or "*").strip().lower(),
                    "conta_debito": (r.get("conta_debito") or "").strip(),
                    "conta_credito": (r.get("conta_credito") or "").strip(),
                    "justificativa_base": (r.get("justificativa_base") or "").strip(),
                    "confianca": (r.get("confianca") or "0.70").strip(),
                })
        logger.info("Mapa CFOP carregado: %d linhas", len(rows))
    except Exception:
        logger.exception("Falha ao ler %s", CSV_CFOP_PATH)
    return rows

def _invalidate_cfop_cache() -> None:
    try:
        _load_cfop_map.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

def upsert_cfop_mapping(mapping: Dict[str, str]) -> None:
    """Atualiza/insere uma linha no CSV (chave = cfop+regime). Cria cabeçalho se necessário."""
    for k in REQUIRED_MAP_FIELDS:
        if not mapping.get(k):
            raise ValueError(f"Campo obrigatório ausente: {k}")

    mapping_norm = {
        "cfop": str(mapping["cfop"]).strip(),
        "regime": str(mapping["regime"]).strip().lower() or "*",
        "conta_debito": str(mapping["conta_debito"]).strip(),
        "conta_credito": str(mapping["conta_credito"]).strip(),
        "justificativa_base": str(mapping["justificativa_base"]).strip(),
        "confianca": str(mapping["confianca"]).strip(),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_cfop_map().copy()
    updated = False

    # upsert por (cfop, regime)
    for i, r in enumerate(rows):
        if r["cfop"] == mapping_norm["cfop"] and r["regime"] == mapping_norm["regime"]:
            rows[i] = mapping_norm
            updated = True
            break
    if not updated:
        rows.append(mapping_norm)

    # sobrescreve o CSV
    with CSV_CFOP_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(REQUIRED_MAP_FIELDS))
        writer.writeheader()
        writer.writerows(rows)

    _invalidate_cfop_cache()
    logger.info("Upsert CSV concluído para CFOP=%s regime=%s", mapping_norm["cfop"], mapping_norm["regime"])

def _match_cfop_in_csv(cfop: str, regime: Optional[str]) -> Optional[Tuple[str, str, str, float]]:
    """
    Matching no CSV:
      1) (cfop exato, regime exato)
      2) (cfop exato, regime="*")
    Retorna (conta_debito, conta_credito, justificativa, confianca) ou None.
    """
    rows = _load_cfop_map()
    if not rows:
        return None

    regime_norm = (regime or "*").strip().lower()

    for r in rows:
        if r["cfop"] == cfop and r["regime"] == regime_norm:
            return (r["conta_debito"], r["conta_credito"], r["justificativa_base"] or f"CFOP {cfop} (regime={regime_norm})", float(r["confianca"] or 0.7))
    for r in rows:
        if r["cfop"] == cfop and r["regime"] == "*":
            return (r["conta_debito"], r["conta_credito"], r["justificativa_base"] or f"CFOP {cfop} (regime=*)", float(r["confianca"] or 0.7))
    return None

def _fallback_por_prefixo(cfop: str) -> Tuple[str, str, str, float]:
    """Fallback mínimo por primeiro dígito do CFOP."""
    if cfop.startswith(("1", "2")):
        return ("Estoques de Mercadorias", "Fornecedores", "Operação de ENTRADA (compra) identificada por CFOP iniciando em 1/2.", 0.65)
    if cfop.startswith(("5", "6")):
        return ("Clientes", "Receita de Vendas", "Operação de SAÍDA (venda) identificada por CFOP iniciando em 5/6.", 0.65)
    return ("Conta a Classificar (Débito)", "Conta a Classificar (Crédito)", "CFOP fora dos intervalos mínimos do MVP; aplicar regras detalhadas.", 0.50)

def classificar_contabil(payload: NFePayload, regime_tributario: Optional[str] = None) -> ClassificacaoContabil:
    """Classificador com CSV, fallback e sinalização de revisão humana."""
    cfop = payload.cfop
    natureza = _natureza(payload.emitente_uf.value, payload.destinatario_uf.value)

    needs_review = False
    review_reason: Optional[str] = None

    contas_csv = _match_cfop_in_csv(cfop, regime_tributario)
    if contas_csv:
        conta_debito, conta_credito, justificativa_base, conf = contas_csv
        if conf < MIN_CONFIDENCE_FOR_AUTO_APPROVE:
            needs_review = True
            review_reason = f"Confiança abaixo do mínimo ({conf:.2f} < {MIN_CONFIDENCE_FOR_AUTO_APPROVE:.2f}). Revisar CFOP {cfop} (regime={regime_tributario or '*'})."
    else:
        conta_debito, conta_credito, justificativa_base, conf = _fallback_por_prefixo(cfop)
        needs_review = True
        review_reason = f"Mapeamento não encontrado no CSV para CFOP {cfop} (regime={regime_tributario or '*'}). Aplicado fallback por prefixo. Revisão humana obrigatória."

    justificativa = f"{justificativa_base} Natureza: {natureza}. Valor total da NF-e considerado para contexto: {payload.valor_total:.2f}."
    ncm_lista = [it.ncm for it in payload.itens]

    out = ClassificacaoContabil(
        cfop=cfop,
        natureza_operacao=natureza,
        conta_debito=conta_debito,
        conta_credito=conta_credito,
        justificativa=justificativa,
        ncm_itens=ncm_lista,
        confianca=conf,
        needs_human_review=needs_review,
        review_reason=review_reason,
    )

    logger.info(
        "Classificação OK",
        extra={
            "cfop": out.cfop,
            "natureza": out.natureza_operacao,
            "conta_debito": out.conta_debito,
            "conta_credito": out.conta_credito,
            "confianca": out.confianca,
            "regime_tributario": (regime_tributario or "*"),
            "fonte": "csv" if contas_csv else "fallback",
            "needs_human_review": out.needs_human_review,
            "review_reason": out.review_reason or "",
        },
    )
    return out

def classificacao_from_human(payload: NFePayload, mapping: Dict[str, str]) -> ClassificacaoContabil:
    """Gera ClassificacaoContabil a partir de um mapeamento humano já validado."""
    natureza = _natureza(payload.emitente_uf.value, payload.destinatario_uf.value)
    justificativa = f"{mapping['justificativa_base']} Natureza: {natureza}. Valor total da NF-e considerado para contexto: {payload.valor_total:.2f}."
    ncm_lista = [it.ncm for it in payload.itens]
    conf = float(mapping["confianca"])
    return ClassificacaoContabil(
        cfop=mapping["cfop"],
        natureza_operacao=natureza,
        conta_debito=mapping["conta_debito"],
        conta_credito=mapping["conta_credito"],
        justificativa=justificativa,
        ncm_itens=ncm_lista,
        confianca=conf,
        needs_human_review=False,
        review_reason="Mapeamento informado por revisão humana aplicado e persistido no CSV.",
    )
