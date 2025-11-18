import streamlit as st
import pandas as pd
from datetime import datetime
import io

# [O resto do código anterior permanece igual...]

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
    csv_template = template_df.to_csv(index=False, sep=';', decimal=',')
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
            df = pd.read_csv(uploaded_file, sep=';', decimal=',')
            
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
                        csv_resultado = df_resultado.to_csv(index=False, sep=';', decimal=',')
                        
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
