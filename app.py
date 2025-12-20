import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import tempfile
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Prazos AIA - CCDR Centro",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tenta importar FPDF
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 2. DADOS DE BASE
# ==========================================

# FERIADOS
# Nota: CARNAVAL 2025 (04/03) REMOVIDO para alinhar com o Excel de referência.
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
# 3. MOTOR DE CÁLCULO
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
        # Lógica inclusiva: se a data for igual ao início ou fim, conta como suspenso
        if s['start'] <= current_date <= s['end']:
            return True
    return False

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, return_log=False):
    current_date = start_date
    days_counted = 0
    log = []
    
    if return_log:
        log.append({"Data": current_date, "Dia Contado": 0, "Status": "Início"})

    # O loop continua enquanto não tivermos contado os dias úteis todos
    while days_counted < target_business_days:
        current_date += timedelta(days=1)
        
        status = "Util"
        # 1. Verifica Suspensão primeiro
        if is_suspended(current_date, suspensions):
            status = "Suspenso"
        # 2. Verifica Fim de Semana
        elif current_date.weekday() >= 5:
            status = "Fim de Semana"
        # 3. Verifica Feriado
        elif current_date in FERIADOS:
            status = "Feriado"
            
        if status == "Util":
            days_counted += 1
            
        if return_log:
            log.append({"Data": current_date, "Dia Contado": days_counted if status == "Util" else "-", "Status": status})
            
    final_date = current_date
    
    # Ajuste CPA: Se o prazo terminar em Sábado/Domingo/Feriado, passa para o próximo útil
    while final_date.weekday() >= 5 or final_date in FERIADOS:
         final_date += timedelta(days=1)
    
    if return_log:
        return final_date, log
    return final_date

def calculate_workflow(start_date, suspensions, milestones_config):
    results = []
    log_final = []
    
    # Marcos Principais definidos na Sidebar
    steps = [
        ("Data Reunião", milestones_config["reuniao"]),
        ("Limite Conformidade", milestones_config["conformidade"]),
        ("Envio PTF à AAIA", milestones_config["ptf"]),
        ("Audiência de Interessados", milestones_config["audiencia"]),
        ("Emissão da DIA (Decisão Final)", milestones_config["dia"])
    ]
    
    conf_date_real = None 
    
    for nome, dias in steps:
        if dias == milestones_config["dia"]: 
            # Gera log detalhado apenas para o prazo final
            final_date, log_data = calculate_deadline_rigorous(start_date, dias, suspensions, return_log=True)
            log_final = log_data
        else:
            final_date = calculate_deadline_rigorous(start_date, dias, suspensions)
            
        if nome == "Limite Conformidade":
            conf_date_real = final_date
            
        results.append({
            "Etapa": nome, 
            "Prazo Legal": f"{dias} dias úteis", 
            "Data Prevista": final_date
        })

    # Marcos Complementares
    complementary = []
    gantt_data = {}
    
    if conf_date_real:
        cp_duration = milestones_config.get("cp_duration", 30)
        visit_days = milestones_config.get("visita", 15)
        sectoral_days = milestones_config.get("setoriais", 75)

        # Cálculos de datas derivadas
        conf_date_theo = calculate_deadline_rigorous(start_date, milestones_config["conformidade"], [])
        
        # 2. Início CP: 5 dias úteis APÓS a Conformidade Real
        cp_start = add_business_days(conf_date_real, 5)
        
        # 3. Fim CP
        cp_end = add_business_days(cp_start, cp_duration)
        
        # 4. Pareceres Externos (Início CP + 23)
        external_ops = add_business_days(cp_start, 23)
        
        # 5. Relatório CP (Fim CP + 7)
        cp_report = add_business_days(cp_end, 7)
        
        # 6. Visita (Início CP + 15)
        visit_date = add_business_days(cp_start, visit_days)
        
        # 7. Pareceres Setoriais (Global)
        sectoral_date = calculate_deadline_rigorous(start_date, sectoral_days, suspensions)
        
        gantt_data = {
            "cp_start": cp_start,
            "cp_end": cp_end,
            "visit": visit_date,
            "sectoral": sectoral_date
        }
        
        complementary = [
            {"Etapa": "1. Limite Conformidade (Ref. Teórica)", "Ref": "Sem suspensões", "Data": conf_date_theo},
            {"Etapa": "1. Limite Conformidade (Real)", "Ref": "Com suspensões", "Data": conf_date_real},
            {"Etapa": "2. Início Consulta Pública", "Ref": "Conf + 5 dias", "Data": cp_start},
            {"Etapa": "3. Fim Consulta Pública", "Ref": f"Início CP + {cp_duration} dias", "Data": cp_end},
            {"Etapa": "4. Data para Pareceres Externos", "Ref": "Início CP + 23 dias", "Data": external_ops},
            {"Etapa": "5. Envio do Relatório da CP", "Ref": "Fim CP + 7 dias", "Data": cp_report},
            {"Etapa": "6. Visita Técnica", "Ref": f"Início CP + {visit_days} dias", "Data": visit_date},
            {"Etapa": "7. Pareceres Setoriais", "Ref": f"Dia {sectoral_days} Global", "Data": sectoral_date},
        ]

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    
    return results, complementary, total_susp, log_final, gantt_data

# ==========================================
# 5. INTERFACE DO UTILIZADOR
# ==========================================

st.title("🌿 Analista EIA - RJAIA Completo")
st.markdown("Ferramenta de cálculo de prazos de acordo com o **RJAIA** e **Simplex Ambiental**.")

if FPDF is None:
    st.error("⚠️ Aviso: A biblioteca 'fpdf' não está instalada. A geração de PDF não funcionará.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Novo Projeto AIA")
    start_date = st.date_input("Data de Instrução (Dia 0)", date.today())
    
    st.markdown("---")
    st.subheader("⚖️ Enquadramento")
    
    selected_typology = st.selectbox("Tipologia do Projeto", list(TIPOLOGIAS_INFO.keys()))
    selected_sector = st.selectbox("Setor de Atividade", list(SPECIFIC_LAWS.keys()))
    
    regime_option = st.radio(
        "Selecione o Prazo Global:",
        (150, 90),
        format_func=lambda x: f"{x} Dias Úteis (AIA {'Geral' if x==150 else 'Simplificado/SIR'})"
    )
    
    with st.expander("⚙️ Definições Avançadas de Prazos", expanded=False):
        st.caption("Valores ajustam-se automaticamente ao Regime (Simplex ou Geral). Pode editar abaixo.")
        
        if regime_option == 150:
            # Defaults 150 dias (RJAIA Geral)
            d_reuniao = st.number_input("Reunião", value=9, key="r150")
            d_conf = st.number_input("Conformidade", value=30, key="c150")
            d_ptf = st.number_input("Envio PTF", value=85, key="p150")
            d_aud = st.number_input("Audiência", value=100, key="a150")
            d_setoriais = st.number_input("Pareceres Setoriais (Dia Global)", value=75, key="s150")
            d_dia = st.number_input("Decisão Final (DIA)", value=150, disabled=True, key="d150")
        else:
            # Defaults 90 dias (Padrões Legais/Excel "Com Suspensão")
            # 65 dias para PTF, 70 para Audiência, 60 para Setoriais, 20 para Conformidade
            d_reuniao = st.number_input("Reunião", value=9, key="r90")
            d_conf = st.number_input("Conformidade", value=20, key="c90")  
            d_ptf = st.number_input("Envio PTF", value=65, key="p90")      
            d_aud = st.number_input("Audiência", value=70, key="a90")      
            d_setoriais = st.number_input("Pareceres Setoriais (Dia Global)", value=60, key="s90")
            d_dia = st.number_input("Decisão Final (DIA)", value=90, disabled=True, key="d90")
        
        st.markdown("**Prazos Complementares:**")
        d_cp_duration = st.number_input("Duração Consulta Pública (dias)", value=30)
        d_visita = st.number_input("Dia da Visita (após Início CP)", value=15)
            
        milestones_config = {
            "reuniao": d_reuniao, "conformidade": d_conf, "ptf": d_ptf,
            "audiencia": d_aud, "dia": d_dia,
            "visita": d_visita, "setoriais": d_setoriais, "cp_duration": d_cp_duration
        }

    st.markdown("---")
    st.subheader("⏸️ Gestão de Suspensões")
    
    if 'suspensions_universal' not in st.session_state:
        st.session_state.suspensions_universal = []
    
    with st.form("add_susp_uni", clear_on_submit=True):
        c1, c2 = st.columns(2)
        new_start = c1.date_input("Início Suspensão")
        new_end = c2.date_input("Fim Suspensão")
        if st.form_submit_button("Adicionar"):
            st.session_state.suspensions_universal.append({'start': new_start, 'end': new_end})
            st.rerun()
    
    if st.session_state.suspensions_universal:
        st.write("**Suspensões Ativas:**")
        for i, s in enumerate(st.session_state.suspensions_universal):
            c_txt, c_btn = st.columns([0.8, 0.2])
            c_txt.text(f"{s['start'].strftime('%d/%m')} a {s['end'].strftime('%d/%m')}")
            if c_btn.button("X", key=f"rm_{i}"):
                del st.session_state.suspensions_universal[i]
                st.rerun()

# ==========================================
# 6. CÁLCULO E RESULTADOS
# ==========================================

milestones, complementary, total_susp, log_dia, gantt_data = calculate_workflow(
    start_date, 
    st.session_state.suspensions_universal, 
    milestones_config
)

final_dia_date = milestones[-1]["Data Prevista"]

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Regime", f"{regime_option} Dias")
c2.metric("Início", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias")
c4.metric("Previsão DIA", final_dia_date.strftime("%d/%m/%Y"))

tab1, tab2, tab3, tab4 = st.tabs(["📋 Prazos Principais", "📑 Complementares", "📅 Gantt", "⚖️ Legislação"])

with tab1:
    df_main = pd.DataFrame(milestones)
    row0 = pd.DataFrame([{"Etapa": "Entrada / Instrução", "Prazo Legal": "Dia 0", "Data Prevista": start_date}])
    df_main = pd.concat([row0, df_main], ignore_index=True)
    df_main["Data Prevista"] = pd.to_datetime(df_main["Data Prevista"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df_main, use_container_width=True, hide_index=True)

with tab2:
    if complementary:
        df_comp = pd.DataFrame(complementary)
        df_comp["Data"] = pd.to_datetime(df_comp["Data"]).dt.strftime("%d-%m-%Y")
        st.dataframe(df_comp, use_container_width=True, hide_index=True)

with tab3:
    data_gantt = []
    last = start_date
    for m in milestones:
        end = m["Data Prevista"]
        start = last if last < end else end
        data_gantt.append(dict(Task=m["Etapa"], Start=start, Finish=end, Resource="Fase Principal"))
        last = end
    
    if gantt_data:
        data_gantt.append(dict(Task="Consulta Pública", Start=gantt_data['cp_start'], Finish=gantt_data['cp_end'], Resource="Consulta Pública"))
        
    for s in st.session_state.suspensions_universal:
        data_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Resource="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(data_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource",
                      color_discrete_map={"Fase Principal": "#2E86C1", "Suspensão": "#E74C3C", "Consulta Pública": "#27AE60", "Outros": "#F1C40F"})
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.write("**Transversal:**")
    for k, v in COMMON_LAWS.items(): st.markdown(f"- [{k}]({v})")
    
st.markdown("---")
if st.button("Gerar Relatório PDF"):
    pdf_bytes = create_pdf(
        proj_name, 
        selected_typology, 
        selected_sector, 
        f"Regime {regime_option} Dias", 
        start_date, 
        milestones, 
        complementary, 
        st.session_state.suspensions_universal, 
        total_susp,
        gantt_data
    )
    if pdf_bytes:
        st.download_button("Descarregar PDF", pdf_bytes, "relatorio_aia.pdf", "application/pdf")

