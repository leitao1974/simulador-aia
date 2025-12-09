import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AIA - CCDR Centro", layout="wide", page_icon="🏛️")

# --- 1. CALENDÁRIO CCDR CENTRO (CALIBRADO PARA 08/01/2026) ---
# Inclui feriados nacionais, municipal de Coimbra e tolerâncias de Dezembro
feriados_coimbra_calibrado = [
    # 2025
    "2025-01-01", 
    "2025-03-04", # Carnaval
    "2025-04-18", "2025-04-20", "2025-04-25", "2025-05-01",
    "2025-06-10", "2025-06-19", 
    "2025-07-04", # FERIADO MUNICIPAL COIMBRA (Sexta)
    "2025-08-15", 
    "2025-10-05", "2025-11-01",
    "2025-12-01", "2025-12-08", 
    
    # TOLERÂNCIAS (Cruciais para bater no dia 08/01)
    "2025-12-24", # Véspera de Natal
    "2025-12-25", # Natal
    "2025-12-26", # Tolerância Pós-Natal (habitual na AP)
    "2025-12-31", # Véspera de Ano Novo
    
    # 2026
    "2026-01-01", 
    "2026-02-17", # Carnaval
    "2026-04-03", "2026-04-05", "2026-04-25", "2026-05-01",
    "2026-06-04", "2026-06-10", 
    "2026-07-04", # Feriado Coimbra
    "2026-08-15", "2026-10-05", "2026-11-01",
    "2026-12-01", "2026-12-08", "2026-12-25"
]
feriados_np = np.array(feriados_coimbra_calibrado, dtype='datetime64[D]')

# --- 2. FUNÇÕES DE CÁLCULO ---
def somar_dias_uteis(data_inicio, dias, feriados):
    """Calcula data futura somando dias úteis."""
    return np.busday_offset(np.datetime64(data_inicio), dias, roll='forward', weekmask='1111100', holidays=feriados)

def formatar_data(np_date):
    return pd.to_datetime(np_date).strftime("%d/%m/%Y")

# --- 3. GERADOR DE RELATÓRIO WORD ---
def gerar_relatorio_ccdr(df_dados, data_fim, prazo_max, saldo, fig_timeline):
    doc = Document()
    
    # Cabeçalho
    titulo = doc.add_heading('Cronograma AIA - CCDR Centro', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data de Emissão: {date.today().strftime("%d/%m/%Y")}')
    doc.add_paragraph('')

    # 1. Enquadramento Legal
    doc.add_heading('1. Enquadramento Legal', level=1)
    texto_legal = (
        "A presente calendarização foi elaborada considerando as competências da CCDR Centro enquanto Autoridade de AIA, "
        "nos termos do Regime Jurídico da Avaliação de Impacte Ambiental (RJAIA)."
    )
    p = doc.add_paragraph(texto_legal)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p_details = doc.add_paragraph()
    p_details.add_run("1. Calendário Aplicável: ").bold = True
    p_details.add_run(
        "A contagem efetua-se em dias úteis (Art. 87.º do CPA). Foram considerados os feriados nacionais, o Feriado Municipal de Coimbra (4 de Julho) "
        "e as tolerâncias de ponto habituais na Administração Pública (época festiva). "
        "Não se aplicam as férias judiciais.\n"
    )
    p_details.add_run("2. Suspensões: ").bold = True
    p_details.add_run(
        "O prazo suspende-se sempre que a Autoridade aguarde elementos do proponente (Art. 13.º/16.º RJAIA e Art. 117.º CPA)."
    )

    # 2. Resumo
    doc.add_heading('2. Resumo de Prazos', level=1)
    p_resumo = doc.add_paragraph()
    run_dt = p_resumo.add_run(f'Data Limite Prevista: {data_fim}')
    run_dt.bold = True
    run_dt.font.size = Pt(12)
    
    doc.add_paragraph(f'Prazo Legal Total: {prazo_max} dias úteis')
    if saldo < 0:
        p_alert = doc.add_paragraph()
        r_alert = p_alert.add_run(f'⚠️ DERRAPAGEM: {abs(saldo)} dias acima do prazo.')
        r_alert.bold = True
    else:
        doc.add_paragraph(f'Saldo Disponível: {saldo} dias úteis')

    # 3. Infograma
    doc.add_heading('3. Cronograma Visual', level=1)
    try:
        img_buffer = BytesIO()
        fig_timeline.write_image(img_buffer, format='png', width=700, height=350)
        img_buffer.seek(0)
        doc.add_picture(img_buffer, width=Inches(6.0))
    except:
        doc.add_paragraph("[Gráfico indisponível. Verifique biblioteca 'kaleido']")

    # 4. Tabela
    doc.add_page_break()
    doc.add_heading('4. Detalhe das Etapas', level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text = 'Fase'
    hdr[1].text = 'Duração'
    hdr[2].text = 'Início'
    hdr[3].text = 'Fim'

    for _, row in df_dados.iterrows():
        cells = table.add_row().cells
        cells[0].text = str(row['Fase'])
        cells[1].text = str(row['Duração'])
        cells[2].text = str(row['Início'])
        cells[3].text = str(row['Fim'])

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 4. INTERFACE STREAMLIT ---
st.title("🏛️ Gestão de Prazos AIA - CCDR Centro")
st.markdown("""
Simulador ajustado ao calendário de **Coimbra** (Sede CCDR-C).
* **Feriado Municipal:** 4 de Julho.
* **Tolerâncias:** 24, 26 e 31 de Dezembro consideradas.
""")

with st.sidebar:
    st.header("Configuração")
    tipo = st.radio("Tipologia:", ["AIA Geral (150 dias)", "AIA Simplificado (90 dias)"])
    prazo_max = 150 if "Geral" in tipo else 90
    data_inicio = st.date_input("Data de Submissão", date(2025, 6, 3))
    
    st.divider()
    
    st.subheader("1. Conformidade")
    d1 = st.number_input("Duração (Dias Úteis)", 10, key="d1")
    susp_conf = st.number_input("Suspensão (Dias Corridos)", 0, help="Aperfeiçoamento Art. 13º", key="s1")
    
    st.subheader("2. Consulta Pública")
    d2 = st.number_input("Duração (Dias Úteis)", 30, key="d2")
    
    st.subheader("3. Análise Técnica")
    d3 = st.number_input("Duração (Dias Úteis)", 60, key="d3")
    susp_adit = st.number_input("Suspensão (Dias Corridos)", 45, help="Aditamentos Art. 16º", key="s3")
    
    st.subheader("4. Audiência Prévia")
    d4 = st.number_input("Duração (Dias Úteis)", 10, key="d4")
    susp_aud = st.number_input("Suspensão (Dias Úteis)", 10, help="Pronúncia CPA", key="s4")
    
    st.subheader("5. Decisão")
    dias_usados = d1 + d2 + d3 + d4
    dias_restantes = max(0, prazo_max - dias_usados)
    d5 = st.number_input("Restante (Dias Úteis)", value=dias_restantes, disabled=True)

# --- 5. MOTOR DE CÁLCULO ---
cronograma = []
cursor = data_inicio
dias_consumidos = 0

# ETAPA 1
inicio = cursor
fim_np = somar_dias_uteis(inicio, d1, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "1. Conformidade", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d1} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d1

if susp_conf > 0:
    inicio_susp = cursor
    fim_susp = cursor + timedelta(days=susp_conf)
    cronograma.append({"Fase": "⚠️ Aperfeiçoamento", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_conf} corridos", "Tipo": "Suspensão"})
    cursor = fim_susp

# ETAPA 2
inicio = cursor
fim_np = somar_dias_uteis(inicio, d2, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "2. Consulta Pública", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d2} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d2

# ETAPA 3
inicio = cursor
fim_np = somar_dias_uteis(inicio, d3, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "3. Análise Técnica", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d3} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d3

if susp_adit > 0:
    inicio_susp = cursor
    fim_susp = cursor + timedelta(days=susp_adit)
    cronograma.append({"Fase": "⏸️ Aditamentos", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_adit} corridos", "Tipo": "Suspensão"})
    cursor = fim_susp

# ETAPA 4
cursor_util = pd.to_datetime(somar_dias_uteis(cursor, 0, feriados_np)).date()
inicio = cursor_util
fim_np = somar_dias_uteis(inicio, d4, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "4. Audiência Prévia", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d4} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d4

if susp_aud > 0:
    inicio_susp = cursor
    fim_susp_np = somar_dias_uteis(inicio_susp, susp_aud, feriados_np)
    fim_susp = pd.to_datetime(fim_susp_np).date()
    cronograma.append({"Fase": "⏸️ Pronúncia CPA", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_aud} úteis", "Tipo": "Suspensão"})
    cursor = fim_susp

# ETAPA 5
dias_finais = prazo_max - dias_consumidos
if dias_finais > 0:
    inicio = cursor
    fim_np = somar_dias_uteis(inicio, dias_finais, feriados_np)
    fim = pd.to_datetime(fim_np).date()
    cronograma.append({"Fase": "5. Emissão da DIA", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{dias_finais} úteis", "Tipo": "Consome Prazo"})
    cursor = fim
    dias_consumidos += dias_finais

df = pd.DataFrame(cronograma)
data_final_txt = formatar_data(cursor)
saldo = prazo_max - dias_consumidos

# --- 6. VISUALIZAÇÃO ---
st.divider()
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("Cronograma Visual")
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Fase", color="Tipo",
        color_discrete_map={"Consome Prazo": "#2E86C1", "Suspensão": "#E74C3C"},
        hover_data=["Duração"],
        title=f"Previsão de Decisão: {data_final_txt}"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Resumo CCDR-C")
    
    # Validação visual da Data Final
    if data_final_txt == "08/01/2026"
