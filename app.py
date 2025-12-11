import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import tempfile
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Prazos AIA",
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
    '2026-01-01', '2026-04-03', '2026-04-05', '2026-04-25', '2026-05-01', '2026-06-04', '2026-06-10', '2026-08-15', '2026-10-05', '2026-11-01', '2026-12-01', '2026-12-08', '2026-12-25'
]
FERIADOS = {pd.to_datetime(d).date() for d in FERIADOS_STR}

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "Simplex Ambiental (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212459",
    "CPA (Prazos)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558838"
}

TIPOLOGIAS_INFO = {
    "Anexo I": "Projetos do Anexo I do RJAIA.",
    "Anexo II": "Projetos do Anexo II (Limiares ou Zonas Sensíveis).",
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
# 2. FUNÇÕES DE CÁLCULO RIGOROSO (MOTOR)
# ==========================================

def is_business_day(check_date):
    """Verifica se é dia útil (seg-sex) E não é feriado."""
    if check_date.weekday() >= 5: return False
    if check_date in FERIADOS: return False
    return True

def add_business_days(start_date, num_days):
    """Adiciona dias úteis simples (sem considerar suspensões de prazo administrativo, apenas calendário)."""
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
    """Algoritmo principal: Conta dias úteis progressivamente, saltando suspensões."""
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
    Calcula todos os marcos do processo com base no regime escolhido e configurações avançadas.
    """
    results = []
    log_final = []
    
    # Lista ordenada de etapas principais
    steps = [
        ("Data Reunião", milestones_config["reuniao"]),
        ("Limite Conformidade", milestones_config["conformidade"]),
        ("Envio PTF à AAIA", milestones_config["ptf"]),
        ("Audiência de Interessados", milestones_config["audiencia"]),
        ("Emissão da DIA (Decisão Final)", milestones_config["dia"])
    ]
    
    conf_date = None # Para guardar a data de conformidade
    
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

    # 2. Marcos Complementares (Baseados na Imagem e Configuração)
    complementary = []
    if conf_date:
        # A. Consulta Pública (Relativo à Conformidade)
        # Gap Conformidade -> Início CP (dias úteis)
        cp_start = add_business_days(conf_date, milestones_config["gap_cp"])
        # Fim CP (dias úteis consecutivos)
        cp_end = add_business_days(cp_start, milestones_config["duracao_cp"])
        # Relatório CP
        cp_report = add_business_days(cp_end, milestones_config["rel_cp"])
        # Pareceres Externos (contado do início da CP)
        external_ops = add_business_days(cp_start, milestones_config["par_externos"])
        
        # Visita: 3ª semana da CP (aprox. 10 dias úteis após início)
        visit_start = add_business_days(cp_start, 10)
        
        # B. Marcos Globais (Relativos ao início do processo, sujeitos a suspensão)
        # Pareceres Setoriais (Global)
        sectorial_date = calculate_deadline_rigorous(start_date, milestones_config["setoriais"], suspensions)
        # Reunião da CA (Global)
        meeting_ca_date = calculate_deadline_rigorous(start_date, milestones_config["reuniao_ca"], suspensions)

        complementary = [
            {"Etapa": "Início Consulta Pública", "Ref": f"Conf + {milestones_config['gap_cp']} dias", "Data": cp_start},
            {"Etapa": "Visita Técnica (Prevista)", "Ref": "3ª Semana da CP", "Data": visit_start},
            {"Etapa": "Prazo Pareceres Externos", "Ref": f"Início CP + {milestones_config['par_externos']} dias", "Data": external_ops},
            {"Etapa": "Fim Consulta Pública", "Ref": f"Duração {milestones_config['duracao_cp']} dias", "Data": cp_end},
            {"Etapa": "Relatório da CP", "Ref": f"Fim CP + {milestones_config['rel_cp']} dias", "Data": cp_report},
            {"Etapa": "Limite Pareceres Setoriais", "Ref": f"Dia {milestones_config['setoriais']} Global", "Data": sectorial_date},
            {"Etapa": "Reunião da CA", "Ref": f"Dia {milestones_config['reuniao_ca']} Global", "Data": meeting_ca_date},
        ]

    total_susp = sum([(s['end'] - s['start']).days + 1 for s in suspensions])
    
    return results, complementary, total_susp, log_final

# ==========================================
# 3. GERADOR DE PDF (COM COMPARAÇÃO)
# ==========================================
def create_pdf(project_name, typology, sector, regime, start_date, milestones, milestones_theory, complementary, complementary_theory, suspensions, total_susp):
    if FPDF is None: return None
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.cell(0, 10, 'Autoridade de AIA', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", "B", 14)
    status_txt = " (COM SUSPENSAO)" if suspensions else ""
    safe_title = f"Relatorio de Prazos{status_txt}: {project_name}"
    pdf.multi_cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), align='C')
    pdf.ln(5)

    # 1. Enquadramento
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "1. Enquadramento Legal e Setorial", 0, 1)
    pdf.set_font("Arial", "B", 10); pdf.cell(40, 6, "Tipologia:", 0, 0)
    pdf.set_font("Arial", "", 10); pdf.multi_cell(0, 6, typology.encode('latin-1','replace').decode('latin-1'))
    pdf.set_font("Arial", "B", 10); pdf.cell(40, 6, "Setor:", 0, 0)
    pdf.set_font("Arial", "", 10); pdf.cell(0, 6, sector.encode('latin-1','replace').decode('latin-1'), 0, 1)
    pdf.ln(2)
    
    # 2. Resumo
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "2. Resumo do Processo", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 6, "Regime Aplicavel:", 0, 0); pdf.cell(0, 6, f"{regime}", 0, 1)
    pdf.cell(50, 6, "Data de Instrucao:", 0, 0); pdf.cell(0, 6, start_date.strftime('%d/%m/%Y'), 0, 1)
    
    if suspensions:
        pdf.set_text_color(220, 50, 50) # Vermelho
        pdf.cell(50, 6, "Total Suspensao:", 0, 0); pdf.cell(0, 6, f"{total_susp} dias de calendario", 0, 1)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.cell(50, 6, "Total Suspensao:", 0, 0); pdf.cell(0, 6, "0 dias (Fluxo Normal)", 0, 1)
    pdf.ln(5)

    # 3. Legislação
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, "3. Legislacao Base", 0, 1)
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "Legislacao aplicavel conforme definido no RJAIA e Simplex Ambiental.", 0, 1)
    pdf.ln(5)

    # 4. CRONOGRAMA
    pdf.set_font("Arial", "B", 11)
    if suspensions:
        pdf.cell(0, 8, "4. Cronograma Comparativo (Normal vs Com Suspensao)", 0, 1)
    else:
        pdf.cell(0, 8, "4. Cronograma Oficial", 0, 1)
    
    # Configuração de Colunas
    has_susp = len(suspensions) > 0
    if has_susp:
        w_etapa, w_prazo, w_data1, w_data2 = 70, 30, 45, 45
    else:
        w_etapa, w_prazo, w_data2 = 90, 50, 50
    
    # 4.1 Fases Principais
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, "4.1. Fases Principais", 0, 1)
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(220, 220, 220)
    
    pdf.cell(w_etapa, 8, "Etapa", 1, 0, 'L', 1)
    pdf.cell(w_prazo, 8, "Prazo Legal", 1, 0, 'C', 1)
    if has_susp:
        pdf.cell(w_data1, 8, "Data Teorica", 1, 0, 'C', 1)
        pdf.set_fill_color(255, 200, 200)
        pdf.cell(w_data2, 8, "Data Efetiva", 1, 1, 'C', 1)
    else:
        pdf.cell(w_data2, 8, "Data Prevista", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", "", 8)
    
    # Linha 0
    pdf.cell(w_etapa, 8, "Entrada / Instrucao", 1, 0, 'L')
    pdf.cell(w_prazo, 8, "Dia 0", 1, 0, 'C')
    if has_susp:
        pdf.cell(w_data1, 8, start_date.strftime('%d/%m/%Y'), 1, 0, 'C')
    pdf.cell(w_data2, 8, start_date.strftime('%d/%m/%Y'), 1, 1, 'C')
    
    for i, m in enumerate(milestones):
        pdf.cell(w_etapa, 8, m["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
        pdf.cell(w_prazo, 8, str(m["Prazo Legal"]), 1, 0, 'C')
        
        if has_susp:
            date_theo = milestones_theory[i]["Data Prevista"]
            pdf.cell(w_data1, 8, date_theo.strftime('%d/%m/%Y'), 1, 0, 'C')
            if m["Data Prevista"] != date_theo:
                pdf.set_font("Arial", "B", 8); pdf.set_text_color(200, 0, 0)
            pdf.cell(w_data2, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 1, 'C')
            pdf.set_font("Arial", "", 8); pdf.set_text_color(0, 0, 0)
        else:
             pdf.cell(w_data2, 8, m["Data Prevista"].strftime('%d/%m/%Y'), 1, 1, 'C')

    # Tabelas Complementares
    if complementary:
        lista_cp = [c for c in complementary if "Consulta" in c['Etapa'] or "Relatório" in c['Etapa'] or "Pareceres Externos" in c['Etapa']]
        lista_tec = [c for c in complementary if "Visita" in c['Etapa'] or "Setoriais" in c['Etapa'] or "CA" in c['Etapa']]
        
        lista_cp_theo = [c for c in complementary_theory if "Consulta" in c['Etapa'] or "Relatório" in c['Etapa'] or "Pareceres Externos" in c['Etapa']] if complementary_theory else []
        lista_tec_theo = [c for c in complementary_theory if "Visita" in c['Etapa'] or "Setoriais" in c['Etapa'] or "CA" in c['Etapa']] if complementary_theory else []

        def print_comp_table(title, items_real, items_theo, color_header):
            pdf.ln(3)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 8, title, 0, 1)
            pdf.set_font("Arial", "B", 8)
            pdf.set_fill_color(*color_header)
            
            pdf.cell(w_etapa, 8, "Acao", 1, 0, 'L', 1)
            pdf.cell(w_prazo, 8, "Ref.", 1, 0, 'C', 1)
            if has_susp:
                pdf.cell(w_data1, 8, "Teorica", 1, 0, 'C', 1)
                pdf.cell(w_data2, 8, "Efetiva", 1, 1, 'C', 1)
            else:
                pdf.cell(w_data2, 8, "Data", 1, 1, 'C', 1)
            
            pdf.set_font("Arial", "", 8)
            for idx, c in enumerate(items_real):
                pdf.cell(w_etapa, 8, c["Etapa"].encode('latin-1','replace').decode('latin-1'), 1)
                pdf.cell(w_prazo, 8, c["Ref"].encode('latin-1','replace').decode('latin-1'), 1, 0, 'C')
                
                if has_susp and items_theo:
                    dt_theo = items_theo[idx]["Data"]
                    pdf.cell(w_data1, 8, dt_theo.strftime('%d/%m/%Y'), 1, 0, 'C')
                    if c["Data"] != dt_theo:
                        pdf.set_font("Arial", "B", 8); pdf.set_text_color(200, 0, 0)
                    pdf.cell(w_data2, 8, c["Data"].strftime('%d/%m/%Y'), 1, 1, 'C')
                    pdf.set_font("Arial", "", 8); pdf.set_text_color(0, 0, 0)
                else:
                    pdf.cell(w_data2, 8, c["Data"].strftime('%d/%m/%Y'), 1, 1, 'C')

        if lista_cp: print_comp_table("4.2. Consulta Publica", lista_cp, lista_cp_theo, (240, 248, 255))
        if lista_tec: print_comp_table("4.3. Agendamento Tecnico", lista_tec, lista_tec_theo, (245, 245, 220))

    # Suspensões
    if suspensions:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, "Registo de Suspensoes Aplicadas", 0, 1)
        pdf.set_font("Arial", "", 9)
        for s in suspensions:
            dur = (s['end'] - s['start']).days + 1
            pdf.cell(0, 6, f"- {s['start'].strftime('%d/%m/%Y')} a {s['end'].strftime('%d/%m/%Y')} ({dur} dias)", 0, 1)

    # 5. GANTT
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    title_gantt = "5. Cronograma Visual (Cenario Efetivo)" if has_susp else "5. Cronograma Visual"
    pdf.cell(0, 10, title_gantt, 0, 1)
    
    try:
        tasks, start_dates, end_dates, colors = [], [], [], []
        
        last = start_date
        for m in milestones:
            end = m["Data Prevista"]
            start = last if last < end else end
            tasks.append(m["Etapa"])
            start_dates.append(start)
            end_dates.append(end)
            colors.append('#87CEEB') # Azul
            last = end
            
        if complementary:
            for c in complementary:
                tasks.append(c["Etapa"])
                end = c["Data"]
                if "Consulta" in c["Etapa"]:
                    col = '#90EE90' 
                    if "Fim" in c["Etapa"]: start = end - timedelta(days=30)
                    else: start = end - timedelta(days=1)
                elif "Visita" in c["Etapa"]:
                    col = '#FFD700' # Dourado
                    start = end - timedelta(days=1)
                elif "Setoriais" in c["Etapa"]:
                    col = '#D3D3D3' # Cinza
                    start = end - timedelta(days=5) 
                elif "CA" in c["Etapa"]:
                    col = '#FFA07A' # Salmão
                    start = end - timedelta(days=1)
                else:
                    col = '#D3D3D3'
                    start = end - timedelta(days=1)
                start_dates.append(start)
                end_dates.append(end)
                colors.append(col)

        for s in suspensions:
            tasks.append("Suspensão")
            start_dates.append(s['start'])
            end_dates.append(s['end'])
            colors.append('#F08080') 

        fig, ax = plt.subplots(figsize=(10, 8))
        for i, task in enumerate(tasks):
            start_num = mdates.date2num(start_dates[i])
            end_num = mdates.date2num(end_dates[i])
            duration = end_num - start_num
            if duration < 1: duration = 1
            ax.barh(task, duration, left=start_num, color=colors[i], align='center', edgecolor='grey', alpha=0.8)
            
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
# 4. INTERFACE GRÁFICA
# ==========================================

st.title("🌿 Simulador de Prazos AIA - Universal")
st.markdown("Ferramenta de cálculo de prazos de acordo com o **RJAIA** e **Simplex Ambiental**.")

if FPDF is None:
    st.error("⚠️ Aviso: A biblioteca 'fpdf' não está instalada. A geração de PDF não funcionará.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Dados do Novo Processo")
    proj_name = st.text_input("Nome do Projeto", "Novo Projeto AIA")
    start_date = st.date_input("Data de Instrução (Dia 0)", date.today())
    
    st.markdown("---")
    st.subheader("⚖️ Enquadramento")
    
    selected_typology = st.selectbox("Tipologia do Projeto", list(TIPOLOGIAS_INFO.keys()))
    selected_sector = st.selectbox("Setor de Atividade", list(SPECIFIC_LAWS.keys()))
    
    regime_option = st.radio(
        "Selecione o Prazo Global:",
        (150, 90),
        format_func=lambda x: f"{x} Dias Úteis (AIA {'Geral' if x==150 else 'Simplificado/Outros'})"
    )
    
    # --- DEFINIÇÕES AVANÇADAS ATUALIZADAS ---
    with st.expander("⚙️ Definições Avançadas de Prazos", expanded=False):
        st.caption("Ajuste os prazos legais e etapas complementares.")
        
        st.markdown("**(1) Fases Principais**")
        if regime_option == 150:
            d_reuniao = st.number_input("Reunião Inicial (Prévia)", value=9)
            d_conf = st.number_input("Conformidade", value=30)
            d_ptf = st.number_input("Envio PTF", value=85, help="Legalmente 85")
            d_aud = st.number_input("Audiência de Interessados", value=100)
            d_dia = st.number_input("Decisão Final (DIA)", value=150, disabled=True)
            
            # --- PARÂMETROS ADICIONAIS ---
            st.markdown("**(2) Detalhe Operacional (C.Pública e Técnica)**")
            gap_conf_cp = st.number_input("Gap Conformidade -> Início CP", value=5) 
            duracao_cp = st.number_input("Duração Consulta Pública", value=30)
            prazo_par_ext = st.number_input("Pareceres Externos (dias após Início CP)", value=23)
            prazo_rel_cp = st.number_input("Relatório CP (dias após Fim CP)", value=7)
            
            st.markdown("**(3) Agendamento Global**")
            prazo_setoriais = st.number_input("Limite Pareceres Setoriais (Global)", value=75)
            prazo_reuniao_ca = st.number_input("Reunião da CA (Global)", value=80)
            
        else: # 90 dias
            d_reuniao = st.number_input("Reunião Inicial", value=5)
            d_conf = st.number_input("Conformidade", value=20)
            d_ptf = st.number_input("Envio PTF", value=50)
            d_aud = st.number_input("Audiência", value=60)
            d_dia = st.number_input("Decisão Final (DIA)", value=90, disabled=True)
            # Valores padrão Simplificado
            gap_conf_cp, duracao_cp, prazo_par_ext, prazo_rel_cp, prazo_setoriais, prazo_reuniao_ca = 5, 20, 15, 5, 40, 45

        milestones_config = {
            "reuniao": d_reuniao,
            "conformidade": d_conf,
            "ptf": d_ptf,
            "audiencia": d_aud,
            "dia": d_dia,
            "gap_cp": gap_conf_cp,
            "duracao_cp": duracao_cp,
            "par_externos": prazo_par_ext,
            "rel_cp": prazo_rel_cp,
            "setoriais": prazo_setoriais,
            "reuniao_ca": prazo_reuniao_ca
        }

    st.markdown("---")
    st.subheader("⏸️ Gestão de Suspensões")
    
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
        st.info("Prazos complementares indisponíveis (aguarda conformidade).")

with tab3:
    data_gantt = []
    last = start_date
    
    # Fases Principais
    for m in milestones:
        end = m["Data Prevista"]
        start = last if last < end else end
        data_gantt.append(dict(Task=m["Etapa"], Start=start, Finish=end, Resource="Fase Principal"))
        last = end
    
    # Complementares (Visualização interativa simplificada)
    for c in complementary:
        if "Consulta" in c["Etapa"]:
            end_c = c["Data"]
            start_c = add_business_days(end_c, -30) if "Fim" in c["Etapa"] else c["Data"]
            data_gantt.append(dict(Task=c["Etapa"], Start=start_c, Finish=end_c, Resource="Consulta Pública"))
        elif "Visita" in c["Etapa"]:
            data_gantt.append(dict(Task=c["Etapa"], Start=c["Data"], Finish=c["Data"], Resource="Visita Técnica"))
        else:
            data_gantt.append(dict(Task=c["Etapa"], Start=c["Data"], Finish=c["Data"], Resource="Outros"))
            
    # Suspensões
    for s in st.session_state.suspensions_universal:
        data_gantt.append(dict(Task="Suspensão", Start=s['start'], Finish=s['end'], Resource="Suspensão"))
        
    fig = px.timeline(pd.DataFrame(data_gantt), x_start="Start", x_end="Finish", y="Task", color="Resource",
                      color_discrete_map={
                          "Fase Principal": "#2E86C1", 
                          "Suspensão": "#E74C3C", 
                          "Consulta Pública": "#27AE60", 
                          "Visita Técnica": "#F1C40F",
                          "Outros": "#95A5A6"
                      })
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Legislação de Referência")
    st.write("**Transversal:**")
    for k, v in COMMON_LAWS.items():
        st.markdown(f"- [{k}]({v})")
    
    st.write(f"**Específica ({selected_sector}):**")
    for k, v in SPECIFIC_LAWS.get(selected_sector, {}).items():
        st.markdown(f"- [{k}]({v})")

st.markdown("---")
if st.button("Gerar Relatório PDF"):
    # 1. Calcular o Cenário Teórico (Sem suspensões) para comparação
    milestones_theory, complementary_theory, _, _ = calculate_workflow(
        start_date, 
        [], # Lista vazia
        regime_option, 
        milestones_config
    )

    pdf_bytes = create_pdf(
        proj_name, 
        selected_typology,
        selected_sector,
        f"Regime {regime_option} Dias", 
        start_date, 
        milestones,         # Real
        milestones_theory,  # Teórico
        complementary,      # Real
        complementary_theory, # Teórico
        st.session_state.suspensions_universal, 
        total_susp
    )
    if pdf_bytes:
        st.download_button("Descarregar PDF", pdf_bytes, "relatorio_aia_comparativo.pdf", "application/pdf")

