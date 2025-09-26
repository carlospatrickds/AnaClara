import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import json
import io

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Benefícios Previdenciários",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dados históricos de salário mínimo e teto do INSS (exemplo simplificado)
dados_historicos = {
    "2023-01": {"piso": 1320.00, "teto": 7507.49},
    "2023-02": {"piso": 1320.00, "teto": 7507.49},
    "2023-03": {"piso": 1320.00, "teto": 7507.49},
    "2023-04": {"piso": 1320.00, "teto": 7507.49},
    "2023-05": {"piso": 1320.00, "teto": 7507.49},
    "2023-06": {"piso": 1320.00, "teto": 7507.49},
    "2023-07": {"piso": 1320.00, "teto": 7507.49},
    "2023-08": {"piso": 1320.00, "teto": 7507.49},
    "2023-09": {"piso": 1320.00, "teto": 7507.49},
    "2023-10": {"piso": 1320.00, "teto": 7507.49},
    "2023-11": {"piso": 1320.00, "teto": 7507.49},
    "2023-12": {"piso": 1320.00, "teto": 7507.49},
    "2024-01": {"piso": 1412.00, "teto": 7786.02},
    "2024-02": {"piso": 1412.00, "teto": 7786.02},
    "2024-03": {"piso": 1412.00, "teto": 7786.02},
    "2024-04": {"piso": 1412.00, "teto": 7786.02},
    "2024-05": {"piso": 1412.00, "teto": 7786.02},
    "2024-06": {"piso": 1412.00, "teto": 7786.02},
    "2024-07": {"piso": 1412.00, "teto": 7786.02},
    "2024-08": {"piso": 1412.00, "teto": 7786.02},
    "2024-09": {"piso": 1412.00, "teto": 7786.02},
    "2024-10": {"piso": 1412.00, "teto": 7786.02},
    "2024-11": {"piso": 1412.00, "teto": 7786.02},
    "2024-12": {"piso": 1412.00, "teto": 7786.02},
    "2025-01": {"piso": 1518.00, "teto": 8157.41},
}

# Função para converter string em date
def parse_date(date_str):
    if isinstance(date_str, str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
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

# Função para calcular tempo de contribuição CORRIGIDA
def calcular_tempo_contribuicao(periodos):
    if not periodos:
        return 0, 0, 0
    
    # Ordenar períodos por data de início
    periodos_ordenados = sorted(periodos, key=lambda x: x['inicio'])
    
    total_dias = 0
    periodos_consolidados = []
    
    for periodo in periodos_ordenados:
        inicio = parse_date(periodo['inicio'])
        fim = parse_date(periodo['fim'])
        
        if inicio and fim:
            # Verificar sobreposição com períodos já consolidados
            periodo_atual = (inicio, fim)
            periodos_consolidados = consolidar_periodos(periodos_consolidados, periodo_atual)
    
    # Calcular total de dias dos períodos consolidados
    for periodo in periodos_consolidados:
        inicio, fim = periodo
        delta = fim - inicio
        total_dias += delta.days + 1  # +1 para incluir o dia final
    
    anos = total_dias // 365
    meses = (total_dias % 365) // 30
    dias = (total_dias % 365) % 30
    
    return anos, meses, dias

# Função para consolidar períodos sobrepostos
def consolidar_periodos(periodos_existentes, novo_periodo):
    inicio_novo, fim_novo = novo_periodo
    periodos_consolidados = []
    periodo_inserido = False
    
    for periodo_existente in periodos_existentes:
        inicio_existente, fim_existente = periodo_existente
        
        # Verificar se há sobreposição
        if (inicio_novo <= fim_existente and fim_novo >= inicio_existente):
            # Há sobreposição - consolidar
            inicio_novo = min(inicio_novo, inicio_existente)
            fim_novo = max(fim_novo, fim_existente)
        else:
            periodos_consolidados.append(periodo_existente)
    
    # Adicionar o período consolidado
    periodos_consolidados.append((inicio_novo, fim_novo))
    
    # Reordenar
    periodos_consolidados.sort(key=lambda x: x[0])
    
    return periodos_consolidados

# Função para calcular RMI CORRIGIDA
def calcular_rmi(salarios, parametros):
    if salarios.empty:
        return 0.0
    
    # Garantir que as competências estão em ordem crescente
    salarios_ordenados = salarios.sort_values('Competência')
    
    # Pegar os últimos 12 salários (ou todos se menos de 12)
    ultimos_salarios = salarios_ordenados.tail(12)
    
    # Calcular média dos 80% maiores salários (regra real do INSS)
    salarios_ordenados_valor = ultimos_salarios['Salário'].sort_values(ascending=False)
    qtd_considerar = max(1, int(len(salarios_ordenados_valor) * 0.8))
    salarios_considerados = salarios_ordenados_valor.head(qtd_considerar)
    media_salarios = salarios_considerados.mean()
    
    # Aplicar teto do INSS
    competencia_atual = datetime.now().strftime("%Y-%m")
    teto_atual = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
    
    rmi = min(media_salarios, teto_atual)
    
    # Aplicar fator previdenciário se necessário
    if parametros.get('fator_previdenciario', 0) > 0:
        rmi = rmi * parametros['fator_previdenciario']
    
    return round(rmi, 2)

# Função para salvar dados em JSON CORRIGIDA
def salvar_dados():
    dados = {
        'dados_segurado': st.session_state.dados_segurado,
        'periodos_contribuicao': [
            {
                'inicio': p['inicio'].isoformat() if hasattr(p['inicio'], 'isoformat') else str(p['inicio']),
                'fim': p['fim'].isoformat() if hasattr(p['fim'], 'isoformat') else str(p['fim']),
                'descricao': p['descricao']
            } for p in st.session_state.periodos_contribuicao
        ],
        'salarios': [
            {
                'Competência': s['Competência'].isoformat() if hasattr(s['Competência'], 'isoformat') else str(s['Competência']),
                'Salário': s['Salário'],
                'Origem': s['Origem']
            } for s in st.session_state.salarios.to_dict('records')
        ],
        'parametros': st.session_state.parametros
    }
    return json.dumps(dados, indent=2, default=str)

# Função para carregar dados de JSON CORRIGIDA
def carregar_dados(arquivo):
    try:
        dados = json.load(arquivo)
        st.session_state.dados_segurado = dados['dados_segurado']
        
        # Corrigir carregamento de períodos
        st.session_state.periodos_contribuicao = []
        for periodo in dados['periodos_contribuicao']:
            st.session_state.periodos_contribuicao.append({
                'inicio': parse_date(periodo['inicio']),
                'fim': parse_date(periodo['fim']),
                'descricao': periodo['descricao']
            })
        
        # Corrigir carregamento de salários
        salarios_data = []
        for salario in dados['salarios']:
            salarios_data.append({
                'Competência': parse_date(salario['Competência']),
                'Salário': salario['Salário'],
                'Origem': salario['Origem']
            })
        
        st.session_state.salarios = pd.DataFrame(salarios_data)
        st.session_state.parametros = dados['parametros']
        st.success("Dados carregados com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

# Restante do código permanece igual...

# Inicializar estado da sessão
init_session_state()

# Cabeçalho
st.title("🧮 Calculadora de Benefícios Previdenciários")
st.markdown("---")

# Barra lateral com ações
with st.sidebar:
    st.header("Ações")
    
    # Botões de salvar e carregar
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salvar", use_container_width=True):
            dados_json = salvar_dados()
            st.download_button(
                label="Baixar Dados",
                data=dados_json,
                file_name="calculo_beneficios.json",
                mime="application/json",
                use_container_width=True
            )
    
    with col2:
        arquivo_carregado = st.file_uploader(
            "Carregar Dados",
            type=["json"],
            key="file_uploader",
            help="Carregar um arquivo JSON com dados salvos"
        )
        if arquivo_carregado is not None:
            carregar_dados(arquivo_carregado)
    
    st.markdown("---")
    
    # Botão de limpar dados
    if st.button("🗑️ Limpar Tudo", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session_state()
        st.rerun()
    
    st.markdown("---")
    
    # Informações do sistema
    st.subheader("Informações")
    st.write(f"**Períodos cadastrados:** {len(st.session_state.periodos_contribuicao)}")
    st.write(f"**Salários cadastrados:** {len(st.session_state.salarios)}")
    
    # Valores atuais
    competencia_atual = datetime.now().strftime("%Y-%m")
    dados_atuais = dados_historicos.get(competencia_atual, {})
    
    if dados_atuais:
        st.markdown("---")
        st.subheader("Valores Atuais")
        st.write(f"**Salário Mínimo:** R$ {dados_atuais['piso']:,.2f}")
        st.write(f"**Teto INSS:** R$ {dados_atuais['teto']:,.2f}")

# Abas principais
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Parâmetros", 
    "📅 Períodos", 
    "💰 Salários", 
    "⏱️ Cálculo Tempo", 
    "📊 Cálculo RMI"
])

# Aba 1: Parâmetros
with tab1:
    st.header("Parâmetros do Cálculo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Dados do Segurado")
        st.session_state.dados_segurado['nome'] = st.text_input(
            "Nome Completo",
            value=st.session_state.dados_segurado['nome']
        )
        
        st.session_state.dados_segurado['nascimento'] = st.date_input(
            "Data de Nascimento",
            value=st.session_state.dados_segurado['nascimento']
        )
        
        st.session_state.dados_segurado['sexo'] = st.selectbox(
            "Sexo",
            options=["Masculino", "Feminino"],
            index=["Masculino", "Feminino"].index(st.session_state.dados_segurado['sexo'])
        )
    
    with col2:
        st.subheader("Parâmetros do Benefício")
        st.session_state.parametros['tipo_beneficio'] = st.selectbox(
            "Tipo de Benefício",
            options=[
                "Aposentadoria por Idade",
                "Aposentadoria por Tempo de Contribuição",
                "Aposentadoria Especial",
                "Auxílio Doença",
                "Aposentadoria por Invalidez"
            ],
            index=["Aposentadoria por Idade", "Aposentadoria por Tempo de Contribuição", 
                   "Aposentadoria Especial", "Auxílio Doença", 
                   "Aposentadoria por Invalidez"].index(st.session_state.parametros['tipo_beneficio'])
        )
        
        st.session_state.parametros['data_inicio'] = st.date_input(
            "Data de Início do Benefício",
            value=st.session_state.parametros['data_inicio']
        )
        
        st.session_state.parametros['fator_previdenciario'] = st.number_input(
            "Fator Previdenciário (se aplicável)",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.parametros['fator_previdenciario'],
            step=0.01
        )

# Aba 2: Períodos
with tab2:
    st.header("Períodos de Contribuição")
    
    # Formulário para adicionar novo período
    with st.expander("Adicionar Novo Período", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            inicio = st.date_input("Data de Início")
        
        with col2:
            fim = st.date_input("Data de Fim")
        
        descricao = st.text_input("Descrição do Período")
        
        if st.button("Adicionar Período", use_container_width=True):
            if inicio and fim and inicio < fim:
                novo_periodo = {
                    'inicio': inicio,
                    'fim': fim,
                    'descricao': descricao
                }
                st.session_state.periodos_contribuicao.append(novo_periodo)
                st.success("Período adicionado com sucesso!")
                st.rerun()
            else:
                st.error("Preencha corretamente as datas (início deve ser anterior ao fim)")
    
    # Lista de períodos cadastrados
    if st.session_state.periodos_contribuicao:
        st.subheader("Períodos Cadastrados")
        
        # Criar DataFrame para exibição
        periodos_df = pd.DataFrame([
            {
                'Início': p['inicio'].strftime('%d/%m/%Y'),
                'Fim': p['fim'].strftime('%d/%m/%Y'),
                'Descrição': p['descricao']
            } for p in st.session_state.periodos_contribuicao
        ])
        
        st.dataframe(periodos_df, use_container_width=True)
        
        # Botão para remover períodos
        if st.button("Remover Último Período", use_container_width=True):
            st.session_state.periodos_contribuicao.pop()
            st.rerun()
    else:
        st.info("Nenhum período de contribuição cadastrado.")

# Aba 3: Salários
with tab3:
    st.header("Salários de Contribuição")
    
    # Formulário para adicionar salário
    with st.expander("Adicionar Salário", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            competencia = st.date_input("Competência (mês/ano)", value=date.today().replace(day=1))
        
        with col2:
            valor = st.number_input("Valor do Salário", min_value=0.0, step=100.0)
        
        origem = st.selectbox(
            "Origem",
            options=["Informado pelo segurado", "CNIS", "Outros"]
        )
        
        if st.button("Adicionar Salário", use_container_width=True):
            if valor > 0:
                novo_salario = {
                    'Competência': competencia,
                    'Salário': valor,
                    'Origem': origem
                }
                st.session_state.salarios = pd.concat([
                    st.session_state.salarios,
                    pd.DataFrame([novo_salario])
                ], ignore_index=True)
                st.success("Salário adicionado com sucesso!")
                st.rerun()
            else:
                st.error("O valor do salário deve ser maior que zero")
    
    # Tabela de salários
    if not st.session_state.salarios.empty:
        st.subheader("Salários Cadastrados")
        
        # Formatar competência para exibição
        salarios_exibicao = st.session_state.salarios.copy()
        salarios_exibicao['Competência'] = salarios_exibicao['Competência'].dt.strftime('%m/%Y')
        
        st.data_editor(
            salarios_exibicao,
            column_config={
                "Salário": st.column_config.NumberColumn(format="R$ %.2f"),
                "Competência": st.column_config.TextColumn("Competência"),
                "Origem": st.column_config.TextColumn("Origem")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Botão para remover último salário
        if st.button("Remover Último Salário", use_container_width=True):
            st.session_state.salarios = st.session_state.salarios.iloc[:-1]
            st.rerun()
    else:
        st.info("Nenhum salário cadastrado.")

# Aba 4: Cálculo de Tempo
with tab4:
    st.header("Cálculo de Tempo de Contribuição")
    
    if st.session_state.periodos_contribuicao:
        # Calcular tempo total
        anos, meses, dias = calcular_tempo_contribuicao(st.session_state.periodos_contribuicao)
        
        st.subheader("Resultado do Cálculo")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Anos", anos)
        
        with col2:
            st.metric("Meses", meses)
        
        with col3:
            st.metric("Dias", dias)
        
        st.markdown("---")
        
        # Detalhamento dos períodos
        st.subheader("Detalhamento dos Períodos")
        
        detalhes_df = pd.DataFrame([
            {
                'Período': f"{p['inicio'].strftime('%d/%m/%Y')} a {p['fim'].strftime('%d/%m/%Y')}",
                'Descrição': p['descricao'],
                'Dias': (p['fim'] - p['inicio']).days + 1
            } for p in st.session_state.periodos_contribuicao
        ])
        
        st.dataframe(detalhes_df, use_container_width=True)
        
        # Gráfico de tempo por período
        st.subheader("Distribuição do Tempo de Contribuição")
        
        chart_data = pd.DataFrame([
            {
                'Período': p['descricao'][:20] + '...' if len(p['descricao']) > 20 else p['descricao'],
                'Dias': (p['fim'] - p['inicio']).days + 1
            } for p in st.session_state.periodos_contribuicao
        ])
        
        st.bar_chart(chart_data, x='Período', y='Dias', use_container_width=True)
    else:
        st.warning("Nenhum período de contribuição cadastrado para calcular o tempo.")

# Aba 5: Cálculo RMI
with tab5:
    st.header("Cálculo da Renda Mensal Inicial (RMI)")
    
    if not st.session_state.salarios.empty:
        # Calcular RMI
        rmi = calcular_rmi(st.session_state.salarios, st.session_state.parametros)
        
        st.subheader("Resultado do Cálculo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("RMI Calculada", f"R$ {rmi:,.2f}")
        
        with col2:
            competencia_atual = datetime.now().strftime("%Y-%m")
            teto_atual = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
            st.metric("Teto INSS Atual", f"R$ {teto_atual:,.2f}")
        
        st.markdown("---")
        
        # Detalhamento do cálculo
        st.subheader("Detalhamento do Cálculo")
        
        # Média dos salários
        salarios_ordenados = st.session_state.salarios.sort_values('Competência')
        ultimos_salarios = salarios_ordenados.tail(12)
        
        # Calcular média dos 80% maiores
        salarios_ordenados_valor = ultimos_salarios['Salário'].sort_values(ascending=False)
        qtd_considerar = max(1, int(len(salarios_ordenados_valor) * 0.8))
        salarios_considerados = salarios_ordenados_valor.head(qtd_considerar)
        media_salarios = salarios_considerados.mean()
        
        st.write(f"**Total de salários considerados:** {len(ultimos_salarios)}")
        st.write(f"**Média dos {qtd_considerar} maiores salários:** R$ {media_salarios:,.2f}")
        st.write(f"**Teto do INSS aplicado:** R$ {teto_atual:,.2f}")
        
        if st.session_state.parametros['fator_previdenciario'] > 0:
            st.write(f"**Fator Previdenciário aplicado:** {st.session_state.parametros['fator_previdenciario']:.2f}")
        
        st.markdown("---")
        
        # Tabela com salários utilizados
        st.subheader("Salários Utilizados no Cálculo")
        
        salarios_exibicao = ultimos_salarios.copy()
        salarios_exibicao['Competência'] = salarios_exibicao['Competência'].dt.strftime('%m/%Y')
        
        st.data_editor(
            salarios_exibicao,
            column_config={
                "Salário": st.column_config.NumberColumn(format="R$ %.2f"),
                "Competência": st.column_config.TextColumn("Competência"),
                "Origem": st.column_config.TextColumn("Origem")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico de evolução salarial
        st.subheader("Evolução Salarial")
        
        chart_data = st.session_state.salarios.copy()
        chart_data['Competência'] = chart_data['Competência'].dt.strftime('%m/%Y')
        
        st.line_chart(chart_data, x='Competência', y='Salário', use_container_width=True)
    else:
        st.warning("Nenhum salário cadastrado para calcular a RMI.")

# Rodapé
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>© 2024 - Calculadora de Benefícios Previdenciários</p>
        <p>Ferramenta para cálculos simplificados - Não substitui assessoria jurídica especializada</p>
    </div>
    """,
    unsafe_allow_html=True
)
