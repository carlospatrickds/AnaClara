import streamlit as st
import pandas as pd
from datetime import datetime
import locale

# Tentativa de configurar locale para português brasileiro
try:
    # Tenta configurar o locale para exibir moedas (R$) corretamente
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        st.warning("Não foi possível configurar o locale para português brasileiro. Usando formato padrão.")

# Configuração básica da página
st.set_page_config(
    page_title="Auditoria Folha de Pagamento",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Auditoria de Folha de Pagamento 2025")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- Dados das tabelas 2025 (Valores de exemplo/referência para 2025) ---
SALARIO_FAMILIA_LIMITE = 1906.04
VALOR_POR_DEPENDENTE = 65.00
DESCONTO_DEPENDENTE_IR = 189.59

# Tabela INSS 2025 (Progressiva) - A chave 'deducao' é adicionada para facilitar o cálculo
# Os limites são: (até 1412.00), (de 1412.01 até 2666.68), (de 2666.69 até 4000.03), (de 4000.04 até 7786.02)
# Teto do Salário de Contribuição: R$ 7.786,02
TABELA_INSS = [
    {"limite": 1412.00, "aliquota": 0.075, "deducao": 0.00},
    {"limite": 2666.68, "aliquota": 0.09,  "deducao": 18.90}, # (2666.68 - 1412.00) * 0.09 + (1412.00 * 0.075) = 227.82. Dedução = 2666.68 * 0.09 - 227.82 = 18.90
    {"limite": 4000.03, "aliquota": 0.12,  "deducao": 96.94}, # Dedução calculada para esta faixa
    {"limite": 7786.02, "aliquota": 0.14,  "deducao": 181.38} # Dedução calculada para esta faixa e teto
]
TETO_INSS_VALOR = 7786.02 # Usado para calcular o valor máximo do INSS

# Tabela IRRF 2025
TABELA_IRRF = [
    {"limite": 2428.80, "aliquota": 0.0, "deducao": 0.0},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 182.16},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 394.16},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 675.49},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 916.90}
]

# --- Funções de Ajuda ---

def formatar_moeda(valor):
    """Formata valor em moeda brasileira (R$ 1.234,56)."""
    # Tenta usar o locale configurado (mais preciso)
    try:
        return locale.currency(valor, grouping=True)
    # Se o locale falhar, usa formatação manual
    except:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(data):
    """Formata data no padrão brasileiro"""
    return data.strftime("%d/%m/%Y")

# --- Funções de Cálculo ---

def calcular_inss(salario_bruto):
    """Calcula desconto do INSS 2025 (Progressivo com Teto)"""
    
    # 1. Aplica o teto do salário de contribuição
    base_inss = min(salario_bruto, TETO_INSS_VALOR)
    
    if base_inss <= 0:
        return 0.0
    
    # 2. Calcula o INSS de forma progressiva
    inss_calculado = 0
    teto_anterior = 0.0
    
    for faixa in TABELA_INSS:
        # Verifica se o salário ultrapassa o limite da faixa
        if base_inss > faixa["limite"]:
            # Valor a ser taxado na FAIXA ATUAL (Limite da Faixa - Limite da Faixa Anterior)
            valor_faixa = faixa["limite"] - teto_anterior
            inss_calculado += valor_faixa * faixa["aliquota"]
        else:
            # Salário cai nesta faixa, calcula o restante
            valor_faixa = base_inss - teto_anterior
            inss_calculado += valor_faixa * faixa["aliquota"]
            break # Termina o cálculo, pois atingiu o limite
        
        teto_anterior = faixa["limite"]
        
    return round(inss_calculado, 2)

def calcular_salario_familia(salario, dependentes):
    """Calcula salário família"""
    if salario <= SALARIO_FAMILIA_LIMITE and dependentes > 0:
        return dependentes * VALOR_POR_DEPENDENTE
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos=0):
    """Calcula IRRF"""
    
    # Base de cálculo IRRF = Salário Bruto - Deduções (INSS + Dependentes + Outros)
    deducao_dependentes = dependentes * DESCONTO_DEPENDENTE_IR
    base_calculo = salario_bruto - inss - deducao_dependentes - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    # Aplica a tabela progressiva do IRRF
    for faixa in TABELA_IRRF:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(irrf, 0.0)
    
    return 0.0 # Caso de segurança

def classificar_faixa_irrf(base_calculo):
    """Classifica em qual faixa do IRRF se enquadra para exibição."""
    for i, faixa in enumerate(TABELA_IRRF):
        if base_calculo <= faixa["limite"]:
            if faixa['aliquota'] == 0.0:
                return "Faixa 1 - Isento"
            return f"Faixa {i+1} - {faixa['aliquota']*100:.1f}%"
    return "Faixa 5 - 27.5%"

# --- Interface Principal ---

tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Individual", "📊 Auditoria em Lote", "ℹ️ Informações"])

with tab1:
    st.header("Cálculo Individual")
    
    col1, col2 = st.columns(2)
    
    with col1:
        nome = st.text_input("Nome do Funcionário", "João Silva")
        salario = st.number_input("Salário Bruto (R$)", 
                                min_value=0.0, 
                                value=5500.00, # Valor de teste para cruzar as faixas
                                step=100.0,
                                format="%.2f")
        dependentes = st.number_input("Número de Dependentes (Salário Família / IR)", 
                                    min_value=0, 
                                    value=1, 
                                    step=1)
    
    with col2:
        outros_descontos = st.number_input("Outros Descontos da Base IRRF (Ex: Pensão, Faltas) (R$)", 
                                         min_value=0.0, 
                                         value=0.0, 
                                         step=50.0,
                                         format="%.2f")
        data_admissao = st.date_input("Data de Admissão", 
                                    value=datetime(2023, 1, 1))
    
    if st.button("Calcular", type="primary"):
        # Realizar cálculos
        inss_valor = calcular_inss(salario)
        sal_familia = calcular_salario_familia(salario, dependentes)
        
        # Base de cálculo IRRF
        base_irrf = salario - inss_valor - (dependentes * DESCONTO_DEPENDENTE_IR) - outros_descontos
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
            st.metric("INSS (Desconto)", formatar_moeda(inss_valor))
        with col3:
            st.metric("IRRF (Desconto)", formatar_moeda(irrf_valor))
        with col4:
            st.metric("Salário Líquido", formatar_moeda(salario_liquido))
        
        # Tabela de detalhes
        st.subheader("📋 Detalhamento Completo")
        
        # Cria a string para a faixa do INSS (ajuda a visualizar a alíquota efetiva)
        if salario <= TETO_INSS_VALOR:
            aliquota_efetiva = inss_valor / salario
        else:
            aliquota_efetiva = inss_valor / TETO_INSS_VALOR # Usa o teto para alíquota
            
        detalhes = pd.DataFrame({
            'Descrição': [
                'Salário Bruto', 
                'Salário Família (Provento)', 
                'INSS (Desconto)', 
                'IRRF (Desconto)', 
                'Outros Descontos (Base IR)',
                'Dedução Dependentes (IR)',
                'Base de Cálculo IRRF',
                'Faixa IRRF',
                'Total Descontos',
                'Salário Líquido'
            ],
            'Valor': [
                formatar_moeda(salario),
                formatar_moeda(sal_familia),
                f"{formatar_moeda(inss_valor)} (Alíq. Efetiva: {aliquota_efetiva*100:.2f}%)",
                formatar_moeda(irrf_valor),
                formatar_moeda(outros_descontos),
                formatar_moeda(dependentes * DESCONTO_DEPENDENTE_IR),
                formatar_moeda(base_irrf),
                classificar_faixa_irrf(base_irrf),
                formatar_moeda(total_descontos),
                formatar_moeda(salario_liquido)
            ]
        })
        st.dataframe(detalhes.set_index('Descrição'), use_container_width=True)


with tab2:
    st.header("Auditoria em Lote")
    
    st.info("Faça upload de um arquivo CSV com os dados dos funcionários (separador ';'). O arquivo deve conter as colunas: `Nome`, `Salario_Bruto`, `Dependentes`, `Outros_Descontos`.")
    
    # Template para download
    template_data = {
        'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira'],
        'Salario_Bruto': [1800.00, 3500.00, 5000.00],
        'Dependentes': [2, 1, 0],
        'Outros_Descontos': [0.0, 100.0, 200.0]
    }
    template_df = pd.DataFrame(template_data)
    
    # Nota: Usando sep=';' para evitar problemas com vírgula decimal em pt-BR
    st.download_button(
        label="📥 Baixar Template CSV (Separador ;)",
        data=template_df.to_csv(index=False, sep=';'),
        file_name="template_funcionarios.csv",
        mime="text/csv"
    )
    
    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
    
    if uploaded_file is not None:
        try:
            # Tenta ler com separador ';' e decodificação UTF-8
            df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
            
            # Validação mínima de colunas
            colunas_necessarias = ['Nome', 'Salario_Bruto', 'Dependentes']
            for col in colunas_necessarias:
                if col not in df.columns:
                    st.error(f"O arquivo CSV deve conter a coluna obrigatória: '{col}'. Por favor, use o template.")
                    return
            
            # Garante que a coluna de descontos exista (pode ser 0)
            if 'Outros_Descontos' not in df.columns:
                 df['Outros_Descontos'] = 0.0

            st.write("**Pré-visualização dos dados:**")
            st.dataframe(df.head())
            
            if st.button("Processar Auditoria", type="primary"):
                
                # Aplica as funções de cálculo a todas as linhas do DataFrame
                df['INSS_Calculado'] = df['Salario_Bruto'].apply(calcular_inss)
                df['Salario_Familia_Calculado'] = df.apply(
                    lambda row: calcular_salario_familia(row['Salario_Bruto'], row['Dependentes']), axis=1
                )
                
                # Calcula o IRRF
                df['IRRF_Calculado'] = df.apply(
                    lambda row: calcular_irrf(
                        row['Salario_Bruto'], 
                        row['Dependentes'], 
                        row['INSS_Calculado'], 
                        row['Outros_Descontos']
                    ), axis=1
                )
                
                # Calcula o Salário Líquido Simulado
                df['Salario_Liquido_Simulado'] = (
                    df['Salario_Bruto'] + df['Salario_Familia_Calculado'] - 
                    df['INSS_Calculado'] - df['IRRF_Calculado'] - df['Outros_Descontos']
                )

                df['Elegivel_Salario_Familia'] = df['Salario_Familia_Calculado'].apply(lambda x: 'Sim' if x > 0 else 'Não')

                colunas_resultado = [
                    'Nome', 'Salario_Bruto', 'Dependentes', 'Outros_Descontos',
                    'Salario_Familia_Calculado', 'INSS_Calculado', 'IRRF_Calculado', 
                    'Salario_Liquido_Simulado', 'Elegivel_Salario_Familia'
                ]
                df_resultado = df[colunas_resultado]
                
                st.success("Auditoria concluída!")
                st.dataframe(df_resultado.style.format(formatar_moeda), use_container_width=True) # Formata valores na tabela
                
                # Estatísticas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Salário Família", formatar_moeda(df_resultado['Salario_Familia_Calculado'].sum()))
                with col2:
                    st.metric("Total INSS", formatar_moeda(df_resultado['INSS_Calculado'].sum()))
                with col3:
                    st.metric("Total IRRF", formatar_moeda(df_resultado['IRRF_Calculado'].sum()))
                with col4:
                    st.metric("Funcionários Auditados", len(df_resultado))
                
                # Download dos resultados
                # Usa to_csv com separador ';' para compatibilidade com Excel em PT-BR
                csv_resultado = df_resultado.to_csv(index=False, sep=';', decimal=',')
                st.download_button(
                    label="📥 Baixar Resultados",
                    data=csv_resultado,
                    file_name=f"auditoria_folha_resultados_{datetime.now().strftime('%d%m%Y')}.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"Erro ao processar arquivo. Verifique se o formato (separador ';') e os dados estão corretos. Detalhe: {e}")

with tab3:
    st.header("Informações Técnicas 2025")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Salário Família & Deduções")
        st.markdown(f"""
        - **Limite de Salário Família:** **{formatar_moeda(SALARIO_FAMILIA_LIMITE)}**
        - **Valor por Dependente (SF):** {formatar_moeda(VALOR_POR_DEPENDENTE)}
        - **Dedução IR por Dependente:** {formatar_moeda(DESCONTO_DEPENDENTE_IR)}
        """)
    
    with col_info2:
        st.subheader("📊 Tabela INSS 2025 (Salário de Contribuição)")
        tabela_inss_data = []
        teto_anterior = 0.0
        
        for faixa in TABELA_INSS:
            limite_atual = faixa["limite"]
            aliquota = faixa["aliquota"] * 100
            
            if teto_anterior == 0.0:
                faixa_str = "Até " + formatar_moeda(limite_atual)
                parcela_teto = limite_atual * faixa["aliquota"]
            else:
                faixa_str = formatar_moeda(teto_anterior + 0.01) + " a " + formatar_moeda(limite_atual)
                parcela_teto = parcela_teto + (limite_atual - teto_anterior) * faixa["aliquota"]
            
            tabela_inss_data.append({
                "Faixa": f"{aliquota:.1f}%",
                "Salário de Contribuição": faixa_str, 
                "Parc. Teto (Acréscimo)": formatar_moeda(parcela_teto)
            })
            teto_anterior = limite_atual
            
        tabela_inss_df_display = pd.DataFrame(tabela_inss_data)
        st.dataframe(tabela_inss_df_display, use_container_width=True, hide_index=True)
        st.caption(f"**Teto Salário de Contribuição:** {formatar_moeda(TETO_INSS_VALOR)} | **Valor Máx. INSS:** {formatar_moeda(calcular_inss(TETO_INSS_VALOR))}")
    
    st.subheader("📈 Tabela IRRF 2025 (Base de Cálculo)")
    tabela_irrf_df = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Dedução": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Dedução": formatar_moeda(182.16)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Dedução": formatar_moeda(394.16)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Dedução": formatar_moeda(675.49)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Dedução": formatar_moeda(916.90)}
    ])
    st.dataframe(tabela_irrf_df, use_container_width=True, hide_index=True)
    
    st.subheader("Fórmulas de Cálculo Aplicadas")
    st.code("""
        # Cálculo do INSS (Progressivo)
        1. Limita a base de cálculo ao Teto do Salário de Contribuição (R$ 7.786,02).
        2. Aplica as alíquotas de cada faixa (7,5%, 9%, 12%, 14%) apenas sobre a parte do salário que cai em cada faixa.

        # Cálculo do IRRF
        Base Cálculo IRRF = Salário Bruto - INSS (Calculado) - Dedução Dependentes (R$ 189,59/cada) - Outros Descontos
        IRRF = (Base Cálculo IRRF × Alíquota da Faixa) - Parcela a Deduzir da Faixa
        
        # Salário Líquido Simulado
        Salário Líquido = Salário Bruto + Salário Família - INSS - IRRF - Outros Descontos
    """)

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info(f"""
**Auditoria Folha de Pagamento 2025**

Cálculos baseados nas tabelas de referência para 2025.

**🚨 Alíquotas e limites do INSS/IRRF são apenas previsões para 2025 e devem ser validados conforme Portaria oficial.**

⚠️ Consulte um contador para validação oficial.
""")

# Rodapé
st.markdown("---")
st.caption(f"📅 Data de referência: {formatar_data(datetime.now())}")
