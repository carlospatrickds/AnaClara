import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Auditoria Folha de Pagamento",
    page_icon="💰",
    layout="wide"
)

class CalculadoraFolha:
    def __init__(self):
        # Salário Família 2025
        self.salario_familia_limite = 1906.04
        self.valor_por_dependente = 65.00
        
        # Tabela IRRF 2025 (vigente a partir de maio/2025)
        self.tabela_irrf = [
            {"limite": 2428.80, "aliquota": 0.0, "deducao": 0.0},
            {"limite": 2826.65, "aliquota": 0.075, "deducao": 182.16},
            {"limite": 3751.05, "aliquota": 0.15, "deducao": 394.16},
            {"limite": 4664.68, "aliquota": 0.225, "deducao": 675.49},
            {"limite": float('inf'), "aliquota": 0.275, "deducao": 916.90}
        ]
        
        # Dedução por dependente IR
        self.deducao_dependente_ir = 189.59

    def calcular_salario_familia(self, salario, num_dependentes):
        """Calcula o valor do salário família"""
        if salario <= self.salario_familia_limite:
            return num_dependentes * self.valor_por_dependente
        return 0.0

    def calcular_irrf(self, salario_bruto, num_dependentes, outros_descontos=0):
        """Calcula o IRRF com base na tabela 2025"""
        # Dedução por dependente
        deducao_dependentes = num_dependentes * self.deducao_dependente_ir
        
        # Base de cálculo
        base_calculo = salario_bruto - deducao_dependentes - outros_descontos
        
        if base_calculo <= 0:
            return 0.0
        
        # Encontra a faixa na tabela
        for faixa in self.tabela_irrf:
            if base_calculo <= faixa["limite"]:
                irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
                return max(irrf, 0.0)
        
        return 0.0

    def classificar_faixa_irrf(self, base_calculo):
        """Classifica em qual faixa do IRRF se enquadra"""
        for i, faixa in enumerate(self.tabela_irrf):
            if base_calculo <= faixa["limite"]:
                return f"Faixa {i+1} - {faixa['aliquota']*100}%"
        return "Faixa 5 - 27.5%"

def main():
    st.title("💰 Auditoria de Folha de Pagamento 2025")
    st.markdown("### Cálculo de Salário Família e IRRF")
    
    calc = CalculadoraFolha()
    
    # Sidebar com informações
    st.sidebar.header("📋 Informações da Tabela 2025")
    st.sidebar.subheader("Salário Família")
    st.sidebar.write(f"**Limite:** R$ {calc.salario_familia_limite:,.2f}")
    st.sidebar.write(f"**Valor por dependente:** R$ {calc.valor_por_dependente:,.2f}")
    
    st.sidebar.subheader("IRRF - Tabela Progressiva")
    st.sidebar.write("""
    | Base de Cálculo | Alíquota | Dedução |
    |----------------|----------|---------|
    | Até 2.428,80 | 0% | R$ 0,00 |
    | 2.428,81 a 2.826,65 | 7,5% | R$ 182,16 |
    | 2.826,66 a 3.751,05 | 15% | R$ 394,16 |
    | 3.751,06 a 4.664,68 | 22,5% | R$ 675,49 |
    | Acima de 4.664,68 | 27,5% | R$ 916,90 |
    """)
    
    # Abas para diferentes funcionalidades
    tab1, tab2, tab3 = st.tabs(["📊 Cálculo Individual", "📈 Auditoria em Lote", "ℹ️ Informações"])
    
    with tab1:
        st.header("Cálculo Individual")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nome_funcionario = st.text_input("Nome do Funcionário", "João Silva")
            salario_bruto = st.number_input("Salário Bruto (R$)", 
                                          min_value=0.0, 
                                          value=3000.0, 
                                          step=100.0)
            num_dependentes = st.number_input("Número de Dependentes", 
                                            min_value=0, 
                                            value=2, 
                                            step=1)
        
        with col2:
            outros_descontos = st.number_input("Outros Descontos (R$)", 
                                             min_value=0.0, 
                                             value=0.0, 
                                             step=50.0)
            data_admissao = st.date_input("Data de Admissão", 
                                        value=datetime(2023, 1, 1))
        
        if st.button("Calcular", type="primary"):
            # Cálculos
            salario_familia = calc.calcular_salario_familia(salario_bruto, num_dependentes)
            irrf = calc.calcular_irrf(salario_bruto, num_dependentes, outros_descontos)
            base_calculo_ir = salario_bruto - (num_dependentes * calc.deducao_dependente_ir) - outros_descontos
            faixa_irrf = calc.classificar_faixa_irrf(base_calculo_ir)
            salario_liquido = salario_bruto + salario_familia - irrf - outros_descontos
            
            # Exibir resultados
            st.success("Cálculos realizados com sucesso!")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Salário Família", f"R$ {salario_familia:,.2f}")
                st.metric("IRRF", f"R$ {irrf:,.2f}")
            
            with col2:
                st.metric("Base Cálculo IR", f"R$ {base_calculo_ir:,.2f}")
                st.metric("Faixa IRRF", faixa_irrf)
            
            with col3:
                st.metric("Salário Líquido", f"R$ {salario_liquido:,.2f}")
            
            # Detalhamento
            st.subheader("📋 Detalhamento dos Cálculos")
            detalhes = {
                "Item": ["Salário Bruto", "Salário Família", "Outros Descontos", "IRRF", "Salário Líquido"],
                "Valor (R$)": [salario_bruto, salario_familia, outros_descontos, irrf, salario_liquido]
            }
            st.dataframe(detalhes, use_container_width=True)
    
    with tab2:
        st.header("Auditoria em Lote")
        
        st.info("Faça upload de um arquivo CSV com os dados dos funcionários ou use o modelo abaixo.")
        
        # Template para download
        template_data = {
            'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira'],
            'Salario_Bruto': [1800.00, 2500.00, 3500.00],
            'Dependentes': [2, 1, 0],
            'Outros_Descontos': [0.0, 100.0, 200.0]
        }
        template_df = pd.DataFrame(template_data)
        
        st.download_button(
            label="📥 Baixar Template CSV",
            data=template_df.to_csv(index=False),
            file_name="template_funcionarios.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("**Pré-visualização dos dados:**")
                st.dataframe(df.head())
                
                if st.button("Processar Auditoria", type="primary"):
                    resultados = []
                    
                    for _, row in df.iterrows():
                        salario_familia = calc.calcular_salario_familia(
                            row['Salario_Bruto'], 
                            row['Dependentes']
                        )
                        irrf = calc.calcular_irrf(
                            row['Salario_Bruto'],
                            row['Dependentes'],
                            row.get('Outros_Descontos', 0)
                        )
                        salario_liquido = row['Salario_Bruto'] + salario_familia - irrf - row.get('Outros_Descontos', 0)
                        
                        resultados.append({
                            'Nome': row['Nome'],
                            'Salario_Bruto': row['Salario_Bruto'],
                            'Dependentes': row['Dependentes'],
                            'Salario_Familia': salario_familia,
                            'IRRF': irrf,
                            'Salario_Liquido': salario_liquido,
                            'Elegivel_Salario_Familia': 'Sim' if salario_familia > 0 else 'Não'
                        })
                    
                    df_resultado = pd.DataFrame(resultados)
                    
                    st.success("Auditoria concluída!")
                    st.dataframe(df_resultado, use_container_width=True)
                    
                    # Estatísticas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Salário Família", f"R$ {df_resultado['Salario_Familia'].sum():,.2f}")
                    with col2:
                        st.metric("Total IRRF", f"R$ {df_resultado['IRRF'].sum():,.2f}")
                    with col3:
                        st.metric("Funcionários Auditados", len(df_resultado))
                    
                    # Download dos resultados
                    csv_resultado = df_resultado.to_csv(index=False)
                    st.download_button(
                        label="📥 Baixar Resultados",
                        data=csv_resultado,
                        file_name="auditoria_folha_resultados.csv",
                        mime="text/csv"
                    )
                    
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")
    
    with tab3:
        st.header("Informações Técnicas")
        
        st.subheader("Salário Família 2025")
        st.write(f"""
        - **Limite de salário:** R$ {calc.salario_familia_limite:,.2f}
        - **Valor por dependente:** R$ {calc.valor_por_dependente:,.2f}
        - **Requisito:** Salário igual ou inferior ao limite
        - **Dependentes:** Filhos até 14 anos ou inválidos de qualquer idade
        """)
        
        st.subheader("IRRF 2025")
        st.write("""
        **Dedução por dependente:** R$ 189,59
        
        **Tabela Progressiva:**
        """)
        
        tabela_ir_df = pd.DataFrame([
            {"Base de Cálculo": "Até R$ 2.428,80", "Alíquota": "0%", "Dedução": "R$ 0,00"},
            {"Base de Cálculo": "De R$ 2.428,81 até R$ 2.826,65", "Alíquota": "7,5%", "Dedução": "R$ 182,16"},
            {"Base de Cálculo": "De R$ 2.826,66 até R$ 3.751,05", "Alíquota": "15%", "Dedução": "R$ 394,16"},
            {"Base de Cálculo": "De R$ 3.751,06 até R$ 4.664,68", "Alíquota": "22,5%", "Dedução": "R$ 675,49"},
            {"Base de Cálculo": "Acima de R$ 4.664,68", "Alíquota": "27,5%", "Dedução": "R$ 916,90"}
        ])
        
        st.dataframe(tabela_ir_df, use_container_width=True)
        
        st.subheader("Fórmulas de Cálculo")
        st.write("""
        **Salário Família:**
        ```
        Se Salário Bruto <= R$ 1.906,04:
            Salário Família = Nº Dependentes × R$ 65,00
        Senão:
            Salário Família = R$ 0,00
        ```
        
        **IRRF:**
        ```
        Base Cálculo = Salário Bruto - (Nº Dependentes × R$ 189,59) - Outros Descontos
        IRRF = (Base Cálculo × Alíquota) - Dedução da Faixa
        ```
        """)

if __name__ == "__main__":
    main()
