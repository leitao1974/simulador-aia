import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
import io

# --- CONFIGURAÇÃO DA PÁGINA (TEM DE SER A PRIMEIRA LINHA STREAMLIT) ---
st.set_page_config(
    page_title="Analista EIA - Cronograma RJAIA",
    page_icon="🌿",
    layout="wide"
)

# --- TENTATIVA DE IMPORTAR FPDF (Modo Seguro) ---
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- DADOS DE FERIADOS (2023-2026) ---
FERIADOS_STR = [
    '2023-10-05', '2023-11-01', '2023-12-01', '2023-12-08', '2023-12-25',
    '2024-01-01', '2024-03-29', '2024-03-31', '2024-04-25', '2024-05-01', '2024-05-30', '2024-06-10',
    '2024-08-15', '2024-10-05', '2024-11-01', '2024-12-25',
    '2025-01-01', '2025-04-18', '2025-04-25', '2025-05-01', '2025-06-10', '2025-06-19', '2025-08-15',
    '2025-12-01', '2025-12-08', '2025-12-25',
    '2026-01-01', '2026-04-03', '2026-04-05', '2026-04-25', '2026-05-01', '2026-06-04', '2026-06-10',
    '2026-08-15', '2026-10-05', '2026-11-01', '2026-12-01', '2026-12-08', '2026-12-25'
]
FERIADOS = {pd.to_datetime(d).date() for d in FERIADOS_STR}

# --- DICIONÁRIO DE TIPOLOGIAS (FILTRADO PARA COMPETÊNCIAS CCDR) ---
TIPOLOGIAS_INFO = {
    "Anexo I (Competência CCDR)": 
        "Projetos do Anexo I do RJAIA sob competência da CCDR (ex: Agropecuária intensiva, Indústria, Pedreiras, Infraestruturas locais).",
    
    "Anexo II (Limiares ou Zonas Sensíveis)": 
        "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localização em zona sensível (Competência CCDR).",
    
    "Anexo II (Resultante de Triagem/Caso a Caso)": 
        "Projetos sujeitos a AIA na sequência de decisão de sujeição (Triagem) positiva emitida pela CCDR.",
    
    "Alteração ou Ampliação (Competência CCDR)": 
        "Alterações a projetos existentes (Anexo I ou II) que, pela sua natureza ou escala, são da competência da CCDR.",
    
    "RECAPE (Pós-DIA CCDR)": 
        "Verificação da conformidade ambiental do projeto de execução (RECAPE) decorrente de uma DIA emitida pela CCDR."
}

# --- FUNÇÕES UTILITÁRIAS ---

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: 
        return False
    if check_date in FERIADOS:
        return False
    return True

def add_business_days(start_date, num_days):
    """Adiciona dias úteis a uma data."""
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

def calculate_milestones(start_date, suspensions, manual_meeting_date=None):
    """Calcula as datas exatas. Permite sobrepor a data da reunião."""
    total_suspension_days = 0
    for susp in suspensions:
        s_start = susp['start']
        s_end = susp['end']
        if s_end >= s_start:
            duration = (s_end - s_start).days + 1
            total_suspension_days += duration
    
    milestones_def = [
        {"dias": 9,   "fase": "Data Reunião", "manual_override": True},
        {"dias": 30,  "fase": "Limite Conformidade", "manual_override": False},
        {"dias": 85,  "fase": "Envio PTF à AAIA", "manual_override": False},
        {"dias": 100, "fase": "Audiência de Interessados", "manual_override": False},
        {"dias": 150, "fase": "Emissão da DIA (Decisão Final)", "manual_override": False}
    ]
    
    results = []
    
    for m in milestones_def:
        if m["manual_override"] and manual_meeting_date:
            final_date = manual_meeting_date
            display_days = "Manual"
        else:
            base_date = add_business_days(start_date, m["dias"])
            final_date = base_date + timedelta(days=total_suspension_days)
            while not is_business_day(final_date):
                final_date += timedelta(days=1)
            display_days = f"{m['dias']} dias úteis"
            
        results.append({
            "Etapa": m["fase"],
            "Prazo Legal": display_days,
            "Data Prevista": final_date
        })
        
    return results, total_suspension_days

# --- FUNÇÃO GERADORA DE PDF ---
def create_pdf(project_name, typology, start_date, milestones, suspensions, total_susp):
    if FPDF is None:
        return None
