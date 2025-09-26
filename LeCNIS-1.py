import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import json
import io
import re
from PyPDF2 import PdfReader

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Benefícios Previdenciários",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dados históricos de salário mínimo e teto do INSS
dados_historicos = {
    "2023-01": {"piso": 1320.00, "teto": 7507.49},
    "2024-01": {"piso": 1412.00, "teto": 7786.02},
    "2025-01": {"piso": 1518.00, "teto": 8157.41},
}

# Função para converter string em date
def parse_date(date_str):
    if isinstance(date_str, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                pass
        return date.today()
    return date_str

# Função para inicializar o estado da sessão
def init_session_state():
    if 'dados_segurado' not in st.session_state:
        st.session_state.dados_segurado = {
            'nome': '',
            'nascimento': date(1980, 1, 1),
            'sexo': 'Masculino'
        }
    if 'periodos_contribuicao' not in st.session_state:
        st.session_state.periodos_contribuicao = []
    if 'salarios' not in st.session_state:
        st.session_state.salarios = pd.DataFrame(columns=['Competência', 'Salário', 'Origem'])
    if 'parametros' not in st.session_state:
        st.session_state.parametros = {
            'tipo_beneficio': 'Aposentadoria por Idade',
            'data_inicio': date.today(),
            'tempo_contribuicao': 0,
            'fator_previdenciario': 0.0
        }

# Função para consolidar períodos sobrepostos
def consolidar_periodos(periodos_existentes, novo_periodo):
    inicio_novo, fim_novo = novo_periodo
    periodos_consolidados = []
    for inicio_existente, fim_existente in periodos_existentes:
        if inicio_novo <= fim_existente and fim_novo >= inicio_existente:
            inicio_novo = min(inicio_novo, inicio_existente)
            fim_novo = max(fim_novo, fim_existente)
        else:
            periodos_consolidados.append((inicio_existente, fim_existente))
    periodos_consolidados.append((inicio_novo, fim_novo))
    return sorted(periodos_consolidados, key=lambda x: x[0])

# Função para calcular tempo de contribuição
def calcular_tempo_contribuicao(periodos):
    if not periodos:
        return 0, 0, 0
    periodos_ordenados = sorted(periodos, key=lambda x: x['inicio'])
    total_dias = 0
    consolidados = []
    for p in periodos_ordenados:
        consolidados = consolidar_periodos(consolidados, (parse_date(p['inicio']), parse_date(p['fim'])))
    for inicio, fim in consolidados:
        total_dias += (fim - inicio).days + 1
    anos = total_dias // 365
    meses = (total_dias % 365) // 30
    dias = (total_dias % 365) % 30
    return anos, meses, dias

# Função para calcular RMI
def calcular_rmi(salarios, parametros):
    if salarios.empty:
        return 0.0
    salarios_ordenados = salarios.sort_values('Competência')
    ultimos = salarios_ordenados.tail(12)
    valores = ultimos['Salário'].sort_values(ascending=False)
    qtd = max(1, int(len(valores) * 0.8))
    media = valores.head(qtd).mean()
    competencia_atual = datetime.now().strftime("%Y-%m")
    teto = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
    rmi = min(media, teto)
    if parametros.get('fator_previdenciario', 0) > 0:
        rmi *= parametros['fator_previdenciario']
    return round(rmi, 2)

# Funções de salvar e carregar
def salvar_dados():
    return json.dumps({
        'dados_segurado': st.session_state.dados_segurado,
        'periodos_contribuicao': [
            {'inicio': str(p['inicio']), 'fim': str(p['fim']), 'descricao': p['descricao']}
            for p in st.session_state.periodos_contribuicao
        ],
        'salarios': st.session_state.salarios.to_dict('records'),
        'parametros': st.session_state.parametros
    }, indent=2, default=str)

def carregar_dados(arquivo):
    try:
        dados = json.load(arquivo)
        st.session_state.dados_segurado = dados['dados_segurado']
        st.session_state.periodos_contribuicao = [
            {'inicio': parse_date(p['inicio']), 'fim': parse_date(p['fim']), 'descricao': p['descricao']}
            for p in dados['periodos_contribuicao']
        ]
        st.session_state.salarios = pd.DataFrame(dados['salarios'])
        st.session_state.parametros = dados['parametros']
        st.success("Dados carregados com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")

# Função para processar CNIS
def processar_texto_cnis(texto):
    try:
        st.session_state.periodos_contribuicao = []
        st.session_state.salarios = pd.DataFrame(columns=['Competência', 'Salário', 'Origem'])
        periodos_extraidos = 0
        salarios_extraidos = 0
        linhas = texto.split('\n')
        for linha in linhas:
            l = linha.strip()
            if 'Nome:' in l:
                m = re.search(r'Nome:\s*(.+)', l)
                if m: st.session_state.dados_segurado['nome'] = m.group(1)
            if re.search(r'\d{2}/\d{4}\s*[a\-]\s*\d{2}/\d{4}', l):
                datas = re.findall(r'(\d{2})/(\d{4})', l)
                if len(datas) >= 2:
                    i_mes, i_ano = datas[0]
                    f_mes, f_ano = datas[1]
                    inicio = date(int(i_ano), int(i_mes), 1)
                    fim = date(int(f_ano), int(f_mes), 1) + timedelta(days=31)
                    fim = fim.replace(day=1) - timedelta(days=1)  # último dia do mês
                    st.session_state.periodos_contribuicao.append(
                        {'inicio': inicio, 'fim': fim, 'descricao': f"{i_mes}/{i_ano} a {f_mes}/{f_ano}"}
                    )
                    periodos_extraidos += 1
            if re.search(r'R?\$?\s*\d{1,3}(?:\.\d{3})*,\d{2}', l):
                m = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', l)
                if m:
                    valor = float(m.group(1).replace('.', '').replace(',', '.'))
                    comp = re.search(r'(\d{2}/\d{4})', l)
                    competencia = date.today().replace(day=1)
                    if comp:
                        mes, ano = comp.group(1).split('/')
                        competencia = date(int(ano), int(mes), 1)
                    st.session_state.salarios = pd.concat([
                        st.session_state.salarios,
                        pd.DataFrame([{'Competência': competencia, 'Salário': valor, 'Origem': 'CNIS'}])
                    ], ignore_index=True)
                    salarios_extraidos += 1
        st.success(f"Períodos extraídos: {periodos_extraidos} | Salários extraídos: {salarios_extraidos}")
        st.rerun()
    except Exception as e:
        st.error(f"Erro no processamento: {e}")

def processar_pdf_cnis(arquivo_pdf):
    try:
        reader = PdfReader(arquivo_pdf)
        texto = "\n".join(p.extract_text() for p in reader.pages if p.extract_text())
        if texto.strip():
            processar_texto_cnis(texto)
        else:
            st.warning("Não foi possível extrair texto (PDF pode ser digitalizado).")
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")

# --- INTERFACE STREAMLIT ---
init_session_state()
st.title("🧮 Calculadora de Benefícios Previdenciários")
st.markdown("---")
