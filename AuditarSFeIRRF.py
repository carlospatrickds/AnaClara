import streamlit as st
import pandas as pd
from datetime import datetime
import locale

# Tentativa de configurar locale para português brasileiro
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        st.warning("Não foi possível configurar o locale para português brasileiro")

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

# Tabela INSS 2025
TABELA_INSS = [
    {"limite": 1412.00, "aliquota": 0.075},
    {"limite": 2666.68, "aliquota": 0.09},
    {"limite": 4000.03, "aliquota": 0.12},
    {"limite": 7786.02, "aliquota": 0.14}
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
    """Calcula desconto do INSS 2025"""
    if salario_bruto <= TABELA_INSS[0]["limite"]:
        return salario_bruto * TABELA_INSS[0]["aliquota"]
    
    inss = 0
    salario_restante = salario_bruto
    teto_inss = TABELA_INSS[3]["limite"]
    
    for i, faixa in enumerate(TABELA_INSS):
        if salario_restante <= 0:
            break
            
        if i == 0:
            # Primeira faixa
            valor_faixa = min(salario_restante, faixa["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
        else:
            # Faixas seguintes
            faixa_anterior = TABELA_INSS[i-1]
            valor_faixa = min(salario_restante, faixa["limite"] - faixa_anterior["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
    
    # Limite máximo do INSS (teto)
    if salario_bruto > teto_inss:
        inss = TABELA_INSS[0]["limite"] * TABELA_INSS[0]["aliquota"] + \
               (TABELA_INSS[1]["limite"] - TABELA_INSS[0]["limite"]) * TABELA_INSS[1]["aliquota"] + \
               (TABELA_INSS[2]["limite"] - TABELA_INSS[1]["limite"]) * TABELA_INSS[2]["aliquota"] + \
               (TABELA_INSS[3]["limite"] - TABELA_INSS[2]["limite"]) * TABELA_INSS[3]["aliquota"]
    
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
        data_admissao = st.date_input("Data de Admissão", 
                                    value=datetime(2023, 1, 1))
    
    if st.button("Calcular", type="primary"):
        # Realizar cálculos
        inss_valor = calcular_inss(salario)
        sal_familia = calcular_salario_familia(salario, dependentes)
        irrf_valor = calcular_irrf(salario, dependentes, inss_valor, outros_descontos)
        
        # Cálculo do salário líquido
        total_descontos = inss_valor + irrf_valor + outros_descontos
        total_acrescimos = sal_familia
        salario_liquido = salario - total_descontos + total_acrescimos
        
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
            st.write(f"**Data de Admissão:** {formatar_data(data_admissao)}")
            st.write(f"**Dependentes para IRRF:** {dependentes}")
            st.write(f"**Base cálculo IRRF:** {formatar_moeda(salario - (dependentes * DESCONTO_DEPENDENTE_IR) - inss_valor - outros_descontos)}")
        
        with col_info2:
            st.write(f"**Elegível Salário Família:** {'Sim' if sal_familia > 0 else 'Não'}")
            st.write(f"**Total de Descontos:** {formatar_moeda(total_descontos)}")
            st.write(f"**Total de Acréscimos:** {formatar_moeda(total_acrescimos)}")

with tab2:
    st.header("Auditoria em Lote")
    
    st.info("Faça upload de um arquivo CSV com os dados dos funcionários")
    
    # Template para download
    template_data = {
        'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira'],
        'Salario_Bruto': [1800.00, 3500.00, 5000.00],
        'Dependentes': [2, 1, 0],
        'Outros_Descontos': [0.0, 100.0, 200.0]
    }
    template_df = pd.DataFrame(template_data)
    
    st.download_button(
        label="📥 Baixar Template CSV",
        data=template_df.to_csv(index=False, sep=';'),
        file_name="template_funcionarios.csv",
        mime="text/csv"
    )
    
    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, sep=';')
            st.write("**Pré-visualização dos dados:**")
            st.dataframe(df.head())
            
            if st.button("Processar Auditoria", type="primary"):
                resultados = []
                
                for _, row in df.iterrows():
                    inss = calcular_inss(row['Salario_Bruto'])
                    sal_familia = calcular_salario_familia(row['Salario_Bruto'], row['Dependentes'])
                    irrf = calcular_irrf(row['Salario_Bruto'], row['Dependentes'], inss, row.get('Outros_Descontos', 0))
                    salario_liquido = row['Salario_Bruto'] + sal_familia - inss - irrf - row.get('Outros_Descontos', 0)
                    
                    resultados.append({
                        'Nome': row['Nome'],
                        'Salario_Bruto': row['Salario_Bruto'],
                        'Dependentes': row['Dependentes'],
                        'Salario_Familia': sal_familia,
                        'INSS': inss,
                        'IRRF': irrf,
                        'Salario_Liquido': salario_liquido,
                        'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não'
                    })
                
                df_resultado = pd.DataFrame(resultados)
                
                st.success("Auditoria concluída!")
                st.dataframe(df_resultado, use_container_width=True)
                
                # Estatísticas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Salário Família", formatar_moeda(df_resultado['Salario_Familia'].sum()))
                with col2:
                    st.metric("Total INSS", formatar_moeda(df_resultado['INSS'].sum()))
                with col3:
                    st.metric("Total IRRF", formatar_moeda(df_resultado['IRRF'].sum()))
                with col4:
                    st.metric("Funcionários Auditados", len(df_resultado))
                
                # Download dos resultados
                csv_resultado = df_resultado.to_csv(index=False, sep=';')
                st.download_button(
                    label="📥 Baixar Resultados",
                    data=csv_resultado,
                    file_name=f"auditoria_folha_{datetime.now().strftime('%d%m%Y')}.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")

with tab3:
    st.header("Informações Técnicas 2025")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Salário Família")
        st.write(f"""
        - **Limite de salário:** {formatar_moeda(SALARIO_FAMILIA_LIMITE)}
        - **Valor por dependente:** {formatar_moeda(VALOR_POR_DEPENDENTE)}
        - **Dedução IR por dependente:** {formatar_moeda(DESCONTO_DEPENDENTE_IR)}
        - **Requisito:** Salário igual ou inferior ao limite
        - **Dependentes:** Filhos até 14 anos ou inválidos de qualquer idade
        """)
    
    with col_info2:
        st.subheader("📊 Tabela INSS 2025")
        tabela_inss_df = pd.DataFrame([
            {"Faixa": "1ª", "Salário": "Até " + formatar_moeda(1412.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário": formatar_moeda(1412.01) + " a " + formatar_moeda(2666.68), "Alíquota": "9%"},
            {"Faixa": "3ª", "Salário": formatar_moeda(2666.69) + " a " + formatar_moeda(4000.03), "Alíquota": "12%"},
            {"Faixa": "4ª", "Salário": formatar_moeda(4000.04) + " a " + formatar_moeda(7786.02), "Alíquota": "14%"}
        ])
        st.dataframe(tabela_inss_df, use_container_width=True, hide_index=True)
        st.caption(f"**Teto máximo do INSS:** {formatar_moeda(7786.02)}")
    
    st.subheader("📈 Tabela IRRF 2025")
    tabela_irrf_df = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Dedução": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Dedução": formatar_moeda(182.16)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Dedução": formatar_moeda(394.16)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Dedução": formatar_moeda(675.49)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Dedução": formatar_moeda(916.90)}
    ])
    st.dataframe(tabela_irrf_df, use_container_width=True, hide_index=True)

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento 2025**

Cálculos baseados na legislação vigente:
- Salário Família
- INSS (Tabela 2025)
- IRRF (Tabela 2025)

⚠️ Consulte um contador para validação oficial.
""")

# Rodapé
st.markdown("---")
st.caption(f"📅 Data de referência: {formatar_data(datetime.now())} | 🏛 Legislação 2025")
