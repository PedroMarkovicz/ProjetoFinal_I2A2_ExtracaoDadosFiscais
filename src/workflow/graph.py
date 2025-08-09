"""
Definição do grafo do workflow
==============================

Fluxo condicional:
- xml_parser → classificador_contabil → (done | need_input | human_review) → END
"""
from __future__ import annotations
import logging
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

from src.workflow.state import WorkflowState
from src.workflow.nodes import xml_parser_node, classificador_contabil_node, human_review_node

def _route_after_classificador(state: WorkflowState) -> str:
    """Retorna uma das chaves do mapping abaixo: 'done' | 'need_input' | 'human_review'."""
    needs = bool(state.get("classificacao_needs_review"))
    has_input = bool(state.get("human_review_input"))
    if not needs:
        return "done"
    if needs and not has_input:
        # sinaliza pendência explícita (o nó de revisão não é chamado)
        state["human_review_pending"] = True  # idempotente
        return "need_input"
    return "human_review"

def build_graph():
    logger.debug("Construindo grafo do workflow")
    graph = StateGraph(WorkflowState)

    graph.add_node("xml_parser", xml_parser_node)
    graph.add_node("classificador_contabil", classificador_contabil_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("xml_parser")
    graph.add_edge("xml_parser", "classificador_contabil")

    # Roteamento condicional conforme explicação acima
    graph.add_conditional_edges(
        "classificador_contabil",
        _route_after_classificador,
        {
            "done": END,
            "need_input": END,
            "human_review": "human_review",
        },
    )

    graph.add_edge("human_review", END)

    logger.debug("Grafo compilado")
    return graph.compile()
