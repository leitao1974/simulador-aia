import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Calculadora Data Limite DIA", page_icon="🎯", layout="wide")

st.title("🎯 Calculadora da Data Limite da DIA")
st.markdown("""
Esta ferramenta foca-se em determinar com precisão a **Data Limite Legal** para a emissão da Declaração de Impacte Ambiental,
contabilizando o efeito das suspensões (tempo do promotor) sobre o prazo administrativo (dias úteis).
""")

# --- FUNÇÕES DE DATAS ---
def obter_feriados_pt(anos):
    return holidays.PT(years=anos)

def eh_dia_util(data_check, lista_feriados):
    if data_check.weekday() >= 5: return False
    if data_check in lista_feriados: return False
    return True

def proximo_dia_util(data_ref, lista_feriados):
    data_calc = data_ref
    while not eh_dia_util(data_calc, lista_feriados):
        data_calc += timedelta(days=1)
    return data_calc

def somar_dias_uteis(data_inicio, dias_a_adicionar, lista_feriados):
    data_atual = data_inicio
    dias_adicionados = 0
    while dias_adicionados < dias_a_adicionar:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, lista_feriados):
            dias_adicionados += 1
    return data_atual

# --- DADOS RJAIA ---
REGRAS = {
    "Anexo I (100 dias úteis)": {"prazo": 100, "conf": 10, "cp": 30},
    "Anexo II (75 dias úteis)": {"prazo": 75, "conf": 10, "cp": 30},
    "AIncA (60 dias úteis)":    {"prazo": 60, "conf": 10, "cp": 20}
}

# --- GERADOR DE RELATÓRIO WORD ---
def gerar_relatorio_word(cronograma, nome_projeto, regras, dias_suspensao, data_limite_final):
    doc = Document()
    
    style = doc.styles['Title']
    style.font.size = Pt(16)
    doc.add_heading(f'Cálculo da Data Limite da DIA: {nome_projeto}', 0)
    
    doc.add_paragraph(f"Data de Emissão do Relatório: {datetime.date.today().strftime('%d/%m/%Y')}")
    
    # Destaque da Data Limite
    p = doc.add_paragraph()
    run = p.add_run(f"DATA LIMITE CALCULADA: {data_limite_final}")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(255, 0, 0) # Vermelho
    
    doc.add_heading("Enquadramento Jurídico", level=1)
    doc.add_paragraph(
        "O presente cronograma visa determinar o termo do prazo para a decisão final de AIA, "
        "nos termos do Decreto-Lei n.º 151-B/2013 (RJAIA) e do Decreto-Lei n.º 11/2023 (Simplex Ambiental)."
    )

    doc.add_heading("Cronograma Detalhado", level=1)

    for item in cronograma:
        data_fmt = item['Data Estimada'].strftime('%d/%m/%Y')
        p = doc.add_heading(f"{data_fmt} - {item['Fase']}", level=2)
        doc.add_paragraph(f"Descrição: {item['Descrição']}")
        doc.add_paragraph(f"Contagem: {item['Duração']}")
        
        if item['Responsável'] == "PROMOTOR":
            doc.add_paragraph("Nota: Período de suspensão do prazo administrativo.").italic = True
            
    return doc

# --- FUNÇÃO DE CÁLCULO ---
def calcular_cronograma(data_inicio, regras, dias_suspensao, feriados):
    cronograma = []
    data_atual = data_inicio
    dias_admin = 0
    prazo_max = regras['prazo']

    def add_line(fase, resp, desc, dias_fase, tipo="UTIL", obs=""):
        nonlocal data_atual, dias_admin
        
        cronograma.append({
            "Data Estimada": data_atual,
            "Dia Admin": dias_admin if resp != "PROMOTOR" else "SUSPENSO",
            "Fase": fase,
            "Responsável": resp,
            "Descrição": desc,
            "Duração": f"{dias_fase} dias ({'Uteis' if tipo=='UTIL' else 'Corridos'})",
            "Obs": obs
        })
        
        if tipo == "UTIL":
            data_atual = somar_dias_uteis(data_atual, dias_fase, feriados)
            if resp != "PROMOTOR": dias_admin += dias_fase
        else:
            # Dias Corridos
            data_fim = data_atual + timedelta(days=dias_fase)
            data_atual = proximo_dia_util(data_fim, feriados)

    # --- FLUXO PADRÃO ---
    add_line("0. Entrada", "Promotor", "Submissão SILiAmb", 0)
    add_line("1. Conformidade", "Autoridade", "Verificação Liminar", regras['conf'])
    add_line("2. Consulta Pública", "Autoridade", "Publicitação e Consulta", regras['cp'] + 5)
    add_line("3. Análise Pós-CP", "Comissão", "Análise e Pedido AI", 10)
    add_line("4. Suspensão (Aditamentos)", "PROMOTOR", "Resposta do Promotor", dias_suspensao, tipo="CORRIDO")
    add_line("5. Avaliação Técnica", "Comissão", "Avaliação Final", 20)
    add_line("6. Audiência Prévia", "PROMOTOR", "Pronúncia CPA", 10, tipo="UTIL")
    
    # CÁLCULO FINAL DA DATA LIMITE
    dias_restantes = prazo_max - dias_admin
    if dias_restantes < 0: dias_restantes = 0
    
    add_line("7. TERMO DO PRAZO (DATA LIMITE)", "Autoridade", "Emissão da DIA", dias_restantes)
    
    return cronograma, data_atual

# ==============================================================================
# INTERFACE
# ==============================================================================

with st.sidebar:
    st.header("1. Definições")
    data_entrada = st.date_input("Data de Entrada", value=date.today())
    
    st.header("2. Projeto")
    nome_projeto = st.text_input("Nome", "Projeto Solar X")
    tipo_input = st.selectbox("Tipo de AIA", list(REGRAS.keys()))
    regras_escolhidas = REGRAS[tipo_input]

    st.header("3. Suspensões")
    dias_suspensao = st.number_input("Dias de Resposta (Promotor)", value=45, help="Dias de calendário que a sua equipa demora a responder aos pedidos.")

# ==============================================================================
# MOTOR
# ==============================================================================
anos = [data_entrada.year, data_entrada.year + 1, data_entrada.year + 2, data_entrada.year + 3]
feriados = obter_feriados_pt(anos)

if not eh_dia_util(data_entrada, feriados):
    data_inicio_contagem = proximo_dia_util(data_entrada, feriados)
    st.warning(f"⚠️ Entrada em dia não útil. Contagem inicia a: {data_inicio_contagem.strftime('%d/%m/%Y')}")
else:
    data_inicio_contagem = data_entrada

if st.button("Calcular Data Limite", type="primary"):
    
    # 1. Calcular Cenário REAL (Com suspensões)
    cronograma_real, data_limite_real = calcular_cronograma(data_inicio_contagem, regras_escolhidas, dias_suspensao, feriados)
    
    # 2. Calcular Cenário IDEAL (Sem suspensões / Zero dias do promotor)
    #    Para mostrar ao cliente "qual seria a data se nós fôssemos instantâneos"
    cronograma_ideal, data_limite_ideal = calcular_cronograma(data_inicio_contagem, regras_escolhidas, 0, feriados)

    # --- RESULTADOS EM DESTAQUE ---
    
    st.divider()
    
    # Layout de Métricas
    c1, c2, c3 = st.columns(3)
    
    c1.metric(
        label="DATA LIMITE (REAL)", 
        value=data_limite_real.strftime("%d/%m/%Y"), 
        delta="Data Final Provável",
        delta_color="inverse" # Preto/Normal
    )
    
    c2.metric(
        label="DATA LIMITE (TEÓRICA)", 
        value=data_limite_ideal.strftime("%d/%m/%Y"),
        delta="Sem suspensões",
        delta_color="off"
    )
    
    atraso = (data_limite_real - data_limite_ideal).days
    c3.metric(
        label="Impacto das Suspensões", 
        value=f"{atraso} dias",
        delta="Tempo de calendário adicionado",
        delta_color="inverse"
    )
    
    # Barra de Progresso Visual
    st.write("")
    st.info(f"ℹ️ **Nota Legal:** Esta data ({data_limite_real.strftime('%d/%m/%Y')}) corresponde ao dia em que se esgotam os **{regras_escolhidas['prazo']} dias úteis** da Administração. O incumprimento deste prazo pela Autoridade de AIA pode desencadear mecanismos de deferimento tácito no licenciamento conexo (Simplex).")

    # Tabela
    df = pd.DataFrame(cronograma_real)
    df_show = df.copy()
    df_show['Data Estimada'] = df_show['Data Estimada'].apply(lambda x: x.strftime("%d/%m/%Y"))
    
    # Destacar a última linha visualmente (via Pandas Styler)
    def highlight_last(s):
        return ['background-color: #ffcccc' if i == len(df_show)-1 else '' for i in range(len(s))]

    st.table(df_show.style.apply(highlight_last, axis=0))

    # --- EXPORTAÇÃO ---
    # Word
    doc = gerar_relatorio_word(cronograma_real, nome_projeto, regras_escolhidas, dias_suspensao, data_limite_real.strftime("%d/%m/%Y"))
    buffer_word = io.BytesIO()
    doc.save(buffer_word)
    buffer_word.seek(0)
    
    st.download_button("📄 Baixar Relatório da Data Limite (.docx)", buffer_word, f"Data_Limite_{nome_projeto}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
