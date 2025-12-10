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

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 1. DADOS DE BASE (FERIADOS ATÉ 2030)
# ==========================================
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
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUIDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "AGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {"ATIVIDADE PECUARIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678"},
    "2. Industria Extrativa": {"MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875"},
    "3. Industria Energetica": {"SISTEMA ELETRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687"},
    "6. Infraestruturas": {"ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678"},
    "9. Projetos Urbanos": {"RJUE (DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452"}
}

TIPOLOGIAS_INFO = {
    "Anexo I (Competencia CCDR)": "Projetos do Anexo I do RJAIA sob competencia da CCDR.",
    "Anexo II (Limiares ou Zonas Sensiveis)": "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localizacao em zona sensivel.",
    "Alteracao ou Ampliacao (Competencia CCDR)": "Alteracoes a projetos existentes."
}

# ==========================================
# 2. FUNÇÕES DE CÁLCULO
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
        log.append({"Data": current_date, "Dia Contado": 0, "Status": "Inicio"})

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
    # Marcos Principais
    milestones_def = [
        {"dias": 9,   "fase": "Data Reunião", "manual": True},
        {"dias": 30,  "fase": "Limite Conformidade", "manual": False},
        {"dias": 100, "fase": "Envio PTF à AAIA (100d)", "manual": False},
        {"dias": 120, "fase": "Audiência de Interessados (120d)", "manual": False},
        {"dias": 150, "fase": "Emissão da DIA (Decisão Final)", "manual": False}
    ]
    results = []
    log_conf = [] 
    
    # Datas Calculadas
    conf_date = None # Para guardar a data da conformidade
    
    for m in milestones_def:
        if m["manual"] and manual_meeting_date:
            final_date = manual_meeting_date
            display = "Manual"
        else:
            if m["dias"] == 30: 
                final_date, log_data = calculate_deadline_rigorous(start_date, m["dias"], suspensions, adjust_weekend, return_log=True)
                log_conf = log_data
                conf_date = final_date
            else:
                final_date = calculate_deadline_rigorous(start_date, m["dias"], suspensions, adjust_weekend)
            display = f"{m['dias']} dias úteis"
        results.append({"Etapa": m["fase"], "Prazo Legal": display, "Data Prevista": final_date})
    
    # Marcos Complementares (Baseados na Conformidade Ajustada)
    # Assumimos que estes prazos correm após a conformidade já ter descontado a suspensão
    if conf_date:
        cp_start = add_business_days(conf_date, 5)
        cp_end = add_business_days(cp_start, 30)
        cp_report = add_business_days(cp_end, 7)
        visit_date = add_business_days(cp_start, 15) # 3ª semana
        # Pareceres externos: ~23 dias uteis apos conformidade
        external_ops = add_business_days(conf_date, 23)
        
        complementary = [
            {"Etapa": "Início Consulta Pública", "Prazo": "Conf + 5 dias", "Data": cp_start},
            {"Etapa": "Fim Consulta Pública", "Prazo": "Início CP + 30 dias", "Data": cp_end},
            {"Etapa": "Relatório da CP", "Prazo": "Fim CP + 7 dias", "Data": cp_report},
            {"Etapa": "Visita Técnica", "Prazo": "3ª semana CP", "Data": visit_date},
            {"Etapa": "Pareceres Externos", "Prazo": "Conf + 23 dias (est.)", "Data": external_ops},
        ]
    else:
        complementary = []

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    return results, complementary, total_susp, log_conf

# ==========================================
# 3. PDF
# ==========================================
def create_pdf(project_name, typology, sector, start_date, milestones, complementary, suspensions, total_susp):
    if FPDF is None: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, 'CCDR CENTRO - Simulador AIA', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    safe_title = f"Relatorio de Analise: {project_name}"
    pdf.multi_cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(5)

    # 1. Enquadramento
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Enquadramento", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(40, 6, "Tipologia:", 0, 0)
    pdf.multi_cell(0, 6, typology.encode('latin-1','replace').decode('latin-1'))
    pdf.cell(40, 6, "Setor:", 0, 0)
    pdf.cell(0, 6, sector.encode('latin-1','replace').decode('latin-1'), 0, 1)
    pdf.ln(4)

    # 2. Cronograma Principal
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Cronograma Principal", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Data Inicio: {start_date.strftime('%d/%m/%Y')}", 0, 1)
    pdf.cell(0, 6, f"Suspensoes (Total): {total_susp} dias", 0, 1)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
    pdf.cell(40, 8, "Prazo", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Data", 1, 1, 'C', 1)
    pdf.set_font("Arial", "", 10)

    pdf.cell(90, 8, "Entrada do Processo / Instrucao", 1, 0, 'L')
    pdf.cell(40, 8, "Dia 0", 1, 0, 'C')
    pdf.cell(40, 8, start_date.strftime('%d/%m/%Y'), 1, 1, 'C')

    for m in milestones:
        pdf.cell(90, 8, m["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
        pdf.cell(40, 8, str(m["Prazo Legal"]), 1, 0, 'C')
        pdf.cell(40, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.ln()

    # 3. Prazos Complementares
    if complementary:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 10, "3. Prazos Complementares (Consulta Publica)", 0, 1)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Referencia", 1, 0, 'C', 1)
        pdf.cell(40, 8, "Data", 1, 1, 'C', 1)
        pdf.set_font("Arial", "", 10)
        
        for c in complementary:
            pdf.cell(90, 8, c["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Prazo"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Data"].strftime('%d/%m/%Y'), 1)
            pdf.ln()

    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, "Registo de Suspensoes:", 0, 1)
        pdf.set_font("Arial", "", 10)
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(0, 6, f"- {s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')} ({dur} dias)", 0, 1)
            
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. INTERFACE
# ==========================================
st.title("🌿 Simulador de prazos do procedimento AIA")

if FPDF is None:
    st.error("Erro: Instale 'fpdf'")
    st.stop()

with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Processo 2025")
    start_date = st.date_input("Data de Instrução (Dia 0)", date(2025, 1, 30))
    
    st.markdown("---")
    st.subheader("⚖️ Enquadramento")
    selected_typology = st.selectbox("Tipologia", list(TIPOLOGIAS_INFO.keys()))
    selected_sector = st.selectbox("Setor", list(SPECIFIC_LAWS.keys()))
    
    st.markdown("---")
    st.subheader("⚙️ Configuração")
    adjust_weekend = st.checkbox("Ajustar termo ao dia útil (CPA)?", True)
    
    st.subheader("🗓️ Agendamentos")
    theo_meeting = add_business_days(start_date, 9)
    meeting_date_input = st.date_input("Data Real Reunião", value=theo_meeting)

    st.markdown("---")
    st.subheader("⏸️ Suspensões")
    st.info("Para obter 09/05/2025 (Conformidade): Início 05/03/2025 | Fim 29/04/2025.")
    
    if 'suspensions' not in st.session_state: st.session_state.suspensions = []
    
    with st.form("add_susp"):
        c1, c2 = st.columns(2)
        s_s = c1.date_input("Início", date(2025, 3, 5))
        s_e = c2.date_input("Fim", date(2025, 4, 29))
        if st.form_submit_button("Adicionar"):
            st.session_state.suspensions.append({'start': s_s, 'end': s_e})
            st.rerun()
            
    if st.session_state.suspensions:
        for i, s in enumerate(st.session_state.suspensions):
            c_txt, c_del = st.columns([0.8, 0.2])
            c_txt.text(f"{s['start'].strftime('%d/%m')} a {s['end'].strftime('%d/%m')}")
            if c_del.button("❌", key=f"d{i}"):
                del st.session_state.suspensions[i]
                st.rerun()

# ==========================================
# 5. EXECUÇÃO
# ==========================================
milestones, complementary, total_susp, log_conf = calculate_all_milestones(
    start_date, st.session_state.suspensions, meeting_date_input, adjust_weekend
)
final_date = milestones[-1]["Data Prevista"]
conformity_date = milestones[1]["Data Prevista"]

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Início", start_date.strftime("%d/%m/%Y"))
c2.metric("Suspensões", f"{total_susp} dias")
c3.metric("Conformidade (30d)", conformity_date.strftime("%d/%m/%Y"))
c4.metric("Limite DIA (150d)", final_date.strftime("%d/%m/%Y"))

tab1, tab2, tab3, tab4 = st.tabs(["📋 Prazos Principais", "📑 Prazos Complementares", "📅 Cronograma", "🔍 Auditoria"])

with tab1:
    df = pd.DataFrame(milestones)
    row0 = pd.DataFrame([{"Etapa": "Entrada do Processo / Instrução", "Prazo Legal": "Dia 0", "Data Prevista": start_date}])
    df = pd.concat([row0, df], ignore_index=True)
    df["Data Prevista"] = pd.to_datetime(df["Data Prevista"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Consulta Pública e Pareceres")
    if complementary:
        df_comp = pd.DataFrame(complementary)
        df_comp["Data"] = pd.to_datetime(df_comp["Data"]).dt.strftime("%d-%m-%Y")
        st.dataframe(df_comp, use_container_width=True)
    else:
        st.warning("Não foi possível calcular prazos complementares (falta data de conformidade).")

with tab3:
    data_gantt = []
    last = start_date
    for m in milestones:
        end = m["Data Prevista"]
        start = last if last < end else end
        data_gantt.append(dict(Task=m["Etapa"], Start=start, Finish=end, Resource="Fase Principal"))
        last = end
    
    # Adicionar Complementares ao Gantt
    for c in complementary:
        if "Consulta" in c["Etapa"]:
            # Duração aproximada visual
            end_c = c["Data"]
            start_c = add_business_days(end_c, -30) if "Fim" in c["Etapa"] else c["Data"]
            data_gantt.append(dict(Task=c["Etapa"], Start=start_c, Finish=end_c, Resource="Consulta Pública"))
        else:
            data_gantt.append(dict(Task=c["Etapa"], Start=c["Data"], Finish=c["Data"], Resource="Outros"))

    for s in st.session_state.suspensions:
        data_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Resource="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(data_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource", 
                      color_discrete_map={"Fase Principal": "#2E86C1", "Suspensão": "#E74C3C", "Consulta Pública": "#27AE60", "Outros": "#F1C40F"})
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Auditoria de Contagem Diária (Conformidade)")
    df_log = pd.DataFrame(log_conf)
    df_log["Data"] = pd.to_datetime(df_log["Data"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df_log, use_container_width=True)

st.markdown("---")
if st.button("Gerar PDF"):
    b = create_pdf(proj_name, selected_typology, selected_sector, start_date, milestones, complementary, st.session_state.suspensions, total_susp)
    if b: st.download_button("Download PDF", b, "relatorio.pdf", "application/pdf")
