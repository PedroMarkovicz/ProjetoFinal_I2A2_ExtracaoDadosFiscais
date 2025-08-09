"""
Modelos de domínio para NF-e
============================

Define as estruturas Pydantic usadas pelo parser:
- `NFeItem`: representa um item de produto
- `NFePayload`: agrega os campos mínimos da NF-e

Inclui validadores para normalização de CFOP e valores numéricos
permitindo entradas em formato brasileiro (vírgula) ou americano (ponto).
"""
# src/domain/models.py
import logging
from enum import Enum
from typing import List, Optional, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
logger = logging.getLogger(__name__)

# O Enum de UFs continua o mesmo
class UfEnum(str, Enum):
    AC = "AC"; AL = "AL"; AP = "AP"; AM = "AM"; BA = "BA"; CE = "CE"; DF = "DF"
    ES = "ES"; GO = "GO"; MA = "MA"; MT = "MT"; MS = "MS"; MG = "MG"; PA = "PA"
    PB = "PB"; PR = "PR"; PE = "PE"; PI = "PI"; RJ = "RJ"; RN = "RN"; RS = "RS"
    RO = "RO"; RR = "RR"; SC = "SC"; SP = "SP"; SE = "SE"; TO = "TO"


class NFeItem(BaseModel):
    """Representa um item de produto dentro de uma NF-e.

    Usa aliases para mapear diretamente os nomes do XML (`xProd`, `NCM`, `vProd`).
    """
    # CORREÇÃO: Adicionado populate_by_name=True para ativar os aliases
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # CORREÇÃO: Adicionados aliases para mapear os campos do XML
    descricao: str = Field(alias="xProd", min_length=1)
    ncm: Optional[str] = Field(alias="NCM", default=None, pattern=r"^\d{8}$")
    valor: float = Field(alias="vProd", ge=0)

    # CORREÇÃO: Adicionado validador para o 'valor' do item
    @field_validator("valor", mode="before")
    @classmethod
    def _normalize_valor_item(cls, v: Any) -> Any:
        logger.debug("Normalizando valor do item: %r", v)
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class NFePayload(BaseModel):
    """Payload com os dados extraídos e validados de uma NF-e.

    O enum `UfEnum` garante valores válidos de UF, e os validadores tratam
    normalizações simples (CFOP somente dígitos; valores com vírgula).
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    cfop: str = Field(pattern=r"^\d{4}$")
    emitente_uf: UfEnum
    destinatario_uf: UfEnum
    valor_total: float = Field(ge=0)
    itens: List[NFeItem] = Field(min_length=1)

    @field_validator("cfop", mode="before")
    @classmethod
    def _normalize_cfop(cls, v: Any) -> str:
        logger.debug("Normalizando CFOP: %r", v)
        if v is None:
            return ""
        if isinstance(v, str):
            return "".join(filter(str.isdigit, v))
        return str(v)

    @field_validator("valor_total", mode="before")
    @classmethod
    def _normalize_valor_total(cls, v: Any) -> Any:
        logger.debug("Normalizando valor_total: %r", v)
        if isinstance(v, str):
            return v.replace(",", ".")
        return v