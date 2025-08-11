"""
Tipos de estado do workflow
===========================
"""
from __future__ import annotations
import logging
from typing import TypedDict, Optional, Dict, Any

logger = logging.getLogger(__name__)

class WorkflowState(TypedDict, total=False):
    # inputs
    xml_path: str
    pdf_path: str
    regime_tributario: str  # "simples" | "presumido" | "real" (opcional)

    # outputs do parser
    ok: bool
    payload: Dict[str, Any]
    error: Optional[str]

    # outputs do classificador
    classificacao_ok: bool
    classificacao: Dict[str, Any]

    # sinalização de revisão humana do classificador
    classificacao_needs_review: bool
    classificacao_review_reason: Optional[str]

    # entrada e resultado da revisão humana
    human_review_input: Dict[str, Any]          # deve conter cfop, regime, conta_debito, conta_credito, justificativa_base, confianca
    human_review_pending: bool                  # true se aguardando input humano
    human_review_applied: bool                  # true quando aplicou/registrou
