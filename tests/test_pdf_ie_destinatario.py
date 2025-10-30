"""
Testes para validar extração de Inscrição Estadual (IE) do destinatário em PDFs

Referência: Issue relatada sobre IE do destinatário não sendo extraída corretamente
"""
from pathlib import Path
import pytest
from src.agents.pdf_parser_agent import parse_pdf


BASE = Path("data/exemplos/pdf")


@pytest.mark.skipif(
    not BASE.exists(),
    reason="Diretório de PDFs de exemplo não encontrado"
)
class TestIEDestinatarioPDF:
    """Testes de extração de IE do destinatário em PDFs."""

    def test_ie_destinatario_exemplo_1(self):
        """Testa extração de IE do destinatário em nfe_exemplo_1.pdf."""
        pdf_path = BASE / "nfe_exemplo_1.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Arquivo não encontrado: {pdf_path}")

        resultado = parse_pdf(pdf_path)

        # Verificar que destinatário foi extraído
        assert resultado.destinatario is not None
        assert resultado.destinatario.razao_social is not None

        # Verificar que IE foi extraída
        assert resultado.destinatario.inscricao_estadual is not None, \
            "IE do destinatário não foi extraída"

        # Verificar que IE não é string vazia
        assert resultado.destinatario.inscricao_estadual.strip() != "", \
            "IE do destinatário está vazia"

        print(f"IE extraída: {resultado.destinatario.inscricao_estadual}")

    def test_ie_destinatario_exemplo_2(self):
        """Testa extração de IE do destinatário em nfe_exemplo_2.pdf."""
        pdf_path = BASE / "nfe_exemplo_2.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Arquivo não encontrado: {pdf_path}")

        resultado = parse_pdf(pdf_path)

        assert resultado.destinatario is not None
        assert resultado.destinatario.inscricao_estadual is not None, \
            "IE do destinatário não foi extraída"
        assert resultado.destinatario.inscricao_estadual.strip() != ""

        print(f"IE extraída: {resultado.destinatario.inscricao_estadual}")

    def test_ie_destinatario_vs_emitente(self):
        """Verifica que IE do destinatário é diferente da IE do emitente."""
        pdf_path = BASE / "nfe_exemplo_1.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Arquivo não encontrado: {pdf_path}")

        resultado = parse_pdf(pdf_path)

        # Ambas IEs devem existir
        assert resultado.emitente.inscricao_estadual is not None
        assert resultado.destinatario.inscricao_estadual is not None

        # IEs devem ser diferentes (emitente ≠ destinatário)
        assert resultado.emitente.inscricao_estadual != resultado.destinatario.inscricao_estadual, \
            "IE do emitente não pode ser igual à IE do destinatário"

        print(f"IE Emitente: {resultado.emitente.inscricao_estadual}")
        print(f"IE Destinatário: {resultado.destinatario.inscricao_estadual}")

    def test_ie_destinatario_localizacao_ao_lado_uf(self):
        """
        Testa o caso específico relatado: IE ao lado do campo UF.

        Este teste documenta o problema original:
        - A IE do destinatário está localizada ao lado direito do campo UF
        - Deve ser extraída corretamente mesmo nessa posição
        """
        pdf_path = BASE / "nfe_exemplo_1.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Arquivo não encontrado: {pdf_path}")

        resultado = parse_pdf(pdf_path)

        # Verificar que UF foi extraída
        assert resultado.destinatario.uf is not None

        # Verificar que IE (que está ao lado de UF) também foi extraída
        assert resultado.destinatario.inscricao_estadual is not None, \
            "IE do destinatário (localizada ao lado de UF) não foi extraída"

        print(f"UF: {resultado.destinatario.uf.value}")
        print(f"IE (ao lado de UF): {resultado.destinatario.inscricao_estadual}")


@pytest.mark.skipif(
    not BASE.exists(),
    reason="Diretório de PDFs de exemplo não encontrado"
)
def test_ie_destinatario_formato_valido():
    """Verifica que IE extraída tem formato válido (não é placeholder)."""
    pdf_path = BASE / "nfe_exemplo_1.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Arquivo não encontrado: {pdf_path}")

    resultado = parse_pdf(pdf_path)

    ie = resultado.destinatario.inscricao_estadual

    # IE não deve ser None
    assert ie is not None

    # IE não deve ser string vazia ou "ISENTO" vazia
    assert ie.strip() != ""

    # IE deve conter pelo menos alguns dígitos (formato válido)
    digitos = sum(c.isdigit() for c in ie)
    assert digitos >= 6, f"IE parece inválida: {ie}"

    print(f"IE válida extraída: {ie}")
