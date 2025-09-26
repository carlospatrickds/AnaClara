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
        date_str = date_str.split(' ')[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%Y-%m"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                if fmt in ("%m/%Y", "%Y-%m"):
                    return dt.replace(day=1)
                return dt
            except ValueError:
                continue
    elif isinstance(date_str, date):
        return date_str
    return date.today()

# Função para inicializar o estado da sessão
def init_session_state():
    if 'dados_segurado' not in st.session_state:
        st.session_state.dados_segurado = {
            'nome': '',
            'nascimento': date(1980, 1, 1),
            'sexo': 'Masculino'
        }
    if 'vinculos' not in st.session_state:
        st.session_state.vinculos = {}
    if 'salarios_consolidados' not in st.session_state:
        st.session_state.salarios_consolidados = pd.DataFrame(columns=['Competência', 'Salário', 'Origem', 'Seq_Vinculo'])
    if 'parametros' not in st.session_state:
        st.session_state.parametros = {
            'tipo_beneficio': 'Aposentadoria por Idade',
            'data_inicio': date.today(),
            'tempo_contribuicao': 0,
            'fator_previdenciario': 0.0
        }
    if 'consolidar_vinculos' not in st.session_state:
        st.session_state.consolidar_vinculos = True

# Função para consolidar períodos sobrepostos
def consolidar_periodos(periodos):
    if not periodos:
        return []
    
    periodos_tuplas = []
    for p in periodos:
        inicio = parse_date(p['inicio'])
        fim = parse_date(p['fim'])
        periodos_tuplas.append((inicio, fim))
    
    periodos_tuplas.sort(key=lambda x: x[0])
    
    consolidados = []
    current_start, current_end = periodos_tuplas[0]
    
    for inicio, fim in periodos_tuplas[1:]:
        if inicio <= current_end + timedelta(days=1):
            current_end = max(current_end, fim)
        else:
            consolidados.append((current_start, current_end))
            current_start, current_end = inicio, fim
    
    consolidados.append((current_start, current_end))
    return consolidados

# Função para calcular tempo de contribuição
def calcular_tempo_contribuicao():
    if not st.session_state.vinculos:
        return 0, 0, 0
    
    periodos = []
    for seq, vinculo in st.session_state.vinculos.items():
        if vinculo['dados'].get('data_inicio') and vinculo['dados'].get('data_fim'):
            periodos.append({
                'inicio': parse_date(vinculo['dados']['data_inicio']),
                'fim': parse_date(vinculo['dados']['data_fim'])
            })
    
    periodos_consolidados = consolidar_periodos(periodos)
    total_dias = 0
    
    for inicio, fim in periodos_consolidados:
        total_dias += (fim - inicio).days + 1
    
    anos = total_dias // 365
    meses = (total_dias % 365) // 30
    dias = (total_dias % 365) % 30
    return anos, meses, dias

# Função para calcular RMI
def calcular_rmi(parametros):
    salarios_df = st.session_state.salarios_consolidados
    if salarios_df.empty:
        return 0.0
    
    salarios_processados = processar_salarios(salarios_df)
    if salarios_processados.empty:
        return 0.0
        
    salarios_ordenados = salarios_processados.sort_values('Competência')
    ultimos_12 = salarios_ordenados.tail(12)
    
    if ultimos_12.empty:
        return 0.0
        
    valores_ordenados = ultimos_12['Salário'].sort_values(ascending=False)
    qtd_considerar = max(1, int(len(valores_ordenados) * 0.8))
    media = valores_ordenados.head(qtd_considerar).mean()
    
    competencia_atual = datetime.now().strftime("%Y-%m")
    teto_atual = dados_historicos.get(competencia_atual, {}).get('teto', 7786.02)
    rmi = min(media, teto_atual)
    
    if parametros.get('fator_previdenciario', 0) > 0:
        rmi *= parametros['fator_previdenciario']
    
    return round(rmi, 2)

# Função para processar salários
def processar_salarios(salarios_df):
    if salarios_df.empty:
        return pd.DataFrame(columns=['Competência', 'Salário', 'Origem', 'Seq_Vinculo'])
    
    df = salarios_df.copy()
    
    def converter_competencia(comp):
        if isinstance(comp, str):
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
        return pd.DataFrame(columns=['Competência', 'Salário', 'Origem', 'Seq_Vinculo'])
    
    df = df.sort_values('Competência_DateTime')
    df['Competência'] = df['Competência_DateTime'].dt.strftime('%m/%Y')
    df = df[['Competência', 'Salário', 'Origem', 'Seq_Vinculo']]
    
    return df

# Função para consolidar todos os vínculos
def consolidar_vinculos():
    todos_salarios = []
    for seq, vinculo in st.session_state.vinculos.items():
        for salario in vinculo['salarios']:
            todos_salarios.append({
                'Competência': salario['competencia'],
                'Salário': salario['valor'],
                'Origem': f"Seq {seq}",
                'Seq_Vinculo': seq
            })
    
    if todos_salarios:
        st.session_state.salarios_consolidados = pd.DataFrame(todos_salarios)
    else:
        st.session_state.salarios_consolidados = pd.DataFrame(columns=['Competência', 'Salário', 'Origem', 'Seq_Vinculo'])

# Função para processar texto CNIS
def processar_texto_cnis_melhorado(texto):
    try:
        st.session_state.vinculos = {}
        linhas = texto.split('\n')
        
        seq_atual = None
        vinculo_atual = {}
        processando_remuneracoes = False
        remuneracoes_vinculo = []
        
        for i, linha in enumerate(linhas):
            l = linha.strip()
            
            # Identifica início de um novo vínculo
            if re.match(r'^\d+\s+[\d\.\-/]', l) or re.match(r'^\d+\s+[A-Z]', l):
                match_seq = re.search(r'^(\d+)', l)
                if match_seq:
                    seq = match_seq.group(1)
                    
                    if seq_atual is not None and vinculo_atual:
                        st.session_state.vinculos[seq_atual] = {
                            'dados': vinculo_atual.copy(),
                            'salarios': remuneracoes_vinculo.copy()
                        }
                    
                    seq_atual = seq
                    vinculo_atual = {'seq': seq}
                    remuneracoes_vinculo = []
                    processando_remuneracoes = False
                    
                    partes = re.split(r'\s{2,}', l)
                    if len(partes) >= 3:
                        vinculo_atual['nit'] = partes[1] if len(partes) > 1 else ''
            
            # Identifica tipo de vínculo
            elif 'Empregado' in l:
                vinculo_atual['tipo'] = 'EMPREGADO'
                vinculo_atual['tipo_filiado'] = 'Empregado'
            elif 'Contribuinte Individual' in l:
                vinculo_atual['tipo'] = 'CONTRIBUINTE_INDIVIDUAL'
                vinculo_atual['tipo_filiado'] = 'Contribuinte Individual'
            
            # Identifica tabela de remunerações
            elif 'Competência' in l and ('Remuneração' in l or 'Salário Contribuição' in l):
                processando_remuneracoes = True
                if 'tipo' not in vinculo_atual:
                    if 'Salário Contribuição' in l:
                        vinculo_atual['tipo'] = 'CONTRIBUINTE_INDIVIDUAL'
                    else:
                        vinculo_atual['tipo'] = 'EMPREGADO'
            
            # Processa linhas de remuneração
            elif processando_remuneracoes:
                if vinculo_atual.get('tipo') == 'CONTRIBUINTE_INDIVIDUAL':
                    padroes = re.findall(r'(\d{2}/\d{4})\s+([\d\.,]+)', l)
                    for comp, salario in padroes:
                        try:
                            valor_salario = float(salario.replace('.', '').replace(',', '.'))
                            remuneracoes_vinculo.append({
                                'competencia': comp,
                                'valor': valor_salario,
                                'tipo': 'SALARIO_CONTRIBUICAO'
                            })
                        except ValueError:
                            continue
                else:
                    competencias = re.findall(r'(\d{2}/\d{4})', l)
                    valores = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', l)
                    
                    for comp, val in zip(competencias, valores):
                        try:
                            valor_float = float(val.replace('.', '').replace(',', '.'))
                            remuneracoes_vinculo.append({
                                'competencia': comp,
                                'valor': valor_float,
                                'tipo': 'REMUNERACAO'
                            })
                        except ValueError:
                            continue
            
            # Fim da tabela de remunerações
            elif processando_remuneracoes and (l == '' or re.match(r'^\d+\s+', l)):
                processando_remuneracoes = False
            
            # Extrai dados pessoais
            elif 'Nome:' in l and not st.session_state.dados_segurado['nome']:
                m = re.search(r'Nome:\s*(.+)', l)
                if m: 
                    st.session_state.dados_segurado['nome'] = m.group(1).strip()
            elif 'Data de nascimento:' in l:
                m = re.search(r'Data de nascimento:\s*(\d{2}/\d{2}/\d{4})', l)
                if m:
                    try:
                        st.session_state.dados_segurado['nascimento'] = datetime.strptime(m.group(1), '%d/%m/%Y').date()
                    except:
                        pass
        
        # Adiciona o último vínculo processado
        if seq_atual is not None and vinculo_atual:
            st.session_state.vinculos[seq_atual] = {
                'dados': vinculo_atual.copy(),
                'salarios': remuneracoes_vinculo.copy()
            }
        
        consolidar_vinculos()
        
        total_salarios = sum(len(v['salarios']) for v in st.session_state.vinculos.values())
        st.success(f"✅ Vínculos processados: {len(st.session_state.vinculos)} | Salários: {total_salarios}")
        st.rerun()
        
    except Exception as e:
        st.error(f"Erro no processamento: {e}")

# Funções de salvar e carregar
def salvar_dados():
    dados = {
        'dados_segurado': st.session_state.dados_segurado,
        'vinculos': st.session_state.vinculos,
        'salarios_consolidados': st.session_state.salarios_consolidados.to_dict('records'),
        'parametros': st.session_state.parametros,
        'consolidar_vinculos': st.session_state.consolidar_vinculos
    }
    return json.dumps(dados, indent=2, default=str)

def carregar_dados(arquivo):
    try:
        dados = json.load(arquivo)
        st.session_state.dados_segurado = dados['dados_segurado']
        st.session_state.vinculos = dados['vinculos']
        st.session_state.salarios_consolidados = pd.DataFrame(dados['salarios_consolidados'])
        st.session_state.parametros = dados['parametros']
        st.session_state.consolidar_vinculos = dados.get('consolidar_vinculos', True)
        st.success("Dados carregados com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")

# --- INTERFACE PRINCIPAL ---
def main():
    init_session_state()
    
    st.title("🧮 Calculadora de Benefícios Previdenciários")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Gerenciar Dados")
        
        uploaded_file = st.file_uploader("Carregar dados salvos", type=['json'])
        if uploaded_file:
            carregar_dados(uploaded_file)
        
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
        
        # Usar session_state para armazenar a opção
        if 'opcao_cnis' not in st.session_state:
            st.session_state.opcao_cnis = "Texto"
        
        opcao_cnis = st.radio("Formato do CNIS:", ["Texto", "PDF"], 
                             index=0 if st.session_state.opcao_cnis == "Texto" else 1,
                             key="opcao_cnis_radio")
        
        st.session_state.opcao_cnis = opcao_cnis
        
        if st.session_state.opcao_cnis == "Texto":
            texto_cnis = st.text_area("Cole o texto do CNIS aqui:", height=200)
            if st.button("Processar Texto CNIS") and texto_cnis:
                processar_texto_cnis_melhorado(texto_cnis)
        else:
            pdf_cnis = st.file_uploader("Upload PDF CNIS", type=['pdf'])
            if st.button("Processar PDF CNIS") and pdf_cnis:
                try:
                    reader = PdfReader(pdf_cnis)
                    texto = ""
                    for pagina in reader.pages:
                        texto_pagina = pagina.extract_text()
                        if texto_pagina:
                            texto += texto_pagina + "\n"
                    if texto.strip():
                        processar_texto_cnis_melhorado(texto)
                    else:
                        st.warning("Não foi possível extrair texto do PDF.")
                except Exception as e:
                    st.error(f"Erro ao ler PDF: {e}")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Dados Pessoais", "📋 Vínculos", "💰 Salários", "📊 Cálculo"])
    
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
        st.header("Vínculos Previdenciários")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            consolidar = st.checkbox("Consolidar vínculos", value=st.session_state.consolidar_vinculos)
            if consolidar != st.session_state.consolidar_vinculos:
                st.session_state.consolidar_vinculos = consolidar
                if consolidar:
                    consolidar_vinculos()
                st.rerun()
        
        if st.session_state.vinculos:
            for seq, vinculo in st.session_state.vinculos.items():
                with st.expander(f"📌 Seq. {seq}: {vinculo['dados'].get('origem_vinculo', 'N/I')}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Tipo:** {vinculo['dados'].get('tipo_filiado', 'N/I')}")
                        st.write(f"**Início:** {vinculo['dados'].get('data_inicio', 'N/I')}")
                        st.write(f"**Fim:** {vinculo['dados'].get('data_fim', 'N/I')}")
                    
                    with col2:
                        tipo = vinculo['dados'].get('tipo', 'INDEFINIDO')
                        st.write(f"**Categoria:** {tipo}")
                        st.write(f"**NIT:** {vinculo['dados'].get('nit', 'N/I')}")
                    
                    with col3:
                        qtd_salarios = len(vinculo['salarios'])
                        st.write(f"**Salários:** {qtd_salarios}")
                        if qtd_salarios > 0:
                            primeiro = vinculo['salarios'][0]['competencia']
                            ultimo = vinculo['salarios'][-1]['competencia']
                            st.write(f"**Período:** {primeiro} a {ultimo}")
                    
                    if vinculo['salarios']:
                        df_vinculo = pd.DataFrame(vinculo['salarios'])
                        st.dataframe(df_vinculo, use_container_width=True, hide_index=True)
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button(f"✅ Incluir no cálculo", key=f"inc_{seq}"):
                            for salario in vinculo['salarios']:
                                novo_salario = {
                                    'Competência': salario['competencia'],
                                    'Salário': salario['valor'],
                                    'Origem': f"Seq {seq}",
                                    'Seq_Vinculo': seq
                                }
                                st.session_state.salarios_consolidados = pd.concat([
                                    st.session_state.salarios_consolidados,
                                    pd.DataFrame([novo_salario])
                                ], ignore_index=True)
                            st.success(f"Vínculo {seq} incluído no cálculo!")
                            st.rerun()
                    
                    with col_btn2:
                        if st.button(f"❌ Excluir vínculo", key=f"exc_{seq}"):
                            del st.session_state.vinculos[seq]
                            st.session_state.salarios_consolidados = st.session_state.salarios_consolidados[
                                st.session_state.salarios_consolidados['Seq_Vinculo'] != seq
                            ]
                            st.success(f"Vínculo {seq} excluído!")
                            st.rerun()
        else:
            st.info("Nenhum vínculo previdenciário identificado. Importe um CNIS para começar.")
    
    with tab3:
        st.header("Salários de Contribuição Consolidados")
        
        if not st.session_state.salarios_consolidados.empty:
            salarios_processados = processar_salarios(st.session_state.salarios_consolidados)
            
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 Reconsolidar Todos"):
                    consolidar_vinculos()
                    st.rerun()
            
            st.dataframe(salarios_processados, use_container_width=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de registros", len(salarios_processados))
            with col2:
                st.metric("Maior salário", f"R$ {salarios_processados['Salário'].max():.2f}")
            with col3:
                st.metric("Média", f"R$ {salarios_processados['Salário'].mean():.2f}")
            with col4:
                vincs_unicos = salarios_processados['Seq_Vinculo'].nunique()
                st.metric("Vínculos", vincs_unicos)
        else:
            st.info("Nenhum salário consolidado. Adicione vínculos na aba anterior.")
    
    with tab4:
        st.header("Cálculo do Benefício")
        
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
            
            anos, meses, dias = calcular_tempo_contribuicao()
            st.session_state.parametros['tempo_contribuicao'] = anos
            st.metric("Tempo de contribuição", f"{anos} anos, {meses} meses")
        
        if st.button("🎯 Calcular RMI", type="primary"):
            if st.session_state.salarios_consolidados.empty:
                st.error("Adicione pelo menos um vínculo com salários para calcular o RMI!")
            else:
                rmi = calcular_rmi(st.session_state.parametros)
                st.session_state.parametros['rmi_calculado'] = rmi
                
                st.success(f"**Renda Mensal Inicial (RMI) calculada:** R$ {rmi:,.2f}")
                
                with st.expander("📈 Detalhes do cálculo"):
                    salarios_processados = processar_salarios(st.session_state.salarios_consolidados)
                    if not salarios_processados.empty:
                        ultimos_12 = salarios_processados.tail(12)
                        st.write("**Últimos 12 salários considerados:**")
                        st.dataframe(ultimos_12)
                        
                        teto_atual = dados_historicos.get(datetime.now().strftime("%Y-%m"), {}).get('teto', 7786.02)
                        st.write(f"**Teto do INSS aplicado:** R$ {teto_atual:,.2f}")
    
    st.markdown("---")
    st.caption("Calculadora desenvolvida para fins educacionais - Consulte um especialista para análise precisa.")

# Executa a aplicação
if __name__ == "__main__":
    main()
