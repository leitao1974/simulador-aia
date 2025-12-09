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

# --- DADOS DE FERIADOS (Extraídos do ficheiro enviado) ---
FERIADOS_STR = [
    '2023-10-05', '2023-11-01', '2023-12-01', '2023-12-08', '2023-12-25',
    '2024-01-01', '2024-03-29', '2024-03-31', '2024-04-25', '2024-05-01', '2024-05-30', '2024-06-10',
    '2024-08-15', '2024-10-05', '2024-11-01', '2024-12-25',
    '2025-01-01', '2025-04-18', '2025-04-25', '2025-05-01', '2025-06-10', '2025-06-19', '2025-08-15',
    '2025-12-01', '2025-12-08', '2025-12-25',
    '2026-01-01', '2026-04-03', '2026-04-05', '2026-04-25', '2026-05-01', '2026-06-04', '2026-06-10',
    '2026-08-15', '2026-10-05', '2026-11-01', '2026-12-01', '2026-12-08', '2026-12-25'
]
# Converter para objetos date para comparação rápida
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
    """Adiciona dias úteis a uma data, saltando fins de semana e feriados."""
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

def calculate_milestones(start_date, suspensions):
    """
    Calcula as datas exatas para cada marco do processo de 150 dias.
    """
    # 1. Calcular total de dias de suspensão (calendário)
    total_suspension_days = 0
    for susp in suspensions:
        s_start = susp['start']
        s_end = susp['end']
        if s_end >= s_start:
            duration = (s_end - s_start).days + 1
            total_suspension_days += duration
    
    # 2. Marcos definidos no Excel (Simplex 150 dias)
    # A lógica: Data Limite = Data Inicio + Dias Úteis + Dias Suspensão
    milestones_def = [
        {"dias": 9,   "fase": "Data Reunião"},
        {"dias": 30,  "fase": "Limite Conformidade"},
        {"dias": 85,  "fase": "Envio PTF à AAIA"},
        {"dias": 100, "fase": "Audiência de Interessados"},
        {"dias": 150, "fase": "Emissão da DIA (Decisão Final)"}
    ]
    
    results = []
    # O dia 0 é a data de início
    last_date = start_date
    
    for m in milestones_def:
        # Data teórica (apenas dias úteis)
        base_date = add_business_days(start_date, m["dias"])
        
        # Adicionar suspensão (empurra o calendário para a frente)
        final_date = base_date + timedelta(days=total_suspension_days)
        
        # Se cair num não-útil após a suspensão, ajusta para o próximo útil
        while not is_business_day(final_date):
            final_date += timedelta(days=1)
            
        results.append({
            "Etapa": m["fase"],
            "Dia do Processo": m["dias"],
            "Data Prevista": final_date
        })
        
    return results, total_suspension_days

# --- INTERFACE PRINCIPAL ---

st.title("🌿 Cronograma RJAIA - 150 Dias (Simplex)")
st.markdown(f"""
Configurado para **CCDR Centro** com base na análise do ficheiro Excel.
* **Feriados incluídos**: {len(FERIADOS)} datas (2023-2026).
* **Estrutura**: Procedimento Geral (150 dias úteis).
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Ampliação Zona Industrial Condeixa")
    start_date = st.date_input("Data de Instrução (Dia 0)", date.today())
    
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
            st.text(f"{i+1}. {s['start']} a {s['end']}")
        if st.button("Limpar Suspensões"):
            st.session_state.suspensions = []
            st.rerun()

# --- CÁLCULOS ---

milestones, total_susp = calculate_milestones(start_date, st.session_state.suspensions)
final_dia_date = milestones[-1]["Data Prevista"]
today = date.today()

# --- DASHBOARD ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Início do Processo", start_date.strftime("%d/%m/%Y"))
c2.metric("Dias de Suspensão", f"{total_susp} dias", delta_color="inverse")
c3.metric("Data Final (DIA)", final_dia_date.strftime("%d/%m/%Y"), 
          delta=f"{(final_dia_date - today).days} dias restantes" if final_dia_date >= today else "Prazo Expirado")

# --- TABELA DETALHADA ---
st.subheader("📋 Tabela de Prazos Calculados")
df_milestones = pd.DataFrame(milestones)
# Formatar a data para ler melhor
df_milestones["Data Prevista"] = df_milestones["Data Prevista"].apply(lambda x: x.strftime("%d-%m-%Y"))
st.table(df_milestones)

# --- GRÁFICO GANTT ---
st.subheader("📅 Linha Temporal")

# Criar dados para o Gantt (Intervalos entre marcos)
gantt_data = []
prev_date = start_date

for m in milestones:
    curr_date = pd.to_datetime(m["Data Prevista"], dayfirst=True).date() # reconverter string se necessario ou usar o obj original
    # Usar o objeto original é melhor, mas aqui vou reconstruir rapidinho para o plot
    # A estrutura do loop acima já tinha a data correta. Vamos refazer o loop para o Gantt limpo.
    pass

# Refazendo lista para Gantt com objetos de data
gantt_list = []
last_date = start_date
for m in milestones:
    # A data que está no dataframe já é string formatada, vamos pegar do calculo original
    # Melhor: usar o dataframe mas converter de volta ou guardar lista original
    pass

# Construção direta do Gantt
df_gantt = []
last_end = start_date

# Adicionar cada etapa como um bloco sequencial para visualização
for item in milestones:
    # Converter string de volta para date se necessário, ou pegar do loop anterior.
    # Vou usar o dataframe que está na tela
    end_date_dt = pd.to_datetime(item["Data Prevista"], format="%d-%m-%Y").date()
    
    df_gantt.append(dict(
        Task=item["Etapa"], 
        Start=last_end, 
        Finish=end_date_dt, 
        Resource="Fase Processual"
    ))
    last_end = end_date_dt # O fim de uma é o inicio visual da proxima

# Adicionar suspensões visualmente
for i, susp in enumerate(st.session_state.suspensions):
    df_gantt.append(dict(
        Task=f"Suspensão {i+1}", 
        Start=susp['start'], 
        Finish=susp['end'], 
        Resource="Suspensão"
    ))

df_g = pd.DataFrame(df_gantt)

fig = px.timeline(df_g, x_start="Start", x_end="Finish", y="Task", color="Resource", 
                  color_discrete_map={"Fase Processual": "#2E86C1", "Suspensão": "#E74C3C"})
fig.update_yaxes(autorange="reversed")

# Linha de Hoje
today_ts = pd.Timestamp(today).timestamp() * 1000
fig.add_vline(x=today_ts, line_width=2, line_dash="dash", line_color="green", annotation_text="Hoje")

st.plotly_chart(fig, use_container_width=True)
