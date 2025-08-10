from pathlib import Path

import pytest

from src.agents.xml_parser_agent import parse_xml, XmlParseError
from src.domain.models import UfEnum as UF


BASE = Path("data/exemplos")


def test_parse_minimo():
    payload = parse_xml(BASE / "nota_minima.xml")
    assert payload.cfop == "5102"
    assert payload.emitente_uf == UF.SP
    assert payload.destinatario_uf == UF.SP
    assert payload.valor_total == 100.00
    assert len(payload.itens) == 1
    assert payload.itens[0].descricao.lower().startswith("camiseta")
    assert payload.itens[0].ncm == "61091000"
    assert payload.itens[0].valor == 100.00


def test_parse_varios_itens(tmp_path: Path):
    xml = tmp_path / "nfe_varios.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit><enderEmit><UF>SP</UF></enderEmit></emit>
          <dest><enderDest><UF>SP</UF></enderDest></dest>
          <det nItem=\"1\"><prod><xProd>A</xProd><NCM>123</NCM><CFOP>5102</CFOP><vProd>10</vProd></prod></det>
          <det nItem=\"2\"><prod><xProd>B</xProd><NCM>456</NCM><CFOP>5102</CFOP><vProd>5</vProd></prod></det>
          <total><ICMSTot><vNF>15</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)
    assert payload.valor_total == 15.0
    assert len(payload.itens) == 2
    assert payload.itens[0].valor == 10.0
    assert payload.itens[1].valor == 5.0
    # NCMs inválidos (123, 456) devem ser sanitizados para None
    assert payload.itens[0].ncm is None
    assert payload.itens[1].ncm is None


def test_parse_campos_faltando(tmp_path: Path):
    xml = tmp_path / "nfe_invalida.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit><enderEmit><UF>SP</UF></enderEmit></emit>
          <dest><enderDest><UF>SP</UF></enderDest></dest>
          <det nItem=\"1\"><prod><xProd>A</xProd><NCM>123</NCM><vProd>10</vProd></prod></det>
          <total><ICMSTot><vNF>10</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    with pytest.raises(XmlParseError):
        parse_xml(xml)


def test_parse_sem_nfeProc(tmp_path: Path):
    """Garante que o parser funciona quando o XML não possui o nó raiz nfeProc."""
    xml = tmp_path / "nfe_sem_nfeproc.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <NFe><infNFe>
          <emit><enderEmit><UF>SP</UF></enderEmit></emit>
          <dest><enderDest><UF>SP</UF></enderDest></dest>
          <det nItem=\"1\"><prod><xProd>Produto X</xProd><NCM>61091000</NCM><CFOP>5102</CFOP><vProd>25</vProd></prod></det>
          <total><ICMSTot><vNF>25</vNF></ICMSTot></total>
        </infNFe></NFe>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)
    assert payload.cfop == "5102"
    assert payload.emitente_uf == UF.SP
    assert payload.destinatario_uf == UF.SP
    assert payload.valor_total == 25.0
    assert len(payload.itens) == 1


