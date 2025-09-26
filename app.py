import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import locale
import os

# Importar módulos locais
from parsers.cnis_parser import CNISParser
from utils.date_calculator import DateCalculator
from utils.period_analyzer import PeriodAnalyzer
from components.timeline_chart import TimelineChart
from components.reports import ReportGenerator

# Configurar locale para formato brasileiro
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except:
        pass  # Usar configuração padrão se não conseguir definir locale brasileiro

def main():
    st.set_page_config(
        page_title="Analisador CNIS - INSS",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📊 Analisador de Documentos CNIS")
    st.markdown("**Sistema de análise de extratos previdenciários do INSS**")
    
    # Sidebar para upload de arquivos
    with st.sidebar:
        st.header("📁 Upload de Documentos")
        
        uploaded_files = st.file_uploader(
            "Selecione os arquivos CNIS",
            type=['pdf', 'txt'],
            accept_multiple_files=True,
            help="Faça upload de arquivos PDF ou TXT do extrato CNIS do INSS"
        )
        
        st.markdown("---")
        st.markdown("### ℹ️ Informações")
        st.markdown("""
        - **Formatos aceitos**: PDF e TXT
        - **Origem**: Extratos CNIS do INSS
        - **Múltiplos arquivos**: Suportado
        """)
    
    if not uploaded_files:
        st.info("👆 Faça upload de um ou mais arquivos CNIS para começar a análise")
        
        # Mostrar exemplo do formato esperado
        with st.expander("📖 Formato de arquivo esperado"):
            st.code("""
            INSS - INSTITUTO NACIONAL DO SEGURO SOCIAL
            CNIS - Cadastro Nacional de Informações Sociais
            Extrato Previdenciário 20/01/2021 12:30:38
            NIT: 167.85304.14-9 CPF: 709.212.374-72 Nome: FULANO DE TAL
            
            Seq. NIT Código Emp. Origem do Vínculo Data Início Data Fim Tipo Filiado...
            1 120.70663.14-2 11.556.719/0001-20 EMPRESA LTDA 01/06/1981 27/08/1983 Empregado...
            """, language="text")
        
        return
    
    # Processar arquivos
    parser = CNISParser()
    all_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processando {uploaded_file.name}...")
        progress_bar.progress((i + 1) / len(uploaded_files))
        
        try:
            if uploaded_file.type == "application/pdf":
                data = parser.parse_pdf(uploaded_file)
            else:
                data = parser.parse_txt(uploaded_file)
            
            if data:
                all_data.extend(data)
                
        except Exception as e:
            st.error(f"Erro ao processar {uploaded_file.name}: {str(e)}")
    
    progress_bar.empty()
    status_text.empty()
    
    if not all_data:
        st.error("❌ Nenhum dado válido encontrado nos arquivos enviados")
        return
    
    # Criar DataFrame principal
    df_vinculos = pd.DataFrame(all_data)
    
    # Análise de períodos
    analyzer = PeriodAnalyzer()
    df_vinculos = analyzer.calculate_periods(df_vinculos)
    overlaps = analyzer.detect_overlaps(df_vinculos)
    
    # Interface principal
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Vínculos", "📈 Linha do Tempo", "⚠️ Análises", "📄 Relatório"])
    
    with tab1:
        show_vinculos_tab(df_vinculos)
    
    with tab2:
        show_timeline_tab(df_vinculos)
    
    with tab3:
        show_analysis_tab(df_vinculos, overlaps)
    
    with tab4:
        show_report_tab(df_vinculos, overlaps)

def show_vinculos_tab(df_vinculos):
    """Exibe a aba de vínculos com tabela e filtros"""
    st.header("📋 Vínculos Identificados")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Vínculos", len(df_vinculos))
    with col2:
        vinculos_ativos = len(df_vinculos[df_vinculos['data_fim'].isna()])
        st.metric("Vínculos Ativos", vinculos_ativos)
    with col3:
        empresas_unicas = df_vinculos['empresa'].nunique()
        st.metric("Empresas Diferentes", empresas_unicas)
    
    # Filtros
    st.subheader("🔍 Filtros")
    col1, col2 = st.columns(2)
    
    with col1:
        tipo_filter = st.selectbox(
            "Tipo de Vínculo",
            ["Todos"] + list(df_vinculos['tipo'].unique())
        )
    
    with col2:
        empresa_filter = st.selectbox(
            "Empresa",
            ["Todas"] + list(df_vinculos['empresa'].unique())
        )
    
    # Aplicar filtros
    df_filtered = df_vinculos.copy()
    if tipo_filter != "Todos":
        df_filtered = df_filtered[df_filtered['tipo'] == tipo_filter]
    if empresa_filter != "Todas":
        df_filtered = df_filtered[df_filtered['empresa'] == empresa_filter]
    
    # Tabela de vínculos
    st.subheader("📊 Detalhes dos Vínculos")
    
    # Preparar dados para exibição
    display_df = df_filtered[['seq', 'empresa', 'cnpj', 'data_inicio', 'data_fim', 
                             'tipo', 'periodo_anos', 'periodo_meses', 'periodo_dias']].copy()
    
    display_df.columns = ['Seq', 'Empresa', 'CNPJ', 'Data Início', 'Data Fim', 
                         'Tipo', 'Anos', 'Meses', 'Dias']
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Remunerações se disponíveis
    if 'remuneracoes' in df_vinculos.columns:
        st.subheader("💰 Remunerações por Vínculo")
        
        vinculo_selected = st.selectbox(
            "Selecione um vínculo para ver remunerações",
            df_filtered['seq'].tolist(),
            format_func=lambda x: f"Seq {x} - {df_filtered[df_filtered['seq']==x]['empresa'].iloc[0]}"
        )
        
        if vinculo_selected:
            vinculo_data = df_filtered[df_filtered['seq'] == vinculo_selected].iloc[0]
            if pd.notna(vinculo_data['remuneracoes']) and vinculo_data['remuneracoes']:
                rem_df = pd.DataFrame(vinculo_data['remuneracoes'])
                st.dataframe(rem_df, use_container_width=True)
            else:
                st.info("Nenhuma remuneração encontrada para este vínculo")

def show_timeline_tab(df_vinculos):
    """Exibe a linha do tempo dos vínculos"""
    st.header("📈 Linha do Tempo dos Vínculos")
    
    timeline_chart = TimelineChart()
    fig = timeline_chart.create_timeline(df_vinculos)
    
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Erro ao gerar linha do tempo")
    
    # Gráfico de barras por período
    st.subheader("📊 Duração dos Vínculos")
    
    # Calcular tempo total em meses para cada vínculo
    df_duration = df_vinculos.copy()
    df_duration['total_meses'] = (
        df_duration['periodo_anos'] * 12 + 
        df_duration['periodo_meses'] + 
        df_duration['periodo_dias'] / 30
    )
    
    fig_bar = px.bar(
        df_duration,
        x='seq',
        y='total_meses',
        hover_data=['empresa', 'data_inicio', 'data_fim'],
        title="Duração dos Vínculos (em meses)",
        labels={'seq': 'Sequência', 'total_meses': 'Duração (meses)'}
    )
    
    st.plotly_chart(fig_bar, use_container_width=True)

def show_analysis_tab(df_vinculos, overlaps):
    """Exibe análises de concomitância e alertas"""
    st.header("⚠️ Análises e Alertas")
    
    # Alertas de concomitância
    if overlaps:
        st.error(f"🚨 {len(overlaps)} sobreposição(ões) de vínculos detectada(s)")
        
        for i, overlap in enumerate(overlaps):
            with st.expander(f"Sobreposição {i+1}: {overlap['days']} dias"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Primeiro Vínculo:**")
                    st.write(f"Seq: {overlap['vinculo1']['seq']}")
                    st.write(f"Empresa: {overlap['vinculo1']['empresa']}")
                    st.write(f"Período: {overlap['vinculo1']['data_inicio']} a {overlap['vinculo1']['data_fim']}")
                
                with col2:
                    st.write("**Segundo Vínculo:**")
                    st.write(f"Seq: {overlap['vinculo2']['seq']}")
                    st.write(f"Empresa: {overlap['vinculo2']['empresa']}")
                    st.write(f"Período: {overlap['vinculo2']['data_inicio']} a {overlap['vinculo2']['data_fim']}")
                
                st.write(f"**Período de Sobreposição:** {overlap['start_overlap']} a {overlap['end_overlap']}")
    else:
        st.success("✅ Nenhuma sobreposição de vínculos detectada")
    
    # Análise de gaps
    st.subheader("📊 Análise de Gaps (Períodos sem Contribuição)")
    
    analyzer = PeriodAnalyzer()
    gaps = analyzer.find_gaps(df_vinculos)
    
    if gaps:
        st.warning(f"⚠️ {len(gaps)} período(s) sem contribuição identificado(s)")
        
        gaps_df = pd.DataFrame(gaps)
        gaps_df.columns = ['Data Início', 'Data Fim', 'Duração (dias)']
        st.dataframe(gaps_df, use_container_width=True)
    else:
        st.success("✅ Nenhum gap significativo encontrado")
    
    # Resumo estatístico
    st.subheader("📈 Resumo Estatístico")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_anos = df_vinculos['periodo_anos'].sum()
    total_meses = df_vinculos['periodo_meses'].sum()
    total_dias = df_vinculos['periodo_dias'].sum()
    
    # Normalizar tempo total
    total_dias_total = total_dias + (total_meses * 30) + (total_anos * 365)
    anos_final = total_dias_total // 365
    meses_final = (total_dias_total % 365) // 30
    dias_final = total_dias_total % 30
    
    with col1:
        st.metric("Tempo Total", f"{anos_final:.0f}a {meses_final:.0f}m {dias_final:.0f}d")
    with col2:
        st.metric("Maior Vínculo", f"{df_vinculos['periodo_anos'].max():.0f} anos")
    with col3:
        st.metric("Menor Vínculo", f"{df_vinculos['periodo_meses'].min():.0f} meses")
    with col4:
        primeira_contrib = df_vinculos['data_inicio'].min()
        st.metric("Primeira Contrib.", primeira_contrib.strftime("%m/%Y") if pd.notna(primeira_contrib) else "N/A")

def show_report_tab(df_vinculos, overlaps):
    """Exibe relatório completo"""
    st.header("📄 Relatório Completo")
    
    report_gen = ReportGenerator()
    
    # Botão para gerar relatório
    if st.button("📊 Gerar Relatório Detalhado", type="primary"):
        with st.spinner("Gerando relatório..."):
            report_data = report_gen.generate_full_report(df_vinculos, overlaps)
            
            # Exibir relatório
            st.markdown("## 📋 Relatório de Análise CNIS")
            st.markdown(f"**Data de Geração:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            
            # Informações do segurado
            if not df_vinculos.empty:
                first_record = df_vinculos.iloc[0]
                if 'nome' in first_record:
                    st.markdown(f"**Nome:** {first_record['nome']}")
                if 'nit' in first_record:
                    st.markdown(f"**NIT:** {first_record['nit']}")
                if 'cpf' in first_record:
                    st.markdown(f"**CPF:** {first_record['cpf']}")
            
            st.markdown("---")
            
            # Resumo executivo
            st.markdown("### 📊 Resumo Executivo")
            for key, value in report_data['resumo'].items():
                st.markdown(f"- **{key}:** {value}")
            
            st.markdown("---")
            
            # Detalhamento por vínculo
            st.markdown("### 📋 Detalhamento dos Vínculos")
            st.dataframe(report_data['vinculos_detalhados'], use_container_width=True)
            
            if report_data['sobreposicoes']:
                st.markdown("---")
                st.markdown("### ⚠️ Sobreposições Detectadas")
                for sobreposicao in report_data['sobreposicoes']:
                    st.error(f"Sobreposição de {sobreposicao['days']} dias entre vínculos {sobreposicao['vinculo1']['seq']} e {sobreposicao['vinculo2']['seq']}")
            
            # Download do relatório
            st.markdown("---")
            st.markdown("### 💾 Download")
            
            # Preparar dados para CSV
            csv_data = df_vinculos.to_csv(index=False)
            st.download_button(
                label="📥 Baixar dados em CSV",
                data=csv_data,
                file_name=f"cnis_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
