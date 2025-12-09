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
    "2025-12-26", # Tolerância Pós-Natal
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
    doc.add_heading('4. Detalhe das Etapas', level=1

