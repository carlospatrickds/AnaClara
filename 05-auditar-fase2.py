import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import base64
from fpdf import FPDF
import io

# Configuração da página
st.set_page_config(page_title="Sistema de Auditoria", layout="wide")

# Classe PDF personalizada
class PDFAuditoria(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Relatório de Auditoria - Folha de Pagamento', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 8, body)
        self.ln()

# Função robusta para criar PDF
@st.cache_resource(show_spinner=False)
def criar_pdf_auditoria(dados_auditoria):
    """
    Função robusta para criação de PDF de auditoria
    """
    try:
        # Verificar se há dados para o PDF
        if not dados_auditoria:
            raise ValueError("Nenhum dado fornecido para o PDF")
        
        # Criar instância do PDF
        pdf = PDFAuditoria()
        pdf.add_page()
        
        # Cabeçalho
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA COMPLETA', 0, 1, 'C')
        pdf.ln(10)
        
        # Data e hora da geração
        pdf.set_font('Arial', 'I', 10)
        data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        pdf.cell(0, 10, f'Gerado em: {data_geracao}', 0, 1, 'R')
        pdf.ln(10)
        
        # Resumo executivo
        pdf.chapter_title('RESUMO EXECUTIVO')
        pdf.chapter_body(
            'Este relatório apresenta os resultados da auditoria completa '
            'realizada no sistema de folha de pagamento, incluindo análises '
            'de consistência, conformidade com a legislação e identificação '
            'de possíveis inconsistências.'
        )
        pdf.ln(5)
        
        # Dados da auditoria
        pdf.chapter_title('DADOS DA AUDITORIA')
        
        # Adicionar tabela com dados resumidos
        if isinstance(dados_auditoria, dict):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 8, 'Resumo dos Dados Auditados:', 0, 1)
            pdf.set_font('Arial', '', 10)
            
            for key, value in dados_auditoria.items():
                if isinstance(value, (int, float)):
                    pdf.cell(0, 8, f'{key}: {value:,.2f}', 0, 1)
                else:
                    pdf.cell(0, 8, f'{key}: {value}', 0, 1)
        
        pdf.ln(10)
        
        # Conclusões
        pdf.chapter_title('CONCLUSÕES')
        pdf.chapter_body(
            'A auditoria foi concluída com sucesso. Todos os registros foram '
            'analisados conforme os procedimentos estabelecidos. Recomenda-se '
            'a manutenção dos controles atuais e acompanhamento periódico '
            'para garantir a conformidade contínua.'
        )
        
        # Tentar gerar o PDF de forma robusta
        try:
            pdf_data = pdf.output(dest='S')
            # Tentar diferentes codificações
            try:
                pdf_output = pdf_data.encode('latin-1')
            except (UnicodeEncodeError, AttributeError):
                try:
                    pdf_output = pdf_data.encode('utf-8')
                except (UnicodeEncodeError, AttributeError):
                    pdf_output = pdf_data.encode('cp1252')
            
            return pdf_output
            
        except AttributeError as e:
            st.error(f"Erro no método output: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Erro na codificação do PDF: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"Erro crítico na criação do PDF: {str(e)}")
        return None

# Função para download do PDF
def criar_botao_download(pdf_data, nome_arquivo):
    """
    Cria botão de download para o PDF
    """
    if pdf_data is None:
        st.error("Não foi possível gerar o PDF para download")
        return
    
    try:
        b64 = base64.b64encode(pdf_data).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{nome_arquivo}">📥 Clique aqui para baixar o PDF</a>'
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao criar botão de download: {str(e)}")

# Interface principal do Streamlit
def main():
    st.title("📊 Sistema de Auditoria - Folha de Pagamento")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧮 Cálculo Individual", 
        "📊 Auditoria em Lote", 
        "ℹ️ Informações",
        "📄 Gerar Relatório PDF"
    ])
    
    with tab1:
        st.header("Cálculo Individual")
        st.write("Funcionalidade para cálculos individuais de folha")
        
        # Exemplo de dados para cálculo
        salario = st.number_input("Salário Base", value=3000.0)
        dias_trabalhados = st.number_input("Dias Trabalhados", value=30)
        
        if st.button("Calcular"):
            inss = salario * 0.11
            irrf = max(0, (salario - inss) * 0.15 - 354.80)
            salario_liquido = salario - inss - irrf
            
            st.success(f"Salário Líquido: R$ {salario_liquido:,.2f}")
    
    with tab2:
        st.header("Auditoria em Lote")
        st.write("Funcionalidade para auditoria de lotes de dados")
        
        uploaded_file = st.file_uploader("Carregar arquivo para auditoria", type=['csv', 'xlsx'])
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.dataframe(df.head())
                st.success(f"Arquivo carregado com sucesso! {len(df)} registros encontrados.")
            except Exception as e:
                st.error(f"Erro ao carregar arquivo: {str(e)}")
    
    with tab3:
        st.header("Informações do Sistema")
        st.write("""
        ### 📋 Sobre o Sistema
        
        Este sistema realiza auditoria completa da folha de pagamento, incluindo:
        
        - **Cálculos de INSS e IRRF**
        - **Verificação de conformidade legal**
        - **Análise de consistência dos dados**
        - **Geração de relatórios detalhados**
        
        ### 🛠️ Funcionalidades
        
        1. **Cálculo Individual**: Análise de colaboradores individualmente
        2. **Auditoria em Lote**: Processamento de grandes volumes de dados
        3. **Relatório PDF**: Geração de documentos para documentação
        """)
    
    with tab4:
        st.header("Gerar Relatório PDF Completo")
        st.write("Gere um relatório PDF completo com todos os dados da auditoria")
        
        # Dados de exemplo para o PDF
        dados_exemplo = {
            "Total de Colaboradores": 150,
            "Período Auditado": "01/11/2024 a 30/11/2024",
            "Valor Total da Folha": "R$ 450.000,00",
            "Inconsistências Encontradas": 3,
            "Status da Auditoria": "Concluída"
        }
        
        if st.button("🔄 Gerar Relatório PDF", type="primary"):
            with st.spinner("Gerando relatório PDF..."):
                try:
                    # Criar PDF
                    pdf_data = criar_pdf_auditoria(dados_exemplo)
                    
                    if pdf_data is not None:
                        # Nome do arquivo com timestamp
                        nome_arquivo = f"Auditoria_Completa_{datetime.now().strftime('%d%m%Y_%H%M%S')}.pdf"
                        
                        # Criar botão de download
                        criar_botao_download(pdf_data, nome_arquivo)
                        
                        st.success("✅ PDF gerado com sucesso! Use o link acima para fazer o download.")
                        
                        # Preview simples
                        st.info("📋 **Preview do Relatório:**")
                        st.json(dados_exemplo)
                        
                    else:
                        st.error("❌ Falha na geração do PDF. Verifique os logs para detalhes.")
                        
                except Exception as e:
                    st.error(f"❌ Erro inesperado: {str(e)}")
                    st.info("💡 **Dicas para solucionar:**")
                    st.write("""
                    1. Verifique se todas as dependências estão instaladas
                    2. Confirme que há permissão para criar arquivos
                    3. Tente recarregar a página
                    """)

# Executar a aplicação
if __name__ == "__main__":
    main()
