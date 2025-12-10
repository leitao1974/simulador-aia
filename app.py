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
    page_title="Simulador de Prazos AIA - CCDR Centro",
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

# Feriados (Lista completa baseada no seu Excel)
FERIADOS_STR = [
    '2023-10-05', '2023-11-01', '2023-12-01', '2023-12-08', '2023-12-25', 
    '2024-01-01', '2024-03-29', '2024-04-25', '2024-05-01', '2024-05-30', '2024-06-10', '2024-08-15', '2024-10-05', '2024-11-01', '2024-12-25', 
    '2025-01-01', '2025-04-18', '2025-04-25', '2025-05-01', '2025-06-10', '2025-06-19', '2025-08-15', '2025-12-01', '2025-12-08', '2025-12-25', 
    '2026-01-01', '2026-04-03', '2026-04-05', '2026-04-25', '2026-05-01', '2026-06-04', '2026-06-10', '2026-08-15', '2026-10-05', '2026-11-01', '2026-12-01', '2026-12-08', '2026-12-25', 
    '2027-01-01', '2027-03-26', '2027-05-27', '2027-06-10', '2027-10-05', '2027-11-01', '2027-12-01', '2027-12-08', 
    '2028-04-14', '2028-04-25', '2028-05-01', '2028-06-15', '2028-08-15', '2028-10-05', '2028-11-01', '2028-12-01', '2028-12-08', '2028-12-25', 
    '2029-01-01', '2029-03-30', '2029-04-25', '2029-05-01', '2029-05-31', '2029-08-15', '2029-10-05', '2029-11-01', '2029-12-25', 
    '2030-01-01', '2030-04-19', '2030-04-25', '2030-05-01', '2030-06-10', '2030-06-20', '2030-08-15', '2030-11-01', '2030-12-25'
]
FERIADOS = {pd.to_datetime(d).date() for d in FERIADOS_STR}

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUIDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "AGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "ATIVIDADE PECUARIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTAO EFLUENTES (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868",
        "FLORESTAS (DL 16/2009 - PGF)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34488356"
    },
    "2. Industria Extrativa (Minas e Pedreiras)": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESIDUOS DE EXTRACAO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "SEGURANCA MINAS (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937"
    },
    "3. Industria Energetica": {
        "SISTEMA ELETRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "EMISSOES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "REFINACAO/COMBUSTIVEIS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34589012"
    },
    "4. Producao e Transformacao de Metais": {
        "EMISSOES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543"
    },
    "5. Industria Mineral e Quimica": {
        "PREVENCAO ACIDENTES GRAVES (SEVESO - DL 150/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558967",
        "EMISSOES (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)": {
        "ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "SERVIDOES AERONAUTICAS (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345",
        "RUIDO GRANDES INFRAESTRUTURAS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
    },
    "7. Projetos de Engenharia Hidraulica (Barragens, Portos)": {
        "SEGURANCA BARRAGENS (DL 21/2018)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2018-114833256",
        "DOMINIO HIDRICO (Lei 54/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
    },
    "8. Tratamento de Residuos e Aguas Residuais": {
        "RESIDUOS (RGGR - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
        "AGUAS RESIDUAIS URBANAS (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345",
        "ATERROS (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "9. Projetos Urbanos, Turisticos e Outros": {
        "RJUE (Urbanizacao - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "EMPREENDIMENTOS TURISTICOS (RJET)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567",
        "ACESSIBILIDADES (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456"
    }
}

TIPOLOGIAS_INFO = {
    "Anexo I (Competencia CCDR)": "Projetos do Anexo I do RJAIA sob competencia da CCDR.",
    "Anexo II (Limiares ou Zonas Sensiveis)": "Projetos do Anexo II sujeitos a AIA por ultrapassarem limiares ou localizacao em zona sensivel.",
    "Anexo II (Resultante de Triagem/Caso a Caso)": "Projetos sujeitos a AIA na sequencia de decisao de sujeicao (Triagem) positiva emitida pela CCDR.",
    "Alteracao ou Ampliacao (Competencia CCDR)": "Alteracoes a projetos existentes (Anexo I ou II) da competencia da CCDR.",
    "RECAPE (Pos-DIA CCDR)": "Verificacao conformidade ambiental (RECAPE) decorrente
