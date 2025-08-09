"""
CLI simples para parsing de NF-e
================================

Expõe um comando `run` que recebe o caminho do XML, executa o parser e
imprime o resultado em JSON. Inclui níveis de log configuráveis.
"""
# src/app/parse_cli.py
import json
import logging
from enum import Enum

import typer
from src.agents.xml_parser_agent import parse_xml, XmlParseError

app = typer.Typer(help="CLI para parsing de NF-e (XmlParserAgent).")

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

def _configure_logging(level: LogLevel) -> None:
    numeric = getattr(logging, level.value, logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

@app.command()
def run(
    xml: str = typer.Option(..., "--xml", help="Caminho do arquivo XML da NF-e"),
    log_level: LogLevel = typer.Option(LogLevel.INFO, "--log-level", help="Nível de log"),
):
    """
    Executa o parser e imprime o payload em JSON.
    Retorna código 1 em falhas de parsing conhecidas, 2 em erros inesperados.
    """
    _configure_logging(log_level)
    logger = logging.getLogger("cli")

    try:
        payload = parse_xml(xml)
        logger.debug("Payload produzido pela CLI: %s", payload.model_dump())
        print(json.dumps(payload.model_dump(), ensure_ascii=False, indent=2))
    except XmlParseError as e:
        logger.error("Falha no parsing: %s", e)
        raise typer.Exit(code=1)
    except Exception:
        logger.exception("Erro inesperado")
        raise typer.Exit(code=2)

if __name__ == "__main__":
    app()
