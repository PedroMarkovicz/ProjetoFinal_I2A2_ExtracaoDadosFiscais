"""
Testes para CSOSN (Simples Nacional) e CEST (Substituicao Tributaria)
======================================================================

Testa a extracao e validacao de codigos fiscais adicionais:
- CSOSN: Codigo de Situacao Tributaria do Simples Nacional (3 digitos)
- CEST: Codigo Especificador da Substituicao Tributaria (7 digitos)
"""
import pytest
from pathlib import Path
from pydantic import ValidationError

from src.agents.xml_parser_agent import parse_xml
from src.domain.models import NFePayload, ICMS


class TestCSOSNExtraction:
    """Testes para extracao de CSOSN (Simples Nacional)"""

    def test_csosn_extraction_from_xml(self):
        """Testa extracao de CSOSN de XML Simples Nacional"""
        xml_path = Path("data/exemplos/xml/nfe_simples_nacional.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificar que a nota foi parseada
        assert payload is not None
        assert len(payload.itens) >= 1

        # Verificar primeiro item com CSOSN 101
        item1 = payload.itens[0]
        assert item1.impostos is not None

        icms1 = item1.impostos.icms
        assert icms1.csosn == "101"
        assert icms1.cst is None  # CST deve ser None quando CSOSN esta presente
        assert icms1.orig == "0"

        # Verificar segundo item com CSOSN 102 (se existir)
        if len(payload.itens) >= 2:
            item2 = payload.itens[1]
            assert item2.impostos is not None

            icms2 = item2.impostos.icms
            assert icms2.csosn == "102"
            assert icms2.cst is None

    def test_csosn_validation_pattern(self):
        """Testa validacao de pattern do CSOSN (3 digitos)"""
        # CSOSN valido (3 digitos)
        icms_valido = ICMS(CSOSN="101", orig="0")
        assert icms_valido.csosn == "101"

        # CSOSN invalido (2 digitos)
        with pytest.raises(ValidationError) as exc_info:
            ICMS(CSOSN="10", orig="0")
        assert "CSOSN" in str(exc_info.value)

        # CSOSN invalido (4 digitos)
        with pytest.raises(ValidationError) as exc_info:
            ICMS(CSOSN="1010", orig="0")
        assert "CSOSN" in str(exc_info.value)

    def test_cst_csosn_mutual_exclusion(self):
        """Testa que CST e CSOSN sao mutuamente exclusivos"""
        # Deve falhar: ambos presentes
        with pytest.raises(ValidationError) as exc_info:
            ICMS(CST="00", CSOSN="101", orig="0")
        assert "nao pode ter CST e CSOSN simultaneamente" in str(exc_info.value)

        # Deve falhar: nenhum presente
        with pytest.raises(ValidationError) as exc_info:
            ICMS(orig="0")
        assert "deve ter CST ou CSOSN" in str(exc_info.value)

        # Deve passar: apenas CST
        icms_cst = ICMS(CST="00", orig="0")
        assert icms_cst.cst == "00"
        assert icms_cst.csosn is None

        # Deve passar: apenas CSOSN
        icms_csosn = ICMS(CSOSN="101", orig="0")
        assert icms_csosn.csosn == "101"
        assert icms_csosn.cst is None


class TestCESTExtraction:
    """Testes para extracao de CEST (Substituicao Tributaria)"""

    def test_cest_extraction_from_xml(self):
        """Testa extracao de CEST de XML com Substituicao Tributaria"""
        xml_path = Path("data/exemplos/xml/nfe_com_cest.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificar que a nota foi parseada
        assert payload is not None
        assert len(payload.itens) >= 1

        # Verificar primeiro item com CEST (Gasolina)
        item1 = payload.itens[0]
        assert item1.cest == "0600100"
        assert item1.ncm == "27101229"

        # Verificar segundo item com CEST (Diesel)
        if len(payload.itens) >= 2:
            item2 = payload.itens[1]
            assert item2.cest == "0600200"
            assert item2.ncm == "27101921"

    def test_cest_validation_pattern(self):
        """Testa validacao de pattern do CEST (7 digitos)"""
        from src.domain.models import NFeItem

        # CEST valido (7 digitos)
        item_valido = NFeItem(
            xProd="Produto Teste",
            NCM="12345678",
            CEST="0600100",
            vProd=100.0
        )
        assert item_valido.cest == "0600100"

        # CEST invalido (6 digitos)
        with pytest.raises(ValidationError) as exc_info:
            NFeItem(
                xProd="Produto Teste",
                NCM="12345678",
                CEST="060010",
                vProd=100.0
            )
        assert "CEST" in str(exc_info.value)

        # CEST invalido (8 digitos)
        with pytest.raises(ValidationError) as exc_info:
            NFeItem(
                xProd="Produto Teste",
                NCM="12345678",
                CEST="06001000",
                vProd=100.0
            )
        assert "CEST" in str(exc_info.value)

    def test_cest_optional(self):
        """Testa que CEST e opcional (pode ser None)"""
        from src.domain.models import NFeItem

        # Item sem CEST deve ser valido
        item_sem_cest = NFeItem(
            xProd="Produto Teste",
            NCM="12345678",
            vProd=100.0
        )
        assert item_sem_cest.cest is None


class TestBackwardCompatibility:
    """Testes de compatibilidade retroativa"""

    def test_xml_regime_normal_ainda_funciona(self):
        """Testa que XMLs com CST (Regime Normal) continuam funcionando"""
        xml_path = Path("data/exemplos/xml/nfe_exemplo_2.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificar que a nota foi parseada
        assert payload is not None
        assert len(payload.itens) >= 1

        # Verificar que CST ainda funciona
        item1 = payload.itens[0]
        assert item1.impostos is not None

        icms1 = item1.impostos.icms
        assert icms1.cst == "00"
        assert icms1.csosn is None  # CSOSN deve ser None no Regime Normal
        assert icms1.orig == "0"

    def test_item_sem_cest_ainda_valido(self):
        """Testa que itens sem CEST continuam validos"""
        xml_path = Path("data/exemplos/xml/nfe_exemplo_2.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificar que itens sem CEST sao parseados corretamente
        for item in payload.itens:
            # CEST e opcional, pode ser None
            assert item.cest is None or isinstance(item.cest, str)
            # NCM deve estar presente
            assert item.ncm is not None


class TestIntegrationCSOSNCEST:
    """Testes de integracao completos"""

    def test_nfe_simples_nacional_completa(self):
        """Testa parsing completo de NF-e Simples Nacional"""
        xml_path = Path("data/exemplos/xml/nfe_simples_nacional.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificacoes gerais
        assert payload.cfop == "5102"
        assert payload.valor_total > 0
        assert len(payload.itens) >= 1

        # Verificar emitente (Simples Nacional - CRT=1)
        assert payload.emitente.razao_social is not None
        assert payload.emitente.cnpj == "44444444000188"

        # Verificar que todos os itens tem CSOSN
        for item in payload.itens:
            assert item.impostos is not None
            assert item.impostos.icms.csosn is not None
            assert item.impostos.icms.cst is None

    def test_nfe_com_cest_completa(self):
        """Testa parsing completo de NF-e com CEST"""
        xml_path = Path("data/exemplos/xml/nfe_com_cest.xml")

        if not xml_path.exists():
            pytest.skip(f"Arquivo de teste nao encontrado: {xml_path}")

        payload = parse_xml(xml_path)

        # Verificacoes gerais
        assert payload.cfop == "5405"  # CFOP de ST
        assert payload.valor_total > 0
        assert len(payload.itens) >= 1

        # Verificar emitente
        assert payload.emitente.razao_social is not None
        assert payload.emitente.cnpj == "66666666000111"

        # Verificar que todos os itens tem CEST
        for item in payload.itens:
            assert item.cest is not None
            assert len(item.cest) == 7
            assert item.ncm is not None

            # Verificar CST 60 (ICMS cobrado anteriormente por ST)
            if item.impostos:
                assert item.impostos.icms.cst == "60"
                assert item.impostos.icms.csosn is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
