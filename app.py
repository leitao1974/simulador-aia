import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador AIA Simplex", page_icon="🇵🇹", layout="wide")

st.title("🇵🇹 Simulador de Prazos AIA (RJAIA & Simplex)")
st.markdown("""
Calculadora oficial de prazos para emissão da DIA, adaptada ao **Decreto-Lei n.º 11/2023** (Simplex Ambiental).
Considera os novos prazos de **150 dias** (Geral) e **90 dias** (Indústria/PIN).
""")

# --- FUNÇÕES UTILITÁRIAS DE DATAS ---
def obter_feriados_pt(anos):
    """Gera feriados de Portugal para os anos indicados."""
    return holidays.PT(years=anos)

def eh_dia_util(data_check, lista_feriados):
    """Verifica se é dia útil (Seg-Sex e não feriado)."""
    if data_check.weekday() >= 5: return False # Sábado ou Domingo
    if data_check in lista_feriados: return False # Feriado
    return True

def proximo_dia_util(data_ref, lista_feriados):
    """Avança no calendário até encontrar um dia útil."""
    data_calc = data_ref
    while not eh_dia_util(data_calc, lista_feriados):
        data_calc += timedelta(days=1)
    return data_calc

def somar_dias_uteis(data_inicio, dias_a_adicionar, lista_feriados):
    """Soma dias úteis à data de início."""
    data_atual = data_inicio
    dias_adicionados = 0
    while dias_adicionados < dias_a_adicionar:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, lista_feriados):
            dias_adicionados += 1
    return data_atual

# --- DADOS LEGAIS ATUALIZADOS (SIMPLEX 2023) ---
REGRAS = {
    "Regra Geral (150 dias úteis)": {
        "prazo": 150, 
        "conf": 10, 
        "cp": 30,
        "desc": "Projetos de Infraestruturas, Turismo, Agricultura, Serviços, etc. (Art. 19.º RJAIA)"
    },
    "Indústria SIR / PIN (90 dias úteis)": {
        "prazo": 90,  
        "conf": 10, 
        "cp": 30,
        "desc": "Projetos ao abrigo do SIR (Sistema da Indústria Responsável) ou PIN. (Art. 19.º RJAIA)"
    },
    "AIncA (60 dias úteis)": {
        "prazo": 60,  
        "conf": 10, 
        "cp": 20,
        "desc": "Avaliação de Incidências Ambientais (Geralmente Renováveis/Áreas Sensíveis)."
    }
}

# --- GERADOR DE RELATÓRIO WORD ---
def gerar_relatorio_word(cronograma, nome_projeto, regras, dias_suspensao, data_limite_final):
    doc = Document()
    
    # Estilos
    style = doc.styles['Title']
    style.font.size = Pt(16)
    
    doc.add_heading(f'Memória de Cálculo de Prazos: {nome_projeto}', 0)
    doc.add_paragraph(f"Data de Simulação: {datetime.date.today().strftime('%d/%m/%Y')}")
    
    # Destaque
    p = doc.add_paragraph()
    run = p.add_run(f"DATA LIMITE PREVISTA (DIA): {data_limite_final}")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(200, 0, 0) # Vermelho escuro
    
    doc.add_heading("1. Enquadramento Legal", level=1)
    doc.add_paragraph(
        f"A presente calendarização foi elaborada considerando o prazo global de {regras['prazo']} dias úteis, "
        "conforme definido no Decreto-Lei n.º 151-B/2013, com as alterações introduzidas pelo Decreto-Lei n.º 11/2023 (Simplex Ambiental)."
    )
    doc.add_paragraph(
        "A contagem observa o Código do Procedimento Administrativo (CPA), suspendendo-se aos sábados, domingos e feriados, "
        "bem como nos períodos de resposta do promotor (suspensão do prazo administrativo)."
    )

    doc.add_heading("2. Detalhe das Etapas", level=1)

    for item in cronograma:
        data_fmt = item['Data Estimada'].strftime('%d/%m/%Y')
        doc.add_heading(f"{data_fmt} - {item['Fase']}", level=2)
        
        doc.add_paragraph(f"Descrição: {item['Descrição']}")
        doc.add_paragraph(f"Duração considerada: {item['Duração']}")
        
        if item['Responsável'] == "PROMOTOR":
            p_nota = doc.add_paragraph("Estado do Prazo Administrativo: ")
            p_nota.add_run("SUSPENSO").bold = True
        
        doc.add_paragraph("-" * 20)

    return doc

# --- MOTOR DE CÁLCULO (ENCAPSULADO) ---
def calcular_cronograma(data_inicio, regras, dias_suspensao, feriados):
    """
    Executa a lógica de cronograma passo a passo.
    Retorna a lista de eventos e a data final.
    """
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
            # Dias Corridos (Suspensão)
            data_fim = data_atual + timedelta(days=dias_fase)
            # Retoma no próximo dia útil
            data_atual = proximo_dia_util(data_fim, feriados)

    # --- FLUXO DO PROCEDIMENTO ---
    
    # 0. Entrada
    add_line("0. Entrada", "Promotor", "Submissão do Pedido", 0)
    
    # 1. Conformidade
    add_line("1. Conformidade", "Autoridade AIA", "Verificação Liminar da Instrução", regras['conf'])
    
    # 2. Consulta Pública (Prazo Legal + 5 dias prep)
    dias_cp_total = regras['cp'] + 5
    add_line("2. Consulta Pública", "Autoridade AIA", "Publicitação e Período de Consulta", dias_cp_total)
    
    # 3. Análise Pós-CP e Pedido de Elementos
    # Estimativa: A autoridade analisa as participações e pede elementos.
    add_line("3. Análise I", "Comissão Avaliação", "Análise Pós-CP e Pedido de AI", 15)
    
    # 4. Suspensão (Aditamentos)
    # AQUI O RELÓGIO ADMIN PARA.
    add_line("4. Aditamentos", "PROMOTOR", "Resposta ao Pedido de Elementos", dias_suspensao, tipo="CORRIDO", obs="Suspensão do Prazo Decisório")
    
    # 5. Avaliação Técnica Final
    add_line("5. Avaliação Técnica", "Comissão Avaliação", "Elaboração do Parecer Final", 20)
    
    # 6. Audiência Prévia (CPA)
    # O promotor tem 10 dias úteis para responder. O prazo da admin está suspenso à espera.
    add_line("6. Audiência Prévia", "PROMOTOR", "Pronúncia em sede de CPA", 10, tipo="UTIL", obs="Prazo de pronúncia (Suspensivo)")
    
    # 7. Termo do Prazo (O que sobra)
    dias_restantes = prazo_max - dias_admin
    if dias_restantes < 0: dias_restantes = 0
    
    add_line("7. TERMO DO PRAZO (DIA)", "Autoridade AIA", "Data Limite para Emissão da Decisão", dias_restantes)
    
    return cronograma, data_atual

# ==============================================================================
# INTERFACE GRÁFICA (SIDEBAR)
# ==============================================================================
with st.sidebar:
    st.header("1. Calendário")
    data_entrada = st.date_input("Data de Entrada", value=date.today())
    
    st.header("2. Projeto")
    nome_projeto = st.text_input("Nome do Projeto", "Projeto Solar Exemplo")
    
    # Menu Dropdown com as Regras
    nome_regra = st.selectbox("Enquadramento Legal", list(REGRAS.keys()))
    regras_escolhidas = REGRAS[nome_regra]
    
    # Mostrar descrição da regra escolhida
    st.info(f"ℹ️ {regras_escolhidas['desc']}")
    
    st.header("3. Suspensões (Promotor)")
    dias_suspensao = st.number_input(
        "Tempo p/ Aditamentos (Dias Corridos)", 
        value=45, 
        step=5,
        help="Estimativa de tempo que a equipa de projeto demora a responder aos pedidos da APA/CCDR."
    )

# ==============================================================================
# MOTOR PRINCIPAL
# ==============================================================================

# Calcular feriados para o ano corrente e os próximos 3 anos (segurança)
anos_calc = [data_entrada.year + i for i in range(4)]
feriados = obter_feriados_pt(anos_calc)

# Validar dia de entrada
if not eh_dia_util(data_entrada, feriados):
    data_inicio_real = proximo_dia_util(data_entrada, feriados)
    aviso_entrada = f"⚠️ A data de entrada ({data_entrada}) não é útil. O prazo inicia a contar em **{data_inicio_real.strftime('%d/%m/%Y')}**."
else:
    data_inicio_real = data_entrada
    aviso_entrada = ""

if st.button("Calcular Data Limite", type="primary"):
    
    if aviso_entrada:
        st.warning(aviso_entrada)
        
    # CÁLCULO 1: CENÁRIO REAL (Com a suspensão inserida)
    cronograma_real, data_final_real = calcular_cronograma(
        data_inicio_real, regras_escolhidas, dias_suspensao, feriados
    )
    
    # CÁLCULO 2: CENÁRIO TEÓRICO (Sem suspensão / 0 dias)
    # Serve para comparar qual seria a data se o promotor fosse instantâneo
    _, data_final_teorica = calcular_cronograma(
        data_inicio_real, regras_escolhidas, 0, feriados
    )
    
    # --- RESULTADOS VISUAIS ---
    st.divider()
    
    # Métricas de Topo
    c1, c2, c3 = st.columns(3)
    
    c1.metric(
        "DATA LIMITE (REAL)", 
        data_final_real.strftime("%d/%m/%Y"), 
        help="Data prevista considerando o tempo de resposta da sua equipa."
    )
    
    c2.metric(
        "DATA LIMITE (TEÓRICA)", 
        data_final_teorica.strftime("%d/%m/%Y"),
        delta="Sem suspensões",
        delta_color="off",
        help="Data limite se o promotor respondesse no próprio dia (0 dias de suspensão)."
    )
    
    diferenca = (data_final_real - data_final_teorica).days
    c3.metric(
        "Impacto Temporal", 
        f"+ {diferenca} dias",
        delta="Derrapagem de Calendário",
        delta_color="inverse"
    )

    # Tabela de Dados
    st.subheader("Cronograma Detalhado")
    df = pd.DataFrame(cronograma_real)
    
    # Formatação para visualização
    df_show = df.copy()
    df_show['Data Estimada'] = df_show['Data Estimada'].apply(lambda x: x.strftime("%d/%m/%Y"))
    
    # Pintar a última linha de vermelho claro
    def highlight_last_row(row):
        return ['background-color: #ffe6e6'] * len(row) if row.name == len(df_show) - 1 else [''] * len(row)

    st.dataframe(df_show.style.apply(highlight_last_row, axis=1), use_container_width=True)
    
    # --- ÁREA DE DOWNLOADS ---
    col_d1, col_d2 = st.columns(2)
    
    # 1. Excel
    buffer_xls = io.BytesIO()
    with pd.ExcelWriter(buffer_xls, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Cronograma')
    
    with col_d1:
        st.download_button(
            "📥 Download Excel (.xlsx)",
            data=buffer_xls,
            file_name=f"Cronograma_{nome_projeto}.xlsx",
            mime="application/vnd.ms-excel"
        )
        
    # 2. Word
    doc_word = gerar_relatorio_word(cronograma_real, nome_projeto, regras_escolhidas, dias_suspensao, data_final_real.strftime("%d/%m/%Y"))
    buffer_word = io.BytesIO()
    doc_word.save(buffer_word)
    buffer_word.seek(0)
    
    with col_d2:
        st.download_button(
            "📄 Download Relatório Jurídico (.docx)",
            data=buffer_word,
            file_name=f"Memoria_Justificativa_{nome_projeto}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
