import io
import json
import sys
from pathlib import Path
import requests
import streamlit as st

# Adicionar o diretório raiz do projeto ao PYTHONPATH
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ===================== Config básica =====================
st.set_page_config(
    page_title="Extração de Dados Fiscais • NF-e",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Interface de UI para o serviço de Extração de Dados Fiscais de NF-e."
    }
)

# ===================== Estilo (CSS) ======================
st.markdown("""
<style>
    /* Container principal */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }
    
    /* Tipografia aprimorada */
    h1, h2, h3 {
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Botões melhorados */
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 0.75rem;
        font-weight: 600;
        transition: all 0.3s ease;
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    }
    
    /* Botão primário */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Containers com bordas melhoradas */
    div[data-testid="stContainer"] {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    /* Sidebar melhorada */
    .css-1d391kg, section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
    }
    
    /* Sidebar header styling */
    section[data-testid="stSidebar"] h1 {
        font-size: 1.5rem !important;
        margin-bottom: 0.5rem !important;
        text-align: center;
    }
    
    /* Sidebar content spacing */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Métricas aprimoradas */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
        border-radius: 0.75rem;
        padding: 1rem;
        border: 1px solid rgba(148, 163, 184, 0.2);
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    /* Upload área melhorada */
    div[data-testid="stFileUploader"] {
        border: 2px dashed #cbd5e1;
        border-radius: 1rem;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        padding: 2rem;
        transition: all 0.3s ease;
    }
    
    div[data-testid="stFileUploader"]:hover {
        border-color: #667eea;
        background: linear-gradient(135deg, #f0f4ff 0%, #e0e7ff 100%);
    }
    
    /* Status badges */
    .success-badge {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    .warning-badge {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    .error-badge {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    /* Animações */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade-in {
        animation: fadeIn 0.6s ease-out;
    }
    
    /* Dividers melhorados */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
        margin: 2rem 0;
    }
    
    /* Cards de informação */
    .info-card {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border: 1px solid #0ea5e9;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Melhoramentos específicos da sidebar */
    section[data-testid="stSidebar"] .stTextInput > div > div > input {
        border-radius: 0.5rem;
        border: 1px solid #cbd5e1;
        background: rgba(255, 255, 255, 0.9);
        font-size: 0.9rem;
    }
    
    section[data-testid="stSidebar"] .stTextInput > div > div > input:focus {
        border-color: #0ea5e9;
        box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
    }
    
    /* Botões da sidebar */
    section[data-testid="stSidebar"] .stButton > button {
        font-size: 0.85rem;
        padding: 0.4rem 0.8rem;
        border-radius: 0.5rem;
    }
    
    /* Expansores da sidebar */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {
        background: rgba(248, 250, 252, 0.8);
        border-radius: 0.5rem;
        font-size: 0.9rem;
    }
    
    /* Spacing e layout responsivo */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"] {
            width: 100% !important;
        }
        
        section[data-testid="stSidebar"] .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    
    /* Loading spinner customizado */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
</style>
""", unsafe_allow_html=True)

# ===================== Estado ============================
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("uploaded_bytes", None)
st.session_state.setdefault("uploaded_name", None)

# ===================== Funcoes Auxiliares ================
def renderizar_resumo_principal(payload):
    """Renderiza as metricas principais sempre visiveis no topo"""
    from src.utils.formatters import format_valor_monetario

    st.markdown("#### 📊 **Resumo da NF-e**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        valor_total = payload.get("valor_total", 0)
        st.metric(
            "💰 Valor Total",
            format_valor_monetario(valor_total),
            help="Valor total da nota fiscal"
        )

    with col2:
        totais_impostos = payload.get("totais_impostos", {})
        total_impostos = 0
        if totais_impostos:
            total_impostos = sum([
                totais_impostos.get('v_icms', 0) or 0,
                totais_impostos.get('v_ipi', 0) or 0,
                totais_impostos.get('v_pis', 0) or 0,
                totais_impostos.get('v_cofins', 0) or 0
            ])
        st.metric(
            "💸 Total Impostos",
            format_valor_monetario(total_impostos),
            help="Soma de todos os impostos (ICMS + IPI + PIS + COFINS)"
        )

    with col3:
        st.metric(
            "🏷️ CFOP",
            payload.get("cfop", "-"),
            help="Codigo Fiscal de Operacoes e Prestacoes"
        )

    with col4:
        # Extrair UF do emitente
        emitente_data = payload.get("emitente")
        if emitente_data:
            if isinstance(emitente_data, dict):
                emitente_uf_value = emitente_data.get("uf", "-")
                if hasattr(emitente_uf_value, "value"):
                    emitente_uf_value = emitente_uf_value.value
            else:
                emitente_uf_value = getattr(emitente_data, "uf", "-")
                if hasattr(emitente_uf_value, "value"):
                    emitente_uf_value = emitente_uf_value.value
        else:
            emitente_uf_value = payload.get("emitente_uf", "-")

        # Extrair UF do destinatario (mesmo processo do emitente)
        destinatario_data = payload.get("destinatario")
        if destinatario_data:
            if isinstance(destinatario_data, dict):
                dest_uf_value = destinatario_data.get("uf", "-")
                if hasattr(dest_uf_value, "value"):
                    dest_uf_value = dest_uf_value.value
            else:
                dest_uf_value = getattr(destinatario_data, "uf", "-")
                if hasattr(dest_uf_value, "value"):
                    dest_uf_value = dest_uf_value.value
        else:
            dest_uf_value = payload.get("destinatario_uf", "-")

        # Determinar se e Interna ou Interestadual
        if emitente_uf_value == dest_uf_value:
            natureza_operacao = "Interna"
        else:
            natureza_operacao = "Interestadual"

        # Mostrar UFs de forma visivel
        ufs_display = f"{emitente_uf_value} → {dest_uf_value}"

        st.metric(
            "🗺️ Natureza",
            natureza_operacao,
            delta=ufs_display,
            delta_color="off",
            help="Interna: mesma UF | Interestadual: UFs diferentes"
        )


def renderizar_aba_visao_geral(payload, classificacao):
    """Renderiza a aba Visao Geral: classificacao + itens resumidos"""
    from src.utils.formatters import format_valor_monetario, format_quantidade

    # Classificacao Fiscal
    if classificacao:
        st.markdown("### 🧮 **Classificacao Fiscal**")

        class_col1, class_col2 = st.columns(2)

        with class_col1:
            st.markdown(f"**🏦 Conta Debito:** `{classificacao.get('conta_debito', '-')}`")
            st.markdown(f"**💳 Conta Credito:** `{classificacao.get('conta_credito', '-')}`")

        with class_col2:
            st.markdown(f"**🌍 Natureza:** {classificacao.get('natureza_operacao', '-').title()}")
            confianca = classificacao.get('confianca', 0)
            confianca_percent = f"{confianca * 100:.1f}%"
            st.markdown(f"**📈 Confianca:** {confianca_percent}")

        if classificacao.get('justificativa'):
            st.markdown("**💭 Justificativa:**")
            st.info(classificacao.get('justificativa'))

        st.markdown("---")

    # Lista resumida de itens
    itens = payload.get("itens", [])
    if itens:
        st.markdown("### 📦 **Itens da Nota (Resumo)**")

        for i, item in enumerate(itens, 1):
            col_item1, col_item2, col_item3 = st.columns([3, 1, 1])

            with col_item1:
                descricao = item.get('descricao', 'Sem descricao')
                st.markdown(f"**{i}.** {descricao}")

            with col_item2:
                qtd = item.get('quantidade')
                unidade = item.get('unidade_comercial', 'UN')
                st.caption(f"Qtd: **{format_quantidade(qtd)} {unidade}**")

            with col_item3:
                valor = item.get('valor', 0)
                st.caption(f"Valor: **{format_valor_monetario(valor)}**")

        st.info("💡 Para ver todos os detalhes (NCM, CEST, valores unitarios), acesse a aba **'Itens Detalhados'**")
    else:
        st.info("Nenhum item encontrado na nota")


def renderizar_aba_partes(payload):
    """Renderiza a aba Partes: emitente e destinatario em expanders"""
    from src.utils.formatters import (
        format_cnpj, format_cpf, format_cep, format_telefone,
        format_inscricao_estadual, format_endereco_completo, format_documento
    )
    from src.domain.models import Emitente as EmitenteModel, Destinatario as DestinatarioModel

    # Emitente
    emitente = payload.get("emitente")
    if emitente:
        with st.expander("📤 **Dados do Emitente**", expanded=False):
            # Criar objeto se for dict
            if isinstance(emitente, dict):
                try:
                    emitente_obj = EmitenteModel(**emitente)
                except:
                    emitente_obj = None
            else:
                emitente_obj = emitente

            # Razao Social em destaque
            razao_social = emitente.get("razao_social", "-") if isinstance(emitente, dict) else getattr(emitente, "razao_social", "-")
            st.markdown("**🏢 Razao Social:**")
            st.info(razao_social)

            # CNPJ em destaque
            cnpj_raw = emitente.get("cnpj", "") if isinstance(emitente, dict) else getattr(emitente, "cnpj", "")
            st.markdown("**📄 CNPJ:**")
            st.info(format_cnpj(cnpj_raw) if cnpj_raw else "-")

            # Dados principais
            col_emit1, col_emit2, col_emit3 = st.columns(3)

            with col_emit1:
                ie = emitente.get("inscricao_estadual") if isinstance(emitente, dict) else getattr(emitente, "inscricao_estadual", None)
                st.metric("Inscricao Estadual", format_inscricao_estadual(ie))

            with col_emit2:
                uf = emitente.get("uf") if isinstance(emitente, dict) else getattr(emitente, "uf", None)
                uf_display = uf.value if hasattr(uf, "value") else (uf or "-")
                st.metric("UF", uf_display)

            with col_emit3:
                municipio = emitente.get("municipio") if isinstance(emitente, dict) else getattr(emitente, "municipio", None)
                st.metric("Municipio", municipio or "-")

            # Telefone em linha separada
            telefone = emitente.get("telefone") if isinstance(emitente, dict) else getattr(emitente, "telefone", None)
            if telefone:
                st.caption(f"📞 Telefone: **{format_telefone(telefone)}**")

            # Endereco completo
            st.markdown("**📍 Endereco Completo:**")
            if emitente_obj:
                st.info(format_endereco_completo(emitente_obj))
            else:
                logradouro = emitente.get("logradouro") if isinstance(emitente, dict) else getattr(emitente, "logradouro", None)
                numero = emitente.get("numero") if isinstance(emitente, dict) else getattr(emitente, "numero", None)
                bairro = emitente.get("bairro") if isinstance(emitente, dict) else getattr(emitente, "bairro", None)
                cep = emitente.get("cep") if isinstance(emitente, dict) else getattr(emitente, "cep", None)

                end_parts = []
                if logradouro:
                    end_parts.append(f"{logradouro}" + (f", {numero}" if numero else ""))
                if bairro:
                    end_parts.append(bairro)
                if municipio:
                    end_parts.append(f"{municipio}/{uf_display}")
                if cep:
                    end_parts.append(f"CEP: {format_cep(cep)}")

                st.info(" - ".join(end_parts) if end_parts else "Endereco nao informado")

    # Destinatario
    destinatario = payload.get("destinatario")
    if destinatario:
        with st.expander("📥 **Dados do Destinatario**", expanded=False):
            # Criar objeto se for dict
            if isinstance(destinatario, dict):
                try:
                    destinatario_obj = DestinatarioModel(**destinatario)
                except:
                    destinatario_obj = None
            else:
                destinatario_obj = destinatario

            # Razao Social em destaque
            razao_social = destinatario.get("razao_social", "-") if isinstance(destinatario, dict) else getattr(destinatario, "razao_social", "-")
            st.markdown("**👤 Razao Social / Nome:**")
            st.info(razao_social)

            # CPF ou CNPJ em destaque
            if destinatario_obj:
                documento = format_documento(destinatario_obj)
                tipo_doc = "CPF" if destinatario_obj.cpf else "CNPJ"
            else:
                cpf = destinatario.get("cpf") if isinstance(destinatario, dict) else getattr(destinatario, "cpf", None)
                cnpj = destinatario.get("cnpj") if isinstance(destinatario, dict) else getattr(destinatario, "cnpj", None)
                if cpf:
                    documento = format_cpf(cpf)
                    tipo_doc = "CPF"
                elif cnpj:
                    documento = format_cnpj(cnpj)
                    tipo_doc = "CNPJ"
                else:
                    documento = "-"
                    tipo_doc = "Documento"

            st.markdown(f"**📄 {tipo_doc}:**")
            st.info(documento)

            # Dados principais
            col_dest1, col_dest2, col_dest3 = st.columns(3)

            with col_dest1:
                ie = destinatario.get("inscricao_estadual") if isinstance(destinatario, dict) else getattr(destinatario, "inscricao_estadual", None)
                st.metric("Inscricao Estadual", format_inscricao_estadual(ie))

            with col_dest2:
                uf = destinatario.get("uf") if isinstance(destinatario, dict) else getattr(destinatario, "uf", None)
                uf_display = uf.value if hasattr(uf, "value") else (uf or "-")
                st.metric("UF", uf_display)

            with col_dest3:
                municipio = destinatario.get("municipio") if isinstance(destinatario, dict) else getattr(destinatario, "municipio", None)
                st.metric("Municipio", municipio or "-")

            # Telefone em linha separada
            telefone = destinatario.get("telefone") if isinstance(destinatario, dict) else getattr(destinatario, "telefone", None)
            if telefone:
                st.caption(f"📞 Telefone: **{format_telefone(telefone)}**")

            # Endereco completo
            st.markdown("**📍 Endereco Completo:**")
            if destinatario_obj:
                st.info(format_endereco_completo(destinatario_obj))
            else:
                logradouro = destinatario.get("logradouro") if isinstance(destinatario, dict) else getattr(destinatario, "logradouro", None)
                numero = destinatario.get("numero") if isinstance(destinatario, dict) else getattr(destinatario, "numero", None)
                bairro = destinatario.get("bairro") if isinstance(destinatario, dict) else getattr(destinatario, "bairro", None)
                municipio = destinatario.get("municipio") if isinstance(destinatario, dict) else getattr(destinatario, "municipio", None)
                cep = destinatario.get("cep") if isinstance(destinatario, dict) else getattr(destinatario, "cep", None)

                end_parts = []
                if logradouro:
                    end_parts.append(f"{logradouro}" + (f", {numero}" if numero else ""))
                if bairro:
                    end_parts.append(bairro)
                if municipio:
                    end_parts.append(f"{municipio}/{uf_display}")
                if cep:
                    end_parts.append(f"CEP: {format_cep(cep)}")

                st.info(" - ".join(end_parts) if end_parts else "Endereco nao informado")


def renderizar_aba_itens_detalhados(payload):
    """Renderiza a aba Itens Detalhados: todos os dados de cada item"""
    from src.utils.formatters import format_quantidade, format_valor_unitario, format_valor_monetario

    itens = payload.get("itens", [])
    if not itens:
        st.info("Nenhum item encontrado na nota")
        return

    st.markdown(f"### 📦 **Detalhamento Completo dos Itens** ({len(itens)} itens)")

    for i, item in enumerate(itens, 1):
        # Titulo do expander com descricao truncada
        titulo_item = f"📦 Item {i}: {item.get('descricao', 'Sem descricao')[:60]}"
        if len(item.get('descricao', '')) > 60:
            titulo_item += "..."

        with st.expander(titulo_item, expanded=(i == 1)):
            # Linha 1: Identificacao do produto
            col_id1, col_id2, col_id3, col_id4 = st.columns(4)
            with col_id1:
                st.markdown("**📝 Descricao:**")
                st.info(item.get('descricao', '-'))
            with col_id2:
                codigo = item.get('codigo_produto', '-')
                st.metric("Codigo do Produto", codigo if codigo else "-")
            with col_id3:
                ncm = item.get('ncm', '-')
                st.metric("NCM", ncm if ncm else "-")
            with col_id4:
                cest = item.get('cest', '-')
                st.metric("CEST", cest if cest else "N/A", help="Codigo de Substituicao Tributaria")

            st.markdown("---")

            # Linha 2: Quantidade e Unidade
            col_qtd1, col_qtd2, col_qtd3 = st.columns(3)
            with col_qtd1:
                qtd = item.get('quantidade')
                st.metric("Quantidade", format_quantidade(qtd))
            with col_qtd2:
                unidade = item.get('unidade_comercial', '-')
                st.metric("Unidade", unidade if unidade else "-")
            with col_qtd3:
                pass

            st.markdown("---")

            # Linha 3: Valores
            col_val1, col_val2, col_val3 = st.columns(3)
            with col_val1:
                valor_unit = item.get('valor_unitario')
                st.metric("Valor Unitario", format_valor_unitario(valor_unit))
            with col_val2:
                valor_total = item.get('valor', 0)
                st.metric("Valor Total", format_valor_monetario(valor_total))
            with col_val3:
                # Calculo visual
                if qtd is not None and valor_unit is not None:
                    calculado = qtd * valor_unit
                    diferenca = abs(calculado - valor_total)
                    if diferenca <= 0.02:
                        st.success("✓ Calculo conferido")
                    else:
                        st.warning(f"⚠ Dif: R$ {diferenca:.2f}")
                else:
                    st.info("Calculo nao disponivel")


def renderizar_aba_impostos(payload):
    """Renderiza a aba Impostos: totais e detalhamento por item"""
    from src.utils.formatters import format_valor_monetario

    totais_impostos = payload.get("totais_impostos")

    # Bloco 1: Totais consolidados (sempre visivel)
    st.markdown("### 📊 **Totais Consolidados**")

    if totais_impostos:
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)

        with col_t1:
            v_icms = totais_impostos.get('v_icms', 0) or 0
            st.metric("Total ICMS", format_valor_monetario(v_icms))

        with col_t2:
            v_ipi = totais_impostos.get('v_ipi', 0) or 0
            st.metric("Total IPI", format_valor_monetario(v_ipi))

        with col_t3:
            v_pis = totais_impostos.get('v_pis', 0) or 0
            st.metric("Total PIS", format_valor_monetario(v_pis))

        with col_t4:
            v_cofins = totais_impostos.get('v_cofins', 0) or 0
            st.metric("Total COFINS", format_valor_monetario(v_cofins))

        # Base de calculo ICMS
        v_bc_icms = totais_impostos.get('v_bc_icms')
        if v_bc_icms:
            st.caption(f"💼 Base de Calculo ICMS: {format_valor_monetario(v_bc_icms)}")
    else:
        st.info("Totais de impostos nao disponiveis nesta nota.")

    st.markdown("---")

    # Bloco 2: Detalhamento por item
    itens = payload.get("itens", [])
    tem_impostos_detalhados = any(item.get('impostos') for item in itens)

    if tem_impostos_detalhados:
        st.markdown("### 📋 **Impostos por Item**")

        itens_sem_impostos = sum(1 for item in itens if not item.get('impostos'))
        if itens_sem_impostos > 0:
            st.warning(
                f"⚠️ Atencao: {itens_sem_impostos} de {len(itens)} itens nao possuem "
                f"detalhamento de impostos. Isso e comum em notas extraidas de PDF."
            )

        for i, item in enumerate(itens, 1):
            impostos = item.get('impostos')
            if not impostos:
                continue

            # Titulo do expander
            desc_item = item.get('descricao', 'Sem descricao')[:40]
            if len(item.get('descricao', '')) > 40:
                desc_item += "..."

            with st.expander(f"💰 Item {i}: {desc_item}"):
                # ICMS
                icms = impostos.get('icms', {})
                if icms:
                    st.markdown("**🔵 ICMS**")
                    col_icms1, col_icms2, col_icms3, col_icms4 = st.columns(4)

                    with col_icms1:
                        csosn = icms.get('csosn')
                        cst_icms = icms.get('cst')
                        orig = icms.get('orig', '-')

                        if csosn:
                            st.caption(f"CSOSN: **{csosn}**")
                            st.caption("Regime: **Simples Nacional**")
                        else:
                            st.caption(f"CST: **{cst_icms if cst_icms else '-'}**")
                            st.caption("Regime: **Normal**")
                        st.caption(f"Origem: **{orig}**")

                    with col_icms2:
                        v_bc_icms = icms.get('v_bc')
                        if v_bc_icms is not None:
                            st.caption(f"Base Calc:")
                            st.caption(f"**{format_valor_monetario(v_bc_icms)}**")

                    with col_icms3:
                        p_icms = icms.get('p_icms')
                        if p_icms is not None:
                            st.caption(f"Aliquota:")
                            st.caption(f"**{p_icms}%**")

                    with col_icms4:
                        v_icms = icms.get('v_icms')
                        if v_icms is not None:
                            st.caption(f"Valor ICMS:")
                            st.caption(f"**{format_valor_monetario(v_icms)}**")

                    st.markdown("---")

                # IPI
                ipi = impostos.get('ipi')
                if ipi:
                    st.markdown("**🟢 IPI**")
                    col_ipi1, col_ipi2, col_ipi3, col_ipi4 = st.columns(4)

                    with col_ipi1:
                        cst_ipi = ipi.get('cst', '-')
                        st.caption(f"CST: **{cst_ipi}**")

                    with col_ipi2:
                        v_bc_ipi = ipi.get('v_bc')
                        if v_bc_ipi is not None:
                            st.caption(f"Base Calc:")
                            st.caption(f"**{format_valor_monetario(v_bc_ipi)}**")

                    with col_ipi3:
                        p_ipi = ipi.get('p_ipi')
                        if p_ipi is not None:
                            st.caption(f"Aliquota:")
                            st.caption(f"**{p_ipi}%**")

                    with col_ipi4:
                        v_ipi = ipi.get('v_ipi')
                        if v_ipi is not None:
                            st.caption(f"Valor IPI:")
                            st.caption(f"**{format_valor_monetario(v_ipi)}**")

                    st.markdown("---")

                # PIS
                pis = impostos.get('pis', {})
                if pis:
                    st.markdown("**🟡 PIS**")
                    col_pis1, col_pis2, col_pis3, col_pis4 = st.columns(4)

                    with col_pis1:
                        cst_pis = pis.get('cst', '-')
                        st.caption(f"CST: **{cst_pis}**")

                    with col_pis2:
                        v_bc_pis = pis.get('v_bc')
                        if v_bc_pis is not None:
                            st.caption(f"Base Calc:")
                            st.caption(f"**{format_valor_monetario(v_bc_pis)}**")

                    with col_pis3:
                        p_pis = pis.get('p_pis')
                        if p_pis is not None:
                            st.caption(f"Aliquota:")
                            st.caption(f"**{p_pis}%**")

                    with col_pis4:
                        v_pis = pis.get('v_pis')
                        if v_pis is not None:
                            st.caption(f"Valor PIS:")
                            st.caption(f"**{format_valor_monetario(v_pis)}**")

                    st.markdown("---")

                # COFINS
                cofins = impostos.get('cofins', {})
                if cofins:
                    st.markdown("**🟠 COFINS**")
                    col_cofins1, col_cofins2, col_cofins3, col_cofins4 = st.columns(4)

                    with col_cofins1:
                        cst_cofins = cofins.get('cst', '-')
                        st.caption(f"CST: **{cst_cofins}**")

                    with col_cofins2:
                        v_bc_cofins = cofins.get('v_bc')
                        if v_bc_cofins is not None:
                            st.caption(f"Base Calc:")
                            st.caption(f"**{format_valor_monetario(v_bc_cofins)}**")

                    with col_cofins3:
                        p_cofins = cofins.get('p_cofins')
                        if p_cofins is not None:
                            st.caption(f"Aliquota:")
                            st.caption(f"**{p_cofins}%**")

                    with col_cofins4:
                        v_cofins = cofins.get('v_cofins')
                        if v_cofins is not None:
                            st.caption(f"Valor COFINS:")
                            st.caption(f"**{format_valor_monetario(v_cofins)}**")
    else:
        st.info(
            "Detalhamento de impostos por item nao disponivel. "
            "Isso e comum em notas extraidas de DANFE, onde apenas os totais sao exibidos."
        )


def renderizar_aba_dados_tecnicos(payload, classificacao, result):
    """Renderiza a aba Dados Tecnicos: JSON completo e downloads"""
    # Classificacao completa em JSON
    if classificacao:
        with st.expander("🧮 Ver classificacao completa (JSON)"):
            st.json(classificacao)

    # Payload completo
    with st.expander("🔧 Ver payload completo da NF-e", expanded=False):
        st.json(payload or {})

    st.markdown("---")

    # Downloads
    st.markdown("### 📥 **Downloads**")

    col_download1, col_download2 = st.columns(2)

    with col_download1:
        st.download_button(
            label="📁 Baixar Resultado Completo",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name=f"resultado_{st.session_state.get('uploaded_name', 'nfe').replace('.xml', '').replace('.pdf', '')}.json",
            mime="application/json",
            use_container_width=True,
            type="secondary"
        )

    with col_download2:
        if classificacao:
            st.download_button(
                label="🧮 Baixar Apenas Classificacao",
                data=json.dumps(classificacao, ensure_ascii=False, indent=2),
                file_name=f"classificacao_{st.session_state.get('uploaded_name', 'nfe').replace('.xml', '').replace('.pdf', '')}.json",
                mime="application/json",
                use_container_width=True,
                type="secondary"
            )

# ===================== Sidebar ===========================
with st.sidebar:
    # Header da sidebar com design mais limpo
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 1.5rem 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 1.5rem;">
        <h1 style="margin: 0; color: #475569; font-size: 1.4rem;">
            ⚙️ Painel de Controle
        </h1>
        <p style="margin: 0.5rem 0 0 0; color: #64748b; font-size: 0.9rem;">
            Configure e monitore suas análises
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Seção de configuração da API
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); 
                padding: 1rem; border-radius: 0.75rem; border: 1px solid #0ea5e9; margin-bottom: 1rem;">
        <h4 style="margin: 0 0 0.5rem 0; color: #0c4a6e; font-size: 0.9rem;">
            🔗 Configuração da API
        </h4>
    """, unsafe_allow_html=True)
    
    backend_url = st.text_input(
        "URL do Backend",
        value="http://127.0.0.1:8000",
        help="Configure o endereço do seu backend",
        placeholder="http://localhost:8000"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Botões de ação reorganizados
    st.markdown("**🎛️ Ações Rápidas**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        test_button = st.button("🔍 Testar", use_container_width=True, type="secondary")
    
    with col2:
        reset_button = st.button("🔄 Reset", use_container_width=True, type="secondary")
    
    # Feedback dos botões em container separado
    if test_button:
        with st.container():
            try:
                with st.spinner("Testando conexão..."):
                    r = requests.get(f"{backend_url}/health", timeout=5)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    st.success("✅ **Conectado!** Backend responde normalmente.", icon="🎉")
                else:
                    st.warning(f"⚠️ **Status inesperado:** HTTP {r.status_code}")
            except Exception:
                st.error("❌ **Falha na conexão** - Verifique se o backend está rodando")
    
    if reset_button:
        st.session_state.clear()
        st.success("🆕 **Sessão reiniciada!** Todos os dados foram limpos.")
        st.rerun()

    # Status da sessão em card elegante
    if st.session_state.get("last_result"):
        st.markdown("---")
        st.markdown("**📊 Status da Análise Atual**")
        
        result = st.session_state.last_result
        
        # Container do status com cores apropriadas
        if result.get("ok"):
            if result.get("human_review_pending") or result.get("classificacao_needs_review"):
                status_color = "#f59e0b"
                status_bg = "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)"
                status_text = "⏳ Aguardando Revisão"
                status_desc = "A análise precisa de intervenção humana"
            else:
                status_color = "#10b981"
                status_bg = "linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)"
                status_text = "✅ Concluído"
                status_desc = "Extração de Dados automática finalizada"
        else:
            status_color = "#ef4444"
            status_bg = "linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)"
            status_text = "❌ Com Erro"
            status_desc = "Falha durante o processamento"
        
        st.markdown(f"""
        <div style="background: {status_bg}; 
                    padding: 0.75rem; border-radius: 0.5rem; 
                    border-left: 4px solid {status_color}; margin-bottom: 0.5rem;">
            <p style="margin: 0; color: #374151; font-weight: 600; font-size: 0.9rem;">
                {status_text}
            </p>
            <p style="margin: 0.25rem 0 0 0; color: #6b7280; font-size: 0.8rem;">
                {status_desc}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.get("uploaded_name"):
            st.markdown(f"""
            <div style="background: #f9fafb; padding: 0.5rem; border-radius: 0.5rem; 
                        border: 1px solid #e5e7eb; margin-top: 0.5rem;">
                <p style="margin: 0; color: #374151; font-size: 0.8rem;">
                    📄 <strong>Arquivo:</strong> {st.session_state.uploaded_name}
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Informações técnicas em expandir compacto
    st.markdown("---")
    with st.expander("ℹ️ **Informações do Sistema**"):
        st.markdown("""
        **🚀 Como iniciar o backend:**
        ```bash
        uvicorn src.api.main:app --reload
        ```
        
        **📋 Detalhes da versão:**
        - Interface: `v2.2 Enhanced`
        - Recursos: Extração + Revisão
        - Tecnologia: Streamlit + FastAPI
        """)
        
        # Status do sistema
        st.markdown("**🔧 Status dos Componentes:**")
        if st.session_state.get("last_result"):
            st.success("Frontend: ✅ Ativo")
            try:
                r = requests.get(f"{backend_url}/health", timeout=2)
                if r.status_code == 200:
                    st.success("Backend: ✅ Conectado")
                else:
                    st.warning("Backend: ⚠️ Status anômalo")
            except:
                st.error("Backend: ❌ Não conectado")
        else:
            st.info("Sistema: 🟡 Aguardando primeira análise")


# ===================== Cabeçalho =========================
st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)

# Logo da equipe centralizada
col_logo1, col_logo2, col_logo3 = st.columns([2, 1, 2])
with col_logo2:
    st.image("logo-agente-aprende.png", use_container_width=True)
st.title("📄 Extração de Dados Fiscais de NF-e")
st.markdown("""
<div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); 
            padding: 1rem; border-radius: 0.75rem; border: 1px solid #0ea5e9; margin-bottom: 2rem;">
    <p style="margin: 0; color: #0c4a6e; font-size: 1.1rem;">
        🤖 <strong>Inteligência Artificial</strong> para automatizar a Extração de Dados Fiscais de notas fiscais eletrônicas<br>
        ⚡ <strong>Processo:</strong> Upload → Análise → Extração → Revisão (se necessário)
    </p>
</div>
""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ===================== Etapa 1: Classificar ===============
st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("### 🎯 **Etapa 1:** Enviar NF-e para Análise")
    
    # Área de upload melhorada
    st.markdown("""
    <div style="text-align: center; margin: 1rem 0;">
        <p style="color: #64748b; margin-bottom: 0.5rem;">
            📁 Arraste o arquivo XML ou clique para selecionar
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    upload_tab_xml, upload_tab_pdf = st.tabs(["XML", "PDF (DANFE)"])

    with upload_tab_xml:
        xml_file = st.file_uploader(
            "Arquivo XML da NF-e",
            type=["xml"],
            accept_multiple_files=False,
            help="Formatos aceitos: .xml",
            label_visibility="collapsed"
        )

    with upload_tab_pdf:
        pdf_file = st.file_uploader(
            "Arquivo PDF (DANFE)",
            type=["pdf"],
            accept_multiple_files=False,
            help="Formatos aceitos: .pdf",
            label_visibility="collapsed"
        )
    
    # Informações sobre o arquivo selecionado
    if xml_file:
        file_details = f"📄 **{xml_file.name}** | 📏 {xml_file.size:,} bytes"
        st.markdown(f'<div style="background: #f0fdf4; padding: 0.75rem; border-radius: 0.5rem; border-left: 4px solid #22c55e; margin: 1rem 0;">{file_details}</div>', unsafe_allow_html=True)
    if pdf_file:
        file_details = f"🧾 **{pdf_file.name}** | 📏 {pdf_file.size:,} bytes"
        st.markdown(f'<div style="background: #eef2ff; padding: 0.75rem; border-radius: 0.5rem; border-left: 4px solid #6366f1; margin: 1rem 0;">{file_details}</div>', unsafe_allow_html=True)

    # Botão de análise melhorado
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_button = st.button(
            "🚀 Analisar com IA", 
            type="primary", 
            use_container_width=True, 
            disabled=(xml_file is None and pdf_file is None),
            help="Clique para iniciar o processamento inteligente da NF-e"
        )

    if analyze_button:
        target_is_pdf = bool(pdf_file and not xml_file)
        if target_is_pdf:
            st.session_state.uploaded_bytes = pdf_file.getvalue()
            st.session_state.uploaded_name = pdf_file.name
        else:
            st.session_state.uploaded_bytes = xml_file.getvalue()
            st.session_state.uploaded_name = xml_file.name
        st.session_state.last_result = None # Limpa resultado anterior antes de nova análise

        try:
            if target_is_pdf:
                files = { "pdf_file": (st.session_state.uploaded_name, io.BytesIO(st.session_state.uploaded_bytes), "application/pdf") }
                endpoint = f"{backend_url}/classificar/pdf"
            else:
                files = { "xml_file": (st.session_state.uploaded_name, io.BytesIO(st.session_state.uploaded_bytes), "application/xml") }
                endpoint = f"{backend_url}/classificar/xml"
            
            # Progress bar com etapas
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("🔍 Carregando arquivo...")
            progress_bar.progress(25)
            
            status_text.text("🤖 IA analisando estrutura da NF-e...")
            progress_bar.progress(50)
            
            status_text.text("⚡ Extraindo contabilmente...")
            progress_bar.progress(75)
            
            resp = requests.post(endpoint, files=files, timeout=120)
            
            progress_bar.progress(100)
            status_text.text("✅ Análise concluída!")

            if resp.status_code == 200:
                st.session_state.last_result = resp.json()
                st.success("🎉 Análise realizada com sucesso!", icon="✅")
            else:
                st.error(f"🚨 Falha na API (HTTP {resp.status_code}). Detalhes: {resp.text}")
                st.session_state.last_result = None

        except requests.exceptions.RequestException as e:
            st.error(f"🔌 Erro de conexão com o backend: {e}")
            st.info("💡 Verifique se o backend está rodando em: `uvicorn src.api.main:app --reload`")
            st.session_state.last_result = None
        except Exception as e:
            st.error(f"⚠️ Erro inesperado durante o processamento: {e}")
            st.session_state.last_result = None
        finally:
            # Limpar indicadores de progresso após 2 segundos
            if 'progress_bar' in locals():
                progress_bar.empty()
            if 'status_text' in locals():
                status_text.empty()

st.markdown('</div>', unsafe_allow_html=True)

# ===================== Resultado e Etapa 2 ==================
if st.session_state.get("last_result"):
    st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
    result = st.session_state.last_result
    ok = bool(result.get("ok", False))
    needs_review = bool(result.get("human_review_pending") or result.get("classificacao_needs_review"))

    # Determina o tipo de resultado para lógica interna
    outcome_type = "success" if ok and not needs_review else "warning" if ok and needs_review else "error"
    
    # Define o rótulo e o estado VÁLIDO para o st.status
    if outcome_type == "success":
        status_label = "✅ Extração de Dados Concluída"
        state_for_status = "complete"
        badge_html = '<span class="success-badge">🎯 Extração de Dados Automática Concluída</span>'
    elif outcome_type == "warning":
        status_label = "⏳ Revisão Necessária"
        state_for_status = "complete"
        badge_html = '<span class="warning-badge">👤 Requer Intervenção Humana</span>'
    else:
        status_label = "❌ Falha na Extração de Dados"
        state_for_status = "error"
        badge_html = '<span class="error-badge">⚠️ Erro no Processamento</span>'

    # Badge de status
    st.markdown(badge_html, unsafe_allow_html=True)
    
    # Container de resultados
    with st.container(border=True):
        # Bloco st.status com o estado corrigido
        with st.status(status_label, state=state_for_status, expanded=True):
            # Fornece feedback visual dentro do bloco
            if outcome_type == "success":
                st.success("🤖 A IA extraiu automaticamente a NF-e com alta confiança!")
            elif outcome_type == "warning":
                st.warning(f"🔍 **Motivo da Revisão:** {result.get('classificacao_review_reason', 'Não especificado.')}")

            payload = result.get("payload")
            classificacao = result.get("classificacao")

            if payload:
                # Resumo principal sempre visivel
                renderizar_resumo_principal(payload)

                st.markdown("---")

                # Sistema de abas
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📊 Visao Geral",
                    "🏢 Partes",
                    "📦 Itens Detalhados",
                    "💰 Impostos",
                    "🔧 Dados Tecnicos"
                ])

                with tab1:
                    renderizar_aba_visao_geral(payload, classificacao)

                with tab2:
                    renderizar_aba_partes(payload)

                with tab3:
                    renderizar_aba_itens_detalhados(payload)

                with tab4:
                    renderizar_aba_impostos(payload)

                with tab5:
                    renderizar_aba_dados_tecnicos(payload, classificacao, result)

    st.markdown('</div>', unsafe_allow_html=True)

    # Etapa 2 (Revisao) so aparece quando necessario.
    if needs_review:
        st.markdown('<div class="animate-fade-in">', unsafe_allow_html=True)
        st.markdown("---")
        
        # Header da revisão
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); 
                    padding: 1.5rem; border-radius: 0.75rem; border: 1px solid #f59e0b; margin: 1rem 0;">
            <h3 style="margin: 0; color: #92400e;">
                👨‍💼 <strong>Etapa 2:</strong> Revisão Humana Necessária
            </h3>
            <p style="margin: 0.5rem 0 0 0; color: #92400e;">
                A IA precisa da sua expertise para melhorar a classificação. Seus dados serão usados para treinar o modelo.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("### 🎯 **Fornecer Classificação Manual**")
            
            with st.form("human_review_form", clear_on_submit=False):
                payload = result.get("payload", {}) or {}
                
                # Informações de contexto
                st.markdown("#### 📋 **Dados para Classificação**")
                
                info_col1, info_col2, info_col3 = st.columns(3)
                info_col1.info(f"**CFOP Original:** {payload.get('cfop', 'N/A')}")

                # Extrair UF do emitente (compatibilidade com nova estrutura)
                emitente_info = payload.get("emitente")
                if emitente_info:
                    if isinstance(emitente_info, dict):
                        emit_uf = emitente_info.get("uf", "N/A")
                        emit_uf = emit_uf.value if hasattr(emit_uf, "value") else emit_uf
                    else:
                        emit_uf = getattr(emitente_info, "uf", "N/A")
                        emit_uf = emit_uf.value if hasattr(emit_uf, "value") else emit_uf
                else:
                    emit_uf = payload.get('emitente_uf', 'N/A')

                info_col2.info(f"**Operação:** {emit_uf} → {payload.get('destinatario_uf', 'N/A')}")
                info_col3.info(f"**Valor:** R$ {payload.get('valor_total', 0):,.2f}".replace(",", ".").replace(".", ",", 1))
                
                st.markdown("#### ✏️ **Classificação Correta**")
                
                c1, c2 = st.columns([1, 1])
                cfop = c1.text_input(
                    "🏷️ CFOP (4 dígitos)", 
                    value=payload.get("cfop", ""), 
                    max_chars=4, 
                    help="Código Fiscal correto para esta operação (Ex.: 5101, 1102, 6108...)",
                    placeholder="Ex: 5102"
                )
                regime = c2.selectbox(
                    "📊 Regime Tributário", 
                    options=["*", "simples", "presumido", "real"], 
                    index=0,
                    help="Regime da empresa para fins de classificação contábil"
                )
                
                c3, c4 = st.columns(2)
                conta_debito = c3.text_input(
                    "🏦 Conta Débito", 
                    placeholder="Ex: 1.1.3.01.0001",
                    help="Número da conta que será debitada"
                )
                conta_credito = c4.text_input(
                    "💳 Conta Crédito", 
                    placeholder="Ex: 3.1.1.02.0001",
                    help="Número da conta que será creditada"
                )
                
                justificativa_base = st.text_area(
                    "💭 Justificativa da Classificação", 
                    placeholder="Explique a lógica contábil para esta classificação. Ex: 'Venda de mercadoria para cliente final em operação estadual, CFOP 5102 conforme legislação...'",
                    help="Esta informação ajudará a IA a aprender e melhorar futuras classificações",
                    height=100
                )
                
                confianca = st.slider(
                    "📈 Nível de Confiança na sua Classificação", 
                    0.0, 1.0, 0.95, 0.05, 
                    help="Qual sua confiança nesta classificação manual? (0% = baixa, 100% = muito alta)",
                    format="%.0f%%"
                )

                # Botão de envio melhorado
                st.markdown("#### 🚀 **Finalizar Revisão**")
                col_submit1, col_submit2, col_submit3 = st.columns([1, 2, 1])
                
                with col_submit2:
                    submit_review = st.form_submit_button(
                        "✅ Enviar Revisão e Reprocessar", 
                        use_container_width=True, 
                        type="primary",
                        help="Aplicar sua classificação manual e atualizar o resultado"
                    )

                if submit_review:
                    if not (cfop and len("".join(filter(str.isdigit, cfop))) == 4):
                        st.error("🚨 **CFOP inválido.** Por favor, informe exatamente 4 dígitos numéricos.")
                    elif not conta_debito.strip():
                        st.error("🚨 **Conta Débito** é obrigatória.")
                    elif not conta_credito.strip():
                        st.error("🚨 **Conta Crédito** é obrigatória.")
                    elif not justificativa_base.strip():
                        st.error("🚨 **Justificativa** é obrigatória para treinar a IA.")
                    else:
                        hr_data = {
                            "cfop": "".join(filter(str.isdigit, cfop)),
                            "regime": regime,
                            "conta_debito": conta_debito.strip(),
                            "conta_credito": conta_credito.strip(),
                            "justificativa_base": justificativa_base.strip(),
                            "confianca": float(confianca),
                        }
                        files = {}
                        if st.session_state.get("uploaded_name", "").lower().endswith(".pdf"):
                            files["pdf_file"] = (st.session_state.uploaded_name, io.BytesIO(st.session_state.uploaded_bytes), "application/pdf")
                            review_endpoint = f"{backend_url}/classificar/review/pdf"
                        else:
                            files["xml_file"] = (st.session_state.uploaded_name, io.BytesIO(st.session_state.uploaded_bytes), "application/xml")
                            review_endpoint = f"{backend_url}/classificar/review/xml"
                        files["human_review_input"] = (None, json.dumps(hr_data), "application/json")
                        
                        try:
                            # Progress da revisão
                            progress_review = st.progress(0)
                            status_review = st.empty()
                            
                            status_review.text("📝 Processando revisão humana...")
                            progress_review.progress(30)
                            
                            status_review.text("🤖 IA aprendendo com sua classificação...")
                            progress_review.progress(70)
                            
                            resp = requests.post(review_endpoint, files=files, timeout=120)
                            
                            progress_review.progress(100)
                            status_review.text("✅ Revisão aplicada!")

                            if resp.status_code == 200:
                                st.session_state.last_result = resp.json()
                                st.success("🎉 **Revisão aplicada com sucesso!** A IA aprendeu com sua classificação.", icon="✅")
                                st.balloons()
                                st.rerun() 
                            else:
                                st.error(f"🚨 **Falha ao aplicar revisão** (HTTP {resp.status_code}). Detalhes: {resp.text}")

                        except Exception as e:
                            st.error(f"🔌 **Erro de comunicação** ao enviar revisão: {e}")
                        finally:
                            # Limpar indicadores de progresso
                            if 'progress_review' in locals():
                                progress_review.empty()
                            if 'status_review' in locals():
                                status_review.empty()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ===================== Rodapé ===============================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 2rem 0; color: #64748b;">
    <p style="margin: 0; font-size: 0.9rem;">
        🤖 <strong>Extração de Dados Fiscais Inteligente</strong> • 
        Powered by AI • 
        <span style="color: #0ea5e9;">v2.2 Enhanced</span>
    </p>
    <p style="margin: 0.5rem 0 0 0; font-size: 0.8rem;">
        Automatize a Extração de Dados Fiscais de notas fiscais com Inteligência Artificial
    </p>
</div>
""", unsafe_allow_html=True)