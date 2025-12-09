import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
import plotly.figure_factory as ff

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão Prazos AIA - CCDR Centro",
    page_icon="🌿",
    layout="wide"
)

# --- FUNÇÕES UTILITÁRIAS ---

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex). Não valida feriados móveis para simplificar, 
    mas pode ser expandido com a biblioteca 'holidays'."""
    return check_date.weekday() < 5

def add_business_days(start_date, num_days):
    """Adiciona dias úteis a uma data."""
    current_date = start_date
    added_days = 0
    while added_days < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            added_days += 1
    return current_date

def calculate_timeline(start_date, deadline_days, suspensions):
    """
    Calcula a data final considerando suspensões.
    """
    # 1. Calcular data final teórica sem suspensões
    base_end_date = add_business_days(start_date, deadline_days)
    
    # 2. Calcular dias de suspensão (em dias úteis ou corridos dependendo da interpretação, 
    # aqui assumimos dias corridos que impactam o calendário, mas o prazo suspende-se).
    total_suspension_days = 0
    suspension_details = []

    for susp in suspensions:
        s_start = susp['start']
        s_end = susp['end']
        if s_end >= s_start:
            duration = (s_end - s_start).days + 1 # Inclui o próprio dia
            total_suspension_days += duration
            suspension_details.append((s_start, s_end, duration))
    
    # A nova data final é a base + dias de suspensão
    # Nota: No RJAIA, a contagem do prazo suspende-se. 
    # Logo, empurramos a data final pelo número de dias que o processo esteve parado.
    final_dia_date = base_end_date + timedelta(days=total_suspension_days)
    
    # Ajustar se cair em fim de semana
    while not is_business_day(final_dia_date):
        final_dia_date += timedelta(days=1)
        
    return base_end_date, final_dia_date, total_suspension_days

# --- INTERFACE PRINCIPAL ---

st.title("🌿 Calculadora de Prazos RJAIA (Simplex) - CCDR Centro")
st.markdown("""
Esta ferramenta auxilia na contagem de prazos para a emissão da **Declaração de Impacte Ambiental (DIA)**, 
considerando as competências da **CCDR Centro** e as alterações do **Decreto-Lei n.º 11/2023 (Simplex)**.
""")

st.warning("⚠️ **Nota:** Os prazos administrativos contam-se em **dias úteis** (CPA). As suspensões (ex: Pedido de Elementos Adicionais) param o relógio.")

# --- SIDEBAR: DADOS DO PROJETO ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Projeto Exemplo")
    start_date = st.date_input("Data de Submissão / Instrução", date.today())
    
    st.markdown("---")
    st.subheader("⏱️ Regime de Prazo (Simplex)")
    # Definição dos prazos conforme DL 11/2023
    prazo_option = st.radio(
        "Selecione o prazo legal aplicável:",
        (90, 150),
        format_func=lambda x: f"{x} dias úteis (AIA {'Simplificado/Outros' if x==90 else 'Geral/Complexo'})"
    )
    
    st.markdown("---")
    st.subheader("⏸️ Suspensões")
    st.caption("Adicione períodos de 'Pedido de Elementos' ou outras suspensões legais.")
    
    if 'suspensions' not in st.session_state:
        st.session_state.suspensions = []

    with st.form("add_suspension"):
        c1, c2 = st.columns(2)
        s_start = c1.date_input("Início Suspensão")
        s_end = c2.date_input("Fim Suspensão")
        submitted = st.form_submit_button("Adicionar Suspensão")
        
        if submitted:
            if s_end < s_start:
                st.error("A data de fim deve ser posterior ao início.")
            else:
                st.session_state.suspensions.append({'start': s_start, 'end': s_end})
                st.success("Suspensão adicionada!")

    # Listar suspensões
    if st.session_state.suspensions:
        st.write("Suspensões registadas:")
        rem_list = []
        for i, s in enumerate(st.session_state.suspensions):
            col_text, col_btn = st.columns([0.8, 0.2])
            col_text.text(f"{s['start']} a {s['end']}")
            if col_btn.button("❌", key=f"del_{i}"):
                rem_list.append(i)
        
        # Remover suspensões selecionadas
        for i in sorted(rem_list, reverse=True):
            del st.session_state.suspensions[i]
            st.rerun()

# --- CÁLCULOS ---

base_deadline, final_deadline, total_suspension = calculate_timeline(
    start_date, 
    prazo_option, 
    st.session_state.suspensions
)

today = date.today()
days_passed = np.busday_count(start_date, today) if today >= start_date else 0
days_remaining = np.busday_count(today, final_deadline) if today < final_deadline else 0

# --- DASHBOARD DE RESULTADOS ---

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Prazo Legal Base", f"{prazo_option} dias úteis")

with col2:
    st.metric("Total Suspensão", f"{total_suspension} dias", help="Dias de calendário que o processo esteve parado")

with col3:
    st.metric("Data Limite (DIA)", final_deadline.strftime("%d/%m/%Y"), delta_color="inverse")

with col4:
    if today > final_deadline:
        st.error(f"⚠️ Prazo Ultrapassado por {abs(days_remaining)} dias")
    else:
        st.metric("Dias Úteis Restantes", f"{days_remaining}", delta_color="normal")

# --- VISUALIZAÇÃO GANTT ---

st.subheader("📅 Cronograma Estimado")

# Preparar dados para o Gantt
# Simplificação das etapas baseada em percentagens típicas do RJAIA
# Nota: Estas são estimativas para visualização, pois os prazos internos variam.
p_conformance = int(prazo_option * 0.10) # 10% Conformidade
p_public = int(prazo_option * 0.30)      # 30% Consulta Pública
p_eval = int(prazo_option * 0.40)        # 40% Avaliação Técnica
p_decision = int(prazo_option * 0.20)    # 20% Decisão

# Datas das etapas (sem considerar suspensões específicas em cada etapa para simplificar visualização geral, 
# mas empurrando tudo pelo total de suspensão)
d1_start = start_date
d1_end = add_business_days(d1_start, p_conformance)

d2_start = d1_end
d2_end = add_business_days(d2_start, p_public)

d3_start = d2_end
d3_end = add_business_days(d3_start, p_eval)

d4_start = d3_end
d4_end = final_deadline # Ajusta o último para bater certo com o cálculo final

df_gantt = pd.DataFrame([
    dict(Task="1. Verificação Conformidade", Start=d1_start, Finish=d1_end, Resource="CCDR Centro"),
    dict(Task="2. Consulta Pública", Start=d2_start, Finish=d2_end, Resource="Público/CCDR"),
    dict(Task="3. Avaliação Técnica", Start=d3_start, Finish=d3_end, Resource="Comissão de Avaliação"),
    dict(Task="4. Emissão da DIA", Start=d4_start, Finish=d4_end, Resource="CCDR Centro (Decisão)"),
])

# Adicionar as suspensões ao gráfico visualmente
for i, susp in enumerate(st.session_state.suspensions):
    df_gantt = pd.concat([df_gantt, pd.DataFrame([
        dict(Task=f"Suspensão {i+1}", Start=susp['start'], Finish=susp['end'], Resource="Promotor (PeA)")
    ])], ignore_index=True)

fig = px.timeline(df_gantt, x_start="Start", x_end="Finish", y="Task", color="Resource", title=f"Timeline: {proj_name}")
fig.update_yaxes(autorange="reversed") # Tarefas de cima para baixo


# Adicionar linha de hoje
fig.add_vline(x=today, line_width=2, line_dash="dash", line_color="red", annotation_text="Hoje")

st.plotly_chart(fig, use_container_width=True)

# --- INFO LEGAL ---
st.markdown("""
---
### 🏛️ Enquadramento Legal
* **Regime**: RJAIA (Decreto-Lei n.º 151-B/2013) atualizado pelo **Simplex Ambiental (DL n.º 11/2023)**.
* **Autoridade de Avaliação**: CCDR Centro (nos casos delegados ou de competência própria).
* **Deferimento Tácito**: Nos termos do Simplex, a ausência de decisão nos prazos máximos pode levar ao deferimento tácito, salvo exceções legais.
""")
