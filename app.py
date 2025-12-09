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
st.set_page_config(page_title="Gestão AIA - Pro", layout="wide", page_icon="📑")

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
    return np.busday_offset(np.datetime64(data_inicio), dias, roll='forward', weekmask='1111100', holidays=feriados)

def formatar_data(np_date):
    return pd.to_datetime(np_date).strftime("%d/%m/%Y")

# --- 3. GERADOR DE WORD (CORRIGIDO) ---
def gerar_relatorio_completo(df_dados, data_fim, prazo_max, saldo, fig_timeline):
    doc = Document()
    
    # Cabeçalho
    titulo = doc.add_heading('Cronograma Oficial AIA', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data de Emissão: {date.today().strftime("%d/%m/%Y")}')
    doc.add_paragraph('')

    # 1. Enquadramento Legal
    doc.add_heading('1. Enquadramento Legal', level=1)
    texto_legal = (
        "A presente calendarização foi elaborada nos termos do Regime Jurídico da Avaliação de Impacte Ambiental (RJAIA), "
        "aprovado pelo Decreto-Lei n.º 151-B/2013, e do Código do Procedimento Administrativo (CPA). "
        "A contagem de prazos efetua-se em dias úteis, suspendendo-se aos sábados, domingos e feriados nacionais, "
        "não sofrendo interrupção durante as férias judiciais (regime administrativo)."
    )
    p = doc.add_paragraph(texto_legal)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2. Resumo Executivo (CORREÇÃO AQUI)
    doc.add_heading('2. Resumo de Prazos', level=1)
    
    # Criamos o parágrafo e aplicamos negrito manualmente ao "run" (texto)
    p = doc.add_paragraph()
    run = p.add_run(f'Data Limite da Decisão (DIA): {data_fim}')
    run.bold = True  # Isto substitui o style='Strong' que dava erro
    
    doc.add_paragraph(f'Prazo Legal Total: {prazo_max} dias úteis')
    
    if saldo >= 0:
        doc.add_paragraph(f'Saldo Disponível: {saldo} dias úteis')
    else:
        # Texto de alerta em vermelho e negrito
        p_alert = doc.add_paragraph()
        r_alert = p_alert.add_run(f'DERRAPAGEM: {abs(saldo)} dias acima do prazo.')
        r_alert.bold = True
        r_alert.font.color.rgb = None # Usar cor padrão ou definir RGB se necessário

    # 3. Infograma (Linha do Tempo)
    doc.add_heading('3. Linha do Tempo Visual', level=1)
    try:
        # Converter o gráfico Plotly em imagem PNG
        img_buffer = BytesIO()
        # Nota: O Streamlit Cloud precisa da biblioteca 'kaleido' instalada
        fig_timeline.write_image(img_buffer, format='png', width=800, height=400)
        img_buffer.seek(0)
        doc.add_picture(img_buffer, width=Inches(6.5))
    except Exception as e:
        doc.add_paragraph("[Aviso: O gráfico não pôde ser gerado nesta versão do documento.]")
        doc.add_paragraph(f"Erro técnico: {e}")
        doc.add_paragraph("Nota: Verifique se 'kaleido' está no requirements.txt")

    # 4. Tabela Detalhada
    doc.add_page_break() # Tabela numa nova página
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
        cells[1].text = f"{row['Duração']} dias"
        cells[2].text = str(row['Início'])
        cells[3].text = str(row['Fim'])

    # Salvar
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 4. INTERFACE STREAMLIT ---
st.title("📅 Gestão de Prazos AIA")

with st.sidebar:
    st.header("Configuração")
    # Inputs Simplificados para teste rápido
    tipo = st.radio("Tipo:", ["AIA Geral (150 dias)", "AIA Simplificado (90 dias)"])
    prazo_max = 150 if "Geral" in tipo else 90
    
    data_inicio = st.date_input("Data Início", date(2025, 6, 3))
    
    st.subheader("Durações (Dias Úteis)")
    d1 = st.number_input("1. Conformidade", 10)
    d2 = st.number_input("2. Consulta Pública", 30)
    d3 = st.number_input("3. Análise Técnica", 60)
    d4 = st.number_input("4. Audiência Prévia", 10)
    d5 = st.number_input("5. Decisão (Restante)", prazo_max - (d1+d2+d3+d4))
    
    st.subheader("Suspensões")
    susp_uteis = st.number_input("Suspensão (Dias Úteis)", 0)

# --- 5. CÁLCULO DO CRONOGRAMA ---
cronograma = []
cursor = data_inicio
dias_gastos = 0

# Fases
etapas = [
    ("1. Conformidade", d1, "Consome Prazo"),
    ("2. Consulta Pública", d2, "Consome Prazo"),
    ("3. Análise Técnica", d3, "Consome Prazo"),
    ("4. Audiência Prévia", d4, "Consome Prazo"),
    ("5. Decisão Final", d5, "Consome Prazo")
]

for nome, duracao, tipo in etapas:
    inicio = cursor
    fim_np = somar_dias_uteis(inicio, duracao, feriados_np)
    fim = pd.to_datetime(fim_np).date()
    
    cronograma.append({
        "Fase": nome, "Início": formatar_data(inicio), "Fim": formatar_data(fim),
        "Start": inicio, "Finish": fim, "Duração": duracao, "Tipo": tipo
    })
    cursor = fim
    dias_gastos += duracao

if susp_uteis > 0:
    inicio_susp = cursor
    fim_susp_np = somar_dias_uteis(inicio_susp, susp_uteis, feriados_np)
    fim_susp = pd.to_datetime(fim_susp_np).date()
    cronograma.append({
        "Fase": "⏸️ PERÍODO DE SUSPENSÃO", "Início": formatar_data(inicio_susp), "Fim": formatar_data(fim_susp),
        "Start": inicio_susp, "Finish": fim_susp, "Duração": susp_uteis, "Tipo": "Suspensão"
    })
    cursor = fim_susp

df = pd.DataFrame(cronograma)
data_final_txt = formatar_data(cursor)
saldo = prazo_max - dias_gastos

# --- 6. VISUALIZAÇÃO E RELATÓRIO ---
st.divider()
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("Infograma: Linha do Tempo")
    # Gráfico Timeline Otimizado
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Fase", color="Tipo",
        color_discrete_map={"Consome Prazo": "#2E86C1", "Suspensão": "#E74C3C"},
        title=f"Cronograma do Processo (Fim: {data_final_txt})"
    )
    fig.update_yaxes(autorange="reversed") # Ordem cronológica
    fig.update_layout(showlegend=True, height=350)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Resumo")
    st.metric("Data Final", data_final_txt)
    st.metric("Dias Consumidos", f"{dias_gastos} / {prazo_max}")
    
    st.markdown("### Exportar")
    # Botão de Download com o Gráfico incluído
    arquivo = gerar_relatorio_completo(df, data_final_txt, prazo_max, saldo, fig)
    
    st.download_button(
        "📥 Download Relatório Completo (.docx)",
        data=arquivo,
        file_name="Relatorio_AIA_Completo.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

st.divider()
st.subheader("Tabela de Dados")
st.dataframe(df[['Fase', 'Início', 'Fim', 'Duração', 'Tipo']], use_container_width=True)
