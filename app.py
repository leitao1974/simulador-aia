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

# Tenta importar FPDF (para gerar PDF)
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 2. MOTOR DE FERIADOS (DINÂMICO & ETERNO)
# ==========================================

def get_easter_date(year):
    """Calcula o Domingo de Páscoa para qualquer ano (Algoritmo de Butcher)."""
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

def get_holidays_for_year(year):
    """Gera a lista de Feriados Nacionais para um ano (Sem Carnaval)."""
    holidays = set()
    
    # Feriados Fixos (Portugal)
    fixed_dates = [
        (1, 1),   # Ano Novo
        (4, 25),  # Dia da Liberdade
        (5, 1),   # Dia do Trabalhador
        (6, 10),  # Dia de Portugal
        (8, 15),  # Assunção de Nossa Senhora
        (10, 5),  # Implantação da República
        (11, 1),  # Dia de Todos os Santos
        (12, 1),  # Restauração da Independência
        (12, 8),  # Imaculada Conceição
        (12, 25)  # Natal
    ]
    for m, d in fixed_dates:
        holidays.add(date(year, m, d))
        
    # Feriados Móveis
    easter = get_easter_date(year)
    good_friday = easter - timedelta(days=2)     # Sexta-Feira Santa
    corpus_christi = easter + timedelta(days=60) # Corpo de Deus
    
    holidays.add(good_friday)
    holidays.add(corpus_christi)
    
    # NOTA: O Carnaval NÃO é feriado nacional obrigatório e foi removido 
    # para bater certo com a contagem do Excel da CCDR.
    
    return holidays

def get_holidays_range(start_year, end_year):
    """Gera feriados para um intervalo de anos."""
    all_holidays = set()
    for y in range(start_year, end_year + 1):
        all_holidays.update(get_holidays_for_year(y))
    return all_holidays

# ==========================================
# 3. DADOS LEGAIS E REFERÊNCIAS
# ==========================================

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
# 4. MOTOR DE CÁLCULO
# ==========================================

def is_business_day(check_date, holidays_set):
    if check_date.weekday() >= 5: return False # Sábado=5, Domingo=6
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

def calculate_deadline_rigorous(start_date, target_business_days, suspensions, holidays_set, return_log=False):
    current_date = start_date
    days_counted = 0
    log = []
    
    if return_log:
        log.append({"Data": current_date, "Dia Contado": 0, "Status": "Início"})

    while days_counted < target_business_days:
        current_date += timedelta(days=1)
        
        status = "Util"
        # 1. Prioridade: Suspensão
        if is_suspended(current_date, suspensions):
            status = "Suspenso"
        # 2. Fim de Semana
        elif current_date.weekday() >= 5:
            status = "Fim de Semana"
        # 3. Feriado
        elif current_date in holidays_set:
            status = "Feriado"
            
        if status == "Util":
            days_counted += 1
            
        if return_log:
            log.append({"Data": current_date, "Dia Contado": days_counted if status == "Util" else "-", "Status": status})
            
    final_date = current_date
    
    # Ajuste CPA: Se terminar em Sábado/Domingo/Feriado, salta para o próximo útil
    while final_date.weekday() >= 5 or final_date in holidays_set:
         final_date += timedelta(days=1)
    
    if return_log:
        return final_date, log
    return final_date

def calculate_workflow(start_date, suspensions, milestones_config, pea_date=None):
    # Gera feriados para o ano atual e seguintes (margem de segurança)
    holidays_set = get_holidays_range(start_date.year, start_date.year + 2)
    
    results = []
    log_final = []
    
    # Lista de Etapas
    steps = [
        ("Data Reunião", milestones_config["reuniao"]),
        ("Limite Conformidade", milestones_config["conformidade"]),
        ("Envio PTF à AAIA", milestones_config["ptf"]),
        ("Audiência de Interessados", milestones_config["audiencia"]),
        ("Emissão da DIA (Decisão Final)", milestones_config["dia"])
    ]
    
    conf_date_real = None 
    
    for nome, dias in steps:
        final_date = None
        
        # --- LÓGICA ESPECIAL: CONFORMIDADE COM PEA ---
        # Resolve o problema de ter de alterar manualmente "20" para "28".
        if nome == "Limite Conformidade" and pea_date and suspensions:
            # 1. Contar dias gastos até ao PEA
            days_spent = 0
            # Começa a contar do dia seguinte à instrução
            temp_date = start_date
            # Avança até ao dia ANTES do PEA
            check_date = start_date + timedelta(days=1)
            while check_date < pea_date:
                if is_business_day(check_date, holidays_set):
                    days_spent += 1
                check_date += timedelta(days=1)
            
            # 2. Dias que sobraram dos 20 (ou do valor configurado)
            remaining_days = dias - days_spent
            if remaining_days < 0: remaining_days = 0
            
            # 3. Aplicar os dias restantes APÓS o fim da suspensão
            last_susp_end = max([s['end'] for s in suspensions])
            final_date = calculate_deadline_rigorous(last_susp_end, remaining_days, [], holidays_set)
            
            conf_date_real = final_date
            
        else:
            # Cálculo Normal (Matemática Pura)
            if dias == milestones_config["dia"]: 
                final_date, log_data = calculate_deadline_rigorous(start_date, dias, suspensions, holidays_set, return_log=True)
                log_final = log_data
            else:
                final_date = calculate_deadline_rigorous(start_date, dias, suspensions, holidays_set)
            
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
        conf_date_theo = calculate_deadline_rigorous(start_date, milestones_config["conformidade"], [], holidays_set)
        
        # Início CP: 5 dias úteis APÓS Conformidade Real
        cp_start = add_business_days(conf_date_real, 5, holidays_set)
        
        # Fim CP
        cp_end = add_business_days(cp_start, cp_duration, holidays_set)
        
        # Pareceres Externos
        external_ops = add_business_days(cp_start, 23, holidays_set)
        
        # Relatório CP
        cp_report = add_business_days(cp_end, 7, holidays_set)
        
        # Visita
        visit_date = add_business_days(cp_start, visit_days, holidays_set)
        
        # Pareceres Setoriais (Conta desde o início, com suspensões)
        sectoral_date = calculate_deadline_rigorous(start_date, sectoral_days, suspensions, holidays_set)
        
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
    pdf.set_text_color(15, 23, 42)
    safe_title = f"Relatorio de Prazos: {project_name}"
    pdf.multi_cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), align='L')
    pdf.ln(5)

    # 1. Enquadramento
    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "1. Enquadramento e Legislacao", 0, 1, 'L', 1)
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Tipologia:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, typology.encode('latin-1','replace').decode('latin-1'))
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 6, "Setor:", 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, sector.encode('latin-1','replace').decode('latin-1'), 0, 1)
    pdf.ln(2)
    
    # 2. Resumo
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "2. Resumo", 0, 1, 'L', 1)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 6, "Regime:", 0, 0)
    pdf.cell(0, 6, f"{regime}", 0, 1)
    pdf.cell(50, 6, "Data de Instrucao:", 0, 0)
    pdf.cell(0, 6, start_date.strftime('%d/%m/%Y'), 0, 1)
    pdf.cell(50, 6, "Total Suspensao:", 0, 0)
    pdf.cell(0, 6, f"{total_susp} dias", 0, 1)
    pdf.ln(5)

    # 3. Cronograma Oficial
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "3. Cronograma Oficial (Fases Principais)", 0, 1, 'L', 1)
    pdf.ln(2)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
    pdf.cell(40, 8, "Prazo Legal", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Data Prevista", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", "", 9)
    pdf.ln()
    pdf.cell(90, 8, "Entrada / Instrucao", 1, 0, 'L')
    pdf.cell(40, 8, "Dia 0", 1, 0, 'C')
    pdf.cell(40, 8, start_date.strftime('%d/%m/%Y'), 1, 1, 'C')
    pdf.ln()
    
    for m in milestones:
        pdf.cell(90, 8, m["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
        pdf.cell(40, 8, str(m["Prazo Legal"]), 1, 0, 'C')
        pdf.cell(40, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.ln()

    # 4. Prazos Complementares
    if complementary:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "4. Prazos Complementares e Setoriais", 0, 1, 'L', 1)
        pdf.set_font("Arial", "", 9)
        
        pdf.set_font("Arial", "B", 9)
        pdf.cell(90, 8, "Etapa", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Referencia", 1, 0, 'C', 1)
        pdf.cell(40, 8, "Data Prevista", 1, 1, 'C', 1)
        pdf.ln()
        
        pdf.set_font("Arial", "", 9)
        for c in complementary:
            pdf.cell(90, 8, c["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Ref"].encode('latin-1','replace').decode('latin-1'), 1)
            pdf.cell(40, 8, c["Data"].strftime('%d/%m/%Y'), 1)
            pdf.ln()

    # 5. Suspensões
    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "Registo de Suspensoes", 0, 1, 'L', 1)
        pdf.set_font("Arial", "", 9)
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(0, 6, f"- {s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')} ({dur} dias)", 0, 1)
            pdf.ln()

    # 6. Cronograma Visual
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "5. Cronograma Visual (Gantt)", 0, 1)
    
    try:
        tasks = []
        start_dates = []
        end_dates = []
        colors = []
        
        last = start_date
        for m in milestones:
            end = m["Data Prevista"]
            start = last if last < end else end
            tasks.append(m["Etapa"])
            start_dates.append(start)
            end_dates.append(end)
            colors.append('skyblue')
            last = end
            
        for s in suspensions:
            tasks.append("Suspensão")
            start_dates.append(s['start'])
            end_dates.append(s['end'])
            colors.append('salmon')
            
        if gantt_data:
            tasks.append("Consulta Pública")
            start_dates.append(gantt_data['cp_start'])
            end_dates.append(gantt_data['cp_end'])
            colors.append('lightgreen')

        fig, ax = plt.subplots(figsize=(10, 6))
        for i, task in enumerate(tasks):
            start_num = mdates.date2num(start_dates[i])
            end_num = mdates.date2num(end_dates[i])
            duration = end_num - start_num
            if duration < 1: duration = 1
            ax.barh(task, duration, left=start_num, color=colors[i], align='center', edgecolor='grey')
            
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)
        plt.grid(axis='x', linestyle='--', alpha=0.5)
        plt.tight_layout()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
            plt.savefig(tmpfile.name, dpi=100)
            tmp_filename = tmpfile.name
            
        pdf.image(tmp_filename, x=10, y=30, w=190)
        plt.close(fig)
        os.unlink(tmp_filename)
        
    except Exception as e:
        pdf.ln(5)
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, f"Erro no grafico: {str(e)}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 6. INTERFACE DO UTILIZADOR
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
        st.caption("Valores ajustam-se automaticamente ao Regime (Simplex ou Geral).")
        
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
        
        st.markdown("**Suspensão Específica:**")
        pea_date = st.date_input("Data do PEA (se aplicável)", value=None, help="Preencha se houve Pedido de Elementos Adicionais na fase de Conformidade (trava o relógio).")
            
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
# 7. CÁLCULO E RESULTADOS
# ==========================================

milestones, complementary, total_susp, log_dia, gantt_data = calculate_workflow(
    start_date, 
    st.session_state.suspensions_universal, 
    milestones_config,
    pea_date=pea_date
)

final_dia_date = milestones[-1]["Data Prevista"]

# --- DASHBOARD ---
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Regime", f"{regime_option} Dias")
c2.metric("Início", start_date.strftime("%d/%m/%Y"))
c3.metric("Suspensões", f"{total_susp} dias")
c4.metric("Previsão DIA", final_dia_date.strftime("%d/%m/%Y"))

# --- ABAS ---
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
    # Gantt Plotly
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
