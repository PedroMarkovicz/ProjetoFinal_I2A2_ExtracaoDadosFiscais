"""
CLI para executar o grafo
=========================
"""
from __future__ import annotations
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import typer
from src.workflow.graph import build_graph

app = typer.Typer(help="CLI para executar o grafo (XmlParserAgent + ClassificadorContábil).")

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class RegimeTributario(str, Enum):
    simples = "simples"
    presumido = "presumido"
    real = "real"

def _configure_logging(level: LogLevel) -> None:
    numeric = getattr(logging, level.value, logging.INFO)
    logging.basicConfig(level=numeric, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def _load_review_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise typer.BadParameter(f"Arquivo não encontrado: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "human_review_input" not in data:
            # permite passar o próprio payload já como human_review_input
            data = {"human_review_input": data}
        return data
    except Exception as e:
        raise typer.BadParameter(f"Falha ao ler/parsear JSON de revisão: {e}")

@app.command()
def run(
    xml: str = typer.Option(..., "--xml", help="Caminho do arquivo XML da NF-e"),
    regime: RegimeTributario | None = typer.Option(None, "--regime", help="Regime tributário (opcional)"),
    review_json: str | None = typer.Option(None, "--review-json", help="Caminho de um JSON com human_review_input"),
    log_level: LogLevel = typer.Option(LogLevel.INFO, "--log-level", help="Nível de log"),
):
    _configure_logging(log_level)
    logger = logging.getLogger("run_graph")

    graph = build_graph()

    state: Dict[str, Any] = {"xml_path": xml}
    if regime is not None:
        state["regime_tributario"] = regime.value
    if review_json:
        state.update(_load_review_json(review_json))

    result = graph.invoke(state)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 1) parser falhou → código 1
    if not result.get("ok", False):
        raise typer.Exit(code=1)

    # 2) aguardando revisão humana → código 5
    if result.get("human_review_pending", False) and result.get("classificacao_needs_review", False):
        logger.warning("Revisão humana necessária: %s", result.get("classificacao_review_reason"))
        if not review_json:
            print("\n[INFO] Para concluir, reexecute com --review-json apontando para um JSON com human_review_input.")
            print(json.dumps({
                "human_review_input": {
                    "regime": "<simples|presumido|real|*>",
                    "conta_debito": "<número da conta>",
                    "conta_credito": "<número da conta>",
                    "justificativa_base": "<texto>",
                    "confianca": 0.85
                }
            }, ensure_ascii=False, indent=2))
        raise typer.Exit(code=5)

    # 3) sucesso normal → 0
    raise typer.Exit(code=0)

if __name__ == "__main__":
    app()
