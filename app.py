import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
from io import BytesIO
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cronograma RJAIA Simplex", layout="wide", page_icon="📅")

# --- 1. BASE DE DADOS DE FERIADOS (2025-2027) ---
feriados_nacionais = [
    # 2025
    "2025-01-01", "2025-04-18", "2025-04-20", "2025-04-25", "2025-05-01",
    "2025-06-10", "2025-06-19", "2025-08-15", "2025-10-05", "2025-11-01",
    "2025-12-01", "2025-12-08", "2025-12-25",
    # 2026
    "2026-01-01", "2026-04-03", "2026-04-05", "2026-04-25", "2026-05-01",
    "2026-06-04", "2026-06-10", "2026-08-15", "2026-10-05", "2026-11-01",
    "2026-12-01", "2026-12-08", "2026-12-25",
    # 2027
    "2027-01-01", "2027-03-26", "2027-03-28", "2027-04-25", "2027-05-01",
    "2027-05-27", "2027-06-10", "2027-08-15", "2027-10-05", "2027-11-01",
    "2027-12-01", "2027-12-08", "2027-12-25"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- 2. FUNÇÕES DE CÁLCULO E FORMATAÇÃO ---
def somar_dias_uteis(data_inicio, dias, feriados):
    """Soma dias úteis (salta sáb, dom e feriados)."""
    return np.busday_offset(
        np.datetime64(data_inicio), 
        dias, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados
    )

def formatar_data(np_date):
    """Converte numpy datetime para string PT."""
    return pd.to_datetime(np_date).strftime("%d/%m/%Y")

# --- 3. FUNÇÃO GERADORA DE WORD ---
def gerar_relatorio_word(df_dados, data_fim, total_dias, prazo_max, saldo):
    doc = Document()
    
    # Estilo do Título
    titulo = doc.add_heading('Cronograma RJAIA (Simplex)', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data de Simulação: {date.today().strftime("%d/%m/%Y")}')
    doc.add_paragraph('')

    # 1. Enquadramento Legal
    doc.add_heading('1. Enquadramento Legal', level=1)
    texto_legal = (
        "A presente calendarização foi elaborada considerando o Regime Jurídico da Avaliação de Impacte Ambiental (RJAIA), "
        "aprovado pelo Decreto-Lei n.º 151-B/2013, na sua redação atual (incluindo alterações do Simplex Ambiental).\n"
        "A contagem de prazos observa o Código do Procedimento Administrativo (CPA), efetuando-se em dias úteis, "
        "suspendendo-se aos sábados, domingos e feriados nacionais. "
        "Considerou-se que o prazo não se suspende durante as férias judiciais, conforme prática administrativa aplicável."
    )
    p = doc.add_paragraph(texto_legal)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2. Resumo
    doc.add_heading('2. Resumo do Cálculo', level=1)
    doc.add_paragraph(f'Data Limite Prevista (DIA): {data_fim}')
    doc.add_paragraph(f'Prazo Legal Total: {prazo_max} dias úteis')
    doc.add_paragraph(f'Dias Consumidos: {total_dias} dias úteis')
    if saldo >= 0:
        doc.add_paragraph(f'Saldo Disponível: {saldo} dias úteis')
    else:
        doc.add_paragraph(f'DERRAPAGEM: {abs(saldo)} dias acima do prazo legal')

    # 3. Tabela Detalhada
    doc.add_heading('3. Detalhe das Etapas', level=1)
    
    # Tabela com cabeçalhos
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Fase'
    hdr_cells[1].text = 'Duração (Dias Úteis)'
    hdr_cells[2].text = 'Início'
    hdr_cells[3].text = 'Fim'

    # Preencher linhas
    for _, row in df_dados.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = str(row['Fase'])
        row_cells[1].text = str(row['Duração'])
        row_cells[2].text = str(row['Início'])
        row_cells[3].text = str(row['Fim'])

    # Salvar em buffer de memória
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 4. INTERFACE E INPUTS ---
st.title("📅 Cronograma RJAIA (Simplex)")
st.markdown("""
Calculadora de prazos de Avaliação de Impacte Ambiental de acordo com o **RJAIA** e **CPA**.
""")

st.sidebar.header("Configuração do Processo")

# A. Tipo de Processo
tipo_processo = st.sidebar.radio(
    "Tipologia do Processo:",
    options=["AIA Geral / Estudo Impacte Ambiental", "AIA Simplificado / Estudo Prévio"],
    index=0
)

if "Geral" in tipo_processo:
    PRAZO_MAXIMO = 150
    st.sidebar.info(f"Prazo Legal: **{PRAZO_MAXIMO} dias úteis**")
else:
    PRAZO_MAXIMO = 90
    st.sidebar.info(f"Prazo Legal: **{PRAZO_MAXIMO} dias úteis**")

# B. Data de Início
data_entrada = st.sidebar.date_input("Data de Submissão/Entrada", value=date(2025, 6, 3))

st.sidebar.markdown("---")
st.sidebar.subheader("Duração das Fases (Dias Úteis)")

# C. Inputs das Fases
dias_conformidade = st.sidebar.number_input("1. Conformidade/Instrução", value=10, min_value=0)
dias_consulta = st.sidebar.number_input("2. Consulta Pública", value=30, min_value=0)
dias_analise = st.sidebar.number_input("3. Análise Técnica", value=60, min_value=0)
dias_audiencia = st.sidebar.number_input("4. Audiência de Interessados (CPA)", value=10, min_value=0)
dias_decisao = st.sidebar.number_input("5. Emissão da DIA", value=PRAZO_MAXIMO - (dias_conformidade+dias_consulta+dias_analise+dias_audiencia))

# D. Suspensões
st.sidebar.markdown("---")
st.sidebar.subheader("Suspensões")
suspensao_dias_uteis = st.sidebar.number_input("Total Dias de Suspensão (Úteis)", value=0, min_value=0)

# --- 5. MOTOR DE CÁLCULO ---
cronograma = []
cursor_data = data_entrada
dias_consumidos = 0

etapas = [
    ("1. Conformidade", dias_conformidade),
    ("2. Consulta Pública", dias_consulta),
    ("3. Análise Técnica", dias_analise),
    ("4. Audiência Prévia", dias_audiencia),
    ("5. Emissão da DIA", dias_decisao)
]

# Loop Principal
for nome, duracao in etapas:
    inicio_fase = cursor_data
    fim_fase_np = somar_dias_uteis(inicio_fase, duracao, feriados_np)
    fim_fase = pd.to_datetime(fim_fase_np).date()
    
    cronograma.append({
        "Fase": nome,
        "Duração": duracao,
        "Início": formatar_data(inicio_fase),
        "Fim": formatar_data(fim_fase),
        "Start_Date": cursor_data,      # Para o gráfico
        "Finish_Date": fim_fase,        # Para o gráfico
        "Tipo": "Consome Prazo"
    })
    
    cursor_data = fim_fase
    dias_consumidos += duracao

# Processamento da Suspensão (Adicionada ao final conforme sua lógica original)
if suspensao_dias_uteis > 0:
    inicio_susp = cursor_data
    fim_susp_np = somar_dias_uteis(inicio_susp, suspensao_dias_uteis, feriados_np)
    fim_susp = pd.to_datetime(fim_susp_np).date()
    
    cronograma.append({
        "Fase": "⏸️ PERÍODO DE SUSPENSÃO",
        "Duração": suspensao_dias_uteis,
        "Início": formatar_data(inicio_susp),
        "Fim": formatar_data(fim_susp),
        "Start_Date": inicio_susp,
        "Finish_Date": fim_susp,
        "Tipo": "Suspensão (Não conta)"
    })
    cursor_data = fim_susp

data_final_real = cursor_data
saldo = PRAZO_MAXIMO - dias_consumidos

# Criar DataFrame
df_crono = pd.DataFrame(cronograma)

# --- 6. APRESENTAÇÃO ---

# Métricas
c1, c2, c3 = st.columns(3)
c1.metric("Prazo Legal", f"{PRAZO_MAXIMO} Dias Úteis")
c2.metric("Saldo Disponível", f"{saldo} Dias", delta_color="inverse" if saldo < 0 else "normal")
c3.metric("Data Final (DIA)", formatar_data(data_final_real))

# Abas para separar a informação
tab1, tab2, tab3 = st.tabs(["📊 Tabela Demonstrativa", "📈 Infograma (Gantt)", "💾 Relatório Word"])

with tab1:
    st.subheader("Tabela de Prazos")
    def style_row(row):
        return ['background-color: #ffebee'] * len(row) if "SUSPENSÃO" in row['Fase'] else [''] * len(row)
    
    # Mostrar apenas colunas relevantes para o utilizador
    cols_show = ['Fase', 'Duração', 'Início', 'Fim', 'Tipo']
    st.dataframe(df_crono[cols_show].style.apply(style_row, axis=1), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Linha do Tempo Visual")
    if not df_crono.empty:
        # Criar gráfico Gantt
        fig = px.timeline(
            df_crono, 
            x_start="Start_Date", 
            x_end="Finish_Date", 
            y="Fase", 
            color="Tipo",
            color_discrete_map={"Consome Prazo": "#2E86C1", "Suspensão (Não conta)": "#E74C3C"},
            title="Cronograma do Processo AIA"
        )
        # Inverter eixo Y para a ordem cronológica ficar de cima para baixo
        fig.update_yaxes(autorange="reversed") 
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Adicione fases para ver o gráfico.")

with tab3:
    st.subheader("Exportar Documentação")
    st.write("Gere um relatório oficial em formato Word (.docx) com o enquadramento legal e o cronograma acima.")
    
    # Botão de Download
    arquivo_word = gerar_relatorio_word(df_crono, formatar_data(data_final_real), dias_consumidos, PRAZO_MAXIMO, saldo)
    
    st.download_button(
        label="📥 Descarregar Relatório (.docx)",
        data=arquivo_word,
        file_name=f"Cronograma_AIA_{date.today()}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

# Validação Rápida no fundo
with st.expander("Verificação de Integridade (Natal 2025)"):
    check = np.is_busday(np.datetime64("2025-12-26"), weekmask='1111100', holidays=feriados_np)
    if check:
        st.success("✅ Sistema validado: Dias 26/12 a 02/01 contam como úteis (sem férias judiciais).")
    else:
        st.error("❌ ERRO: Férias Judiciais detetadas no sistema.")
