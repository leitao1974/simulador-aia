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
st.set_page_config(page_title="Gestão AIA - Pro", layout="wide", page_icon="⚖️")

# --- 1. BASE DE DADOS DE FERIADOS (VALIDADA) ---
feriados_nacionais = [
    "2025-01-01", "2025-04-18", "2025-04-20", "2025-04-25", "2025-05-01",
    "2025-06-10", "2025-06-19", "2025-08-15", "2025-10-05", "2025-11-01",
    "2025-12-01", "2025-12-08", "2025-12-25",
    "2026-01-01", "2026-04-03", "2026-04-05", "2026-04-25", "2026-05-01",
    "2026-06-04", "2026-06-10", "2026-08-15", "2026-10-05", "2026-11-01",
    "2026-12-01", "2026-12-08", "2026-12-25"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- 2. FUNÇÕES DE CÁLCULO ---
def somar_dias_uteis(data_inicio, dias, feriados):
    """Calcula data futura somando dias úteis."""
    return np.busday_offset(np.datetime64(data_inicio), dias, roll='forward', weekmask='1111100', holidays=feriados)

def formatar_data(np_date):
    """Formata data para PT."""
    return pd.to_datetime(np_date).strftime("%d/%m/%Y")

# --- 3. GERADOR DE RELATÓRIO WORD (JURIDICAMENTE ATUALIZADO) ---
def gerar_relatorio_completo(df_dados, data_fim, prazo_max, saldo, fig_timeline):
    doc = Document()
    
    # Cabeçalho
    titulo = doc.add_heading('Cronograma de Prazos AIA', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data de Emissão: {date.today().strftime("%d/%m/%Y")}')
    doc.add_paragraph('')

    # 1. Enquadramento Legal (ATUALIZADO)
    doc.add_heading('1. Enquadramento Legal', level=1)
    
    texto_legal = (
        "A presente calendarização foi elaborada nos termos do Regime Jurídico da Avaliação de Impacte Ambiental (RJAIA), "
        "aprovado pelo Decreto-Lei n.º 151-B/2013, conjugado com o Código do Procedimento Administrativo (CPA).\n"
    )
    p = doc.add_paragraph(texto_legal)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    # Lista de fundamentos
    p_details = doc.add_paragraph()
    p_details.add_run("1. Contagem: ").bold = True
    p_details.add_run(
        "Os prazos administrativos contam-se em dias úteis (Art. 87.º do CPA), suspendendo-se aos sábados, domingos e feriados nacionais. "
        "Não há suspensão durante férias judiciais.\n"
    )
    p_details.add_run("2. Suspensões: ").bold = True
    p_details.add_run(
        "O prazo de decisão suspende-se sempre que a Autoridade aguarde elementos do proponente. "
        "Esta suspensão fundamenta-se no "
    )
    p_details.add_run("Art. 13.º, n.º 4 do RJAIA ").bold = True
    p_details.add_run("(fase de conformidade/aperfeiçoamento) e no ")
    p_details.add_run("Art. 16.º do RJAIA ").bold = True
    p_details.add_run("(fase de análise técnica), em articulação com o princípio geral do ")
    p_details.add_run("Art. 117.º, n.º 2 do CPA.").bold = True

    # 2. Resumo Executivo
    doc.add_heading('2. Resumo de Prazos', level=1)
    
    p_resumo = doc.add_paragraph()
    run_dt = p_resumo.add_run(f'Data Limite da Decisão (DIA): {data_fim}')
    run_dt.bold = True
    run_dt.font.size = Pt(12)
    
    doc.add_paragraph(f'Prazo Legal Total: {prazo_max} dias úteis')
    
    if saldo >= 0:
        doc.add_paragraph(f'Saldo Disponível: {saldo} dias úteis')
    else:
        p_alert = doc.add_paragraph()
        r_alert = p_alert.add_run(f'DERRAPAGEM: {abs(saldo)} dias acima do prazo.')
        r_alert.bold = True
        r_alert.font.color.rgb = None 

    # 3. Infograma
    doc.add_heading('3. Linha do Tempo Visual', level=1)
    try:
        img_buffer = BytesIO()
        # Nota: Requer kaleido==0.2.1 no requirements.txt
        fig_timeline.write_image(img_buffer, format='png', width=800, height=400)
        img_buffer.seek(0)
        doc.add_picture(img_buffer, width=Inches(6.5))
    except Exception as e:
        doc.add_paragraph("[Gráfico indisponível nesta versão. Verifique biblioteca 'kaleido']")

    # 4. Tabela
    doc.add_page_break()
    doc.add_heading('4. Tabela Detalhada das Etapas', level=1)
    
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
st.title("📅 Gestão de Prazos AIA")
st.markdown("Simulador de Prazos RJAIA/CPA com gestão de suspensões e relatórios.")

with st.sidebar:
    st.header("1. Configuração Base")
    tipo = st.radio("Tipologia:", ["AIA Geral (150 dias)", "AIA Simplificado (90 dias)"])
    prazo_max = 150 if "Geral" in tipo else 90
    data_inicio = st.date_input("Data de Submissão", date(2025, 6, 3))
    
    st.markdown("---")
    st.header("2. Fases e Suspensões")
    
    # FASE 1
    st.subheader("Fase 1: Conformidade")
    d1 = st.number_input("Duração (Dias Úteis)", 10, key="d1")
    susp_conf = st.number_input("Suspensão / Aperfeiçoamento (Dias Corridos)", value=0, help="Art. 13º RJAIA: Convite ao aperfeiçoamento.", key="s1")
    
    # FASE 2
    st.subheader("Fase 2: Consulta Pública")
    d2 = st.number_input("Duração (Dias Úteis)", 30, key="d2")
    
    # FASE 3
    st.subheader("Fase 3: Análise Técnica")
    d3 = st.number_input("Duração (Dias Úteis)", 60, key="d3")
    susp_adit = st.number_input("Suspensão / Aditamentos (Dias Corridos)", value=45, help="Art. 16º RJAIA: Pedido de elementos adicionais.", key="s3")
    
    # FASE 4
    st.subheader("Fase 4: Audiência Prévia")
    d4 = st.number_input("Duração (Dias Úteis)", 10, key="d4")
    susp_aud = st.number_input("Suspensão da Contagem (Dias Úteis)", value=10, help="Art. 117º CPA: Suspensão para pronúncia.", key="s4")
    
    # FASE 5
    st.subheader("Fase 5: Decisão (DIA)")
    dias_restantes_calc = prazo_max - (d1+d2+d3+d4)
    d5 = st.number_input("Duração Restante (Dias Úteis)", value=dias_restantes_calc, disabled=True)

# --- 5. MOTOR DE CÁLCULO ---
cronograma = []
cursor = data_inicio
dias_consumidos = 0

# --- Lógica Passo a Passo ---

# 1. CONFORMIDADE
inicio = cursor
fim_np = somar_dias_uteis(inicio, d1, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "1. Conformidade", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d1} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d1

# Suspensão Conformidade (NOVO)
if susp_conf > 0:
    inicio_susp = cursor
    fim_susp = cursor + timedelta(days=susp_conf) # Dias Corridos
    cronograma.append({"Fase": "⚠️ Aperfeiçoamento (Art. 13º)", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_conf} corridos", "Tipo": "Suspensão"})
    cursor = fim_susp

# 2. CONSULTA PÚBLICA
inicio = cursor
fim_np = somar_dias_uteis(inicio, d2, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "2. Consulta Pública", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d2} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d2

# 3. ANÁLISE TÉCNICA
inicio = cursor
fim_np = somar_dias_uteis(inicio, d3, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "3. Análise Técnica", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d3} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d3

# Suspensão Aditamentos
if susp_adit > 0:
    inicio_susp = cursor
    fim_susp = cursor + timedelta(days=susp_adit) # Dias Corridos
    cronograma.append({"Fase": "⏸️ Aditamentos (Art. 16º)", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_adit} corridos", "Tipo": "Suspensão"})
    cursor = fim_susp

# 4. AUDIÊNCIA PRÉVIA
# Ajuste: Se suspensão acabou ao FDS, começar em dia útil
cursor_util = pd.to_datetime(somar_dias_uteis(cursor, 0, feriados_np)).date()
inicio = cursor_util
fim_np = somar_dias_uteis(inicio, d4, feriados_np)
fim = pd.to_datetime(fim_np).date()
cronograma.append({"Fase": "4. Audiência Prévia", "Início": formatar_data(inicio), "Fim": formatar_data(fim), "Start": inicio, "Finish": fim, "Duração": f"{d4} úteis", "Tipo": "Consome Prazo"})
cursor = fim
dias_consumidos += d4

# Suspensão Audiência (Dias Úteis - Art 117 CPA)
if susp_aud > 0:
    inicio_susp = cursor
    fim_susp_np = somar_dias_uteis(inicio_susp, susp_aud, feriados_np) # Dias Úteis
    fim_susp = pd.to_datetime(fim_susp_np).date()
    cronograma.append({"Fase": "⏸️ Análise Pronúncias (CPA)", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp), "Start": inicio_susp, "Finish": fim_susp, "Duração": f"{susp_aud} úteis", "Tipo": "Suspensão"})
    cursor = fim_susp

# 5. DECISÃO FINAL (Saldo)
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

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Linha do Tempo (Gantt)")
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Fase", color="Tipo",
        color_discrete_map={"Consome Prazo": "#2E86C1", "Suspensão": "#E74C3C"},
        hover_data=["Duração"],
        title=f"Previsão de Fim: {data_final_txt}"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Resumo Oficial")
    st.metric("Data Final (DIA)", data_final_txt)
    st.metric("Dias Consumidos", f"{dias_consumidos} / {prazo_max}")
    
    st.write("---")
    st.write("📄 **Documentação**")
    
    # Tratamento de erro caso kaleido falhe na primeira execução
    try:
        arquivo = gerar_relatorio_completo(df, data_final_txt, prazo_max, saldo, fig)
        st.download_button(
            "📥 Baixar Relatório (.docx)",
            data=arquivo,
            file_name=f"Cronograma_AIA_{date.today()}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {e}")
        st.caption("Verifique se 'kaleido==0.2.1' está no requirements.txt")

st.divider()
with st.expander("Ver Tabela de Dados Completa"):
    st.dataframe(df[['Fase', 'Início', 'Fim', 'Duração', 'Tipo']], use_container_width=True)
