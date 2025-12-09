import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px

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
    """
    Calcula as datas exatas. Permite sobrepor a data da reunião.
    """
    # 1. Calcular total de dias de suspensão
    total_suspension_days = 0
    for susp in suspensions:
        s_start = susp['start']
        s_end = susp['end']
        if s_end >= s_start:
            duration = (s_end - s_start).days + 1
            total_suspension_days += duration
    
    # 2. Definição dos Marcos Legais
    milestones_def = [
        {"dias": 9,   "fase": "Data Reunião", "manual_override": True}, # Flag para permitir override
        {"dias": 30,  "fase": "Limite Conformidade", "manual_override": False},
        {"dias": 85,  "fase": "Envio PTF à AAIA", "manual_override": False},
        {"dias": 100, "fase": "Audiência de Interessados", "manual_override": False},
        {"dias": 150, "fase": "Emissão da DIA (Decisão Final)", "manual_override": False}
    ]
    
    results = []
    
    for m in milestones_def:
        # Se for a Reunião e tivermos uma data manual, usamos essa data fixa
        if m["manual_override"] and manual_meeting_date:
            final_date = manual_meeting_date
            # Recalcular quantos dias passaram desde o início (apenas informativo)
            days_diff = (final_date - start_date).days
            display_days = f"{days_diff} (Manual)"
        else:
            # Cálculo padrão: Inicio + Dias Uteis + Suspensão
            base_date = add_business_days(start_date, m["dias"])
            final_date = base_date + timedelta(days=total_suspension_days)
            
            # Ajuste de fim de semana/feriado
            while not is_business_day(final_date):
                final_date += timedelta(days=1)
            
            display_days = m["dias"]
            
        results.append({
            "Etapa": m["fase"],
            "Dia Legal": display_days,
            "Data Prevista": final_date
        })
        
    return results, total_suspension_days

# --- INTERFACE PRINCIPAL ---

st.title("🌿 Cronograma RJAIA - 150 Dias (Simplex)")
st.markdown("""
**Configuração:** Procedimento Geral (150 dias úteis).
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Ampliação Zona Industrial Condeixa")
    start_date = st.date_input("Data de Instrução (Dia 0)", date.today())
    
    st.markdown("---")
    st.subheader("🗓️ Agendamentos")
    # Cálculo da data teórica para sugestão (Dia 9)
    theoretical_meeting = add_business_days(start_date, 9)
    meeting_date_input = st.date_input(
        "Data Real da Reunião", 
        value=theoretical_meeting,
        help="A legislação aponta o dia 9, mas defina aqui a data real do agendamento."
    )
    
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
                st.success("Adicionado!")
                st.rerun()

    if st.session_state.suspensions:
        st.write("Períodos de paragem:")
        for i, s in enumerate(st.session_state.suspensions):
            col_txt, col_del = st.columns([0.8, 0.2])
            col_txt.text(f"{s['start']} a {s['end']}")
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
today = date.today()

# --- DASHBOARD ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Início do Processo", start_date.strftime("%d/%m/%Y"))
c2.metric("Total Suspensão", f"{total_susp} dias", delta_color="inverse")

days_left = (final_dia_date - today).days
label_status = "Dias Restantes" if days_left >= 0 else "Dias de Atraso"
color_status = "normal" if days_left >= 0 else "inverse"

c3.metric("Data Limite (DIA)", final_dia_date.strftime("%d/%m/%Y"), 
          delta=f"{abs(days_left)} {label_status}", delta_color=color_status)

# --- TABELA DETALHADA ---
st.subheader("📋 Prazos Calculados")
df_milestones = pd.DataFrame(milestones)
df_milestones["Data Prevista"] = df_milestones["Data Prevista"].apply(lambda x: x.strftime("%d-%m-%Y"))
st.dataframe(df_milestones, use_container_width=True, hide_index=True)

# --- GRÁFICO GANTT ---
st.subheader("📅 Cronograma Visual")

# Construção do Gantt
df_gantt = []
last_end = start_date

# Adicionar fases processuais
for item in milestones:
    end_date_dt = item["Data Prevista"] # Já é objeto date
    
    # Se a data de inicio for depois da data de fim (caso de reunião manual atrasada em relação ao inicio), ajustamos visualmente
    start_viz = last_end
    if start_viz > end_date_dt:
        start_viz = end_date_dt - timedelta(days=1)

    df_gantt.append(dict(
        Task=item["Etapa"], 
        Start=start_viz, 
        Finish=end_date_dt, 
        Resource="Fase Processual"
    ))
    last_end = end_date_dt

# Adicionar suspensões
for i, susp in enumerate(st.session_state.suspensions):
    df_gantt.append(dict(
        Task=f"Suspensão {i+1} (PeA)", 
        Start=susp['start'], 
        Finish=susp['end'], 
        Resource="Suspensão"
    ))

df_g = pd.DataFrame(df_gantt)

fig = px.timeline(df_g, x_start="Start", x_end="Finish", y="Task", color="Resource", 
                  color_discrete_map={"Fase Processual": "#2E86C1", "Suspensão": "#E74C3C"},
                  title=f"Cronograma: {proj_name}")
fig.update_yaxes(autorange="reversed")

# Linha de Hoje (Correção Timestamp)
today_ts = pd.Timestamp(today).timestamp() * 1000
fig.add_vline(x=today_ts, line_width=2, line_dash="dash", line_color="green", annotation_text="Hoje")

st.plotly_chart(fig, use_container_width=True)
