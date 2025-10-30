"""
Formatadores de Dados
=====================

Funções auxiliares para formatação de dados fiscais brasileiros
para apresentação no frontend e relatórios.
"""
from typing import Optional, Union
from src.domain.models import Emitente, Destinatario


def format_cnpj(cnpj: str) -> str:
    """Formata CNPJ para o padrão XX.XXX.XXX/XXXX-XX.

    Args:
        cnpj: String com 14 dígitos do CNPJ

    Returns:
        CNPJ formatado ou string original se não tiver 14 dígitos

    Examples:
        >>> format_cnpj("12345678000195")
        "12.345.678/0001-95"
    """
    if not cnpj or not isinstance(cnpj, str):
        return cnpj or ""

    # Remove caracteres não numéricos
    digits = ''.join(ch for ch in cnpj if ch.isdigit())

    if len(digits) != 14:
        return cnpj  # retorna original se não tiver 14 dígitos

    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def format_cpf(cpf: str) -> str:
    """Formata CPF para o padrão XXX.XXX.XXX-XX.

    Args:
        cpf: String com 11 dígitos do CPF

    Returns:
        CPF formatado ou string original se não tiver 11 dígitos

    Examples:
        >>> format_cpf("12345678901")
        "123.456.789-01"
    """
    if not cpf or not isinstance(cpf, str):
        return cpf or ""

    # Remove caracteres não numéricos
    digits = ''.join(ch for ch in cpf if ch.isdigit())

    if len(digits) != 11:
        return cpf  # retorna original se não tiver 11 dígitos

    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def format_documento(destinatario: Destinatario) -> str:
    """Formata CPF ou CNPJ do destinatário automaticamente.

    Detecta se o destinatário é pessoa física (CPF) ou jurídica (CNPJ)
    e aplica a formatação apropriada.

    Args:
        destinatario: Objeto Destinatario

    Returns:
        Documento formatado (CPF ou CNPJ) ou "-" se nenhum estiver presente

    Examples:
        >>> destinatario_pj = Destinatario(cnpj="12345678000195", ...)
        >>> format_documento(destinatario_pj)
        "12.345.678/0001-95"
        >>> destinatario_pf = Destinatario(cpf="12345678901", ...)
        >>> format_documento(destinatario_pf)
        "123.456.789-01"
    """
    if destinatario.cnpj:
        return format_cnpj(destinatario.cnpj)
    elif destinatario.cpf:
        return format_cpf(destinatario.cpf)
    return "-"


def format_cep(cep: Optional[str]) -> str:
    """Formata CEP para o padrão XXXXX-XXX.

    Args:
        cep: String com 8 dígitos do CEP ou None

    Returns:
        CEP formatado ou "-" se None/inválido

    Examples:
        >>> format_cep("01310100")
        "01310-100"
    """
    if not cep or not isinstance(cep, str):
        return "-"

    # Remove caracteres não numéricos
    digits = ''.join(ch for ch in cep if ch.isdigit())

    if len(digits) != 8:
        return cep  # retorna original se não tiver 8 dígitos

    return f"{digits[:5]}-{digits[5:]}"


def format_telefone(telefone: Optional[str]) -> str:
    """Formata telefone brasileiro.

    Tenta detectar o formato baseado no número de dígitos:
    - 10 dígitos: (XX) XXXX-XXXX
    - 11 dígitos: (XX) XXXXX-XXXX
    - Outros: retorna como está

    Args:
        telefone: String com dígitos do telefone ou None

    Returns:
        Telefone formatado ou "-" se None/inválido

    Examples:
        >>> format_telefone("11987654321")
        "(11) 98765-4321"
        >>> format_telefone("1155551234")
        "(11) 5555-1234"
    """
    if not telefone or not isinstance(telefone, str):
        return "-"

    # Remove caracteres não numéricos
    digits = ''.join(ch for ch in telefone if ch.isdigit())

    if len(digits) == 10:
        # Telefone fixo: (XX) XXXX-XXXX
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    elif len(digits) == 11:
        # Celular: (XX) XXXXX-XXXX
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    else:
        # Formato desconhecido, retorna com espaçamento básico se tiver DDD
        if len(digits) >= 2:
            return f"({digits[:2]}) {digits[2:]}"
        return digits


def format_endereco_completo(entidade: Union[Emitente, Destinatario]) -> str:
    """Formata endereço completo do emitente ou destinatário em uma string legível.

    Args:
        entidade: Objeto Emitente ou Destinatario com dados de endereço

    Returns:
        String formatada com endereço completo

    Examples:
        >>> emitente = Emitente(...)
        >>> format_endereco_completo(emitente)
        "Rua das Flores, 123 - Centro - São Paulo/SP - CEP: 01310-100"
        >>> destinatario = Destinatario(...)
        >>> format_endereco_completo(destinatario)
        "Av. Paulista, 1000 - Bela Vista - São Paulo/SP - CEP: 01310-100"
    """
    partes = []

    # Logradouro e número
    if entidade.logradouro:
        if entidade.numero:
            partes.append(f"{entidade.logradouro}, {entidade.numero}")
        else:
            partes.append(entidade.logradouro)

    # Bairro
    if entidade.bairro:
        partes.append(entidade.bairro)

    # Município e UF
    if entidade.municipio:
        partes.append(f"{entidade.municipio}/{entidade.uf.value}")
    else:
        partes.append(entidade.uf.value)

    # CEP
    if entidade.cep:
        partes.append(f"CEP: {format_cep(entidade.cep)}")

    # Junta as partes com " - "
    return " - ".join(partes) if partes else "Endereço não informado"


def format_inscricao_estadual(ie: Optional[str]) -> str:
    """Formata Inscrição Estadual.

    Args:
        ie: String com a IE ou None

    Returns:
        IE formatada ou "ISENTO" / "-"
    """
    if not ie:
        return "-"

    ie_upper = ie.upper()

    if ie_upper == "ISENTO":
        return "ISENTO"

    return ie_upper


def format_valor_monetario(valor: float) -> str:
    """Formata valor monetário para o padrão brasileiro.

    Args:
        valor: Valor numérico

    Returns:
        String formatada: "R$ 1.234,56"

    Examples:
        >>> format_valor_monetario(1234.56)
        "R$ 1.234,56"
    """
    # Formata com separador de milhar e decimal
    valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_formatado}"


def format_quantidade(qtd: Optional[float]) -> str:
    """Formata quantidade comercial com 4 casas decimais.

    Args:
        qtd: Valor da quantidade ou None

    Returns:
        String formatada: "1.234,5000" ou "-" se None

    Examples:
        >>> format_quantidade(3.0)
        "3,0000"
        >>> format_quantidade(10.5)
        "10,5000"
        >>> format_quantidade(None)
        "-"
    """
    if qtd is None:
        return "-"

    # Formata com 4 casas decimais e separador brasileiro
    valor_formatado = f"{qtd:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return valor_formatado


def format_valor_unitario(valor: Optional[float]) -> str:
    """Formata valor unitário comercial no padrão monetário brasileiro.

    Similar a format_valor_monetario, mas aceita None.

    Args:
        valor: Valor unitário ou None

    Returns:
        String formatada: "R$ 1.234,56" ou "-" se None

    Examples:
        >>> format_valor_unitario(2800.00)
        "R$ 2.800,00"
        >>> format_valor_unitario(None)
        "-"
    """
    if valor is None:
        return "-"

    # Formata com separador de milhar e decimal
    valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_formatado}"
