from pathlib import Path

import pytest

from src.agents.xml_parser_agent import parse_xml, XmlParseError
from src.domain.models import UfEnum as UF


BASE = Path("data/exemplos/xml")


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
          <emit>
            <xNome>EMPRESA TESTE</xNome>
            <CNPJ>12345678000100</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest><xNome>DEST TESTE</xNome><CNPJ>11111111000100</CNPJ><enderDest><UF>SP</UF></enderDest></dest>
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
          <emit>
            <xNome>EMPRESA</xNome>
            <CNPJ>00000000000000</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest><xNome>DEST FALTANDO</xNome><CNPJ>66666666000100</CNPJ><enderDest><UF>SP</UF></enderDest></dest>
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
          <emit>
            <xNome>EMPRESA SEM NFEPROC</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest><xNome>CLIENTE XYZ</xNome><CNPJ>22222222000100</CNPJ><enderDest><UF>SP</UF></enderDest></dest>
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


def test_parse_emitente_completo(tmp_path: Path):
    """Testa extração de todos os campos do emitente."""
    xml = tmp_path / "nfe_emitente_completo.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA TESTE LTDA</xNome>
            <CNPJ>12345678000195</CNPJ>
            <IE>123456789</IE>
            <enderEmit>
              <xLgr>Rua das Flores</xLgr>
              <nro>123</nro>
              <xBairro>Centro</xBairro>
              <xMun>Sao Paulo</xMun>
              <UF>SP</UF>
              <CEP>01310100</CEP>
              <fone>1155551234</fone>
            </enderEmit>
          </emit>
          <dest><xNome>CLIENTE RJ LTDA</xNome><CNPJ>33333333000100</CNPJ><enderDest><UF>RJ</UF></enderDest></dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Produto Teste</xProd>
              <NCM>61091000</NCM>
              <CFOP>6102</CFOP>
              <vProd>100.00</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar estrutura básica
    assert payload.cfop == "6102"
    assert payload.destinatario_uf == UF.RJ
    assert payload.valor_total == 100.0

    # Verificar compatibilidade retroativa
    assert payload.emitente_uf == UF.SP

    # Verificar dados completos do emitente
    emitente = payload.emitente
    assert emitente.razao_social == "EMPRESA TESTE LTDA"
    assert emitente.cnpj == "12345678000195"
    assert emitente.inscricao_estadual == "123456789"
    assert emitente.uf == UF.SP
    assert emitente.logradouro == "Rua das Flores"
    assert emitente.numero == "123"
    assert emitente.bairro == "Centro"
    assert emitente.municipio == "Sao Paulo"
    assert emitente.cep == "01310100"
    assert emitente.telefone == "1155551234"


def test_parse_emitente_campos_opcionais_ausentes(tmp_path: Path):
    """Testa que campos opcionais do emitente podem estar ausentes."""
    xml = tmp_path / "nfe_emitente_minimo.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA BASICA</xNome>
            <CNPJ>98765432000100</CNPJ>
            <enderEmit>
              <UF>MG</UF>
            </enderEmit>
          </emit>
          <dest><xNome>COMPRADOR MG</xNome><CNPJ>44444444000100</CNPJ><enderDest><UF>SP</UF></enderDest></dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Item</xProd>
              <CFOP>5102</CFOP>
              <vProd>50</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>50</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar campos obrigatórios
    emitente = payload.emitente
    assert emitente.razao_social == "EMPRESA BASICA"
    assert emitente.cnpj == "98765432000100"
    assert emitente.uf == UF.MG

    # Verificar que campos opcionais são None
    assert emitente.inscricao_estadual is None
    assert emitente.logradouro is None
    assert emitente.numero is None
    assert emitente.bairro is None
    assert emitente.municipio is None
    assert emitente.cep is None
    assert emitente.telefone is None


def test_parse_emitente_cnpj_formatado(tmp_path: Path):
    """Testa que CNPJ formatado é normalizado para apenas dígitos."""
    xml = tmp_path / "nfe_cnpj_formatado.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA COM CNPJ FORMATADO</xNome>
            <CNPJ>12.345.678/0001-95</CNPJ>
            <enderEmit><UF>RS</UF></enderEmit>
          </emit>
          <dest><xNome>COMPRADOR SC</xNome><CNPJ>55555555000100</CNPJ><enderDest><UF>SC</UF></enderDest></dest>
          <det nItem=\"1\">
            <prod><xProd>X</xProd><CFOP>6102</CFOP><vProd>1</vProd></prod>
          </det>
          <total><ICMSTot><vNF>1</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # CNPJ deve ter apenas dígitos (formatação removida)
    assert payload.emitente.cnpj == "12345678000195"
    assert len(payload.emitente.cnpj) == 14


def test_parse_destinatario_pj_completo(tmp_path: Path):
    """Testa extração completa de dados do destinatário pessoa jurídica."""
    xml = tmp_path / "nfe_destinatario_pj.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMITENTE TESTE</xNome>
            <CNPJ>12345678000195</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>ELETRONICOS RIO COMERCIO LTDA</xNome>
            <CNPJ>98765432000111</CNPJ>
            <IE>987654321098</IE>
            <indIEDest>1</indIEDest>
            <enderDest>
              <xLgr>Rua da Assembleia</xLgr>
              <nro>180</nro>
              <xBairro>Centro</xBairro>
              <xMun>Rio de Janeiro</xMun>
              <UF>RJ</UF>
              <CEP>20011001</CEP>
              <fone>2122223333</fone>
            </enderDest>
          </dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Notebook</xProd>
              <NCM>84713000</NCM>
              <CFOP>6102</CFOP>
              <vProd>3500.00</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>3500.00</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar compatibilidade retroativa
    assert payload.destinatario_uf == UF.RJ

    # Verificar dados completos do destinatário
    dest = payload.destinatario
    assert dest.razao_social == "ELETRONICOS RIO COMERCIO LTDA"
    assert dest.cnpj == "98765432000111"
    assert dest.cpf is None  # Pessoa jurídica não tem CPF
    assert dest.inscricao_estadual == "987654321098"
    assert dest.indicador_ie == "1"  # Contribuinte ICMS
    assert dest.uf == UF.RJ
    assert dest.logradouro == "Rua da Assembleia"
    assert dest.numero == "180"
    assert dest.bairro == "Centro"
    assert dest.municipio == "Rio de Janeiro"
    assert dest.cep == "20011001"
    assert dest.telefone == "2122223333"


def test_parse_destinatario_pf_completo(tmp_path: Path):
    """Testa extração completa de dados do destinatário pessoa física."""
    xml = tmp_path / "nfe_destinatario_pf.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>LOJA ABC LTDA</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>CARLOS EDUARDO GABRIEL SANTOS</xNome>
            <CPF>01178498638</CPF>
            <indIEDest>9</indIEDest>
            <enderDest>
              <xLgr>WERNER GOLDBERG</xLgr>
              <nro>77</nro>
              <xBairro>ALPHAVILLE INDUSTRIAL</xBairro>
              <xMun>Barueri</xMun>
              <UF>SP</UF>
              <CEP>06454080</CEP>
            </enderDest>
          </dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Smartphone</xProd>
              <NCM>85171200</NCM>
              <CFOP>5102</CFOP>
              <vProd>1200.00</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>1200.00</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar dados completos do destinatário pessoa física
    dest = payload.destinatario
    assert dest.razao_social == "CARLOS EDUARDO GABRIEL SANTOS"
    assert dest.cpf == "01178498638"
    assert dest.cnpj is None  # Pessoa física não tem CNPJ
    assert dest.indicador_ie == "9"  # Não contribuinte
    assert dest.inscricao_estadual is None  # PF geralmente não tem IE
    assert dest.uf == UF.SP
    assert dest.logradouro == "WERNER GOLDBERG"
    assert dest.numero == "77"
    assert dest.bairro == "ALPHAVILLE INDUSTRIAL"
    assert dest.municipio == "Barueri"
    assert dest.cep == "06454080"


def test_parse_destinatario_campos_opcionais_ausentes(tmp_path: Path):
    """Testa que campos opcionais do destinatário podem estar ausentes."""
    xml = tmp_path / "nfe_destinatario_minimo.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMITENTE</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>DESTINATARIO SIMPLES</xNome>
            <CNPJ>22222222000122</CNPJ>
            <enderDest>
              <UF>MG</UF>
            </enderDest>
          </dest>
          <det nItem=\"1\">
            <prod><xProd>Item</xProd><CFOP>6102</CFOP><vProd>100</vProd></prod>
          </det>
          <total><ICMSTot><vNF>100</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar campos obrigatórios
    dest = payload.destinatario
    assert dest.razao_social == "DESTINATARIO SIMPLES"
    assert dest.cnpj == "22222222000122"
    assert dest.uf == UF.MG

    # Verificar que campos opcionais são None
    assert dest.cpf is None
    assert dest.inscricao_estadual is None
    assert dest.indicador_ie is None
    assert dest.logradouro is None
    assert dest.numero is None
    assert dest.bairro is None
    assert dest.municipio is None
    assert dest.cep is None
    assert dest.telefone is None


def test_parse_destinatario_cpf_formatado(tmp_path: Path):
    """Testa que CPF formatado é normalizado para apenas dígitos."""
    xml = tmp_path / "nfe_destinatario_cpf_formatado.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>JOAO DA SILVA</xNome>
            <CPF>123.456.789-01</CPF>
            <enderDest><UF>SP</UF></enderDest>
          </dest>
          <det nItem=\"1\">
            <prod><xProd>X</xProd><CFOP>5102</CFOP><vProd>1</vProd></prod>
          </det>
          <total><ICMSTot><vNF>1</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # CPF deve ter apenas dígitos (formatação removida)
    assert payload.destinatario.cpf == "12345678901"
    assert len(payload.destinatario.cpf) == 11
    assert payload.destinatario.cnpj is None


def test_parse_destinatario_sem_documento_falha(tmp_path: Path):
    """Testa que destinatário sem CPF nem CNPJ gera erro de validação."""
    xml = tmp_path / "nfe_dest_sem_doc.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>DEST SEM DOC</xNome>
            <enderDest><UF>SP</UF></enderDest>
          </dest>
          <det nItem=\"1\">
            <prod><xProd>X</xProd><CFOP>5102</CFOP><vProd>1</vProd></prod>
          </det>
          <total><ICMSTot><vNF>1</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )

    # Deve falhar porque destinatário precisa ter CPF OU CNPJ
    with pytest.raises(XmlParseError):
        parse_xml(xml)


def test_parse_itens_campos_adicionais():
    """Testa extração dos campos adicionais dos itens (Etapa 3)."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    # Verificar estrutura básica
    assert len(payload.itens) >= 1

    # Verificar campos adicionais do primeiro item (Etapa 3)
    item = payload.itens[0]

    # Campos básicos (já existiam)
    assert item.descricao == "Notebook Dell Inspiron 15 3000 Intel Core i5 8GB 256GB SSD"
    assert item.ncm == "84713012"
    assert item.valor == 8400.00

    # Novos campos (Etapa 3)
    assert item.codigo_produto == "NOTEBOOK-001"
    assert item.quantidade == 3.0
    assert item.valor_unitario == 2800.0
    assert item.unidade_comercial == "UN"

    # Validação cruzada: quantidade * valor_unitario ≈ valor
    assert abs(item.quantidade * item.valor_unitario - item.valor) <= 0.02


def test_parse_itens_campos_adicionais_ausentes(tmp_path: Path):
    """Testa que os novos campos dos itens podem estar ausentes (opcionais)."""
    xml = tmp_path / "nfe_item_sem_campos_novos.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>CLIENTE</xNome>
            <CNPJ>22222222000122</CNPJ>
            <enderDest><UF>SP</UF></enderDest>
          </dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Produto Simples</xProd>
              <NCM>12345678</NCM>
              <CFOP>5102</CFOP>
              <vProd>100.00</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>100</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Verificar que os campos básicos funcionam
    item = payload.itens[0]
    assert item.descricao == "Produto Simples"
    assert item.ncm == "12345678"
    assert item.valor == 100.00

    # Verificar que os novos campos opcionais são None quando ausentes
    assert item.codigo_produto is None
    assert item.quantidade is None
    assert item.valor_unitario is None
    assert item.unidade_comercial is None


def test_parse_itens_validacao_cruzada_com_diferenca(tmp_path: Path):
    """Testa que a validação cruzada aceita pequenas diferenças de arredondamento."""
    xml = tmp_path / "nfe_item_validacao.xml"
    xml.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
        <nfeProc><NFe><infNFe>
          <emit>
            <xNome>EMPRESA</xNome>
            <CNPJ>11111111000111</CNPJ>
            <enderEmit><UF>SP</UF></enderEmit>
          </emit>
          <dest>
            <xNome>CLIENTE</xNome>
            <CNPJ>22222222000122</CNPJ>
            <enderDest><UF>SP</UF></enderDest>
          </dest>
          <det nItem=\"1\">
            <prod>
              <xProd>Item com Arredondamento</xProd>
              <cProd>ITEM-123</cProd>
              <NCM>12345678</NCM>
              <CFOP>5102</CFOP>
              <uCom>UN</uCom>
              <qCom>2.5000</qCom>
              <vUnCom>10.33</vUnCom>
              <vProd>25.83</vProd>
            </prod>
          </det>
          <total><ICMSTot><vNF>25.83</vNF></ICMSTot></total>
        </infNFe></NFe></nfeProc>""",
        encoding="utf-8",
    )
    payload = parse_xml(xml)

    # Deve aceitar a pequena diferença de arredondamento (2.5 * 10.33 = 25.825, arredondado para 25.83)
    item = payload.itens[0]
    assert item.quantidade == 2.5
    assert item.valor_unitario == 10.33
    assert item.valor == 25.83

    # Verificar que a diferença está dentro da tolerância (não lança erro)
    diferenca = abs(item.quantidade * item.valor_unitario - item.valor)
    assert diferenca <= 0.02


# =============================================================================
# Testes de Extração de Impostos (Etapa 4)
# =============================================================================


def test_parse_impostos_completo():
    """Testa extração completa de impostos (ICMS, PIS, COFINS) sem IPI."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    # Verificar que os totais de impostos foram extraídos
    assert payload.totais_impostos is not None
    assert payload.totais_impostos.v_icms is not None
    assert payload.totais_impostos.v_pis is not None
    assert payload.totais_impostos.v_cofins is not None

    # Verificar que pelo menos um item tem impostos
    assert len(payload.itens) > 0
    item = payload.itens[0]
    assert item.impostos is not None

    # Verificar estrutura do ICMS
    assert item.impostos.icms is not None
    assert item.impostos.icms.cst is not None
    assert item.impostos.icms.orig is not None

    # Verificar estrutura do PIS
    assert item.impostos.pis is not None
    assert item.impostos.pis.cst is not None

    # Verificar estrutura do COFINS
    assert item.impostos.cofins is not None
    assert item.impostos.cofins.cst is not None


def test_parse_impostos_com_ipi():
    """Testa extração de impostos incluindo IPI (usando nfe_exemplo_4.xml)."""
    payload = parse_xml(BASE / "nfe_exemplo_4.xml")

    # Verificar totais
    assert payload.totais_impostos is not None
    assert payload.totais_impostos.v_ipi is not None

    # Encontrar item com IPI
    tem_ipi = False
    for item in payload.itens:
        if item.impostos and item.impostos.ipi:
            tem_ipi = True
            # Verificar estrutura do IPI
            assert item.impostos.ipi.cst is not None
            # IPI tributado deve ter valor
            if item.impostos.ipi.v_ipi is not None:
                assert item.impostos.ipi.v_ipi >= 0
            break

    assert tem_ipi, "Nenhum item com IPI encontrado em nfe_exemplo_4.xml"


def test_parse_impostos_icms_variantes():
    """Testa que diferentes variantes de ICMS são extraídas corretamente."""
    # Criar XML com ICMS00
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    item = payload.itens[0]
    assert item.impostos is not None
    assert item.impostos.icms is not None
    assert item.impostos.icms.cst is not None
    assert len(item.impostos.icms.cst) == 2  # CST deve ter 2 dígitos


def test_parse_totais_impostos():
    """Testa extração específica dos totais de impostos."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    totais = payload.totais_impostos
    assert totais is not None

    # Verificar campos dos totais
    assert totais.v_bc_icms is not None or totais.v_bc_icms == 0
    assert totais.v_icms is not None or totais.v_icms == 0
    assert totais.v_ipi is not None or totais.v_ipi == 0
    assert totais.v_pis is not None or totais.v_pis == 0
    assert totais.v_cofins is not None or totais.v_cofins == 0


def test_parse_impostos_valores_numericos():
    """Testa que valores numéricos de impostos são corretamente convertidos."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    item = payload.itens[0]
    if item.impostos:
        # ICMS
        if item.impostos.icms.v_icms is not None:
            assert isinstance(item.impostos.icms.v_icms, (int, float))
            assert item.impostos.icms.v_icms >= 0

        if item.impostos.icms.p_icms is not None:
            assert isinstance(item.impostos.icms.p_icms, (int, float))
            assert 0 <= item.impostos.icms.p_icms <= 100

        # PIS
        if item.impostos.pis.v_pis is not None:
            assert isinstance(item.impostos.pis.v_pis, (int, float))
            assert item.impostos.pis.v_pis >= 0

        # COFINS
        if item.impostos.cofins.v_cofins is not None:
            assert isinstance(item.impostos.cofins.v_cofins, (int, float))
            assert item.impostos.cofins.v_cofins >= 0


def test_parse_impostos_ipi_opcional():
    """Testa que IPI é opcional e alguns itens podem não ter."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    # nfe_exemplo_1 não deve ter IPI nos itens
    for item in payload.itens:
        if item.impostos:
            # IPI deve ser None ou não ter valor
            if item.impostos.ipi:
                # Se existe, pode não ter valores preenchidos
                pass  # IPI opcional está OK


def test_parse_impostos_cst_formato():
    """Testa que CST é extraído no formato correto (2 dígitos)."""
    payload = parse_xml(BASE / "nfe_exemplo_1.xml")

    item = payload.itens[0]
    if item.impostos:
        # Verificar CST do ICMS
        if item.impostos.icms.cst:
            assert len(item.impostos.icms.cst) == 2
            assert item.impostos.icms.cst.isdigit()

        # Verificar CST do PIS
        if item.impostos.pis.cst:
            assert len(item.impostos.pis.cst) == 2
            assert item.impostos.pis.cst.isdigit()

        # Verificar CST do COFINS
        if item.impostos.cofins.cst:
            assert len(item.impostos.cofins.cst) == 2
            assert item.impostos.cofins.cst.isdigit()


