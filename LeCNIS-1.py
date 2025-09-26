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

# Função para converter string em date - CORRIGIDA
def parse_date(date_str):
    if isinstance(date_str, str):
        # Remove horas se existirem
        date_str = date_str.split(' ')[0]
        
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%Y-%m"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                # Se só tem mês/ano, assume dia 1
                if fmt in ("%m/%Y", "%Y-%m"):
                    return dt.replace(day=1)
                return dt
            except ValueError:
                continue
    elif isinstance(date_str, date):
        return date_str
    return date.today()

# Função para inicializar o estado da sessão - CORRIGIDA
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

# Função para consolidar períodos sobrepostos - COMPLETAMENTE REFEITA
def consolidar_periodos(periodos):
    if not periodos:
        return []
    
    # Converte para lista de tuplas (inicio, fim)
    periodos_tuplas = []
    for p in periodos:
        inicio = parse_date(p['inicio'])
        fim = parse_date(p['fim'])
        periodos_tuplas.append((inicio, fim))
    
    # Ordena por data de início
    periodos_tuplas.sort(key=lambda x: x[0])
    
    consolidados = []
    current_start, current_end = periodos_tuplas[0]
    
    for inicio, fim in periodos_tuplas[1:]:
        if inicio <= current_end + timedelta(days=1):  # Permite sobreposição ou continuidade
            current_end = max(current_end, fim)
        else:
            consolidados.append((current_start, current_end))
            current_start, current_end = inicio, fim
    
    consolidados.append((current_start, current_end))
    return consolidados

# Função para calcular tempo de contribuição - CORRIGIDA
def calcular_tempo_contribuicao(periodos):
    if not periodos:
        return 0, 0, 0
    
    periodos_consolidados = consolidar_periodos(periodos)
    total_dias = 0
    
    for inicio, fim in periodos_consolidados:
        total_dias += (fim - inicio).days + 1
    
    anos = total_dias // 365
    meses = (total_dias % 365) // 30
    dias = (total_dias % 365) % 30
    return anos, meses, dias

# Função para calcular RMI - CORRIGIDA
def calcular_rmi(salarios_df, parametros):
    if salarios_df.empty:
        return 0.0
    
    # Garante que Competência está no formato correto
    salarios_processados = processar_salarios(salarios_df)
    
    if salarios_processados.empty:
        return 0.0
        
    # Ordena por competência e pega últimos 12 meses
    salarios_ordenados = salarios_processados.sort_values('Competência')
    ultimos_12 = salarios_ordenados.tail(12)
    
    if ultimos_12.empty:
        return 0.0
        
    # Calcula média dos 80% maiores salários
    valores_ordenados = ultimos_12['Salário'].sort_values(ascending=False)
    qtd_considerar = max(1, int(len(valores_ordenados) * 0.8))
    media = valores_ordenados.head(qtd_considerar).mean()
    
    # Aplica teto
    competencia_atual = datetime.now().strftime("%Y-%m")
    teto_atual = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
    rmi = min(media, teto_atual)
    
    # Aplica fator previdenciário se existir
    if parametros.get('fator_previdenciario', 0) > 0:
        rmi *= parametros['fator_previdenciario']
    
    return round(rmi, 2)

# FUNÇÃO PROCESSAR SALÁRIOS - AGORA FUNCIONANDO
def processar_salarios(salarios_df):
    if salarios_df.empty:
        return pd.DataFrame(columns=['Competência', 'Salário', 'Origem'])
    
    df = salarios_df.copy()
    
    # Converte Competência para datetime de forma segura
    def converter_competencia(comp):
        if isinstance(comp, str):
            # Tenta diferentes formatos
            for fmt in ['%m/%Y', '%Y-%m', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    return datetime.strptime(comp, fmt)
                except ValueError:
                    continue
        elif isinstance(comp, (datetime, pd.Timestamp)):
            return comp
        return None
    
    df['Competência_DateTime'] = df['Competência'].apply(converter_competencia)
    df = df.dropna(subset=['Competência_DateTime'])
    
    if df.empty:
        return pd.DataFrame(columns=['Competência', 'Salário', 'Origem'])
    
    # Ordena por data
    df = df.sort_values('Competência_DateTime')
    
    # Formata para exibição
    df['Competência'] = df['Competência_DateTime'].dt.strftime('%m/%Y')
    df = df[['Competência', 'Salário', 'Origem']]
    
    return df

# Funções de salvar e carregar - CORRIGIDAS
def salvar_dados():
    dados = {
        'dados_segurado': st.session_state.dados_segurado,
        'periodos_contribuicao': [
            {'inicio': p['inicio'].isoformat() if hasattr(p['inicio'], 'isoformat') else str(p['inicio']),
             'fim': p['fim'].isoformat() if hasattr(p['fim'], 'isoformat') else str(p['fim']),
             'descricao': p['descricao']}
            for p in st.session_state.periodos_contribuicao
        ],
        'salarios': st.session_state.salarios.to_dict('records'),
        'parametros': st.session_state.parametros
    }
    return json.dumps(dados, indent=2)

def carregar_dados(arquivo):
    try:
        dados = json.load(arquivo)
        st.session_state.dados_segurado = dados['dados_segurado']
        st.session_state.periodos_contribuicao = [
            {'inicio': parse_date(p['inicio']), 
             'fim': parse_date(p['fim']), 
             'descricao': p['descricao']}
            for p in dados['periodos_contribuicao']
        ]
        st.session_state.salarios = pd.DataFrame(dados['salarios'])
        st.session_state.parametros = dados['parametros']
        st.success("Dados carregados com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")

# Função para processar CNIS - CORRIGIDA
def processar_texto_cnis(texto):
    try:
        # Limpa dados anteriores
        st.session_state.periodos_contribuicao = []
        novos_salarios = []
        
        periodos_extraidos = 0
        salarios_extraidos = 0
        
        linhas = texto.split('\n')
        
        for linha in linhas:
            l = linha.strip()
            
            # Extrai nome
            if 'Nome:' in l and not st.session_state.dados_segurado['nome']:
                m = re.search(r'Nome:\s*(.+)', l)
                if m: 
                    st.session_state.dados_segurado['nome'] = m.group(1).strip()
            
            # Extrai períodos (formato: MM/AAAA a MM/AAAA)
            if re.search(r'\d{2}/\d{4}\s*[a\-]\s*\d{2}/\d{4}', l):
                datas = re.findall(r'(\d{2})/(\d{4})', l)
                if len(datas) >= 2:
                    i_mes, i_ano = datas[0]
                    f_mes, f_ano = datas[1]
                    
                    inicio = date(int(i_ano), int(i_mes), 1)
                    # Último dia do mês
                    if int(f_mes) == 12:
                        fim = date(int(f_ano), 12, 31)
                    else:
                        fim = date(int(f_ano), int(f_mes) + 1, 1) - timedelta(days=1)
                    
                    st.session_state.periodos_contribuicao.append({
                        'inicio': inicio, 
                        'fim': fim, 
                        'descricao': f"{i_mes}/{i_ano} a {f_mes}/{f_ano}"
                    })
                    periodos_extraidos += 1
            
            # Extrai salários (valores monetários)
            if re.search(r'R?\$?\s*\d{1,3}(?:\.\d{3})*,\d{2}', l):
                m = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', l)
                if m:
                    valor_str = m.group(1).replace('.', '').replace(',', '.')
                    try:
                        valor = float(valor_str)
                        
                        # Tenta encontrar competência na mesma linha
                        comp_match = re.search(r'(\d{2}/\d{4})', l)
                        if comp_match:
                            mes, ano = comp_match.group(1).split('/')
                            competencia = date(int(ano), int(mes), 1)
                            novos_salarios.append({
                                'Competência': competencia.strftime('%m/%Y'),
                                'Salário': valor, 
                                'Origem': 'CNIS'
                            })
                            salarios_extraidos += 1
                    except ValueError:
                        continue
        
        # Adiciona novos salários ao DataFrame existente
        if novos_salarios:
            novos_df = pd.DataFrame(novos_salarios)
            st.session_state.salarios = pd.concat([st.session_state.salarios, novos_df], ignore_index=True)
        
        st.success(f"✅ Períodos extraídos: {periodos_extraidos} | Salários extraídos: {salarios_extraidos}")
        st.rerun()
        
    except Exception as e:
        st.error(f"Erro no processamento: {e}")

def processar_pdf_cnis(arquivo_pdf):
    try:
        reader = PdfReader(arquivo_pdf)
        texto = ""
        for pagina in reader.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto += texto_pagina + "\n"
        
        if texto.strip():
            processar_texto_cnis(texto)
        else:
            st.warning("Não foi possível extrair texto do PDF (pode ser um PDF digitalizado).")
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")

# --- INTERFACE STREAMLIT CORRIGIDA ---
init_session_state()

st.title("🧮 Calculadora de Benefícios Previdenciários")
st.markdown("---")

# Sidebar para upload e salvamento
with st.sidebar:
    st.header("📁 Gerenciar Dados")
    
    # Upload de arquivo
    uploaded_file = st.file_uploader("Carregar dados salvos", type=['json'])
    if uploaded_file:
        carregar_dados(uploaded_file)
    
    # Download de dados
    if st.button("💾 Salvar Dados Atuais"):
        dados_json = salvar_dados()
        st.download_button(
            label="⬇️ Baixar Dados",
            data=dados_json,
            file_name=f"dados_previdenciarios_{date.today().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
    
    st.markdown("---")
    st.header("📄 Importar CNIS")
    
    # Upload CNIS
    opcao_cnis = st.radio("Formato do CNIS:", ["Texto", "PDF"])
    
    if opcao_cnis == "Texto":
        texto_cnis = st.text_area("Cole o texto do CNIS aqui:", height=200)
        if st.button("Processar Texto CNIS") and texto_cnis:
            processar_texto_cnis(texto_cnis)
    else:
        pdf_cnis = st.file_uploader("Upload PDF CNIS", type=['pdf'])
        if st.button("Processar PDF CNIS") and pdf_cnis:
            processar_pdf_cnis(pdf_cnis)

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs(["👤 Dados Pessoais", "📅 Períodos Contribuição", "💰 Salários", "📊 Cálculo"])

with tab1:
    st.header("Dados do Segurado")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        nome = st.text_input("Nome completo:", value=st.session_state.dados_segurado['nome'])
        st.session_state.dados_segurado['nome'] = nome
    
    with col2:
        nascimento = st.date_input("Data de nascimento:", value=st.session_state.dados_segurado['nascimento'])
        st.session_state.dados_segurado['nascimento'] = nascimento
    
    with col3:
        sexo = st.selectbox("Sexo:", ["Masculino", "Feminino"], 
                           index=0 if st.session_state.dados_segurado['sexo'] == 'Masculino' else 1)
        st.session_state.dados_segurado['sexo'] = sexo

with tab2:
    st.header("Períodos de Contribuição")
    
    # Adicionar novo período
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        novo_inicio = st.date_input("Início do período:", key="inicio_periodo")
    with col2:
        novo_fim = st.date_input("Fim do período:", key="fim_periodo")
    with col3:
        st.write("")  # Espaçamento
        st.write("")
        if st.button("➕ Adicionar Período"):
            if novo_inicio and novo_fim:
                if novo_inicio <= novo_fim:
                    novo_periodo = {
                        'inicio': novo_inicio,
                        'fim': novo_fim,
                        'descricao': f"{novo_inicio.strftime('%m/%Y')} a {novo_fim.strftime('%m/%Y')}"
                    }
                    st.session_state.periodos_contribuicao.append(novo_periodo)
                    st.success("Período adicionado!")
                    st.rerun()
                else:
                    st.error("Data de início deve ser anterior à data de fim!")
    
    # Lista de períodos
    if st.session_state.periodos_contribuicao:
        st.subheader("Períodos cadastrados:")
        for i, periodo in enumerate(st.session_state.periodos_contribuicao):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.write(f"**{periodo['descricao']}**")
            with col2:
                dias = (periodo['fim'] - periodo['inicio']).days + 1
                st.write(f"({dias} dias)")
            with col3:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.periodos_contribuicao.pop(i)
                    st.rerun()
    else:
        st.info("Nenhum período de contribuição cadastrado.")
    
    # Cálculo do tempo total
    if st.session_state.periodos_contribuicao:
        anos, meses, dias = calcular_tempo_contribuicao(st.session_state.periodos_contribuicao)
        st.success(f"**Tempo total de contribuição:** {anos} anos, {meses} meses e {dias} dias")

with tab3:
    st.header("Histórico de Salários")
    
    # Adicionar novo salário
    col1, col2, col3 = st.columns(3)
    with col1:
        comp_salario = st.text_input("Competência (MM/AAAA):", placeholder="01/2024")
    with col2:
        valor_salario = st.number_input("Valor do salário (R$):", min_value=0.0, step=100.0)
    with col3:
        st.write("")
        st.write("")
        if st.button("➕ Adicionar Salário"):
            if comp_salario and valor_salario > 0:
                # Valida formato MM/AAAA
                if re.match(r'^\d{2}/\d{4}$', comp_salario):
                    novo_salario = {
                        'Competência': comp_salario,
                        'Salário': valor_salario,
                        'Origem': 'Manual'
                    }
                    st.session_state.salarios = pd.concat([
                        st.session_state.salarios,
                        pd.DataFrame([novo_salario])
                    ], ignore_index=True)
                    st.success("Salário adicionado!")
                    st.rerun()
                else:
                    st.error("Formato inválido! Use MM/AAAA (ex: 01/2024)")
    
    # Tabela de salários processada
    if not st.session_state.salarios.empty:
        salarios_processados = processar_salarios(st.session_state.salarios)
        st.subheader("Salários cadastrados:")
        st.dataframe(salarios_processados, use_container_width=True)
        
        # Estatísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de registros", len(salarios_processados))
        with col2:
            st.metric("Maior salário", f"R$ {salarios_processados['Salário'].max():.2f}")
        with col3:
            st.metric("Média", f"R$ {salarios_processados['Salário'].mean():.2f}")
    else:
        st.info("Nenhum salário cadastrado.")

with tab4:
    st.header("Cálculo do Benefício")
    
    # Parâmetros do cálculo
    col1, col2 = st.columns(2)
    with col1:
        tipo_beneficio = st.selectbox(
            "Tipo de benefício:",
            ["Aposentadoria por Idade", "Aposentadoria por Tempo de Contribuição", 
             "Aposentadoria por Invalidez", "Pensão por Morte"],
            index=0
        )
        st.session_state.parametros['tipo_beneficio'] = tipo_beneficio
        
        data_inicio = st.date_input("Data de início do benefício:", value=date.today())
        st.session_state.parametros['data_inicio'] = data_inicio
    
    with col2:
        fator_prev = st.number_input("Fator previdenciário (opcional):", 
                                   min_value=0.0, max_value=2.0, value=0.0, step=0.01)
        st.session_state.parametros['fator_previdenciario'] = fator_prev
        
        # Exibe tempo total calculado
        if st.session_state.periodos_contribuicao:
            anos, meses, dias = calcular_tempo_contribuicao(st.session_state.periodos_contribuicao)
            st.session_state.parametros['tempo_contribuicao'] = anos
            st.metric("Tempo de contribuição", f"{anos} anos, {meses} meses")
    
    # Botão para calcular
    if st.button("🎯 Calcular RMI", type="primary"):
        if st.session_state.salarios.empty:
            st.error("Adicione pelo menos um salário para calcular o RMI!")
        else:
            rmi = calcular_rmi(st.session_state.salarios, st.session_state.parametros)
            st.session_state.parametros['rmi_calculado'] = rmi
            
            # Exibe resultado
            st.success(f"**Renda Mensal Inicial (RMI) calculada:** R$ {rmi:,.2f}")
            
            # Detalhes do cálculo
            with st.expander("📈 Detalhes do cálculo"):
                salarios_processados = processar_salarios(st.session_state.salarios)
                if not salarios_processados.empty:
                    ultimos_12 = salarios_processados.tail(12)
                    st.write("**Últimos 12 salários considerados:**")
                    st.dataframe(ultimos_12)
                    
                    # Teto aplicado
                    competencia_atual = datetime.now().strftime("%Y-%m")
                    teto_atual = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
                    st.write(f"**Teto do INSS aplicado:** R$ {teto_atual:,.2f}")

st.markdown("---")
st.caption("Calculadora desenvolvida para fins educacionais - Consulte um especialista para análise precisa.")
