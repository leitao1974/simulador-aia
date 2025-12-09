import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import plotly.express as px
import io

# --- CONFIGURAÇÃO DA PÁGINA (TEM DE SER A PRIMEIRA LINHA) ---
st.set_page_config(
    page_title="Simulador de prazos do procedimento AIA",
    page_icon="🌿",
    layout="wide"
)

# --- TENTATIVA DE IMPORTAR FPDF (Modo Seguro) ---
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 1. BASE DE DADOS LEGISLATIVA (RJAIA COMPLETO) ---
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "ATIVIDADE PECUÁRIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTÃO EFLUENTES (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868",
        "FLORESTAS (DL 16/2009 - PGF)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34488356"
    },
    "2. Indústria Extrativa (Minas e Pedreiras)": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESÍDUOS DE EXTRAÇÃO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "SEGURANÇA MINAS (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937"
    },
    "3. Indústria Energética": {
        "SISTEMA ELÉTRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "REFINAÇÃO/COMBUSTÍVEIS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34589012"
    },
    "4. Produção e Transformação de Metais": {
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543"
    },
    "5. Indústria Mineral e Química": {
        "PREVENÇÃO ACIDENTES GRAVES (SEVESO - DL 150/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558967",
        "EMISSÕES (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)": {
        "ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "SERVIDÕES AERONÁUTICAS (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345",
        "RUÍDO GRANDES INFRAESTRUTURAS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
    },
    "7. Projetos de Engenharia Hidráulica (Barragens, Portos)": {
        "SEGURANÇA BARRAGENS (DL 21/2018)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2018-114833256",
        "DOMÍNIO HÍDRICO (Lei 54/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
    },
    "8. Tratamento de Resíduos e Águas Residuais": {
        "RESÍDUOS (RGGR - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
        "ÁGUAS RESIDUAIS URBANAS (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345",
        "ATERROS (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "9. Projetos Urbanos, Turísticos e Outros": {
        "RJUE (Urbanização - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "EMPREENDIMENTOS TURÍSTICOS (RJET)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567",
        "ACESSIBILIDADES (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456"
    }
}

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

# --- DICIONÁRIO DE TIPOLOGIAS (CCDR) ---
TIPOLOGIAS_INFO = {
    "Anexo I (Competência CCDR)": 
        "Projetos do Anexo I do RJAIA sob competência da CCDR (ex: Agropecuária intensiva, Indústria, Pedreiras).",
    "Anexo II (Limiares ou Zonas Sensíveis)": 
        "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localização em zona sensível.",
    "Anexo II (Resultante de Triagem/Caso a Caso)": 
        "Projetos sujeitos a AIA na sequência de decisão de sujeição (Triagem) positiva emitida pela CCDR.",
    "Alteração ou Ampliação (Competência CCDR)": 
        "Alterações a projetos existentes (Anexo I ou II) que, pela sua natureza ou escala, são da competência da CCDR.",
    "RECAPE (Pós-DIA CCDR)": 
        "Verificação da conformidade ambiental do projeto de execução (RECAPE) decorrente de uma DIA emitida pela CCDR."
}

# --- FUNÇÕES UTILITÁRIAS ---

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: 
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
def create_pdf(project_name, typology, sector, start_date, milestones, suspensions, total_susp):
    if FPDF is None:
        return None 

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
    pdf.ln(8)
    
    # 1. Enquadramento Legal e Setorial
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Enquadramento Legal e Setorial", 0, 1)
    
    # Bloco Informativo
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Tipologia RJAIA:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, typology.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Setor de Atividade:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, sector.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.ln(4)
    
    # Sub-bloco: Legislação Aplicável
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "Legislação de Referência:", 0, 1)
    
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 6, "Transversal:", 0, 1)
    pdf.set_font("Arial", "", 9)
    for name, link in COMMON_LAWS.items():
        pdf.cell(5, 5, "-")
        # Criar link clicável no PDF
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 5, name.encode('latin-1', 'replace').decode('latin-1'), link=link, ln=1)
        pdf.set_text_color(0, 0, 0)

    pdf.ln(2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 6, "Específica do Setor:", 0, 1)
    pdf.set_font("Arial", "", 9)
    
    sector_laws = SPECIFIC_LAWS.get(sector, {})
    for name, link in sector_laws.items():
        pdf.cell(5, 5, "-")
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 5, name.encode('latin-1', 'replace').decode('latin-1'), link=link, ln=1)
        pdf.set_text_color(0, 0, 0)
    
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

    # 3. Cronograma Oficial
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "3. Cronograma Oficial (Previsão)", 0, 1)
    
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(90, 10, "Etapa Processual", 1, 0, 'L', 1)
    pdf.cell(50, 10, "Prazo Legal Base", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Data Limite Prevista", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", "", 10)
    
    # Linha Entrada
    pdf.cell(90, 10, "Entrada do Processo / Instrução", 1, 0, 'L')
    pdf.cell(50, 10, "Dia 0", 1, 0, 'C')
    pdf.cell(50, 10, start_date.strftime("%d/%m/%Y"), 1, 1, 'C')

    for m in milestones:
        clean_etapa = m["Etapa"].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(90, 10, clean_etapa, 1, 0, 'L')
        pdf.cell(50, 10, str(m["Prazo Legal"]), 1, 0, 'C')
        d_str = m["Data Prevista"].strftime("%d/%m/%Y")
        if "Emissão da DIA" in m["Etapa"]:
            pdf.set_font("Arial", "B", 10)
        pdf.cell(50, 10, d_str, 1, 1, 'C')
        pdf.set_font("Arial", "", 10)
    
    # 4. Suspensões Detalhadas (se houver)
    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 10, "Anexo: Suspensões Registadas (PeA)", 0, 1)
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

    pdf.ln(10)
    pdf.set_font("Arial", "I", 8)
    note = "Nota: Documento gerado pela ferramenta 'Simulador de prazos do procedimento AIA'. Prazos calculados com base em dias úteis."
    pdf.multi_cell(0, 5, note.encode('latin-1', 'replace').decode('latin-1'))

    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE PRINCIPAL ---

st.title("🌿 Simulador de prazos do procedimento AIA")

# Verificação de segurança da biblioteca
if FPDF is None:
    st.error("⚠️ ERRO CRÍTICO: A biblioteca 'fpdf' não está instalada.")
    st.warning("Por favor, adicione `fpdf` ao ficheiro `requirements.txt`.")
    st.stop() 

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Processo")
    proj_name = st.text_input("Nome do Projeto", "Ampliação Zona Industrial Condeixa")
    start_date = st.date_input("Data de Instrução (Dia 0)", date(2025, 1, 30))
    
    st.markdown("---")
    st.subheader("⚖️ Enquadramento")
    
    # 1. Tipologia Jurídica
    selected_typology = st.selectbox(
        "Tipologia do Projeto (RJAIA)",
        list(TIPOLOGIAS_INFO.keys())
    )
    
    # 2. Setor de Atividade (Para Legislação)
    selected_sector = st.selectbox(
        "Setor de Atividade",
        list(SPECIFIC_LAWS.keys())
    )
    
    st.caption(f"ℹ️ {TIPOLOGIAS_INFO[selected_typology]}")

    st.markdown("---")
    st.subheader("⚙️ Simulação Temporal")
    use_simulated_date = st.checkbox("Simular 'Hoje' diferente?")
    today = st.date_input("Data de Referência", date.today()) if use_simulated_date else date.today()
    
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

short_typology = selected_typology.split("(")[0].strip() + " (" + selected_typology.split("(")[1]
c1.metric("Enquadramento", short_typology[:20] + "...", help=selected_typology)

c2.metric("Início Processo", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias", delta_color="inverse")

days_left = (final_dia_date - today).days
label_status = "Dias Restantes" if days_left >= 0 else "Dias de Atraso"
color_status = "normal" if days_left >= 0 else "inverse"

c4.metric("Data Limite (DIA)", final_dia_date.strftime("%d/%m/%Y"), 
          delta=f"{abs(days_left)} {label_status}", delta_color=color_status)

# --- TABS: TABELA, GRÁFICO, LEGISLAÇÃO ---
tab1, tab2, tab3 = st.tabs(["📋 Tabela Detalhada", "📅 Cronograma Visual", "📚 Legislação"])

with tab1:
    df_milestones = pd.DataFrame(milestones)
    entry_row = pd.DataFrame([{
        "Etapa": "Entrada do Processo / Instrução",
        "Prazo Legal": "Dia 0",
        "Data Prevista": start_date
    }])
    df_display = pd.concat([entry_row, df_milestones], ignore_index=True)
    df_display["Data Prevista"] = pd.to_datetime(df_display["Data Prevista"]).dt.strftime("%d-%m-%Y")
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

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

with tab3:
    st.subheader("Base Legislativa Aplicável")
    st.info("Clique nos links para abrir o diploma no Diário da República.")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("### 🏛️ Transversal (Todos os Setores)")
        for name, link in COMMON_LAWS.items():
            st.markdown(f"- [{name}]({link})")
            
    with col_b:
        st.markdown(f"### 🏭 Específico: {selected_sector}")
        sector_laws = SPECIFIC_LAWS.get(selected_sector, {})
        for name, link in sector_laws.items():
            st.markdown(f"- [{name}]({link})")

# --- GERAR PDF ---
st.markdown("---")
st.subheader("🖨️ Exportar Relatório de Análise")

if st.button("Gerar Relatório PDF"):
    pdf_bytes = create_pdf(proj_name, selected_typology, selected_sector, start_date, milestones, st.session_state.suspensions, total_susp)
    if pdf_bytes:
        st.download_button(
            label="📥 Descarregar PDF",
            data=pdf_bytes,
            file_name=f"Analise_AIA_{proj_name.replace(' ', '_')}.pdf",
            mime='application/pdf'
        )
    else:
        st.error("Erro ao gerar PDF.")
