import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Analista EIA - Cronograma RJAIA",
    page_icon="🌿",
    layout="wide"
)

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

# --- DICIONÁRIO DE TIPOLOGIAS RJAIA ---
TIPOLOGIAS_INFO = {
    "Anexo I (AIA Obrigatória)": 
        "Projeto incluído no Anexo I do RJAIA, sujeito a Avaliação de Impacte Ambiental sistemática devido à sua natureza, dimensão ou localização.",
    "Anexo II (Limiares/Zonas Sensíveis)": 
        "Projeto incluído no Anexo II do RJAIA, sujeito a AIA por ultrapassar os limiares estabelecidos ou por se localizar em zona sensível, conforme verificado pela autoridade.",
    "Anexo II (Decisão Caso a Caso)": 
        "Projeto sujeito a AIA na sequência de decisão de análise caso a caso (Triagem), por se considerar suscetível de provocar impactes significativos no ambiente.",
    "AIA Voluntária / Autoproposura": 
        "Procedimento de AIA iniciado por autoproposura do promotor, independentemente dos limiares legais.",
    "Alteração ou Ampliação (Anexo I/II)": 
        "Alteração ou ampliação de projeto preexistente (Anexo I ou II) suscetível de provocar impactes significativos no ambiente.",
    "RECAPE (Projeto de Execução)": 
        "Fase de verificação da conformidade ambiental do projeto de execução com a Declaração de Impacte Ambiental (DIA) emitida em fase de Estudo Prévio."
}

# --- FUNÇÕES UTILITÁRIAS ---

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: # 5=Sábado, 6=Domingo
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
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, 'CCDR CENTRO - Autoridade de Avaliação de Impacte Ambiental', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 16)
    title = f"Relatório de Análise e Prazos: {project_name}"
    pdf.multi_cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(10)
    
    # 1. Enquadramento Legal (NOVO: Com Tipologia)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Enquadramento Legal e Tipologia", 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 8, "Regime Jurídico:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, "RJAIA (DL 151-B/2013) atualizado pelo Simplex (DL 11/2023)", 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 8, "Classificação:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, typology.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    
    # Texto descritivo da tipologia
    desc_text = TIPOLOGIAS_INFO.get(typology, "")
    if desc_text:
        pdf.set_font("Arial", "I", 9)
        pdf.multi_cell(0, 6, f"Análise: {desc_text}".encode('latin-1', 'replace').decode('latin-1'))
    
    pdf.ln(5)
    
    # 2. Resumo do Processo
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Dados do Processo", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 8, "Data de Instrução:", 0, 0)
    pdf.cell(0, 8, start_date.strftime("%d/%m/%Y"), 0, 1)
    pdf.cell(50, 8, "Prazo Base Decisão:", 0, 0)
    pdf.cell(0, 8, "150 dias úteis", 0, 1)
    pdf.cell(50, 8, "Total de Suspensões:", 0, 0)
    pdf.cell(0, 8, f"{total_susp} dias de calendario", 0, 1)
    pdf.ln(5)

    # 3. Suspensões Detalhadas
    if suspensions:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 10, "Suspensões Registadas (PeA)", 0, 1)
        pdf.set_font("Arial", "", 10)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(60, 8, "Início", 1, 0, 'C', 1)
        pdf.cell(60, 8, "Fim", 1, 0, 'C', 1)
        pdf.cell(60, 8, "Duração", 1, 1, 'C', 1)
        
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(60, 8, s['start'].strftime("%d/%m/%Y"), 1, 0, 'C')
            pdf.cell(60, 8, s['end'].strftime("%d/%m/%Y"), 1, 0, 'C')
            pdf.cell(60, 8, f"{dur} dias", 1, 1, 'C')
        pdf.ln(5)

    # 4. Cronograma Oficial
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "3. Cronograma Oficial (Previsão)", 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(90, 10, "Etapa Processual", 1, 0, 'L', 1)
    pdf
