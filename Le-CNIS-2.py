import re
import pandas as pd
import streamlit as st
from io import BytesIO

st.set_page_config(page_title="Extrator CNIS", page_icon="📊", layout="wide")

st.title("📊 Extrator de Informações do CNIS")
st.markdown("---")

# Entrada de dados
col1, col2 = st.columns([2, 1])
with col1:
    texto = st.text_area(
        "**Cole os dados do CNIS abaixo:**",
        placeholder="Cole aqui o conteúdo completo do CNIS...",
        height=300
    )

with col2:
    st.markdown("### 💡 Dicas:")
    st.markdown("""
    - Copie todo o conteúdo do CNIS
    - Inclua cabeçalhos e tabelas
    - Mantenha a formatação original
    - Dados sensíveis serão processados localmente
    """)

# Funções de processamento
def extrair_informacoes_basicas(texto):
    """Extrai CPF, Nome e Data de Nascimento"""
    info = {
        'cpf': 'Não encontrado',
        'nome': 'Não encontrado', 
        'nascimento': 'Não encontrado'
    }
    
    # CPF
    cpf_match = re.search(r'CPF[:\s]*([\d\.\-]+)', texto, re.IGNORECASE)
    if cpf_match:
        info['cpf'] = cpf_match.group(1)
    
    # Nome
    nome_match = re.search(r'Nome[:\s]*([^\n\r]+)', texto, re.IGNORECASE)
    if nome_match:
        info['nome'] = nome_match.group(1).strip()
    
    # Data de Nascimento
    nasc_match = re.search(r'(Data\s*de\s*Nascimento|Nascimento)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})', texto, re.IGNORECASE)
    if nasc_match:
        info['nascimento'] = nasc_match.group(2)
    
    return info['cpf'], info['nome'], info['nascimento']

def processar_tabela_flexivel(texto):
    """Processa tabelas de forma flexível, detectando automaticamente o formato"""
    
    # Padrão 1: Tabela com pipes (|)
    padrao_pipes = r'\|([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)'
    matches_pipes = re.findall(padrao_pipes, texto)
    
    # Padrão 2: Linhas com datas e valores
    padrao_linhas = r'(\b[jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|dec]{3}/\d{2}\b)[\s\t]*([\d\.,]+)?[\s\t]*([\d\.,]+)?[\s\t]*([\d\.,]+)?[\s\t]*([\d\.,]+)?[\s\t]*([\d\.,]+)?[\s\t]*([\d\.,]+)?'
    matches_linhas = re.findall(padrao_linhas, texto, re.IGNORECASE)
    
    dados = []
    
    # Processar matches de pipes
    for linha in matches_pipes:
        competencia = linha[0].strip()
        if re.match(r'[a-z]{3}/\d{2}', competencia, re.IGNORECASE):
            linha_dict = {'Competência': competencia}
            for i, valor in enumerate(linha[1:7], 1):
                if valor.strip():
                    linha_dict[f'Vínculo {i}'] = valor.strip().replace(',', '.')
            dados.append(linha_dict)
    
    # Processar matches de linhas
    for match in matches_linhas:
        competencia = match[0]
        linha_dict = {'Competência': competencia}
        for i, valor in enumerate(match[1:7], 1):
            if valor:
                linha_dict[f'Vínculo {i}'] = valor.replace(',', '.')
        dados.append(linha_dict)
    
    if not dados:
        return pd.DataFrame()
    
    df = pd.DataFrame(dados)
    
    # Converter valores numéricos
    for col in df.columns:
        if col != 'Competência':
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df.fillna('')

def converter_competencia(comp):
    """Converte competência para formato padrão"""
    meses = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12',
        'dec': '12'
    }
    
    try:
        mes, ano = comp.split('/')
        mes_num = meses.get(mes.lower(), mes)
        ano_completo = f"20{ano}" if int(ano) <= 30 else f"19{ano}"
        return f"{mes_num}/{ano_completo}"
    except:
        return comp

# Processamento principal
if st.button("🚀 Processar Dados", type="primary", use_container_width=True):
    if not texto.strip():
        st.error("❌ Por favor, cole os dados do CNIS na caixa acima.")
    else:
        with st.spinner("Processando dados..."):
            # Extrair informações básicas
            cpf, nome, nascimento = extrair_informacoes_basicas(texto)
            
            # Processar tabela
            df = processar_tabela_flexivel(texto)
            
            # Exibir resultados
            st.markdown("---")
            
            # Informações básicas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📋 CPF", cpf)
            with col2:
                st.metric("👤 Nome", nome[:30] + "..." if len(nome) > 30 else nome)
            with col3:
                st.metric("🎂 Data Nasc.", nascimento)
            
            st.markdown("---")
            
            # Tabela processada
            if not df.empty:
                st.subheader("📊 Tabela de Competências e Valores")
                
                # Aplicar conversão de competência
                df_display = df.copy()
                df_display['Competência'] = df_display['Competência'].apply(converter_competencia)
                
                # Ordenar por competência
                df_display['AnoMes'] = pd.to_datetime(df_display['Competência'], format='%m/%Y')
                df_display = df_display.sort_values('AnoMes').drop('AnoMes', axis=1)
                
                # Exibir tabela
                st.dataframe(df_display, use_container_width=True)
                
                # Estatísticas
                st.subheader("📈 Estatísticas")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_vinculos = len([col for col in df.columns if 'Vínculo' in col])
                    st.metric("Nº de Vínculos", total_vinculos)
                
                with col2:
                    total_competencias = len(df)
                    st.metric("Competências", total_competencias)
                
                with col3:
                    total_valor = df.select_dtypes(include=['number']).sum().sum()
                    st.metric("Valor Total", f"R$ {total_valor:,.2f}")
                
                with col4:
                    competencias_unicas = len(df['Competência'].unique())
                    st.metric("Comp. Únicas", competencias_unicas)
                
                # Download
                st.markdown("---")
                st.subheader("💾 Download dos Dados")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV
                    output_csv = BytesIO()
                    df_display.to_csv(output_csv, index=False, sep=';', decimal=',', encoding='utf-8')
                    output_csv.seek(0)
                    
                    st.download_button(
                        label="📥 Baixar CSV",
                        data=output_csv,
                        file_name="cnis_competencias.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    # Excel
                    output_excel = BytesIO()
                    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                        df_display.to_excel(writer, sheet_name='CNIS', index=False)
                    output_excel.seek(0)
                    
                    st.download_button(
                        label="📥 Baixar Excel",
                        data=output_excel,
                        file_name="cnis_competencias.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                # Área para copiar
                st.subheader("📋 Copiar para Planilha")
                texto_copia = df_display.to_csv(index=False, sep='\t')
                st.text_area(
                    "Selecione e copie o conteúdo abaixo:",
                    texto_copia,
                    height=150,
                    key="area_copia"
                )
                
            else:
                st.warning("⚠️ Nenhuma tabela foi detectada nos dados. Verifique o formato.")
                
                # Debug opcional
                with st.expander("🔍 Ver dados crus (para debug)"):
                    st.text(texto[:2000] + "..." if len(texto) > 2000 else texto)

# Rodapé
st.markdown("---")
st.markdown(
    "**Extrator CNIS v1.0** | "
    "Processa dados do Cadastro Nacional de Informações Sociais"
)
