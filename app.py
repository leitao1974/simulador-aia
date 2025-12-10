import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import tempfile
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA E ESTILO (O SEGREDO DO VISUAL) ---
st.set_page_config(
    page_title="Simulador AIA | CCDR Centro",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personalizado para um look moderno
st.markdown("""
    <style>
    /* Importar fonte moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Estilo dos Cartões de Métricas */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0,0,0,0.1);
        border-color: #4CAF50;
    }
    
    /* Cabeçalhos */
    h1 { color: #1E3A8A; font-weight: 700; letter-spacing: -1px; }
    h2, h3 { color: #333; }
    
    /* Barra Lateral */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
    
    /* Botões */
    div.stButton > button {
        background-color: #1E3A8A;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        font-weight: 600;
    }
    div.stButton > button:hover {
        background-color: #152c6b;
        color: white;
    }
    
    /* Alertas */
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Tenta importar FPDF
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 2. DADOS DE BASE (FERIADOS E LEGISLAÇÃO)
# ==========================================

# Feriados
FERIADOS_STR = [
    '2023-10-05', '2023-11-01', '2023-12-01', '2023-12-08', '2023-12-25', 
    '2024-01-01', '2024-03-29', '2024-04-25', '2024-05-01', '2024-05-30', '2024-06-10', '2024-08-15', '2024-10-05', '2024-11-01', '2024-12-25', 
    '2025-01-01', '2025-04-18', '2025-04-25', '2025-05-01', '2025-06-10', '2025-06-19', '2025-08-15', '2025-12-01', '2025-12-08', '2025-12-25', 
    '2026-01-01', '2026-04-03', '2026-04-05', '2026-04-25', '2026-05-01', '2026-06-04', '2026-06-10', '2026-08-15', '2026-10-05', '2026-11-01', '2026-12-01', '2026-12-08', '2026-12-25', 
    '2027-01-01', '2027-03-26', '2027-05-27', '2027-06-10', '2027-10-05', '2027-11-01', '2027-12-01', '2027-12-08', 
    '2028-04-14', '2028-04-25', '2028-05-01', '2028-06-15', '2028-08-15', '2028-10-05', '2028-11-01', '2028-12-01', '2028-12-08', '2028-12-25', 
    '2029-01-01', '2029-03-30', '2029-04-25', '2029-05-01', '2029-05-31', '2029-08-15', '2029-10-05', '2029-11-01', '2029-12-25', 
    '2030-01-01', '2030-04-19', '2030-04-25', '2030-05-01', '2030-06-10', '2030-06-20', '2030-08-15', '2030-11-01', '2030-12-25'
]
FERIADOS = {pd.to_datetime(d).date() for d in FERIADOS_STR}

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "Simplex Ambiental (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212459",
    "CPA (Prazos)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558838"
}

TIPOLOGIAS_INFO = {
    "Anexo I (Competência CCDR)": "Projetos do Anexo I do RJAIA sob competência da CCDR.",
    "Anexo II (Limiares ou Zonas Sensíveis)": "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localização em zona sensível.",
    "Alteração ou Ampliação": "Alterações a projetos existentes.",
    "AIA Simplificado": "Procedimento simplificado nos termos do Simplex."
}

SPECIFIC_LAWS = {
    "Indústria Extrativa": {"DL 270/2001 (Massas Minerais)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875"},
    "Indústria Transformadora": {"DL 127/2013 (Emissões Industriais)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"},
    "Agropecuária": {"DL 81/2013 (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34763567"},
    "Energia": {"DL 15/2022 (Sistema Elétrico)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687"},
    "Infraestruturas": {"Lei 34/2015 (Estatuto Estradas)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678"},
    "Outros": {}
}

# ==========================================
# 3. MOTOR DE CÁLCULO (LÓGICA INALTERADA)
# ==========================================

def is_business_day(check_date):
    if check_date.weekday() >= 5: return False
    if check_date in FERIADOS: return False
    return True

def add_business_days(start_date, num_days):
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

def is_suspended(current_date, suspensions):
    for s in suspensions:
        if s['start'] <= current_date <= s['end']:
            return True
    return False

def is_business_day_rigorous(check_date, suspensions):
    if is_suspended(check_date, suspensions): return False
    if check_date.weekday() >= 5: return False
    if check_date in FERIADOS: return False
    return True

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, adjust_weekend=True, return_log=False):
    current_date = start_date
    days_counted = 0
    log = []
    
    if return_log:
        log.append({"Data": current_date, "Dia Contado": 0, "Status": "Início"})

    while days_counted < target_business_days:
        current_date += timedelta(days=1)
        
        status = "Util"
        if is_suspended(current_date, suspensions):
            status = "Suspenso"
        elif current_date.weekday() >= 5:
            status = "Fim de Semana"
        elif current_date in FERIADOS:
            status = "Feriado"
            
        if status == "Util":
            days_counted += 1
            
        if return_log:
            log.append({"Data": current_date, "Dia Contado": days_counted if status == "Util" else "-", "Status": status})
            
    final_date = current_date
    if adjust_weekend:
        while final_date.weekday() >= 5 or final_date in FERIADOS:
             final_date += timedelta(days=1)
    
    if return_log:
        return final_date, log
    return final_date

def calculate_all_milestones(start_date, suspensions, manual_meeting_date=None, adjust_weekend=True):
    milestones_def = [
        {"dias": 9,   "fase": "Reunião Prévia", "manual": True},
        {"dias": 30,  "fase": "Conformidade", "manual": False},
        {"dias": 100, "fase": "Envio PTF", "manual": False},
        {"dias": 120, "fase": "Audiência Interessados", "manual": False},
        {"dias": 150, "fase": "Emissão da DIA", "manual": False}
    ]
    results = []
    log_dia = []
    conf_date = None
    
    for m in milestones_def:
        if m["manual"] and manual_meeting_date:
            final_date = manual_meeting_date
            display = "Manual"
        else:
            if m["dias"] == 150: 
                final_date, log_data = calculate_deadline_rigorous(start_date, m["dias"], suspensions, adjust_weekend, return_log=True)
                log_dia = log_data
            else:
                final_date = calculate_deadline_rigorous(start_date, m["dias"], suspensions, adjust_weekend)
            display = f"{m['dias']} dias úteis"
            
            if m["dias"] == 30: conf_date = final_date
            
        results.append({"Etapa": m["fase"], "Prazo Legal": display, "Data Prevista": final_date})
    
    complementary = []
    if conf_date:
        cp_start = add_business_days(conf_date, 5)
        cp_end = add_business_days(cp_start, 30)
        cp_report = add_business_days(cp_end, 7)
        visit_date = add_business_days(cp_start, 15)
        external_ops = add_business_days(cp_start, 23)
        
        complementary = [
            {"Etapa": "Início Consulta Pública", "Ref": "Conf + 5 dias", "Data": cp_start},
            {"Etapa": "Fim Consulta Pública", "Ref": "Início CP + 30 dias", "Data": cp_end},
            {"Etapa": "Prazo Pareceres", "Ref": "Início CP + 23 dias", "Data": external_ops},
            {"Etapa": "Relatório CP", "Ref": "Fim CP + 7 dias", "Data": cp_report},
        ]

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    return results, complementary, total_susp, log_dia

# ==========================================
# 4. GERADOR DE PDF (COM GANTT)
# ==========================================
def create_pdf(project_name, typology, sector, regime, start_date, milestones, complementary, suspensions, total_susp):
    if FPDF is None: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(30, 58, 138) # Azul Profissional
            self.cell(0, 10, 'CCDR CENTRO - AUTORIDADE DE AIA', 0, 1, 'C')
            self.line(10, 20, 200, 20)
            self.ln(10)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Pagina {self.page_no()} - Gerado pelo Simulador AIA', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(0, 0, 0)
    safe_title = f"Relatorio de Prazos: {project_name}"
    pdf.multi_cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(5)

    # 1. Enquadramento Legal
    pdf.set_fill_color(240, 248, 255) # Azul muito claro
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "1. Enquadramento Legal", 0, 1, 'L', 1)
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Tipologia:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, typology.encode('latin-1','replace').decode('latin-1'))
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Setor:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, sector.encode('latin-1','replace').decode('latin-1'), 0, 1)
    pdf.ln(4)

    # 2. Resumo
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. Resumo do Processo", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 6, "Regime:", 0, 0)
