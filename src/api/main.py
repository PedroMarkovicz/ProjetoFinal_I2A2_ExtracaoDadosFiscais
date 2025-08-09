# src/api/main.py
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from src.workflow.graph import build_graph
from src.agents.classificador_contabil_agent import upsert_cfop_mapping, REQUIRED_MAP_FIELDS

# ----------------------------------------------------
# Setup
# ----------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="API Classificação Contábil",
    version="1.2.0",
    description=(
        "API para classificar NF-e via workflow (LangGraph).\n"
        "Etapas:\n"
        "  (1) Classificar (sem input humano)\n"
        "  (2) Se necessário, enviar revisão humana em endpoint dedicado"
    ),
)

# Compila o grafo uma única vez
GRAPH = build_graph()


# ----------------------------------------------------
# Schemas
# ----------------------------------------------------
class ClassificarByPathRequest(BaseModel):
    xml_path: str = Field(..., description="Caminho completo do arquivo XML da NF-e")


class HumanReviewInput(BaseModel):
    cfop: str = Field(min_length=4, max_length=4)
    regime: str = Field(default="*", description='simples|presumido|real|*')
    conta_debito: str
    conta_credito: str
    justificativa_base: str
    confianca: float

    @field_validator("cfop")
    @classmethod
    def _cfop_digits(cls, v: str) -> str:
        v = "".join(ch for ch in v if ch.isdigit())
        if len(v) != 4:
            raise ValueError("cfop deve ter 4 dígitos")
        return v

    @field_validator("regime")
    @classmethod
    def _regime_valid(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in {"simples", "presumido", "real", "*"}:
            raise ValueError('regime deve ser "simples", "presumido", "real" ou "*"')
        return v

    @field_validator("confianca")
    @classmethod
    def _conf_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confianca deve estar entre 0.0 e 1.0")
        return v


class ReviewByPathRequest(BaseModel):
    xml_path: str
    review: HumanReviewInput


class UpsertMappingRequest(BaseModel):
    cfop: str
    regime: str
    conta_debito: str
    conta_credito: str
    justificativa_base: str
    confianca: float

    @field_validator("cfop")
    @classmethod
    def _cfop_digits(cls, v: str) -> str:
        v = "".join(ch for ch in v if ch.isdigit())
        if len(v) != 4:
            raise ValueError("cfop deve ter 4 dígitos")
        return v

    @field_validator("regime")
    @classmethod
    def _regime_valid(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in {"simples", "presumido", "real", "*"}:
            raise ValueError('regime deve ser "simples", "presumido", "real" ou "*"')
        return v

    @field_validator("confianca")
    @classmethod
    def _conf_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confianca deve estar entre 0.0 e 1.0")
        return v


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def _invoke_graph(xml_path: str, human_review_input: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Invoca o grafo exatamente como o CLI faz.
    - Etapa 1: sem 'human_review_input'
    - Etapa 2: com 'human_review_input' (se necessário)
    """
    state: Dict[str, Any] = {"xml_path": xml_path}
    if human_review_input:
        state["human_review_input"] = human_review_input

    logger.info("Invocando grafo | xml=%s has_hr=%s", xml_path, bool(human_review_input))
    return GRAPH.invoke(state)


# ----------------------------------------------------
# Infra
# ----------------------------------------------------
@app.get("/health", tags=["infra"], summary="Healthcheck")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ----------------------------------------------------
# ETAPA 1 — Classificar (sem input humano)
# ----------------------------------------------------
@app.post(
    "/classificar/path",
    tags=["classificacao"],
    summary="Classifica informando caminho do XML (somente xml_path)"
)
def classificar_by_path(payload: ClassificarByPathRequest) -> Dict[str, Any]:
    xmlp = Path(payload.xml_path)
    if not xmlp.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Arquivo não encontrado: {xmlp}")

    result = _invoke_graph(str(xmlp))
    return result


@app.post(
    "/classificar/xml",
    tags=["classificacao"],
    summary="Classifica enviando o XML via upload (somente o arquivo)"
)
async def classificar_by_upload(
    xml_file: UploadFile = File(..., description="Arquivo .xml da NF-e")
) -> Dict[str, Any]:
    if not xml_file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie um arquivo .xml")

    # Salva o XML em arquivo temporário para passar o caminho ao grafo
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            content = await xml_file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar XML temporário: {e}")

    try:
        result = _invoke_graph(str(tmp_path))
        return result
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ----------------------------------------------------
# ETAPA 2 — Enviar revisão humana (se necessário)
# ----------------------------------------------------
@app.post(
    "/classificar/review/path",
    tags=["revisao"],
    summary="Aplica revisão humana informando caminho do XML (somente quando human_review_pending=true)"
)
def review_by_path(body: ReviewByPathRequest) -> Dict[str, Any]:
    xmlp = Path(body.xml_path)
    if not xmlp.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Arquivo não encontrado: {xmlp}")

    # O grafo valida, faz upsert no CSV e aplica classificação final
    result = _invoke_graph(str(xmlp), human_review_input=body.review.model_dump())
    return result


@app.post(
    "/classificar/review/xml",
    tags=["revisao"],
    summary="Aplica revisão humana enviando o XML via upload + JSON de revisão"
)
async def review_by_upload(
    xml_file: UploadFile = File(..., description="Arquivo .xml da NF-e"),
    # O Swagger mostra como string; envie JSON como texto.
    human_review_input: str = File(..., description="JSON com cfop, regime, conta_debito, conta_credito, justificativa_base, confianca")
) -> Dict[str, Any]:
    if not xml_file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie um arquivo .xml")

    # Parse do JSON de revisão
    try:
        hr = json.loads(human_review_input)
        if isinstance(hr, dict) and "human_review_input" in hr:
            hr = hr["human_review_input"]
        if not isinstance(hr, dict):
            raise ValueError("Estrutura inválida")
        # valida com Pydantic para mensagens melhores
        hr = HumanReviewInput(**hr).model_dump()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"human_review_input inválido: {e}")

    # Salva o XML em temporário
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            content = await xml_file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar XML temporário: {e}")

    try:
        result = _invoke_graph(str(tmp_path), human_review_input=hr)
        return result
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ----------------------------------------------------
# Utilitário opcional — persistir mapeamentos
# ----------------------------------------------------
@app.post(
    "/mappings/upsert",
    tags=["mapeamento"],
    summary="(Opcional) Persiste/atualiza regra CFOP→contas no CSV"
)
def mappings_upsert(body: UpsertMappingRequest) -> Dict[str, Any]:
    # Checagem adicional dos campos obrigatórios
    for k in REQUIRED_MAP_FIELDS:
        if getattr(body, k, None) in (None, ""):
            raise HTTPException(status_code=400, detail=f"Campo obrigatório ausente: {k}")

    try:
        upsert_cfop_mapping({
            "cfop": body.cfop,
            "regime": body.regime,
            "conta_debito": body.conta_debito,
            "conta_credito": body.conta_credito,
            "justificativa_base": body.justificativa_base,
            "confianca": f"{body.confianca}",
        })
        return {"ok": True, "message": "Mapeamento atualizado com sucesso."}
    except Exception as e:
        logger.exception("Falha ao fazer upsert do mapeamento")
        raise HTTPException(status_code=500, detail=f"Falha ao atualizar mapeamento: {e}")
