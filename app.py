import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador AIA + Jurídico", page_icon="⚖️", layout="wide")

st.title("⚖️ Simulador AIA & Fundamentação Jurídica")
st.markdown("""
Gera o cronograma técnico e a **Memória Justificativa** com base no RJAIA e no Código do Procedimento Administrativo (CPA).
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

# --- GERADOR DE RELATÓRIO WORD ---
def gerar_relatorio_word(cronograma, nome_projeto, regras, dias_suspensao):
    doc = Document()
    
    # Título
    style = doc.styles['Title']
    style.font.size = Pt(16)
    doc.add_heading(f'Memória Justificativa de Prazos: {nome_projeto}', 0)
    
    doc.add_paragraph(f"Data de Emissão: {datetime.date.today().strftime('%d/%m/%Y')}")
    doc.add_paragraph("Este documento fundamenta legalmente a contagem de prazos para o procedimento de AIA, considerando o Decreto-Lei n.º 151-B/2013 (RJAIA) na sua redação atual e o Código do Procedimento Administrativo (CPA).")
    
    doc.add_heading("Enquadramento Legal Geral", level=1)
    doc.add_paragraph(
        "Nos termos do Artigo 87.º do CPA e do DL n.º 11/2023, os prazos administrativos contam-se em dias úteis. "
        "A contagem suspende-se nos Sábados, Domingos e Feriados. "
        "Quando o prazo terminaria num dia não útil, transfere-se para o primeiro dia útil seguinte."
    )

    doc.add_heading("Detalhamento das Etapas", level=1)

    for item in cronograma:
        # Título da Fase
        data_fmt = item['Data Estimada'].strftime('%d/%m/%Y')
        p = doc.add_heading(f"{item['Fase']} - {data_fmt}", level=2)
        
        # Descrição e Duração
        doc.add_paragraph(f"Descrição: {item['Descrição']}")
        doc.add_paragraph(f"Duração considerada: {item['Duração']}")
        
        # Fundamentação Jurídica Dinâmica
        fundamentacao = ""
        fase_nome = item['Fase']

        if "Entrada" in fase_nome:
            fundamentacao = (
                "Termo inicial (dies a quo): A submissão marca o início do procedimento. "
                "Nos termos do Art. 88.º do CPA, a contagem do prazo administrativo inicia-se no dia útil seguinte."
            )
        
        elif "Conformidade" in fase_nome:
            fundamentacao = (
                "Base Legal: Artigo 13.º do RJAIA. A autoridade de AIA dispõe deste prazo para verificar a conformidade liminar do Estudo de Impacte Ambiental. "
                "A ausência de pronúncia neste prazo implica deferimento tácito da conformidade (Simplex Ambiental)."
            )

        elif "Consulta Pública" in fase_nome:
            fundamentacao = (
                "Base Legal: Artigo 15.º e 15.º-A do RJAIA. O período de consulta pública não pode ser inferior a 30 dias úteis (Anexo I e II). "
                "Inclui-se aqui o prazo procedimental de publicitação dos avisos."
            )

        elif "Análise I" in fase_nome:
            fundamentacao = (
                "Base Legal: Artigo 16.º do RJAIA. A Autoridade de AIA pode solicitar elementos adicionais (AI) numa única vez. "
                "Este pedido suspende o prazo de decisão da administração nos termos do CPA."
            )

        elif "Aditamentos" in fase_nome:
            fundamentacao = (
                "Regime de Suspensão: Durante este período, a contagem do prazo da administração encontra-se suspensa. "
                "O prazo aqui indicado corresponde ao tempo estimado pelo Promotor para resposta, contando-se em dias corridos (calendário civil), "
                "pois trata-se de um prazo para a prática de atos pelo interessado."
            )

        elif "Análise II" in fase_nome:
            fundamentacao = (
                "Base Legal: Artigo 16.º e 17.º do RJAIA. Após receção dos aditamentos, retoma-se a contagem do prazo administrativo para avaliação técnica final."
            )

        elif "Audiência Prévia" in fase_nome:
            fundamentacao = (
                "Base Legal: Artigos 121.º e 122.º do CPA. Antes da decisão final, o promotor tem direito a ser ouvido. "
                "O prazo mínimo legal é de 10 dias úteis. Este período suspende novamente a contagem do prazo decisório da Autoridade."
            )
        
        elif "Decisão Final" in fase_nome:
            artigo_prazo = "18.º (Anexo II)" if regras['prazo'] == 75 else "19.º (Anexo I)"
            fundamentacao = (
                f"Base Legal: Artigo {artigo_prazo} do RJAIA. A Declaração de Impacte Ambiental (DIA) deve ser emitida até ao termo deste prazo. "
                "O incumprimento pode gerar deferimento tácito do licenciamento principal, mas não da avaliação ambiental em si (Art. 23.º DL 11/2023)."
            )

        if fundamentacao:
            p_fund = doc.add_paragraph()
            runner = p_fund.add_run("Fundamentação: ")
            runner.bold = True
            p_fund.add_run(fundamentacao)
            
        doc.add_paragraph("-" * 30) # Separador

    return doc

# --- LÓGICA DE CÁLCULO (WRAPPER PARA EVITAR ERRO NONLOCAL) ---
def calcular_cronograma_completo(data_inicio, regras, dias_suspensao, feriados):
    """
    Função encapsulada para calcular o cronograma.
    Resolve o erro 'SyntaxError: no binding for nonlocal'.
    """
    cronograma = []
    data_atual = data_inicio
    dias_admin = 0
    prazo_max = regras['prazo']

    # Função interna agora funciona corretamente porque está dentro de outra função
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

    # --- EXECUÇÃO DAS FASES ---
    add_line("0. Entrada do Processo", "Promotor", "Submissão SILiAmb", 0)
    add_line("1. Conformidade", "Autoridade", "Verificação Liminar", regras['conf'])
    add_line("2. Consulta Pública", "Autoridade", "Publicitação e Consulta", regras['cp'] + 5)
    add_line("3. Análise I (Pedido AI)", "Comissão", "Análise Pós-CP", 10)
    add_line("4. Aditamentos (Suspensão)", "PROMOTOR", "Resposta aos Pedidos", dias_suspensao, tipo="CORRIDO")
    add_line("5. Análise II (Técnica)", "Comissão", "Avaliação Final", 20)
    add_line("6. Audiência Prévia", "PROMOTOR", "Pronúncia CPA", 10, tipo="UTIL")
    
    dias_restantes = prazo_max - dias_admin
    if dias_restantes < 0: dias_restantes = 0
    
    add_line("7. Decisão Final (DIA)", "Autoridade", "Emissão da Decisão", dias_restantes)
    
    return cronograma

# --- DADOS RJAIA ---
REGRAS = {
    "Anexo I (100 dias úteis)": {"prazo": 100, "conf": 10, "cp": 30},
    "Anexo II (75 dias úteis)": {"prazo": 75, "conf": 10, "cp": 30},
    "AIncA (60 dias úteis)":    {"prazo": 60, "conf": 10, "cp": 20}
}

# ==============================================================================
# INTERFACE
# ==============================================================================
with st.sidebar:
    st.header("1. Configuração")
    data_entrada = st.date_input("Data de Entrada", value=date.today())
    
    st.header("2. Projeto")
    nome_projeto = st.text_input("Nome", "Projeto Solar X")
    tipo_input = st.selectbox("Tipo", list(REGRAS.keys()))
    regras_escolhidas = REGRAS[tipo_input]

    st.header("3. Promotor")
    dias_suspensao = st.number_input("Dias para Aditamentos (Corridos)", value=60)

# ==============================================================================
# MOTOR PRINCIPAL
# ==============================================================================

# 1. Preparar Feriados
anos = [data_entrada.year, data_entrada.year + 1, data_entrada.year + 2]
feriados = obter_feriados_pt(anos)

# 2. Verificar data inicial
if not eh_dia_util(data_entrada, feriados):
    data_inicio_contagem = proximo_dia_util(data_entrada, feriados)
