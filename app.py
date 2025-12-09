import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
from fpdf import FPDF
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão Prazos AIA - CCDR Centro",
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
            # Recalculo inverso aproximado para display
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
def create_pdf(project_name, start_date, milestones, suspensions, total_susp):
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
    # Encode latin-1 para lidar com acentos em fonts padrão
    title = f"Relatório de Contagem de Prazos: {project_name}"
    pdf.multi_cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(10)
    
    # 1. Enquadramento Legal
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Enquadramento Legal e Tipologia", 0, 1)
    pdf.set_font("Arial", "", 10)
    
    legal_text = (
        "O presente cronograma foi calculado nos termos do Regime Jurídico da Avaliação de Impacte Ambiental "
        "(Decreto-Lei n.º 151-B/2013), com as alterações introduzidas pelo Decreto-Lei n.º 11/2023 "
        "(Simplex Ambiental).\n\n"
        "Tipologia do Processo: Procedimento de Avaliação de Impacte Ambiental (AIA).\n"
        "Prazo Base de Decisão: 150 dias úteis.\n"
        "Competência: CCDR Centro (Autoridade de AIA).\n\n"
        "Nota Importante: A contagem de prazos administrativos suspende-se sempre que sejam solicitados "
        "elementos adicionais ao promotor (PeA), nos termos legais em vigor."
    )
    pdf.multi_cell(0, 6, legal_text.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)
    
    # 2. Resumo do Processo
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Dados do Processo", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 8, "Data de Instrução:", 0, 0)
    pdf.cell(0, 8, start_date.strftime("%d/%m/%Y"), 0, 1)
    pdf.cell(50, 8, "Total de Suspensões:", 0, 0)
    pdf.cell(0, 8, f"{total_susp} dias de calendario", 0, 1)
    pdf.ln(5)

    # 3. Suspensões Detalhadas
    if suspensions:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 10, "Suspensões Registadas (PeA)", 0, 1)
        pdf.set_font("Arial", "", 10)
        
        # Cabeçalho da tabela de suspensão
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
    
    # Tabela Headers
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(90, 10, "Etapa Processual", 1, 0, 'L', 1)
    pdf.cell(50, 10, "Prazo Legal Base", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Data Limite Prevista", 1, 1, 'C', 1)
    
    # Tabela Content
    pdf.set_font("Arial", "", 10)
    for m in milestones:
        # Etapa
        pdf.cell(90, 10, m["Etapa"].encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'L')
        # Prazo Legal
        pdf.cell(50, 10, str(m["Prazo Legal"]), 1, 0, 'C')
        # Data
        d_str = m["Data Prevista"].strftime("%d/%m/%Y")
        
        # Highlight se for a Decisão Final
        if "Emissão da DIA" in m["Etapa"]:
            pdf.set_font("Arial", "B", 10)
        
        pdf.cell(50, 10, d_str, 1, 1, 'C')
        pdf.set_font("Arial", "", 10)

    pdf.ln(10)
    pdf.set_font("Arial", "I", 9)
    note = (
        "Nota: Este documento é meramente informativo e de apoio à gestão. "
        "Não dispensa a consulta dos prazos legais no sistema oficial."
    )
    pdf.multi_cell(0, 5, note.encode('latin-1', 'replace').decode('latin-1'))

    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE PRINCIPAL ---

st.title("🌿 Cronograma RJAIA - 150 Dias (Simplex)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Ampliação Zona Industrial Condeixa")
    start_date = st.date_input("Data de Instrução (Dia 0)", date(2025, 1, 30))
    
    st.markdown("---")
    st.subheader("⚙️ Simulação Temporal")
    use_simulated_date = st.checkbox("Simular 'Hoje' diferente?")
    today = st.date_input("Data de Referência", date.today()) if use_simulated_date else date.today()
    if use_simulated_date: st.info(f"Simulação a: {today}")
    
    st.markdown("---")
    st.subheader("🗓️ Agendamentos")
    theoretical_meeting = add_business_days(start_date, 9)
    meeting_date_input = st.date_input("Data Real da Reunião", value=theoretical_meeting)
    
    st.markdown("---")
    st.subheader("⏸️ Suspensões (PeA)")
    
    if 'suspensions' not in st.session_state:
        st.session_state.suspensions = []

    with st.form("add_suspension"):
        c1, c2 = st.columns(2)
        s_start = c1.date_input("Início")
        s_end = c2.date_input("Fim")
        if st.form_submit_button("Adicionar"):
            if s_end < s_start:
                st.error("Data fim inválida.")
            else:
                st.session_state.suspensions.append({'start': s_start, 'end': s_end})
                st.rerun()

    if st.session_state.suspensions:
        st.write("Períodos de paragem:")
        for i, s in enumerate(st.session_state.suspensions):
            col_txt, col_del = st.columns([0.8, 0.2])
            col_txt.text(f"{s['start'].strftime('%d/%m')} a {s['end'].strftime('%d/%m')}")
            if col_del.button("❌", key=f"del_{i}"):
                del st.session_state.suspensions[i]
                st.rerun()

# --- CÁLCULOS ---

milestones, total_susp = calculate_milestones(
    start_date, 
    st.session_state.suspensions,
    manual_meeting_date=meeting_date_input
)

final_dia_date = milestones[-1]["Data Prevista"]

# --- DASHBOARD ---
st.divider()
c1, c2, c3, c4 = st.columns(4)

c1.metric("Data Referência", today.strftime("%d/%m/%Y"))
c2.metric("Início Processo", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias", delta_color="inverse")

days_left = (final_dia_date - today).days
label_status = "Dias Restantes" if days_left >= 0 else "Dias de Atraso"
color_status = "normal" if days_left >= 0 else "inverse"

c4.metric("Data Limite (DIA)", final_dia_date.strftime("%d/%m/%Y"), 
          delta=f"{abs(days_left)} {label_status}", delta_color=color_status)

# --- TABELA E GRÁFICO ---
tab1, tab2 = st.tabs(["📋 Tabela Detalhada", "📅 Cronograma Visual"])

with tab1:
    df_milestones = pd.DataFrame(milestones)
    df_milestones["Data Prevista"] = df_milestones["Data Prevista"].apply(lambda x: x.strftime("%d-%m-%Y"))
    st.dataframe(df_milestones, use_container_width=True, hide_index=True)

with tab2:
    df_gantt = []
    last_end = start_date
    for item in milestones:
        end_date_dt = item["Data Prevista"]
        start_viz = last_end if last_end <= end_date_dt else end_date_dt - timedelta(days=1)
        df_gantt.append(dict(Task=item["Etapa"], Start=start_viz, Finish=end_date_dt, Resource="Fase Processual"))
        last_end = end_date_dt

    for i, susp in enumerate(st.session_state.suspensions):
        df_gantt.append(dict(Task=f"Suspensão {i+1}", Start=susp['start'], Finish=susp['end'], Resource="Suspensão"))

    fig = px.timeline(pd.DataFrame(df_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource", 
                      color_discrete_map={"Fase Processual": "#2E86C1", "Suspensão": "#E74C3C"})
    fig.update_yaxes(autorange="reversed")
    fig.add_vline(x=pd.Timestamp(today).timestamp() * 1000, line_width=2, line_dash="dash", line_color="green", annotation_text="Hoje")
    st.plotly_chart(fig, use_container_width=True)

# --- GERAR PDF ---
st.markdown("---")
st.subheader("🖨️ Exportar Relatório")

if st.button("Gerar Relatório PDF"):
    pdf_bytes = create_pdf(proj_name, start_date, milestones, st.session_state.suspensions, total_susp)
    st.download_button(
        label="📥 Descarregar PDF",
        data=pdf_bytes,
        file_name=f"Relatorio_Prazos_{proj_name.replace(' ', '_')}.pdf",
        mime='application/pdf'
    )
