import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import base64
from io import BytesIO

# Configuração básica da página
st.set_page_config(
    page_title="Auditoria Folha de Pagamento",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Auditoria de Folha de Pagamento 2025")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

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

def gerar_pdf_individual(dados):
    """Gera PDF profissional para cálculo individual"""
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA - FOLHA DE PAGAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    # Informações da Empresa
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'INFORMAÇÕES DA EMPRESA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Data da Análise: {dados["data_analise"]}', 0, 1)
    pdf.cell(0, 6, f'Competência: {dados["competencia"]}', 0, 1)
    pdf.ln(5)
    
    # Dados do Funcionário
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'DADOS DO FUNCIONÁRIO', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Nome: {dados["nome"]}', 0, 1)
    pdf.cell(0, 6, f'Salário Bruto: {dados["salario_bruto"]}', 0, 1)
    pdf.cell(0, 6, f'Dependentes: {dados["dependentes"]}', 0, 1)
    pdf.cell(0, 6, f'Outros Descontos: {dados["outros_descontos"]}', 0, 1)
    pdf.ln(5)
    
    # Resultados dos Cálculos
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'RESULTADOS DOS CÁLCULOS', 0, 1)
    
    resultados = [
        ('Salário Bruto', dados["salario_bruto"]),
        ('Salário Família', dados["salario_familia"]),
        ('INSS', dados["inss"]),
        ('IRRF', dados["irrf"]),
        ('Outros Descontos', dados["outros_descontos"]),
        ('Total de Descontos', dados["total_descontos"]),
        ('SALÁRIO LÍQUIDO', dados["salario_liquido"])
    ]
    
    pdf.set_font('Arial', '', 10)
    for descricao, valor in resultados:
        if 'SALÁRIO LÍQUIDO' in descricao:
            pdf.set_font('Arial', 'B', 11)
        pdf.cell(100, 7, descricao)
        pdf.cell(0, 7, valor, 0, 1)
        if 'SALÁRIO LÍQUIDO' in descricao:
            pdf.set_font('Arial', '', 10)
    pdf.ln(5)
    
    # Informações Adicionais
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'INFORMAÇÕES ADICIONAIS', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Elegível para Salário Família: {dados["elegivel_salario_familia"]}', 0, 1)
    pdf.cell(0, 6, f'Base de Cálculo IRRF: {dados["base_irrf"]}', 0, 1)
    pdf.ln(10)
    
    # Tabelas de Referência
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA 2025', 0, 1)
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA INSS 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor', 1, 1)
    
    faixas_inss = [
        (f'Até {formatar_moeda(1518.00)}', '7,5%', formatar_moeda(1518.00 * 0.075)),
        (f'{formatar_moeda(1518.01)} a {formatar_moeda(2793.88)}', '9,0%', formatar_moeda((2793.88 - 1518.00) * 0.09)),
        (f'{formatar_moeda(2793.89)} a {formatar_moeda(4190.83)}', '12,0%', formatar_moeda((4190.83 - 2793.88) * 0.12)),
        (f'{formatar_moeda(4190.84)} a {formatar_moeda(8157.41)}', '14,0%', formatar_moeda((8157.41 - 4190.83) * 0.14))
    ]
    
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(8157.41)}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA IRRF 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Dedução', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = [
        (f'Até {formatar_moeda(2428.80)}', '0%', formatar_moeda(0), 'Isento'),
        (f'{formatar_moeda(2428.81)} a {formatar_moeda(2826.65)}', '7,5%', formatar_moeda(182.16), '1ª'),
        (f'{formatar_moeda(2826.66)} a {formatar_moeda(3751.05)}', '15%', formatar_moeda(394.16), '2ª'),
        (f'{formatar_moeda(3751.06)} a {formatar_moeda(4664.68)}', '22,5%', formatar_moeda(675.49), '3ª'),
        (f'Acima de {formatar_moeda(4664.68)}', '27,5%', formatar_moeda(916.90), '4ª')
    ]
    
    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.ln(10)
    
    # Rodapé
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, 'Este relatório foi gerado automaticamente pelo Sistema de Auditoria de Folha de Pagamento.', 0, 1, 'C')
    pdf.cell(0, 5, 'Consulte um contador para validação oficial dos cálculos.', 0, 1, 'C')
    
    return pdf

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
        pdf_output = pdf.output(dest='S').encode('latin1')
        
        st.markdown(
            criar_link_download_pdf(
                pdf_output, 
                f"Auditoria_Folha_{nome.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
            ), 
            unsafe_allow_html=True
        )

with tab2:
    st.header("Auditoria em Lote")
    
    st.info("""
    **📊 Como preparar seu arquivo CSV:**
    
    1. **Baixe o template abaixo** ou crie seu próprio arquivo
    2. **Formato esperado:** 4 colunas separadas por ponto e vírgula
    3. **Salve como CSV** no Excel/Google Sheets
    4. **Faça o upload** do arquivo
    """)
    
    # Template mais completo para download
    template_data = {
        'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira', 'Ana Costa', 'Carlos Lima'],
        'Salario_Bruto': [1500.00, 2800.00, 4200.00, 1800.50, 6000.00],
        'Dependentes': [2, 1, 0, 3, 1],
        'Outros_Descontos': [0.00, 100.00, 200.50, 50.00, 300.00]
    }
    template_df = pd.DataFrame(template_data)
    
    # Mostrar preview do template
    st.subheader("📝 Estrutura do Arquivo Esperado")
    st.dataframe(template_df, use_container_width=True)
    
    # Download do template
    csv_template = template_df.to_csv(index=False, sep=';')
    st.download_button(
        label="📥 Baixar Template CSV",
        data=csv_template,
        file_name="template_funcionarios.csv",
        mime="text/csv",
        help="Clique para baixar um template pré-formatado"
    )
    
    st.subheader("📤 Upload do Arquivo")
    uploaded_file = st.file_uploader(
        "Escolha um arquivo CSV", 
        type="csv",
        help="Arquivo deve ter as colunas: Nome, Salario_Bruto, Dependentes, Outros_Descontos"
    )
    
    if uploaded_file is not None:
        try:
            # Ler o arquivo CSV
            df = pd.read_csv(uploaded_file, sep=';')
            
            st.success("✅ Arquivo carregado com sucesso!")
            
            # Verificar se as colunas necessárias existem
            colunas_necessarias = ['Nome', 'Salario_Bruto', 'Dependentes']
            colunas_faltantes = [col for col in colunas_necessarias if col not in df.columns]
            
            if colunas_faltantes:
                st.error(f"❌ Colunas faltantes no arquivo: {', '.join(colunas_faltantes)}")
                st.info("""
                **Verifique se seu arquivo tem estas colunas:**
                - Nome
                - Salario_Bruto  
                - Dependentes
                - Outros_Descontos (opcional)
                """)
            else:
                st.write("**👀 Pré-visualização dos dados (primeiras 5 linhas):**")
                st.dataframe(df.head(), use_container_width=True)
                
                # Estatísticas rápidas
                st.write("**📊 Estatísticas do arquivo:**")
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
                            inss = calcular_inss(row['Salario_Bruto'])
                            sal_familia = calcular_salario_familia(row['Salario_Bruto'], row['Dependentes'])
                            outros_desc = row.get('Outros_Descontos', 0)
                            irrf = calcular_irrf(row['Salario_Bruto'], row['Dependentes'], inss, outros_desc)
                            salario_liquido = row['Salario_Bruto'] + sal_familia - inss - irrf - outros_desc
                            
                            resultados.append({
                                'Nome': row['Nome'],
                                'Salario_Bruto': row['Salario_Bruto'],
                                'Dependentes': row['Dependentes'],
                                'Salario_Familia': sal_familia,
                                'INSS': inss,
                                'IRRF': irrf,
                                'Outros_Descontos': outros_desc,
                                'Salario_Liquido': salario_liquido,
                                'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não'
                            })
                        
                        df_resultado = pd.DataFrame(resultados)
                        
                        st.success("🎉 Auditoria concluída!")
                        
                        # Resultados completos
                        st.subheader("📈 Resultados da Auditoria")
                        st.dataframe(df_resultado, use_container_width=True)
                        
                        # Estatísticas finais
                        st.subheader("📊 Resumo Financeiro")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric(
                                "Total Salário Família", 
                                formatar_moeda(df_resultado['Salario_Familia'].sum())
                            )
                        with col2:
                            st.metric(
                                "Total INSS", 
                                formatar_moeda(df_resultado['INSS'].sum())
                            )
                        with col3:
                            st.metric(
                                "Total IRRF", 
                                formatar_moeda(df_resultado['IRRF'].sum())
                            )
                        with col4:
                            st.metric(
                                "Folha Líquida Total", 
                                formatar_moeda(df_resultado['Salario_Liquido'].sum())
                            )
                        
                        # Download dos resultados
                        st.subheader("💾 Exportar Resultados")
                        csv_resultado = df_resultado.to_csv(index=False, sep=';')
                        
                        st.download_button(
                            label="📥 Baixar Resultados em CSV",
                            data=csv_resultado,
                            file_name=f"auditoria_folha_{datetime.now().strftime('%d%m%Y_%H%M')}.csv",
                            mime="text/csv",
                            help="Baixe os resultados completos da auditoria"
                        )
                        
        except Exception as e:
            st.error(f"❌ Erro ao processar arquivo: {e}")
            st.info("""
            **Dicas para corrigir o arquivo:**
            - Verifique se o arquivo é um CSV válido
            - Confirme que as colunas estão separadas por ponto e vírgula
            - Certifique-se de que números usam ponto como decimal (ex: 1500.00)
            - Verifique se não há linhas vazias no arquivo
            """)

with tab3:
    st.header("Informações Técnicas 2025")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Salário Família")
        st.write(f"""
        - **Limite de salário:** {formatar_moeda(SALARIO_FAMILIA_LIMITE)}
        - **Valor por dependente:** {formatar_
