import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Prazos AIA - CCDR Centro",
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

# Feriados Nacionais (até 2030)
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

# ==========================================
# 2. FUNÇÕES DE CÁLCULO RIGOROSO (MOTOR)
# ==========================================

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: return False
    if check_date in FERIADOS: return False
    return True

def add_business_days(start_date, num_days):
    """Adiciona dias úteis simples."""
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

def is_suspended(current_date, suspensions):
    """Verifica se data está num intervalo de suspensão (inclusive)."""
    for s in suspensions:
        if s['start'] <= current_date <= s['end']:
            return True
    return False

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, adjust_weekend=True, return_log=False):
    """
    Algoritmo principal: Conta dias úteis progressivamente, saltando suspensões.
    """
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
    
    # Ajuste CPA (Art. 87): Se terminar em dia não útil, passa para o próximo útil
    if adjust_weekend:
        while final_date.weekday() >= 5 or final_date in FERIADOS:
             final_date += timedelta(days=1)
    
    if return_log:
        return final_date, log
    return final_date

def calculate_workflow(start_date, suspensions, regime_days, milestones_config):
    """
    Calcula todos os marcos do processo com base no regime escolhido.
    """
    results = []
    log_final = []
    
    # Lista ordenada de etapas para calcular
    steps = [
        ("Data Reunião", milestones_config["reuniao"]),
        ("Limite Conformidade", milestones_config["conformidade"]),
        ("Envio PTF à AAIA", milestones_config["ptf"]),
        ("Audiência de Interessados", milestones_config["audiencia"]),
        ("Emissão da DIA (Decisão Final)", milestones_config["dia"])
    ]
    
    conf_date = None # Para guardar a data de conformidade para uso nos complementares
    
    for nome, dias in steps:
        if dias == milestones_config["dia"]: # Se for o último dia, guarda o log
            final_date, log_data = calculate_deadline_rigorous(start_date, dias, suspensions, return_log=True)
            log_final = log_data
        else:
            final_date = calculate_deadline_rigorous(start_date, dias, suspensions)
            
        if nome == "Limite Conformidade":
            conf_date = final_date
            
        results.append({
            "Etapa": nome, 
            "Prazo Legal": f"{dias} dias úteis", 
            "Data Prevista": final_date
        })

    # 2. Marcos Complementares (Dependentes da Conformidade)
    complementary = []
    if conf_date:
        # Início CP: 5 dias úteis após Conformidade
        cp_start = add_business_days(conf_date, 5)
        # Fim CP: 30 dias úteis após Início CP
        cp_end = add_business_days(cp_start, 30)
        # Relatório CP: 7 dias úteis após Fim CP
        cp_report = add_business_days(cp_end, 7)
        # Pareceres Externos: 23 dias úteis após INÍCIO da CP
        external_ops = add_business_days(cp_start, 23)
        
        complementary = [
            {"Etapa": "Início Consulta Pública", "Ref": "Conf + 5 dias", "Data": cp_start},
            {"Etapa": "Fim Consulta Pública", "Ref": "Início CP + 30 dias", "Data": cp_end},
            {"Etapa": "Prazo Pareceres Externos", "Ref": "Início CP + 23 dias", "Data": external_ops},
            {"Etapa": "Relatório da CP", "Ref": "Fim CP + 7 dias", "Data": cp_report},
        ]

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    
    return results, complementary, total_susp, log_final

# ==========================================
# 3. GERADOR DE PDF
# ==========================================
def create_pdf(project_name, regime, start_date, milestones, complementary, suspensions, total_susp):
    if FPDF is None: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, 'CCDR CENTRO - Autoridade de AIA', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 14)
    safe_title = f"Simulacao de Prazos: {project_name}"
    pdf.multi_cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(5)

    # Resumo
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Resumo do Processo", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 6, "Regime Aplicavel:", 0, 0)
    pdf.cell(0, 6, f"{regime} dias uteis", 0, 1)
    pdf.cell(50, 6, "Data de Instrucao:", 0, 0)
    pdf.cell(0, 6, start_date.strftime('%d/%m/%Y'), 0, 1)
    pdf.cell(50, 6, "Total Suspensao:", 0, 0)
    pdf.cell(0, 6, f"{total_susp} dias de calendario", 0, 1)
    pdf.ln(5)

    # Tabela Principal
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Cronograma Principal", 0, 1)
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
    pdf.cell(40, 8, "Prazo Legal", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Data Prevista", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", "", 9)
    # Linha 0
    pdf.cell(90, 8, "Entrada / Instrucao", 1, 0, 'L')
    pdf.cell(40, 8, "Dia 0", 1, 0, 'C')
    pdf.cell(40, 8, start_date.strftime('%d/%m/%Y'), 1, 1, 'C')
    
    for m in milestones:
        pdf.cell(90, 8, m["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
        pdf.cell(40, 8, str(m["Prazo Legal"]), 1, 0, 'C')
        pdf.cell(40, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.ln()

    # Tabela Complementar
    if complementary:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "Prazos Complementares (Consulta Publica)", 0, 1)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Referencia", 1, 0, 'C', 1)
        pdf.cell(40, 8, "Data Prevista", 1, 1, 'C', 1)
        pdf.set_font("Arial", "", 9)
        for c in complementary:
            pdf.cell(90, 8, c["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Ref"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Data"].strftime('%d/%m/%Y'), 1)
            pdf.ln()

    # Suspensões
    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "Registo de Suspensoes", 0, 1)
        pdf.set_font("Arial", "", 9)
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(0, 6, f"- {s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')} ({dur} dias)", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. INTERFACE GRÁFICA (UNIVERSAL)
# ==========================================

st.title("🌿 Simulador de Prazos AIA - Universal (CCDR Centro)")
st.markdown("Ferramenta de cálculo de prazos de acordo com o **RJAIA** e **Simplex Ambiental**.")

if FPDF is None:
    st.error("⚠️ Aviso: A biblioteca 'fpdf' não está instalada. A geração de PDF não funcionará.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Novo Processo")
    proj_name = st.text_input("Nome do Projeto", "Novo Projeto AIA")
    start_date = st.date_input("Data de Instrução (Dia 0)", date.today())
    
    st.markdown("---")
    st.subheader("⚖️ Regime Legal")
    
    # SELETOR DE REGIME
    regime_option = st.radio(
        "Selecione o Prazo Global:",
        (150, 90),
        format_func=lambda x: f"{x} Dias Úteis (AIA {'Geral' if x==150 else 'Simplificado/Outros'})"
    )
    
    # DEFINIÇÕES DE MARCOS (Preenchimento automático mas editável)
    with st.expander("⚙️ Definições Avançadas de Prazos", expanded=False):
        st.caption("Pode ajustar os prazos intermédios se houver regras específicas de gestão.")
        
        if regime_option == 150:
            d_reuniao = st.number_input("Reunião", value=9)
            d_conf = st.number_input("Conformidade", value=30)
            d_ptf = st.number_input("Envio PTF", value=85, help="Legalmente 85")
            d_aud = st.number_input("Audiência", value=100)
            d_dia = st.number_input("Decisão Final (DIA)", value=150, disabled=True)
        else: # 90 dias
            d_reuniao = st.number_input("Reunião", value=5)
            d_conf = st.number_input("Conformidade", value=20)
            d_ptf = st.number_input("Envio PTF", value=50)
            d_aud = st.number_input("Audiência", value=60)
            d_dia = st.number_input("Decisão Final (DIA)", value=90, disabled=True)
            
        milestones_config = {
            "reuniao": d_reuniao,
            "conformidade": d_conf,
            "ptf": d_ptf,
            "audiencia": d_aud,
            "dia": d_dia
        }

    st.markdown("---")
    st.subheader("⏸️ Gestão de Suspensões")
    
    # GESTÃO DE LISTA DE SUSPENSÕES (UNIVERSAL)
    if 'suspensions_universal' not in st.session_state:
        st.session_state.suspensions_universal = []
    
    with st.form("add_susp_uni", clear_on_submit=True):
        c1, c2 = st.columns(2)
        new_start = c1.date_input("Início Suspensão")
        new_end = c2.date_input("Fim Suspensão")
        if st.form_submit_button("Adicionar Suspensão"):
            if new_end < new_start:
                st.error("Data de fim anterior à data de início.")
            else:
                st.session_state.suspensions_universal.append({'start': new_start, 'end': new_end})
                st.rerun()
    
    # Lista e Remoção
    if st.session_state.suspensions_universal:
        st.write("**Suspensões Ativas:**")
        idx_to_remove = None
        for i, s in enumerate(st.session_state.suspensions_universal):
            col_info, col_btn = st.columns([0.85, 0.15])
            col_info.text(f"{s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')}")
            if col_btn.button("❌", key=f"rm_{i}"):
                idx_to_remove = i
        
        if idx_to_remove is not None:
            del st.session_state.suspensions_universal[idx_to_remove]
            st.rerun()

# ==========================================
# 5. CÁLCULO E RESULTADOS
# ==========================================

milestones, complementary, total_susp, log_dia = calculate_workflow(
    start_date, 
    st.session_state.suspensions_universal, 
    regime_option, 
    milestones_config
)

final_dia_date = milestones[-1]["Data Prevista"]

# --- DASHBOARD ---
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Regime", f"{regime_option} Dias")
c2.metric("Início Processo", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias")
c4.metric("Previsão DIA", final_dia_date.strftime("%d/%m/%Y"))

# --- ABAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📋 Prazos Principais", "📑 Prazos Complementares", "📅 Cronograma", "⚖️ Legislação"])

with tab1:
    df_main = pd.DataFrame(milestones)
    row0 = pd.DataFrame([{"Etapa": "Entrada / Instrução", "Prazo Legal": "Dia 0", "Data Prevista": start_date}])
    df_main = pd.concat([row0, df_main], ignore_index=True)
    df_main["Data Prevista"] = pd.to_datetime(df_main["Data Prevista"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df_main, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Fases de Consulta e Pareceres")
    if complementary:
        df_comp = pd.DataFrame(complementary)
        df_comp["Data"] = pd.to_datetime(df_comp["Data"]).dt.strftime("%d-%m-%Y")
        st.dataframe(df_comp, use_container_width=True)
    else:
        st.info("Prazos complementares indisponíveis.")

with tab3:
    data_gantt = []
    last = start_date
    for m in milestones:
        end = m["Data Prevista"]
        start = last if last < end else end
        data_gantt.append(dict(Task=m["Etapa"], Start=start, Finish=end, Resource="Fase Principal"))
        last = end
    
    for c in complementary:
        if "Consulta" in c["Etapa"]:
            end_c = c["Data"]
            start_c = add_business_days(end_c, -30) if "Fim" in c["Etapa"] else c["Data"]
            data_gantt.append(dict(Task=c["Etapa"], Start=start_c, Finish=end_c, Resource="Consulta Pública"))
        else:
            data_gantt.append(dict(Task=c["Etapa"], Start=c["Data"], Finish=c["Data"], Resource="Outros"))
            
    for s in st.session_state.suspensions_universal:
        data_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Resource="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(data_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource",
                      color_discrete_map={"Fase Principal": "#2E86C1", "Suspensão": "#E74C3C", "Consulta Pública": "#27AE60", "Outros": "#F1C40F"})
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Legislação de Referência")
    for k, v in COMMON_LAWS.items():
        st.markdown(f"- [{k}]({v})")

st.markdown("---")
if st.button("Gerar Relatório PDF"):
    pdf_bytes = create_pdf(
        proj_name, 
        f"Regime {regime_option} Dias", 
        start_date, 
        milestones, 
        complementary, 
        st.session_state.suspensions_universal, 
        total_susp
    )
    if pdf_bytes:
        st.download_button("Descarregar PDF", pdf_bytes, "relatorio_aia.pdf", "application/pdf")
