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
    model_validator,
)
logger = logging.getLogger(__name__)

# O Enum de UFs continua o mesmo
class UfEnum(str, Enum):
    AC = "AC"; AL = "AL"; AP = "AP"; AM = "AM"; BA = "BA"; CE = "CE"; DF = "DF"
    ES = "ES"; GO = "GO"; MA = "MA"; MT = "MT"; MS = "MS"; MG = "MG"; PA = "PA"
    PB = "PB"; PR = "PR"; PE = "PE"; PI = "PI"; RJ = "RJ"; RN = "RN"; RS = "RS"
    RO = "RO"; RR = "RR"; SC = "SC"; SP = "SP"; SE = "SE"; TO = "TO"


class Emitente(BaseModel):
    """Representa os dados completos do emitente da NF-e.

    Inclui informações cadastrais e de endereço do emissor da nota fiscal.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # Campos de prioridade ALTA
    razao_social: str = Field(alias="xNome", min_length=1)
    cnpj: str = Field(alias="CNPJ", pattern=r"^\d{14}$")

    # Campos de prioridade MEDIA
    inscricao_estadual: Optional[str] = Field(alias="IE", default=None)
    uf: UfEnum
    municipio: Optional[str] = Field(alias="xMun", default=None)
    bairro: Optional[str] = Field(alias="xBairro", default=None)
    logradouro: Optional[str] = Field(alias="xLgr", default=None)
    numero: Optional[str] = Field(alias="nro", default=None)

    # Campos de prioridade BAIXA
    cep: Optional[str] = Field(alias="CEP", default=None, pattern=r"^\d{8}$")
    telefone: Optional[str] = Field(alias="fone", default=None)

    @field_validator("cnpj", mode="before")
    @classmethod
    def _normalize_cnpj(cls, v: Any) -> str:
        """Remove caracteres não numéricos do CNPJ."""
        logger.debug("Normalizando CNPJ: %r", v)
        if v is None:
            return ""
        if isinstance(v, str):
            return "".join(filter(str.isdigit, v))
        return str(v)

    @field_validator("cep", mode="before")
    @classmethod
    def _normalize_cep(cls, v: Any) -> Optional[str]:
        """Remove caracteres não numéricos do CEP."""
        logger.debug("Normalizando CEP: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            return digits if len(digits) == 8 else None
        return str(v)

    @field_validator("telefone", mode="before")
    @classmethod
    def _normalize_telefone(cls, v: Any) -> Optional[str]:
        """Remove caracteres não numéricos do telefone."""
        logger.debug("Normalizando telefone: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return "".join(filter(str.isdigit, v))
        return str(v)

    @field_validator("inscricao_estadual", mode="before")
    @classmethod
    def _normalize_ie(cls, v: Any) -> Optional[str]:
        """Normaliza inscrição estadual, tratando casos especiais como ISENTO."""
        logger.debug("Normalizando IE: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_upper = v.strip().upper()
            # Casos especiais: ISENTO, ISENTA, etc.
            if "ISENT" in v_upper or v_upper in ("ISENTO", "ISENTA"):
                return "ISENTO"
            return v_upper
        return str(v)


class Destinatario(BaseModel):
    """Representa os dados completos do destinatario da NF-e.

    O destinatario pode ser pessoa fisica (CPF) ou juridica (CNPJ).
    Inclui informacoes cadastrais e de endereco do receptor da nota fiscal.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # Campos de prioridade ALTA
    razao_social: str = Field(alias="xNome", min_length=1)
    # IMPORTANTE: Destinatario pode ter CPF OU CNPJ (mutuamente exclusivo)
    cnpj: Optional[str] = Field(alias="CNPJ", default=None, pattern=r"^\d{14}$")
    cpf: Optional[str] = Field(alias="CPF", default=None, pattern=r"^\d{11}$")

    # Campos de prioridade MEDIA
    inscricao_estadual: Optional[str] = Field(alias="IE", default=None)
    indicador_ie: Optional[str] = Field(alias="indIEDest", default=None)
    uf: UfEnum
    municipio: Optional[str] = Field(alias="xMun", default=None)
    bairro: Optional[str] = Field(alias="xBairro", default=None)
    logradouro: Optional[str] = Field(alias="xLgr", default=None)
    numero: Optional[str] = Field(alias="nro", default=None)

    # Campos de prioridade BAIXA
    cep: Optional[str] = Field(alias="CEP", default=None, pattern=r"^\d{8}$")
    telefone: Optional[str] = Field(alias="fone", default=None)

    @model_validator(mode="after")
    def validate_cpf_or_cnpj(self):
        """Garante que o destinatario tenha CPF OU CNPJ (nunca ambos, nunca nenhum)."""
        if not self.cpf and not self.cnpj:
            raise ValueError("Destinatario deve ter CPF ou CNPJ")
        if self.cpf and self.cnpj:
            raise ValueError("Destinatario nao pode ter CPF e CNPJ simultaneamente")
        return self

    @field_validator("cnpj", mode="before")
    @classmethod
    def _normalize_cnpj(cls, v: Any) -> Optional[str]:
        """Remove caracteres nao numericos do CNPJ."""
        logger.debug("Normalizando CNPJ do destinatario: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            return digits if len(digits) == 14 else None
        return str(v)

    @field_validator("cpf", mode="before")
    @classmethod
    def _normalize_cpf(cls, v: Any) -> Optional[str]:
        """Remove caracteres nao numericos do CPF."""
        logger.debug("Normalizando CPF do destinatario: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            return digits if len(digits) == 11 else None
        return str(v)

    @field_validator("cep", mode="before")
    @classmethod
    def _normalize_cep(cls, v: Any) -> Optional[str]:
        """Remove caracteres nao numericos do CEP."""
        logger.debug("Normalizando CEP do destinatario: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            return digits if len(digits) == 8 else None
        return str(v)

    @field_validator("telefone", mode="before")
    @classmethod
    def _normalize_telefone(cls, v: Any) -> Optional[str]:
        """Remove caracteres nao numericos do telefone."""
        logger.debug("Normalizando telefone do destinatario: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return "".join(filter(str.isdigit, v))
        return str(v)

    @field_validator("inscricao_estadual", mode="before")
    @classmethod
    def _normalize_ie(cls, v: Any) -> Optional[str]:
        """Normaliza inscricao estadual, tratando casos especiais como ISENTO."""
        logger.debug("Normalizando IE do destinatario: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_upper = v.strip().upper()
            # Casos especiais: ISENTO, ISENTA, etc.
            if "ISENT" in v_upper or v_upper in ("ISENTO", "ISENTA"):
                return "ISENTO"
            return v_upper
        return str(v)

    @field_validator("indicador_ie", mode="before")
    @classmethod
    def _normalize_indicador_ie(cls, v: Any) -> Optional[str]:
        """Normaliza indicador de IE do destinatario."""
        logger.debug("Normalizando indicador IE do destinatario: %r", v)
        if v is None or v == "":
            return None
        return str(v).strip()


class NFeItem(BaseModel):
    """Representa um item de produto dentro de uma NF-e.

    Usa aliases para mapear diretamente os nomes do XML (`xProd`, `NCM`, `vProd`).
    Campos adicionais incluem quantidade, valor unitario, unidade comercial e codigo do produto.
    """
    # CORREÇÃO: Adicionado populate_by_name=True para ativar os aliases
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # CORREÇÃO: Adicionados aliases para mapear os campos do XML
    descricao: str = Field(alias="xProd", min_length=1)
    ncm: Optional[str] = Field(alias="NCM", default=None, pattern=r"^\d{8}$")
    cest: Optional[str] = Field(alias="CEST", default=None, pattern=r"^\d{7}$")
    valor: float = Field(alias="vProd", ge=0)

    # Campos adicionais (Etapa 3)
    quantidade: Optional[float] = Field(alias="qCom", default=None, gt=0)
    valor_unitario: Optional[float] = Field(alias="vUnCom", default=None, gt=0)
    unidade_comercial: Optional[str] = Field(alias="uCom", default=None)
    codigo_produto: Optional[str] = Field(alias="cProd", default=None)

    # Impostos do item (Etapa 4)
    impostos: Optional["ImpostosItem"] = None

    # CORREÇÃO: Adicionado validador para o 'valor' do item
    @field_validator("valor", mode="before")
    @classmethod
    def _normalize_valor_item(cls, v: Any) -> Any:
        logger.debug("Normalizando valor do item: %r", v)
        if isinstance(v, str):
            return v.replace(",", ".")
        return v

    @field_validator("quantidade", "valor_unitario", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        logger.debug("Normalizando campo numerico: %r", v)
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v

    @model_validator(mode="after")
    def validate_calculation(self):
        """Valida que quantidade * valor_unitario ≈ valor (com tolerancia)."""
        if self.quantidade is not None and self.valor_unitario is not None:
            calculated_value = self.quantidade * self.valor_unitario
            tolerance = 0.02  # Tolerancia de 2 centavos
            difference = abs(calculated_value - self.valor)

            if difference > tolerance:
                logger.warning(
                    "Validacao cruzada: quantidade (%.4f) * valor_unitario (%.4f) = %.2f "
                    "difere de valor (%.2f) em %.2f",
                    self.quantidade, self.valor_unitario, calculated_value, self.valor, difference
                )
                # Nao lançamos erro, apenas logamos o warning para permitir pequenas diferencas de arredondamento

        return self


# =============================================================================
# Modelos de Impostos (Etapa 4)
# =============================================================================


class ICMS(BaseModel):
    """Representa os dados do ICMS (Imposto sobre Circulacao de Mercadorias e Servicos).

    O ICMS possui multiplas variantes (ICMS00, ICMS10, ICMS20, etc.) que sao
    consolidadas neste modelo com campos opcionais.

    Suporta tanto CST (Regime Normal) quanto CSOSN (Simples Nacional).
    Pelo menos um dos dois deve estar presente.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # Campos alternativos: CST (Regime Normal) OU CSOSN (Simples Nacional)
    cst: Optional[str] = Field(alias="CST", default=None, pattern=r"^\d{2}$")
    csosn: Optional[str] = Field(alias="CSOSN", default=None, pattern=r"^\d{3}$")

    # Campos de ALTA prioridade (opcionais)
    orig: Optional[str] = Field(alias="orig", default=None, pattern=r"^[0-8]$")
    v_bc: Optional[float] = Field(alias="vBC", default=None, ge=0)
    p_icms: Optional[float] = Field(alias="pICMS", default=None, ge=0)
    v_icms: Optional[float] = Field(alias="vICMS", default=None, ge=0)

    # Campos de MEDIA prioridade (opcionais)
    mod_bc: Optional[str] = Field(alias="modBC", default=None)

    @model_validator(mode="after")
    def validate_cst_or_csosn(self):
        """Garante que ICMS tenha CST OU CSOSN (nunca ambos, nunca nenhum)."""
        if not self.cst and not self.csosn:
            raise ValueError("ICMS deve ter CST ou CSOSN")
        if self.cst and self.csosn:
            raise ValueError("ICMS nao pode ter CST e CSOSN simultaneamente")
        return self

    @field_validator("v_bc", "p_icms", "v_icms", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class IPI(BaseModel):
    """Representa os dados do IPI (Imposto sobre Produtos Industrializados).

    O IPI pode estar ausente (nao tributado - IPINT) ou presente (tributado - IPITrib).
    Todos os campos sao opcionais.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    cst: Optional[str] = Field(alias="CST", default=None, pattern=r"^\d{2}$")
    v_bc: Optional[float] = Field(alias="vBC", default=None, ge=0)
    p_ipi: Optional[float] = Field(alias="pIPI", default=None, ge=0)
    v_ipi: Optional[float] = Field(alias="vIPI", default=None, ge=0)

    @field_validator("v_bc", "p_ipi", "v_ipi", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class PIS(BaseModel):
    """Representa os dados do PIS (Programa de Integracao Social).

    O PIS possui multiplas variantes (PISAliq, PISNT, etc.) que sao
    consolidadas neste modelo.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # Campo obrigatorio
    cst: str = Field(alias="CST", pattern=r"^\d{2}$")

    # Campos opcionais
    v_bc: Optional[float] = Field(alias="vBC", default=None, ge=0)
    p_pis: Optional[float] = Field(alias="pPIS", default=None, ge=0)
    v_pis: Optional[float] = Field(alias="vPIS", default=None, ge=0)

    @field_validator("v_bc", "p_pis", "v_pis", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class COFINS(BaseModel):
    """Representa os dados do COFINS (Contribuicao para Financiamento da Seguridade Social).

    O COFINS possui multiplas variantes (COFINSAliq, COFINSNT, etc.) que sao
    consolidadas neste modelo.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    # Campo obrigatorio
    cst: str = Field(alias="CST", pattern=r"^\d{2}$")

    # Campos opcionais
    v_bc: Optional[float] = Field(alias="vBC", default=None, ge=0)
    p_cofins: Optional[float] = Field(alias="pCOFINS", default=None, ge=0)
    v_cofins: Optional[float] = Field(alias="vCOFINS", default=None, ge=0)

    @field_validator("v_bc", "p_cofins", "v_cofins", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class ImpostosItem(BaseModel):
    """Agrega todos os impostos associados a um item da NF-e.

    Consolida ICMS, IPI (opcional), PIS e COFINS de um item especifico.
    IMPORTANTE: PIS e COFINS sao opcionais pois muitos PDFs nao exibem esses impostos por item.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    icms: ICMS
    ipi: Optional[IPI] = None
    pis: Optional[PIS] = None
    cofins: Optional[COFINS] = None


class TotaisImpostos(BaseModel):
    """Representa os totais de impostos consolidados da NF-e.

    Extrai os valores totais do bloco total.ICMSTot do XML.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    v_bc_icms: Optional[float] = Field(alias="vBC", default=None, ge=0)
    v_icms: Optional[float] = Field(alias="vICMS", default=None, ge=0)
    v_ipi: Optional[float] = Field(alias="vIPI", default=None, ge=0)
    v_pis: Optional[float] = Field(alias="vPIS", default=None, ge=0)
    v_cofins: Optional[float] = Field(alias="vCOFINS", default=None, ge=0)

    @field_validator("v_bc_icms", "v_icms", "v_ipi", "v_pis", "v_cofins", mode="before")
    @classmethod
    def _normalize_numeric_fields(cls, v: Any) -> Any:
        """Normaliza campos numericos, convertendo virgula para ponto."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v.replace(",", ".")
        return v


class NFePayload(BaseModel):
    """Payload com os dados extraídos e validados de uma NF-e.

    O enum `UfEnum` garante valores válidos de UF, e os validadores tratam
    normalizações simples (CFOP somente dígitos; valores com vírgula).
    Agora inclui dados completos do emitente e destinatario.
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    cfop: str = Field(pattern=r"^\d{4}$")
    emitente: Emitente
    destinatario: Destinatario
    valor_total: float = Field(ge=0)
    itens: List[NFeItem] = Field(min_length=1)

    # Totais de impostos (Etapa 4)
    totais_impostos: Optional["TotaisImpostos"] = None

    @property
    def emitente_uf(self) -> UfEnum:
        """Property para compatibilidade retroativa com código antigo."""
        return self.emitente.uf

    @property
    def destinatario_uf(self) -> UfEnum:
        """Property para compatibilidade retroativa com código antigo."""
        return self.destinatario.uf

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