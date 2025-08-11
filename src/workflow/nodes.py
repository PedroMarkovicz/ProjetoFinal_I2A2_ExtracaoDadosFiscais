"""
Nós do workflow
===============
"""
from __future__ import annotations
import logging
from typing import Dict, Any

from src.agents.xml_parser_agent import parse_xml, XmlParseError
from src.agents.pdf_parser_agent import parse_pdf
from src.workflow.state import WorkflowState
from src.agents.classificador_contabil_agent import (
    classificar_contabil,
    ClassificacaoContabil,
    upsert_cfop_mapping,
    classificacao_from_human,
    REQUIRED_MAP_FIELDS,
)
from src.domain.models import NFePayload

logger = logging.getLogger(__name__)

def xml_parser_node(state: WorkflowState) -> WorkflowState:
    logger.debug("xml_parser_node recebido estado: %s", state)
    pdf_path = state.get("pdf_path")
    if pdf_path:
        try:
            payload = parse_pdf(pdf_path)
            return {"ok": True, "payload": payload.model_dump()}
        except XmlParseError as e:
            logger.warning("Falha conhecida no parsing PDF: %s", e)
            return {"ok": False, "error": str(e)}
        except Exception as e:
            logger.exception("Erro inesperado no pdf_parser_node")
            return {"ok": False, "error": f"Erro inesperado (PDF): {e}"}

    xml_path = state.get("xml_path")
    if not xml_path:
        logger.error("Entrada ausente: informe pdf_path ou xml_path")
        return {"ok": False, "error": "Entrada ausente: informe pdf_path ou xml_path"}

    try:
        payload = parse_xml(xml_path)
        return {"ok": True, "payload": payload.model_dump()}
    except XmlParseError as e:
        logger.warning("Falha conhecida no parsing XML: %s", e)
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("Erro inesperado no xml_parser_node")
        return {"ok": False, "error": f"Erro inesperado (XML): {e}"}

def classificador_contabil_node(state: WorkflowState) -> WorkflowState:
    logger.debug("classificador_contabil_node recebido estado: %s", state)
    if not state.get("ok"):
        logger.warning("classificador_contabil_node ignorado pois ok=False do parser")
        return state

    try:
        payload = NFePayload.model_validate(state["payload"])
        regime = state.get("regime_tributario")
        result: ClassificacaoContabil = classificar_contabil(payload, regime_tributario=regime)

        state.update({
            "classificacao_ok": True,
            "classificacao": result.model_dump(),
            "classificacao_needs_review": bool(getattr(result, "needs_human_review", False)),
            "classificacao_review_reason": getattr(result, "review_reason", None),
            "human_review_pending": bool(getattr(result, "needs_human_review", False)),
        })
        return state
    except Exception as e:
        logger.exception("Erro no classificador contábil")
        state.update({"classificacao_ok": False, "error": f"Erro no classificador contábil: {e}"})
        return state

def human_review_node(state: WorkflowState) -> WorkflowState:
    """
    Se a classificação pedir revisão:
      - valida 'human_review_input'
      - injeta CFOP do payload se não vier do humano
      - faz upsert no CSV
      - aplica classificação final a partir do input humano
    Caso contrário, apenas retorna o estado.
    """
    logger.debug("human_review_node recebido estado: %s", state)

    if not state.get("classificacao_needs_review"):
        state["human_review_pending"] = False
        return state

    hr: Dict[str, Any] = state.get("human_review_input", {}) or {}

    # Preenche CFOP a partir do payload se não vier no input humano
    try:
        payload = NFePayload.model_validate(state["payload"])
        if not hr.get("cfop"):
            hr["cfop"] = payload.cfop
    except Exception:
        pass

    # Checagem de campos obrigatórios (agora com cfop garantido)
    missing = [k for k in REQUIRED_MAP_FIELDS if not hr.get(k)]
    if missing:
        state.update({
            "human_review_pending": True,
            "human_review_applied": False,
            "error": f"Aguardando revisão humana. Campos faltantes: {', '.join(missing)}",
        })
        logger.info("Revisão humana pendente. Faltando: %s", ", ".join(missing))
        return state

    # validação de CFOP
    cfop = str(hr.get("cfop", "")).strip()
    if not (len(cfop) == 4 and cfop.isdigit()):
        state.update({"human_review_pending": True, "human_review_applied": False, "error": "CFOP inválido (espera 4 dígitos)."})
        return state

    # validação de confiança
    try:
        conf = float(hr.get("confianca"))
        if not (0.0 <= conf <= 1.0):
            raise ValueError
    except Exception:
        state.update({"human_review_pending": True, "human_review_applied": False, "error": "Campo 'confianca' inválido (0.0 a 1.0)."})
        return state

    # upsert no CSV
    try:
        upsert_cfop_mapping({
            "cfop": cfop,
            "regime": str(hr.get("regime", "*")).strip().lower() or "*",
            "conta_debito": str(hr.get("conta_debito")).strip(),
            "conta_credito": str(hr.get("conta_credito")).strip(),
            "justificativa_base": str(hr.get("justificativa_base")).strip(),
            "confianca": str(conf),
        })
    except Exception as e:
        logger.exception("Falha no upsert do CSV")
        state.update({"human_review_pending": True, "human_review_applied": False, "error": f"Falha ao atualizar CSV: {e}"})
        return state

    # aplica classificação final com base no input humano
    try:
        payload = NFePayload.model_validate(state["payload"])
        final_cls = classificacao_from_human(payload, {
            "cfop": cfop,
            "regime": str(hr.get("regime", "*")).strip().lower() or "*",
            "conta_debito": str(hr.get("conta_debito")).strip(),
            "conta_credito": str(hr.get("conta_credito")).strip(),
            "justificativa_base": str(hr.get("justificativa_base")).strip(),
            "confianca": str(conf),
        })
        state.update({
            "classificacao_ok": True,
            "classificacao": final_cls.model_dump(),
            "classificacao_needs_review": False,
            "classificacao_review_reason": None,
            "human_review_pending": False,
            "human_review_applied": True,
        })
        logger.info("Revisão humana aplicada para CFOP=%s", cfop)
        return state
    except Exception as e:
        logger.exception("Falha ao aplicar classificação a partir do input humano")
        state.update({"human_review_pending": True, "human_review_applied": False, "error": f"Falha ao aplicar classificação humana: {e}"})
        return state
