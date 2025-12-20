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
# 2. MOTOR DE FERIADOS (DINÂMICO)
# ==========================================

def get_easter_date(year):
    """Calcula o Domingo de Páscoa."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def get_holidays_range(start_year, end_year):
    """Gera feriados para um intervalo de anos (sem Carnaval)."""
    holidays = set()
    for year in range(start_year, end_year + 1):
        # Fixos
        fixed_dates = [(1, 1), (4, 25), (5, 1), (6, 10), (8, 15), 
                       (10, 5), (11, 1), (12, 1), (12, 8), (12, 25)]
        for m, d in fixed_dates:
            holidays.add(date(year, m, d))
        # Móveis
        easter = get_easter_date(year)
        holidays.add(easter - timedelta(days=2)) # Sexta-Feira Santa
        holidays.add(easter + timedelta(days=60)) # Corpo de Deus
    return holidays

# ==========================================
# 3. DADOS LEGAIS
# ==========================================
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "Simplex Ambiental (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212459",
    "CPA (Prazos)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558838"
}
# (Mantive os dicionários TIPOLOGIAS_INFO e SPECIFIC_LAWS como estavam, por brevidade)
TIPOLOGIAS_INFO = {"Anexo I": "Competência CCDR", "Anexo II": "Limiares", "Alteração": "Existentes", "AIA Simplificado": "Simplex"}
SPECIFIC_LAWS = {"Indústria Extrativa": {}, "Indústria Transformadora": {}, "Agropecuária": {}, "Energia": {}, "Infraestruturas": {}, "Outros": {}}

# ==========================================
# 4. MOTOR DE CÁLCULO
# ==========================================

def is_business_day(check_date, holidays_set):
    if check_date.weekday() >= 5: return False
    if check_date in holidays_set: return False
    return True

def add_business_days(start_date, num_days, holidays_set):
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date, holidays_set):
            added_days += 1
    return current_date

def is_suspended(current_date, suspensions):
    for s in suspensions:
        if s['start'] <= current_date <= s['end']:
            return True
    return False

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, holidays_set):
    current_date = start_date
    days_counted = 0
    while days_counted < target_business_days:
        current_date += timedelta(days=1)
        status = "Util"
        if is_suspended(current_date, suspensions): status = "Suspenso"
        elif current_date.weekday() >= 5: status = "Fim de Semana"
        elif current_date in holidays_set: status = "Feriado"
        
        if status == "Util": days_counted += 1
            
    final_date = current_date
    # Ajuste CPA (Fim de semana/Feriado passa para útil seguinte)
    while final_date.weekday() >= 5 or final_date in holidays_set:
         final_date += timedelta(days=1)
    return final_date

def calculate_workflow(start_date, suspensions, milestones_config, pea_date=None):
    holidays_set = get_holidays_range(start_date.year, start_date.year + 2)
    results = []
    
    # 1. Conformidade (Cálculo Especial Automático)
    dias_conf = milestones_config["conformidade"]
    conf_date = None
    
    # LÓGICA DE PEA AUTOMÁTICA:
    # Se houver PEA e Suspensão, calculamos o saldo de dias que faltavam e aplicamos APÓS a suspensão.
    if pea_date and suspensions:
        # Conta dias gastos até ao PEA
        days_spent = 0
        temp_date = start_date
        # Avança até ao dia anterior ao PEA
        while temp_date < (pea_date - timedelta(days=1)):
            temp_date += timedelta(days=1)
            if is_business_day(temp_date, holidays_set):
                days_spent += 1
        
        days_remaining = dias_conf - days_spent
        if days_remaining < 0: days_remaining = 0
        
        # Encontra o fim da suspensão
        last_susp_end = max([s['end'] for s in suspensions])
        # Soma o resto
        conf_date = add_business_days(last_susp_end, days_remaining, holidays_set)
    else:
        # Cálculo normal (sem PEA ou sem suspensão)
        conf_date = calculate_deadline_rigorous(start_date, dias_conf, suspensions, holidays_set)

    results.append({"Etapa": "Limite Conformidade", "Prazo Legal": f"{dias_conf} dias", "Data Prevista": conf_date})

    # 2. Outras Etapas (Cálculo Normal)
    other_steps = [
        ("Data Reunião", milestones_config["reuniao"]),
        ("Envio PTF à AAIA", milestones_config["ptf"]),
        ("Audiência de Interessados", milestones_config["audiencia"]),
        ("Emissão da DIA (Decisão Final)", milestones_config["dia"])
    ]
    
    for nome, dias in other_steps:
        f_date = calculate_deadline_rigorous(start_date, dias, suspensions, holidays_set)
        results.append({"Etapa": nome, "Prazo Legal": f"{dias} dias", "Data Prevista": f_date})

    # 3. Complementares
    complementary = []
    gantt_data = {}
    if conf_date:
        cp_start = add_business_days(conf_date, 5, holidays_set)
        cp_end = add_business_days(cp_start, milestones_config["cp_duration"], holidays_set)
        visit_date = add_business_days(cp_start, milestones_config["visita"], holidays_set)
        
        gantt_data = {"cp_start": cp_start, "cp_end": cp_end, "visit": visit_date}
        
        complementary = [
            {"Etapa": "Início Consulta Pública", "Ref": "Conf + 5 dias", "Data": cp_start},
            {"Etapa": "Fim Consulta Pública", "Ref": f"Início CP + {milestones_config['cp_duration']} dias", "Data": cp_end},
            {"Etapa": "Visita Técnica", "Ref": f"Início CP + {milestones_config['visita']} dias", "Data": visit_date},
            {"Etapa": "Pareceres Setoriais", "Ref": f"Dia {milestones_config['setoriais']} Global", 
             "Data": calculate_deadline_rigorous(start_date, milestones_config['setoriais'], suspensions, holidays_set)}
        ]

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    return results, complementary, total_susp, gantt_data

# ==========================================
# 5. GERADOR DE PDF
# ==========================================
def create_pdf(project_name, typology, sector, regime, start_date, milestones, complementary, suspensions, total_susp, gantt_data):
    if FPDF is None: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(30, 58, 138)
            self.cell(0, 10, 'CCDR CENTRO - AUTORIDADE DE AIA', 0, 1, 'C')
            self.line(10, 20, 200, 20)
            self.ln(10)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Relatorio: {project_name}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Regime: {regime}", 0, 1)
    pdf.cell(0, 6, f"Data Inicio: {start_date.strftime('%d/%m/%Y')}", 0, 1)
    pdf.cell(0, 6, f"Suspensao Total: {total_susp} dias", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Cronograma Oficial", 0, 1, 'L')
    pdf.set_font("Arial", "", 10)
    for m in milestones:
        pdf.cell(90, 8, m["Etapa"], 1)
        pdf.cell(40, 8, m["Prazo Legal"], 1)
        pdf.cell(40, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 1)
        
    if complementary:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "Prazos Complementares", 0, 1)
        pdf.set_font("Arial", "", 10)
        for c in complementary:
            pdf.cell(90, 8, c["Etapa"], 1)
            pdf.cell(40, 8, c["Ref"], 1)
            pdf.cell(40, 8, c["Data"].strftime('%d/%m/%Y'), 1, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 6. INTERFACE
# ==========================================

st.title("🌿 Analista EIA - RJAIA Completo")

# SIDEBAR
with st.sidebar:
    st.header("Processo")
    proj_name = st.text_input("Nome", "Novo Projeto")
    start_date = st.date_input("Data Instrução (Dia 0)", date.today())
    
    st.divider()
    regime_option = st.radio("Regime:", (150, 90), format_func=lambda x: f"{x} Dias")
    
    with st.expander("Definições de Prazos", expanded=True):
        if regime_option == 150:
            d_reuniao, d_conf, d_ptf, d_aud, d_set, d_dia = 9, 30, 85, 100, 75, 150
        else:
            # DEFAULTS DO EXCEL
            d_reuniao, d_conf, d_ptf, d_aud, d_set, d_dia = 9, 20, 65, 70, 60, 90
            
        c_reuniao = st.number_input("Reunião", value=d_reuniao, key=f"r{regime_option}")
        c_conf = st.number_input("Conformidade", value=d_conf, key=f"c{regime_option}")
        c_ptf = st.number_input("Envio PTF", value=d_ptf, key=f"p{regime_option}")
        c_aud = st.number_input("Audiência", value=d_aud, key=f"a{regime_option}")
        c_set = st.number_input("Setoriais", value=d_set, key=f"s{regime_option}")
        c_dia = st.number_input("DIA", value=d_dia, disabled=True)
        
        milestones_config = {
            "reuniao": c_reuniao, "conformidade": c_conf, "ptf": c_ptf,
            "audiencia": c_aud, "setoriais": c_set, "dia": c_dia,
            "visita": 15, "cp_duration": 30
        }
        
    st.markdown("---")
    st.subheader("Suspensões")
    pea_date = st.date_input("Data do PEA (Opcional)", value=None, help="Preencher se houve pedido de elementos na conformidade")
    
    if 'suspensions' not in st.session_state: st.session_state.suspensions = []
    
    with st.form("add_susp"):
        s1, s2 = st.columns(2)
        d1 = s1.date_input("Início")
        d2 = s2.date_input("Fim")
        if st.form_submit_button("Adicionar"):
            st.session_state.suspensions.append({'start': d1, 'end': d2})
            st.rerun()
            
    for i, s in enumerate(st.session_state.suspensions):
        st.text(f"{s['start']} a {s['end']}")
        if st.button("X", key=f"del{i}"):
            del st.session_state.suspensions[i]
            st.rerun()

# CÁLCULO
milestones, complementary, total_susp, gantt_data = calculate_workflow(
    start_date, st.session_state.suspensions, milestones_config, pea_date
)

# RESULTADOS
c1, c2, c3, c4 = st.columns(4)
c1.metric("Regime", f"{regime_option} Dias")
c2.metric("Início", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensão", f"{total_susp} dias")
c4.metric("Previsão DIA", milestones[-1]["Data Prevista"].strftime("%d/%m/%Y"))

tab1, tab2 = st.tabs(["Tabela Prazos", "Gantt"])
with tab1:
    df = pd.DataFrame(milestones)
    df["Data Prevista"] = pd.to_datetime(df["Data Prevista"]).dt.strftime("%d-%m-%Y")
    st.dataframe(df, use_container_width=True)
    
    if complementary:
        st.write("Prazos Complementares:")
        df_c = pd.DataFrame(complementary)
        df_c["Data"] = pd.to_datetime(df_c["Data"]).dt.strftime("%d-%m-%Y")
        st.dataframe(df_c, use_container_width=True)

with tab2:
    # GANTT SIMPLIFICADO
    data_gantt = []
    last = start_date
    for m in milestones:
        end = m["Data Prevista"]
        start = last if last < end else end
        data_gantt.append(dict(Task=m["Etapa"], Start=start, Finish=end, Type="Fase"))
        last = end
    for s in st.session_state.suspensions:
        data_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Type="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(data_gantt), x_start="Start", x_end="Finish", y="Task", color="Type",
                      color_discrete_map={"Fase": "#2E86C1", "Suspensão": "#E74C3C"})
    st.plotly_chart(fig, use_container_width=True)

if st.button("Gerar PDF"):
    pdf_bytes = create_pdf(proj_name, "Tipologia", "Setor", f"{regime_option} Dias", start_date, milestones, complementary, st.session_state.suspensions, total_susp, gantt_data)
    if pdf_bytes:
        st.download_button("Download PDF", pdf_bytes, "relatorio.pdf", "application/pdf")
