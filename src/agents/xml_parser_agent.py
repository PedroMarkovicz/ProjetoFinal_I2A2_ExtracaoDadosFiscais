"""
XmlParserAgent
=================

Este módulo implementa o parser de NF-e (XML) focado no "happy path",
convertendo a estrutura XML para o modelo de domínio `NFePayload`.

Principais pontos:
- Tenta localizar `infNFe` em caminhos comuns (com e sem `nfeProc`).
- Faz duas tentativas de parsing: com namespaces e removendo namespaces comuns.
- Usa helpers utilitários para: leitura de arquivo, acesso seguro a chaves
  aninhadas (`safe_get`), conversão de nós para lista (`_as_list`) e uma
  sanitização leve dos produtos para adequação aos modelos Pydantic.
- Gera logs em pontos relevantes para facilitar troubleshooting.
"""
# src/agents/xml_parser_agent.py
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import xmltodict
from pydantic import ValidationError
from src.domain.models import NFePayload

logger = logging.getLogger(__name__)


class XmlParseError(ValueError):
    """Erro de parsing da NF-e com campo opcional de código.

    Use este erro para sinalizar problemas conhecidos e fornecer uma
    mensagem clara ao usuário. O atributo `code` pode ser usado no futuro
    para categorização programática.
    """
    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code

# ----------------- Funções Auxiliares (sem alterações) -----------------

def _read_bytes(path: Path) -> bytes:
    """Lê o conteúdo bruto do arquivo no caminho fornecido.

    Levanta `XmlParseError` com mensagem clara em caso de falha de I/O.
    """
    try:
        return path.read_bytes()
    except Exception as exc:
        logger.error("Falha ao ler o arquivo XML: %s", path, exc_info=True)
        raise XmlParseError(f"Falha ao ler o arquivo XML: {path}") from exc

def _strip_common_xmlns(xml_bytes: bytes) -> bytes:
    """Remove atributos de namespace (`xmlns`/`xmlns:foo`) comuns.

    Isso ajuda a simplificar o parsing em ambientes onde o XML inclui
    namespaces que atrapalham a navegação por chaves simples.
    """
    return re.sub(rb'\s+xmlns(?::\w+)?="[^"]+"', b"", xml_bytes)

def _as_list(node_or_list: Any) -> list:
    """Garante uma lista a partir de um nó que pode ser `None`, dict ou list."""
    if node_or_list is None:
        return []
    return node_or_list if isinstance(node_or_list, list) else [node_or_list]

def safe_get(data: Any, path: str, default: Any | None = None) -> Any:
    """Acessa chaves aninhadas em um dicionário usando caminho com pontos.

    Exemplo: `safe_get(doc, "nfeProc.NFe.infNFe")`.
    Retorna `default` caso algum nível não exista ou o nó não seja um dict.
    """
    node = data
    for key in path.split("."):
        if not isinstance(node, dict):
            return default
        node = node.get(key)
        if node is None:
            return default
    return node

def _locate_infNFe(tree: dict[str, Any]) -> dict[str, Any] | None:
    """Tenta localizar o nó `infNFe` em caminhos comuns do XML da NF-e."""
    candidate_paths = ["nfeProc.NFe.infNFe", "NFe.infNFe"]
    for p in candidate_paths:
        node = safe_get(tree, p)
        if isinstance(node, dict):
            return node
    return None


# Sanitização leve para adequar aos modelos Pydantic sem alterar a semântica
def _sanitize_prod_for_model(prod: Any) -> dict[str, Any]:
    """Normaliza o nó `prod` para aderir às validações dos modelos.

    Extrai todos os campos do produto incluindo:
    - xProd: Descrição do produto (obrigatório)
    - NCM: Código NCM (opcional, validado)
    - vProd: Valor total do produto (obrigatório)
    - qCom: Quantidade comercial (opcional, Etapa 3)
    - vUnCom: Valor unitário comercial (opcional, Etapa 3)
    - uCom: Unidade comercial (opcional, Etapa 3)
    - cProd: Código do produto (opcional, Etapa 3)

    Sanitizações aplicadas:
    - Remove `NCM` inválido (não 8 dígitos), permitindo `Optional[str]`
      permanecer como `None` quando necessário.
    - Garante `xProd` com valor mínimo.
    """
    if not isinstance(prod, dict):
        prod = {}
    out = dict(prod)
    # Remover NCM inválido (não 8 dígitos) para permitir Optional[str] com default None
    ncm = out.get("NCM")
    if ncm is not None and not re.fullmatch(r"\d{8}", str(ncm)):
        out.pop("NCM", None)
    # Garantir xProd mínimo
    if not out.get("xProd"):
        out["xProd"] = "Item"
    # Os campos adicionais (qCom, vUnCom, uCom, cProd) são extraídos automaticamente
    # pois estão inclusos no dict(prod) copiado acima
    return out


# ----------------- Funções de Extração de Impostos (Etapa 4) -----------------

def _extract_icms(imposto_node: Any) -> dict[str, Any] | None:
    """Extrai dados do ICMS do nó imposto, tratando variações (ICMS00, ICMS10, etc).

    O ICMS pode ter diferentes situações tributárias (ICMS00, ICMS10, ICMS20, etc)
    para Regime Normal ou ICMSSN* para Simples Nacional.
    Esta função detecta qual variante está presente e extrai os campos relevantes,
    incluindo CST (Regime Normal) ou CSOSN (Simples Nacional).

    Returns:
        Dicionário com campos do ICMS ou None se não encontrado.
    """
    icms_node = safe_get(imposto_node, "ICMS")
    if not isinstance(icms_node, dict):
        return None

    # Possíveis variantes de ICMS
    icms_variants = [
        "ICMS00", "ICMS10", "ICMS20", "ICMS30", "ICMS40", "ICMS51",
        "ICMS60", "ICMS70", "ICMS90", "ICMSSN101", "ICMSSN102",
        "ICMSSN201", "ICMSSN202", "ICMSSN500", "ICMSSN900"
    ]

    # Encontrar qual variante está presente
    icms_data = None
    for variant in icms_variants:
        variant_node = icms_node.get(variant)
        if isinstance(variant_node, dict):
            icms_data = variant_node
            break

    if not icms_data:
        logger.warning("Nó ICMS encontrado mas nenhuma variante identificada: %s", icms_node.keys())
        return None

    # Extrair campos disponíveis (CST para Regime Normal, CSOSN para Simples Nacional)
    return {
        "CST": safe_get(icms_data, "CST"),
        "CSOSN": safe_get(icms_data, "CSOSN"),
        "orig": safe_get(icms_data, "orig"),
        "vBC": safe_get(icms_data, "vBC"),
        "pICMS": safe_get(icms_data, "pICMS"),
        "vICMS": safe_get(icms_data, "vICMS"),
        "modBC": safe_get(icms_data, "modBC"),
    }


def _extract_ipi(imposto_node: Any) -> dict[str, Any] | None:
    """Extrai dados do IPI do nó imposto, tratando IPITrib vs IPINT.

    O IPI pode estar tributado (IPITrib) ou não tributado (IPINT).
    Caso não tributado, apenas o CST é preenchido.

    Returns:
        Dicionário com campos do IPI ou None se não encontrado.
    """
    ipi_node = safe_get(imposto_node, "IPI")
    if not isinstance(ipi_node, dict):
        return None

    # Verificar IPITrib (tributado)
    ipi_trib = ipi_node.get("IPITrib")
    if isinstance(ipi_trib, dict):
        return {
            "CST": safe_get(ipi_trib, "CST"),
            "vBC": safe_get(ipi_trib, "vBC"),
            "pIPI": safe_get(ipi_trib, "pIPI"),
            "vIPI": safe_get(ipi_trib, "vIPI"),
        }

    # Verificar IPINT (não tributado)
    ipi_nt = ipi_node.get("IPINT")
    if isinstance(ipi_nt, dict):
        return {
            "CST": safe_get(ipi_nt, "CST"),
            "vBC": None,
            "pIPI": None,
            "vIPI": None,
        }

    logger.warning("Nó IPI encontrado mas sem IPITrib ou IPINT: %s", ipi_node.keys())
    return None


def _extract_pis(imposto_node: Any) -> dict[str, Any] | None:
    """Extrai dados do PIS do nó imposto, tratando variações (PISAliq, PISNT, etc).

    O PIS pode ter diferentes regimes de tributação (PISAliq, PISNT, PISQtde, etc).

    Returns:
        Dicionário com campos do PIS ou None se não encontrado.
    """
    pis_node = safe_get(imposto_node, "PIS")
    if not isinstance(pis_node, dict):
        return None

    # Possíveis variantes de PIS
    pis_variants = ["PISAliq", "PISNT", "PISQtde", "PISOutr"]

    pis_data = None
    for variant in pis_variants:
        variant_node = pis_node.get(variant)
        if isinstance(variant_node, dict):
            pis_data = variant_node
            break

    if not pis_data:
        logger.warning("Nó PIS encontrado mas nenhuma variante identificada: %s", pis_node.keys())
        return None

    return {
        "CST": safe_get(pis_data, "CST"),
        "vBC": safe_get(pis_data, "vBC"),
        "pPIS": safe_get(pis_data, "pPIS"),
        "vPIS": safe_get(pis_data, "vPIS"),
    }


def _extract_cofins(imposto_node: Any) -> dict[str, Any] | None:
    """Extrai dados do COFINS do nó imposto, tratando variações (COFINSAliq, COFINSNT, etc).

    O COFINS pode ter diferentes regimes de tributação (COFINSAliq, COFINSNT, COFINSQtde, etc).

    Returns:
        Dicionário com campos do COFINS ou None se não encontrado.
    """
    cofins_node = safe_get(imposto_node, "COFINS")
    if not isinstance(cofins_node, dict):
        return None

    # Possíveis variantes de COFINS
    cofins_variants = ["COFINSAliq", "COFINSNT", "COFINSQtde", "COFINSOutr"]

    cofins_data = None
    for variant in cofins_variants:
        variant_node = cofins_node.get(variant)
        if isinstance(variant_node, dict):
            cofins_data = variant_node
            break

    if not cofins_data:
        logger.warning("Nó COFINS encontrado mas nenhuma variante identificada: %s", cofins_node.keys())
        return None

    return {
        "CST": safe_get(cofins_data, "CST"),
        "vBC": safe_get(cofins_data, "vBC"),
        "pCOFINS": safe_get(cofins_data, "pCOFINS"),
        "vCOFINS": safe_get(cofins_data, "vCOFINS"),
    }


def _extract_impostos_item(item_node: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai todos os impostos de um item (det) da NF-e.

    Consolida ICMS, IPI (opcional), PIS e COFINS de um item específico.

    Args:
        item_node: Nó 'det' do XML representando um item

    Returns:
        Dicionário com estrutura ImpostosItem ou None se impostos não encontrados
    """
    imposto_node = safe_get(item_node, "imposto")
    if not isinstance(imposto_node, dict):
        logger.warning("Nó 'imposto' não encontrado ou inválido no item")
        return None

    # Extrair cada tipo de imposto
    icms_data = _extract_icms(imposto_node)
    ipi_data = _extract_ipi(imposto_node)  # Opcional
    pis_data = _extract_pis(imposto_node)
    cofins_data = _extract_cofins(imposto_node)

    # Validar campos obrigatórios
    if not icms_data:
        logger.warning("ICMS não encontrado no item - impostos incompletos")
        return None
    if not pis_data:
        logger.warning("PIS não encontrado no item - impostos incompletos")
        return None
    if not cofins_data:
        logger.warning("COFINS não encontrado no item - impostos incompletos")
        return None

    result = {
        "icms": icms_data,
        "pis": pis_data,
        "cofins": cofins_data,
    }

    # IPI é opcional
    if ipi_data:
        result["ipi"] = ipi_data

    return result


def _extract_totais_impostos(nfe_node: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai os totais de impostos do bloco total.ICMSTot.

    Args:
        nfe_node: Nó 'infNFe' do XML

    Returns:
        Dicionário com estrutura TotaisImpostos ou None se não encontrado
    """
    icms_tot = safe_get(nfe_node, "total.ICMSTot")
    if not isinstance(icms_tot, dict):
        logger.warning("Nó 'total.ICMSTot' não encontrado")
        return None

    return {
        "vBC": safe_get(icms_tot, "vBC"),
        "vICMS": safe_get(icms_tot, "vICMS"),
        "vIPI": safe_get(icms_tot, "vIPI"),
        "vPIS": safe_get(icms_tot, "vPIS"),
        "vCOFINS": safe_get(icms_tot, "vCOFINS"),
    }


# ----------------- Função Principal (com a correção) -----------------

def parse_xml(xml_path: str | Path) -> NFePayload:
    """Converte um arquivo XML de NF-e em `NFePayload` validado.

    Passos principais:
    1) Lê bytes do arquivo
    2) Faz parsing com `xmltodict` (com e sem namespaces)
    3) Localiza `infNFe` e extrai campos mínimos
    4) Normaliza itens e valida tudo via Pydantic
    """
    logger.debug("parse_xml chamado com xml_path=%s", xml_path)
    path = Path(xml_path)
    if not path.exists():
        raise XmlParseError(f"Arquivo XML não encontrado: {path}")

    logger.debug("Lendo bytes do arquivo: %s", path)
    raw_bytes = _read_bytes(path)

    try:
        logger.debug("Primeira tentativa de parsing XML (com namespaces)")
        data = xmltodict.parse(raw_bytes)
        nfe_node = _locate_infNFe(data)
        if not nfe_node:
            logger.debug("Segunda tentativa de parsing XML (removendo namespaces comuns)")
            data = xmltodict.parse(_strip_common_xmlns(raw_bytes))
            nfe_node = _locate_infNFe(data)
    except Exception as e:
        logger.exception("Falha crítica ao fazer o parsing do XML para dicionário")
        raise XmlParseError(f"Erro irrecuperável ao processar o XML: {e}") from e

    if not nfe_node:
        raise XmlParseError("Estrutura XML inválida: não foi possível encontrar 'infNFe'")

    det_list = _as_list(safe_get(nfe_node, "det"))
    logger.debug("Itens (det) encontrados: %d", len(det_list))
    
    # --- INÍCIO DA CORREÇÃO ---
    # Primeiro, pegamos o primeiro item da lista de forma segura.
    first_item_dict = det_list[0] if det_list else {}
    # Depois, usamos safe_get no dicionário do item para pegar o 'prod'.
    first_prod = safe_get(first_item_dict, "prod") or {}
    # --- FIM DA CORREÇÃO ---

    # Extrair dados completos do emitente
    emitente_data = {
        "xNome": safe_get(nfe_node, "emit.xNome"),
        "CNPJ": safe_get(nfe_node, "emit.CNPJ"),
        "IE": safe_get(nfe_node, "emit.IE"),
        "uf": safe_get(nfe_node, "emit.enderEmit.UF"),
        "xMun": safe_get(nfe_node, "emit.enderEmit.xMun"),
        "xBairro": safe_get(nfe_node, "emit.enderEmit.xBairro"),
        "xLgr": safe_get(nfe_node, "emit.enderEmit.xLgr"),
        "nro": safe_get(nfe_node, "emit.enderEmit.nro"),
        "CEP": safe_get(nfe_node, "emit.enderEmit.CEP"),
        "fone": safe_get(nfe_node, "emit.enderEmit.fone"),
    }

    # Extrair dados completos do destinatario
    destinatario_data = {
        "xNome": safe_get(nfe_node, "dest.xNome"),
        "CNPJ": safe_get(nfe_node, "dest.CNPJ"),
        "CPF": safe_get(nfe_node, "dest.CPF"),
        "IE": safe_get(nfe_node, "dest.IE"),
        "indIEDest": safe_get(nfe_node, "dest.indIEDest"),
        "uf": safe_get(nfe_node, "dest.enderDest.UF"),
        "xMun": safe_get(nfe_node, "dest.enderDest.xMun"),
        "xBairro": safe_get(nfe_node, "dest.enderDest.xBairro"),
        "xLgr": safe_get(nfe_node, "dest.enderDest.xLgr"),
        "nro": safe_get(nfe_node, "dest.enderDest.nro"),
        "CEP": safe_get(nfe_node, "dest.enderDest.CEP"),
        "fone": safe_get(nfe_node, "dest.enderDest.fone"),
    }

    # Extrair impostos dos itens (Etapa 4) e CEST (Etapa 5)
    itens_list = []
    for item in det_list:
        item_data = _sanitize_prod_for_model(safe_get(item, "prod"))
        # Extrair CEST (Código de Substituição Tributária) - Etapa 5
        cest = safe_get(item, "prod.CEST")
        if cest:
            item_data["CEST"] = cest
        # Tentar extrair impostos do item
        impostos = _extract_impostos_item(item)
        if impostos:
            item_data["impostos"] = impostos
        itens_list.append(item_data)

    # Extrair totais de impostos (Etapa 4)
    totais_impostos = _extract_totais_impostos(nfe_node)

    payload_data = {
        "cfop": safe_get(first_prod, "CFOP"),
        "emitente": emitente_data,
        "destinatario": destinatario_data,
        "valor_total": safe_get(nfe_node, "total.ICMSTot.vNF"),
        "itens": itens_list,
    }

    # Adicionar totais de impostos se disponíveis (Etapa 4)
    if totais_impostos:
        payload_data["totais_impostos"] = totais_impostos

    try:
        payload = NFePayload.model_validate(payload_data)

        # Determinar tipo de documento do destinatario
        dest_doc = payload.destinatario.cnpj if payload.destinatario.cnpj else payload.destinatario.cpf
        dest_doc_tipo = "CNPJ" if payload.destinatario.cnpj else "CPF"

        logger.info(
            "NFe parse OK | cfop=%s emitente=%s (CNPJ: %s, UF: %s) destinatario=%s (%s: %s, UF: %s) itens=%d vtotal=%.2f",
            payload.cfop,
            payload.emitente.razao_social[:30] if len(payload.emitente.razao_social) > 30 else payload.emitente.razao_social,
            payload.emitente.cnpj,
            payload.emitente.uf.value,
            payload.destinatario.razao_social[:30] if len(payload.destinatario.razao_social) > 30 else payload.destinatario.razao_social,
            dest_doc_tipo,
            dest_doc,
            payload.destinatario_uf.value,
            len(payload.itens),
            payload.valor_total,
        )
        logger.debug("Payload validado com sucesso: %s", payload.model_dump())
        return payload

    except ValidationError as e:
        logger.error("Dados da NF-e são inválidos. Erros: %s", e.errors())
        error_details = "; ".join(
            f"{err['loc'][-1]}: {err['msg']}" for err in e.errors()
        )
        raise XmlParseError(f"Dados da NF-e inválidos: {error_details}") from e