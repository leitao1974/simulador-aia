import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Simulador de prazos do procedimento AIA",
    page_icon="🌿",
    layout="wide"
)

# Tenta importar FPDF
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 1. DADOS DE BASE (FERIADOS E LEGISLAÇÃO)
# ==========================================

# Feriados até 2030
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

# Legislação Transversal
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUIDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "AGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

# Legislação Específica
SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "ATIVIDADE PECUARIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTAO EFLUENTES (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868",
        "FLORESTAS (DL 16/2009 - PGF)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34488356"
    },
    "2. Industria Extrativa (Minas e Pedreiras)": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESIDUOS DE EXTRACAO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "SEGURANCA MINAS (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937"
    },
    "3. Industria Energetica": {
        "SISTEMA ELETRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "EMISSOES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "REFINACAO/COMBUSTIVEIS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34589012"
    },
    "4. Producao e Transformacao de Metais": {
        "EMISSOES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543"
    },
    "5. Industria Mineral e Quimica": {
        "PREVENCAO ACIDENTES GRAVES (SEVESO - DL 150/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558967",
        "EMISSOES (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)": {
        "ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "SERVIDOES AERONAUTICAS (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345",
        "RUIDO GRANDES INFRAESTRUTURAS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
    },
    "7. Projetos de Engenharia Hidraulica (Barragens, Portos)": {
        "SEGURANCA BARRAGENS (DL 21/2018)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2018-114833256",
        "DOMINIO HIDRICO (Lei 54/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
    },
    "8. Tratamento de Residuos e Aguas Residuais": {
        "RESIDUOS (RGGR - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
        "AGUAS RESIDUAIS URBANAS (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345",
        "ATERROS (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "9. Projetos Urbanos, Turisticos e Outros": {
        "RJUE (Urbanizacao - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "EMPREENDIMENTOS TURISTICOS (RJET)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567",
        "ACESSIBILIDADES (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456"
    }
}

# Tipologias CCDR
TIPOLOGIAS_INFO = {
    "Anexo I (Competencia CCDR)": 
        "Projetos do Anexo I do RJAIA sob competencia da CCDR (ex: Agropecuaria intensiva, Industria, Pedreiras).",
    "Anexo II (Limiares ou Zonas Sensiveis)": 
        "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localizacao em zona sensivel.",
    "Anexo II (Resultante de Triagem/Caso a Caso)": 
        "Projetos sujeitos a AIA na sequencia de decisao de sujeicao (Triagem) positiva emitida pela CCDR.",
    "Alteracao ou Ampliacao (Competencia CCDR)": 
        "Alteracoes a projetos existentes (Anexo I ou II) que, pela sua natureza ou escala, sao da competencia da CCDR.",
    "RECAPE (Pos-DIA CCDR)": 
        "Verificacao da conformidade ambiental do projeto de execucao (RECAPE) decorrente de uma DIA emitida pela CCDR."
}

# ==========================================
# 2. FUNÇÕES DE CÁLCULO
# ==========================================

# --- FUNÇÕES BÁSICAS ---
def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: 
        return False
    if check_date in FERIADOS:
        return False
    return True

def add_business_days(start_date, num_days):
    """Adiciona dias úteis a uma data (Simples, sem suspensão)."""
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

# --- FUNÇÕES RIGOROSAS (PARA O CRONOGRAMA) ---
def is_suspended(current_date, suspensions):
    """Verifica se uma data cai dentro de qualquer período de suspensão."""
    for s in suspensions:
        if s['start'] <= current_date <= s['end']:
            return True
    return False

def is_business_day_rigorous(check_date, suspensions):
    """
    Verifica se é dia útil para contagem.
    NÃO conta se: Fim de Semana, Feriado OU Suspensão Ativa.
    """
    if is_suspended(check_date, suspensions):
        return False
    if check_date.weekday() >= 5: # Sábado/Domingo
        return False
    if check_date in FERIADOS:
        return False
    return True

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, adjust_weekend=True):
    """
    Conta dias úteis um a um, saltando suspensões e feriados, até atingir o alvo.
    """
    current_date = start_date
    days_counted = 0
    
    while days_counted < target_business_days:
        current_date += timedelta(days=1)
        # Só conta o dia se for útil E não estiver suspenso
        if is_business_day_rigorous(current_date, suspensions):
            days_counted += 1
            
    # Ajuste CPA
    final_date = current_date
    if adjust_weekend:
        while final_date.weekday() >= 5 or final_date in FERIADOS:
             final_date += timedelta(days=1)
             
    return final_date

def calculate_all_milestones(start_date, suspensions, manual_meeting_date=None, adjust_weekend=True):
    milestones_def = [
        {"dias": 9,   "fase": "Data Reunião", "manual": True},
        {"dias": 30,  "fase": "Limite Conformidade", "manual": False},
        {"dias": 85,  "fase": "Envio PTF à AAIA", "manual": False},
        {"dias": 100, "fase": "Audiência de Interessados", "manual": False},
        {"dias": 150, "fase": "Emissão da DIA (Decisão Final)", "manual": False}
    ]
    
    results = []
    
    for m in milestones_def:
        if m["manual"] and manual_meeting_date:
            final_date = manual_meeting_date
            display = "Manual"
        else:
            final_date = calculate_deadline_rigorous(
                start_date, 
                m["dias"], 
                suspensions, 
                adjust_weekend
            )
            display = f"{m['dias']} dias úteis"
            
        results.append({
            "Etapa": m["fase"],
            "Prazo Legal": display,
            "Data Prevista": final_date
        })
        
    total_susp_days = 0
    for s in suspensions:
        total_susp_days += (s['end'] - s['start']).days + 1
        
    return results, total_susp_days

# ==========================================
# 3. GERADOR DE PDF COMPLETO
# ==========================================

def create_pdf(project_name, typology, sector, start_date, milestones, suspensions, total_susp):
    if FPDF is None: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, 'CCDR CENTRO - Simulador AIA', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
            
    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 14)
    # Codificação segura para latin-1
    title = f"Relatório de Análise: {project_name}"
    pdf.multi_cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(5)
    
    # 1. Enquadramento
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Enquadramento e Legislação", 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Tipologia:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, typology.encode('latin-1','replace').decode('latin-1'))
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Setor:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, sector.encode('latin-1','replace').decode('latin-1'), 0, 1)
    pdf.ln(4)
    
    # Legislação
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Legislação Aplicável:", 0, 1)
    pdf.set_font("Arial", "", 9)
    
    # Transversal
    pdf.cell(0, 5, "Transversal:", 0, 1)
    for name, link in COMMON_LAWS.items():
        pdf.cell(5)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 5, f"- {name}".encode('latin-1','replace').decode('latin-1'), link=link, ln=1)
    
    # Específica
    pdf.set_text_color(0,0,0)
    pdf.cell(0, 5, "Setorial:", 0, 1)
    sector_laws = SPECIFIC_LAWS.get(sector, {})
    for name, link in sector_laws.items():
        pdf.cell(5)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 5, f"- {name}".encode('latin-1','replace').decode('latin-1'), link=link, ln=1)
    
    pdf.set_text_color(0,0,0)
    pdf.ln(5)
    
    # 2. Cronograma
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Cronograma do Processo", 0, 1)
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Data Início: {start_date.strftime('%d/%m/%Y')}", 0, 1)
    pdf.cell(0, 6, f"Suspensões (Total): {total_susp} dias", 0, 1)
    pdf.ln(3)
    
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
    pdf.cell(40, 8, "Prazo Legal", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Data Prevista", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", "", 10)
    
    # --- LINHA ADICIONAL: ENTRADA DO PROCESSO ---
    pdf.cell(90, 8, "Entrada do Processo / Instrucao", 1, 0, 'L')
    pdf.cell(40, 8, "Dia 0", 1, 0, 'C')
    pdf.cell(40, 8, start_date.strftime('%d/%m/%Y'), 1, 1, 'C')
    # --------------------------------------------
    
    for m in milestones:
        pdf.cell(90, 8, m["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
        pdf.cell(40, 8, str(m["Prazo Legal"]), 1, 0, 'C')
        pdf.cell(40, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.ln()
    
    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, "Registo de Suspensões (PeA):", 0, 1)
        pdf.set_font("Arial", "", 10)
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(0, 6, f"- {s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')} ({dur} dias)", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. INTERFACE GRÁFICA
# ==========================================

st.title("🌿 Simulador de prazos do procedimento AIA")

if FPDF is None:
    st.error("⚠️ ERRO CRÍTICO: A biblioteca 'fpdf' não está instalada.")
    st.stop()

with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Ampliação Zona Industrial Condeixa")
    start_date = st.date_input("Data de Instrução (Dia 0)", date(2025, 11, 20))
    
    st.markdown("---")
    st.subheader("⚖️ Enquadramento")
    
    selected_typology = st.selectbox(
        "Tipologia do Projeto (RJAIA)",
        list(TIPOLOGIAS_INFO.keys())
    )
    
    selected_sector = st.selectbox(
        "Setor de Atividade",
        list(SPECIFIC_LAWS.keys())
    )
    
    st.caption(f"ℹ️ {TIPOLOGIAS_INFO[selected_typology]}")

    st.markdown("---")
    st.subheader("⚙️ Configuração")
    adjust_weekend = st.checkbox("Ajustar termo ao dia útil (CPA)?", True)
    
    st.subheader("🗓️ Agendamentos")
    theoretical_meeting = add_business_days(start_date, 9)
    meeting_date_input = st.date_input("Data Real da Reunião", value=theoretical_meeting)
    
    st.markdown("---")
    st.subheader("⏸️ Suspensões (PeA)")
    
    if 'suspensions' not in st.session_state:
        st.session_state.suspensions = []

    with st.form("add_suspension"):
        c1, c2 = st.columns(2)
        s_start = c1.date_input("Início", date(2025, 12, 16))
        s_end = c2.date_input("Fim", date(2026, 3, 27))
        if st.form_submit_button("Adicionar"):
            if s_end < s_start:
                st.error("Data Fim inválida.")
            else:
                st.session_state.suspensions.append({'start': s_start, 'end': s_end})
                st.rerun()

    if st.session_state.suspensions:
        for i, s in enumerate(st.session_state.suspensions):
            col_txt, col_del = st.columns([0.8, 0.2])
            col_txt.text(f"{s['start'].strftime('%d/%m')} a {s['end'].strftime('%d/%m')}")
            if col_del.button("❌", key=f"del_{i}"):
                del st.session_state.suspensions[i]
                st.rerun()

# ==========================================
# 5. EXECUÇÃO
# ==========================================

milestones, total_susp = calculate_all_milestones(
    start_date, 
    st.session_state.suspensions, 
    manual_meeting_date=meeting_date_input,
    adjust_weekend=adjust_weekend
)

final_dia_date = milestones[-1]["Data Prevista"]

st.divider()
c1, c2, c3, c4 = st.columns(4)

short_typology = selected_typology.split("(")[0].strip()
c1.metric("Enquadramento", short_typology[:20]+"...", help=selected_typology)
c2.metric("Início Processo", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias")
c4.metric("Data Limite (DIA)", final_dia_date.strftime("%d/%m/%Y"))

tab1, tab2, tab3 = st.tabs(["📋 Tabela", "📅 Cronograma", "📚 Legislação"])

with tab1:
    df = pd.DataFrame(milestones)
    # Adicionar a linha de entrada na tabela visual também
    entry_row = pd.DataFrame([{
        "Etapa": "Entrada do Processo / Instrução",
        "Prazo Legal": "Dia 0",
        "Data Prevista": start_date
    }])
    df = pd.concat([entry_row, df], ignore_index=True)
    
    df["Data Prevista"] = pd.to_datetime(df["Data Prevista"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    df_gantt = []
    last_end = start_date
    for item in milestones:
        end_date_dt = item["Data Prevista"]
        start_viz = last_end 
        if start_viz > end_date_dt: start_viz = end_date_dt
        df_gantt.append(dict(Task=item["Etapa"], Start=start_viz, Finish=end_date_dt, Resource="Fase"))
        last_end = end_date_dt
        
    for s in st.session_state.suspensions:
        df_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Resource="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(df_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource",
                      color_discrete_map={"Fase": "#2E86C1", "Suspensão": "#E74C3C"})
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader(f"Legislação: {selected_sector}")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Transversal**")
        for name, link in COMMON_LAWS.items():
            st.markdown(f"- [{name}]({link})")
    with col_b:
        st.markdown("**Específica**")
        for name, link in SPECIFIC_LAWS.get(selected_sector, {}).items():
            st.markdown(f"- [{name}]({link})")

st.markdown("---")
if st.button("Gerar Relatório PDF"):
    pdf_bytes = create_pdf(
        proj_name, 
        selected_typology, 
        selected_sector, 
        start_date, 
        milestones, 
        st.session_state.suspensions, 
        total_susp
    )
    if pdf_bytes:
        st.download_button(
            label="📥 Descarregar PDF",
            data=pdf_bytes,
            file_name=f"Relatorio_{proj_name.replace(' ', '_')}.pdf",
            mime='application/pdf'
        )
