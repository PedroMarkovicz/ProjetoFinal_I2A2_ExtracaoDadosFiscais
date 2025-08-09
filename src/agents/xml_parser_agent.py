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
    return out


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

    payload_data = {
        "cfop": safe_get(first_prod, "CFOP"), # Agora 'first_prod' terá o valor correto
        "emitente_uf": safe_get(nfe_node, "emit.enderEmit.UF"),
        "destinatario_uf": safe_get(nfe_node, "dest.enderDest.UF"),
        "valor_total": safe_get(nfe_node, "total.ICMSTot.vNF"),
        "itens": [_sanitize_prod_for_model(safe_get(item, "prod")) for item in det_list],
    }

    try:
        payload = NFePayload.model_validate(payload_data)

        logger.info(
            "NFe parse OK | cfop=%s emit_uf=%s dest_uf=%s itens=%d vtotal=%.2f",
            payload.cfop,
            payload.emitente_uf.value,
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