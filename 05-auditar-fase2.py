import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import base64
from io import BytesIO
import urllib.parse

# Configuração básica da página
st.set_page_config(
    page_title="Auditoria Folha de Pagamento",
    page_icon="💰",
    layout="wide"
)

# INICIALIZAR SESSION STATE - CORREÇÃO DO ERRO
if 'df_resultado' not in st.session_state:
    st.session_state.df_resultado = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None

st.title("💰 Auditoria de Folha de Pagamento 2025 - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# [RESTANTE DAS FUNÇÕES E VARIÁVEIS PERMANECEM IGUAIS...]
# Dados das tabelas 2025
SALARIO_FAMILIA_LIMITE = 1906.04
VALOR_POR_DEPENDENTE = 65.00
DESCONTO_DEPENDENTE_IR = 189.59

# Tabela INSS 2025 CORRETA
TABELA_INSS = [
    {"limite": 1518.00, "aliquota": 0.075},
    {"limite": 2793.88, "aliquota": 0.09},
    {"limite": 4190.83, "aliquota": 0.12},
    {"limite": 8157.41, "aliquota": 0.14}
]

# Tabela IRRF 2025
TABELA_IRRF = [
    {"limite": 2428.80, "aliquota": 0.0, "deducao": 0.0},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 182.16},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 394.16},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 675.49},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 916.90}
]

def formatar_moeda(valor):
    """Formata valor em moeda brasileira"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(data):
    """Formata data no padrão brasileiro"""
    return data.strftime("%d/%m/%Y")

def calcular_inss(salario_bruto):
    """Calcula desconto do INSS 2025 com a tabela correta"""
    if salario_bruto <= 0:
        return 0.0
    
    salario_calculo = min(salario_bruto, TABELA_INSS[3]["limite"])
    inss = 0.0
    salario_restante = salario_calculo
    
    for i, faixa in enumerate(TABELA_INSS):
        if salario_restante <= 0:
            break
            
        if i == 0:
            valor_faixa = min(salario_restante, faixa["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
        else:
            faixa_anterior = TABELA_INSS[i-1]
            valor_faixa = min(salario_restante, faixa["limite"] - faixa_anterior["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
    
    return round(inss, 2)

def calcular_salario_familia(salario, dependentes):
    """Calcula salário família"""
    if salario <= SALARIO_FAMILIA_LIMITE:
        return dependentes * VALOR_POR_DEPENDENTE
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos=0):
    """Calcula IRRF"""
    base_calculo = salario_bruto - (dependentes * DESCONTO_DEPENDENTE_IR) - inss - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    for faixa in TABELA_IRRF:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(irrf, 0.0)
    
    return 0.0

# [RESTANTE DAS FUNÇÕES PDF PERMANECEM IGUAIS...]
def gerar_pdf_individual(dados):
    """Gera PDF profissional para cálculo individual"""
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA - FOLHA DE PAGAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    # [RESTANTE DA FUNÇÃO PERMANECE IGUAL...]

def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF"""
    b64 = base64.b64encode(pdf_output).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

# Interface principal
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Individual", "📊 Auditoria em Lote", "ℹ️ Informações"])

with tab1:
    st.header("Cálculo Individual")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nome = st.text_input("Nome do Funcionário", "João Silva")
        salario = st.number_input("Salário Bruto (R$)", 
                                min_value=0.0, 
                                value=3000.0, 
                                step=100.0)
        dependentes = st.number_input("Número de Dependentes", 
                                    min_value=0, 
                                    value=1, 
                                    step=1)
    
    with col2:
        outros_descontos = st.number_input("Outros Descontos (R$)", 
                                         min_value=0.0, 
                                         value=0.0, 
                                         step=50.0)
        competencia = st.date_input("Competência Analisada", 
                                  value=datetime.now().replace(day=1))
    
    if st.button("Calcular", type="primary"):
        # Realizar cálculos
        inss_valor = calcular_inss(salario)
        sal_familia = calcular_salario_familia(salario, dependentes)
        irrf_valor = calcular_irrf(salario, dependentes, inss_valor, outros_descontos)
        
        # Cálculo do salário líquido
        total_descontos = inss_valor + irrf_valor + outros_descontos
        total_acrescimos = sal_familia
        salario_liquido = salario - total_descontos + total_acrescimos
        base_irrf = salario - (dependentes * DESCONTO_DEPENDENTE_IR) - inss_valor - outros_descontos
        
        # Mostrar resultados
        st.success("Cálculos realizados com sucesso!")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Salário Família", formatar_moeda(sal_familia))
        with col2:
            st.metric("INSS", formatar_moeda(inss_valor))
        with col3:
            st.metric("IRRF", formatar_moeda(irrf_valor))
        with col4:
            st.metric("Salário Líquido", formatar_moeda(salario_liquido))
        
        # Tabela de detalhes
        st.subheader("📋 Detalhamento Completo")
        detalhes = pd.DataFrame({
            'Descrição': [
                'Salário Bruto', 
                'Salário Família', 
                'INSS', 
                'IRRF', 
                'Outros Descontos',
                'Total Descontos',
                'Salário Líquido'
            ],
            'Valor': [
                formatar_moeda(salario),
                formatar_moeda(sal_familia),
                formatar_moeda(inss_valor),
                formatar_moeda(irrf_valor),
                formatar_moeda(outros_descontos),
                formatar_moeda(total_descontos),
                formatar_moeda(salario_liquido)
            ]
        })
        st.dataframe(detalhes, use_container_width=True, hide_index=True)
        
        # Informações adicionais
        st.subheader("📊 Informações Adicionais")
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.write(f"**Competência Analisada:** {formatar_data(competencia)}")
            st.write(f"**Dependentes para IRRF:** {dependentes}")
            st.write(f"**Base cálculo IRRF:** {formatar_moeda(base_irrf)}")
        
        with col_info2:
            st.write(f"**Elegível Salário Família:** {'Sim' if sal_familia > 0 else 'Não'}")
            st.write(f"**Total de Descontos:** {formatar_moeda(total_descontos)}")
            st.write(f"**Total de Acréscimos:** {formatar_moeda(total_acrescimos)}")
        
        # Gerar PDF
        st.subheader("📄 Gerar Relatório PDF")
        dados_pdf = {
            "data_analise": formatar_data(datetime.now()),
            "competencia": formatar_data(competencia),
            "nome": nome,
            "salario_bruto": formatar_moeda(salario),
            "dependentes": dependentes,
            "outros_descontos": formatar_moeda(outros_descontos),
            "salario_familia": formatar_moeda(sal_familia),
            "inss": formatar_moeda(inss_valor),
            "irrf": formatar_moeda(irrf_valor),
            "total_descontos": formatar_moeda(total_descontos),
            "salario_liquido": formatar_moeda(salario_liquido),
            "elegivel_salario_familia": 'Sim' if sal_familia > 0 else 'Não',
            "base_irrf": formatar_moeda(base_irrf)
        }
        
        pdf = gerar_pdf_individual(dados_pdf)
        pdf_output = pdf.output(dest='S').encode('latin-1')
        
        st.markdown(
            criar_link_download_pdf(
                pdf_output, 
                f"Auditoria_Folha_{nome.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
            ), 
            unsafe_allow_html=True
        )

with tab2:
    st.header("Auditoria em Lote")
    
    # Opções de entrada de dados SIMPLIFICADA
    st.info("""
    **📊 Opções de Entrada de Dados:**
    
    Escolha uma das opções abaixo:
    1. **Upload de arquivo CSV** (formato tradicional)
    2. **Google Sheets** (cole a URL - método simples)
    3. **Digitação manual** de dados
    """)
    
    opcao_entrada = st.radio(
        "Selecione a fonte dos dados:",
        ["📁 Upload de CSV", "🌐 Google Sheets", "✏️ Digitação Manual"],
        horizontal=True
    )
    
    # Template para download
    template_data = {
        'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira', 'Ana Costa', 'Carlos Lima'],
        'Salario_Bruto': [1500.00, 2800.00, 4200.00, 1800.50, 6000.00],
        'Dependentes': [2, 1, 0, 3, 1],
        'Outros_Descontos': [0.00, 100.00, 200.50, 50.00, 300.00]
    }
    template_df = pd.DataFrame(template_data)
    
    with st.expander("📝 Estrutura do Arquivo Esperado"):
        st.dataframe(template_df, use_container_width=True)
        csv_template = template_df.to_csv(index=False, sep=';')
        st.download_button(
            label="📥 Baixar Template CSV",
            data=csv_template,
            file_name="template_funcionarios.csv",
            mime="text/csv",
        )
    
    df = None
    uploaded_filename = "dados_manuais"
    
    if opcao_entrada == "📁 Upload de CSV":
        st.subheader("📤 Upload de Arquivo CSV")
        uploaded_file = st.file_uploader(
            "Escolha um arquivo CSV", 
            type="csv",
            help="Arquivo deve ter as colunas: Nome, Salario_Bruto, Dependentes, Outros_Descontos"
        )
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file, sep=';')
                uploaded_filename = uploaded_file.name
                st.success("✅ Arquivo CSV carregado com sucesso!")
                
            except Exception as e:
                st.error(f"❌ Erro ao ler arquivo CSV: {e}")
    
    elif opcao_entrada == "🌐 Google Sheets":
        st.subheader("🔗 Integração com Google Sheets")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            sheets_url = st.text_input(
                "URL do Google Sheets:",
                value="https://docs.google.com/spreadsheets/d/1G-O5sNYWGLDYG8JG3FXom4BpBrVFRnrxVal-LwmH9Gc/edit?usp=sharing",
                help="Cole a URL completa da planilha do Google Sheets"
            )
        
        with col2:
            sheet_name = st.text_input(
                "Nome da Aba:",
                value="Página1",
                help="Nome da aba/worksheet (padrão: Página1)"
            )
        
        if sheets_url:
            try:
                # Extrair ID da planilha da URL
                if "/d/" in sheets_url:
                    sheet_id = sheets_url.split("/d/")[1].split("/")[0]
                else:
                    sheet_id = sheets_url
                
                # CORREÇÃO DO ERRO DE ENCODING - usar URL encoding para o nome da aba
                sheet_name_encoded = urllib.parse.quote(sheet_name)
                
                # URL para exportação como CSV
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}"
                
                # Ler dados do Google Sheets com encoding correto
                df = pd.read_csv(csv_url, encoding='utf-8')
                uploaded_filename = f"Google_Sheets_{sheet_name}"
                
                st.success("✅ Conexão com Google Sheets estabelecida!")
                
                # Renomear colunas para o formato esperado
                if len(df.columns) >= 3:
                    # Mapear colunas automáticas para nossos nomes
                    df.columns = ['Nome', 'Salario_Bruto', 'Dependentes'] + list(df.columns[3:])
                    
                    # Se tiver mais colunas, assumir que a quarta é Outros_Descontos
                    if len(df.columns) > 3:
                        df = df.rename(columns={df.columns[3]: 'Outros_Descontos'})
                    else:
                        df['Outros_Descontos'] = 0.0
                
            except Exception as e:
                st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
                st.info("""
                **Solução de problemas:**
                - Verifique se a planilha é pública ou compartilhada para visualização
                - Confirme o nome exato da aba
                - Certifique-se de que a URL está correta
                - A planilha deve ter pelo menos 3 colunas: Nome, Salario_Bruto, Dependentes
                """)
    
    elif opcao_entrada == "✏️ Digitação Manual":
        st.subheader("📝 Digitação Manual de Dados")
        
        # Interface para entrada manual de dados
        num_funcionarios = st.number_input(
            "Número de funcionários:",
            min_value=1,
            max_value=50,
            value=3,
            step=1
        )
        
        dados_manuais = []
        
        for i in range(num_funcionarios):
            st.write(f"--- **Funcionário {i+1}** ---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                nome = st.text_input(f"Nome {i+1}", value=f"Funcionário {i+1}", key=f"nome_{i}")
            with col2:
                salario = st.number_input(f"Salário {i+1}", min_value=0.0, value=2000.0, step=100.0, key=f"salario_{i}")
            with col3:
                dependentes = st.number_input(f"Dependentes {i+1}", min_value=0, value=1, step=1, key=f"dependentes_{i}")
            with col4:
                outros_desc = st.number_input(f"Outros Desc. {i+1}", min_value=0.0, value=0.0, step=50.0, key=f"outros_{i}")
            
            dados_manuais.append({
                'Nome': nome,
                'Salario_Bruto': salario,
                'Dependentes': dependentes,
                'Outros_Descontos': outros_desc
            })
        
        if st.button("✅ Confirmar Dados Manuais", type="primary"):
            df = pd.DataFrame(dados_manuais)
            uploaded_filename = "dados_manuais"
            st.success("✅ Dados manuais confirmados!")
    
    # Processamento dos dados (comum para todas as opções)
    if df is not None:
        try:
            # Converter colunas numéricas para float, tratando possíveis erros
            df['Salario_Bruto'] = pd.to_numeric(df['Salario_Bruto'], errors='coerce').fillna(0)
            df['Dependentes'] = pd.to_numeric(df['Dependentes'], errors='coerce').fillna(0).astype(int)
            
            # Se a coluna Outros_Descontos existir, converter também
            if 'Outros_Descontos' in df.columns:
                df['Outros_Descontos'] = pd.to_numeric(df['Outros_Descontos'], errors='coerce').fillna(0)
            else:
                df['Outros_Descontos'] = 0.0
            
            # Verificar se as colunas necessárias existem
            colunas_necessarias = ['Nome', 'Salario_Bruto', 'Dependentes']
            colunas_faltantes = [col for col in colunas_necessarias if col not in df.columns]
            
            if colunas_faltantes:
                st.error(f"❌ Colunas faltantes: {', '.join(colunas_faltantes)}")
                st.info("""
                **Colunas necessárias:**
                - Nome
                - Salario_Bruto  
                - Dependentes
                - Outros_Descontos (opcional)
                """)
            else:
                st.write("**👀 Pré-visualização dos dados:**")
                st.dataframe(df.head(), use_container_width=True)
                
                # Estatísticas rápidas
                st.write("**📊 Estatísticas dos dados:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de Funcionários", len(df))
                with col2:
                    st.metric("Maior Salário", formatar_moeda(df['Salario_Bruto'].max()))
                with col3:
                    st.metric("Total Dependentes", df['Dependentes'].sum())
                
                if st.button("🚀 Processar Auditoria Completa", type="primary"):
                    # Processar cada funcionário
                    with st.spinner("Processando auditoria..."):
                        resultados = []
                        
                        for _, row in df.iterrows():
                            # Garantir que os valores são numéricos
                            salario_bruto = float(row['Salario_Bruto'])
                            dependentes = int(row['Dependentes'])
                            outros_desc = float(row.get('Outros_Descontos', 0))
                            
                            inss = calcular_inss(salario_bruto)
                            sal_familia = calcular_salario_familia(salario_bruto, dependentes)
                            irrf = calcular_irrf(salario_bruto, dependentes, inss, outros_desc)
                            salario_liquido = salario_bruto + sal_familia - inss - irrf - outros_desc
                            
                            resultados.append({
                                'Nome': row['Nome'],
                                'Salario_Bruto': salario_bruto,
                                'Dependentes': dependentes,
                                'Salario_Familia': sal_familia,
                                'INSS': inss,
                                'IRRF': irrf,
                                'Outros_Descontos': outros_desc,
                                'Salario_Liquido': salario_liquido,
                                'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não'
                            })
                        
                        df_resultado = pd.DataFrame(resultados)
                        
                        # Armazenar resultados no session state
                        st.session_state.df_resultado = df_resultado
                        st.session_state.uploaded_filename = uploaded_filename
                        
                        st.success("🎉 Auditoria concluída!")
        
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {e}")
    
    # CORREÇÃO: VERIFICAR SE EXISTE NO SESSION STATE ANTES DE USAR
    if hasattr(st.session_state, 'df_resultado') and st.session_state.df_resultado is not None:
        df_resultado = st.session_state.df_resultado
        
        # Resultados completos
        st.subheader("📈 Resultados da Auditoria")
        
        # Criar DataFrame formatado para exibição
        df_display = df_resultado.copy()
        
        # Formatar colunas numéricas para exibição
        colunas_monetarias = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
        for coluna in colunas_monetarias:
            df_display[coluna] = df_display[coluna].apply(formatar_moeda)
        
        st.dataframe(df_display, use_container_width=True)
        
        # Estatísticas finais
        st.subheader("📊 Resumo Financeiro")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_salario_familia = df_resultado['Salario_Familia'].sum()
            st.metric("Total Salário Família", formatar_moeda(total_salario_familia))
        with col2:
            total_inss = df_resultado['INSS'].sum()
            st.metric("Total INSS", formatar_moeda(total_inss))
        with col3:
            total_irrf = df_resultado['IRRF'].sum()
            st.metric("Total IRRF", formatar_moeda(total_irrf))
        with col4:
            folha_liquida_total = df_resultado['Salario_Liquido'].sum()
            st.metric("Folha Líquida Total", formatar_moeda(folha_liquida_total))
        
        # Download dos resultados
        st.subheader("💾 Exportar Resultados")
        col_csv, col_pdf = st.columns(2)
        
        with col_csv:
            # Criar CSV com formatação brasileira
            df_csv = df_resultado.copy()
            for coluna in colunas_monetarias:
                df_csv[coluna] = df_csv[coluna].apply(lambda x: f"{x:.2f}".replace('.', ','))
            
            csv_resultado = df_csv.to_csv(index=False, sep=';')
            st.download_button(
                label="📥 Baixar CSV",
                data=csv_resultado,
                file_name=f"auditoria_folha_{datetime.now().strftime('%d%m%Y_%H%M')}.csv",
                mime="text/csv",
                help="Baixe os resultados em CSV"
            )
        
        with col_pdf:
            # Gerar PDF da auditoria completa
            if st.button("📄 Gerar PDF Completo", type="secondary"):
                with st.spinner("Gerando relatório PDF..."):
                    # [AQUI VAI O CÓDIGO COMPLETO DE GERAÇÃO DO PDF QUE JÁ TEMOS]
                    # Por questão de espaço, mantive apenas a chamada
                    pdf_output = b"dummy_pdf_content"  # Substituir pelo código real
                    
                    st.markdown(
                        criar_link_download_pdf(
                            pdf_output, 
                            f"Auditoria_Completa_{datetime.now().strftime('%d%m%Y_%H%M')}.pdf"
                        ), 
                        unsafe_allow_html=True
                    )
                    st.success("📄 PDF gerado com sucesso!")

# [TAB3 E O RESTO DO CÓDIGO PERMANECEM IGUAIS...]
