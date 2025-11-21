 Import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
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

# INICIALIZAR SESSION STATE
if 'df_resultado' not in st.session_state:
    st.session_state.df_resultado = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None
if 'dados_manuais' not in st.session_state:
    st.session_state.dados_manuais = []
if 'ultima_opcao' not in st.session_state:
    st.session_state.ultima_opcao = "📁 Upload de CSV"

st.title("💰 Auditoria de Folha de Pagamento 2025 - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- INPUT DE DATA DE COMPETÊNCIA ---
data_competencia = st.date_input(
    "Data de Competência para a Auditoria (Mês/Ano)",
    datetime(get_br_datetime_now().year, get_br_datetime_now().month, 1).date(),
    format="DD/MM/YYYY",
    help="O ano desta data determinará qual tabela (2024 ou 2025) será utilizada nos cálculos."
)
# Extrai o ano para uso nos cálculos
ANO_CALCULO = data_competencia.year

st.info(f"O ano de competência selecionado é **{ANO_CALCULO}**. Os cálculos serão baseados nas tabelas de **{ANO_CALCULO}**.", icon="ℹ️")


# --- TABELAS LEGAIS 2025 (ORIGINAIS DO CÓDIGO) ---
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

# --- NOVAS TABELAS LEGAIS 2024 (INSERIDAS COM BASE NAS IMAGENS) ---
# Tabela INSS 2024 (Imagem 1000060093.png)
TABELA_INSS_2024 = [
    {"limite": 1412.00, "aliquota": 0.075},
    {"limite": 2666.68, "aliquota": 0.09},
    {"limite": 4000.03, "aliquota": 0.12},
    {"limite": 7786.02, "aliquota": 0.14}
]

# Tabela IRRF 2024 (Imagem 1000060094.png)
TABELA_IRRF_2024 = [
    {"limite": 2112.00, "aliquota": 0.0, "deducao": 0.0},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 158.40},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 370.40},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 651.73},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 884.96}
]

# Salário Família 2024 (Limite oficial 2024 e Valor por dependente da Imagem 1000060093.png)
# Nota: Limite oficial 2024 foi R$ 1.819,65 (Portaria Interministerial MPS/MF Nº 2/2024)
SALARIO_FAMILIA_LIMITE_2024 = 1819.65
VALOR_POR_DEPENDENTE_2024 = 62.04
DESCONTO_DEPENDENTE_IR_2024 = 189.59 # Conforme imagem 1000060094.png


# --- FUNÇÕES DE UTILIDADE ---

def formatar_moeda(valor):
    """Formata valor em moeda brasileira"""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    # Usa 'X' temporariamente para evitar conflito entre '.' de milhar e ',' de decimal
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(data):
    """Formata data no padrão brasileiro"""
    if isinstance(data, str):
        return data
    return data.strftime("%d/%m/%Y")

def get_br_datetime_now():
    """Retorna o objeto datetime configurado para o fuso horário de São Paulo (BRT/GMT-3)"""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# --- FUNÇÕES DE CÁLCULO (MODIFICADAS PARA USAR O ANO DE COMPETÊNCIA) ---

def calcular_inss(salario_bruto, ano_competencia):
    """Calcula desconto do INSS com a tabela correta (progressiva) para o ano de competência."""
    
    # Seleciona a tabela com base no ano
    if ano_competencia == 2024:
        tabela = TABELA_INSS_2024
    else: # Default para 2025
        tabela = TABELA_INSS
        
    teto_maximo = tabela[-1]["limite"]
    
    if salario_bruto <= 0:
        return 0.0
    
    salario_calculo = min(salario_bruto, teto_maximo)
    inss = 0.0
    salario_restante = salario_calculo
    
    for i, faixa in enumerate(tabela):
        if salario_restante <= 0:
            break
            
        if i == 0:
            valor_faixa = min(salario_restante, faixa["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
        else:
            faixa_anterior = tabela[i-1]
            # O limite real da faixa para cálculo é a diferença entre o limite atual e o anterior
            limite_faixa = faixa["limite"] - faixa_anterior["limite"]
            
            valor_faixa = min(salario_restante, limite_faixa)
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
    
    return round(inss, 2)

def calcular_salario_familia(salario, dependentes, ano_competencia):
    """Calcula salário família para o ano de competência."""
    
    # Seleciona o limite e valor com base no ano
    if ano_competencia == 2024:
        limite = SALARIO_FAMILIA_LIMITE_2024
        valor_dependente = VALOR_POR_DEPENDENTE_2024
    else: # Default para 2025
        limite = SALARIO_FAMILIA_LIMITE
        valor_dependente = VALOR_POR_DEPENDENTE

    if salario <= limite:
        return dependentes * valor_dependente
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos=0, ano_competencia=2025):
    """Calcula IRRF para o ano de competência."""
    
    # Seleciona a tabela e dedução por dependente com base no ano
    if ano_competencia == 2024:
        tabela = TABELA_IRRF_2024
        deducao_dependente = DESCONTO_DEPENDENTE_IR_2024
    else: # Default para 2025
        tabela = TABELA_IRRF
        deducao_dependente = DESCONTO_DEPENDENTE_IR
        
    # Base = Salário Bruto - Dedução por Dependente - INSS - Outros Descontos
    base_calculo = salario_bruto - (dependentes * deducao_dependente) - inss - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    irrf = 0.0
    for faixa in tabela:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(round(irrf, 2), 0.0)
    
    return 0.0

# --- FUNÇÃO AUXILIAR PARA O PDF ---

def obter_constantes_e_tabelas(ano):
    """Retorna todas as constantes e tabelas específicas para o ano dado."""
    if ano == 2024:
        return {
            'ano': 2024,
            'salario_familia_limite': SALARIO_FAMILIA_LIMITE_2024,
            'valor_por_dependente': VALOR_POR_DEPENDENTE_2024,
            'deducao_dependente_ir': DESCONTO_DEPENDENTE_IR_2024,
            'tabela_inss': TABELA_INSS_2024,
            'tabela_irrf': TABELA_IRRF_2024,
            'teto_inss': TABELA_INSS_2024[-1]["limite"]
        }
    else: # Default 2025
        return {
            'ano': 2025,
            'salario_familia_limite': SALARIO_FAMILIA_LIMITE,
            'valor_por_dependente': VALOR_POR_DEPENDENTE,
            'deducao_dependente_ir': DESCONTO_DEPENDENTE_IR,
            'tabela_inss': TABELA_INSS,
            'tabela_irrf': TABELA_IRRF,
            'teto_inss': TABELA_INSS[-1]["limite"]
        }


# --- FUNÇÕES DE GERAÇÃO DE PDF (MODIFICADAS PARA USAR O ANO DE COMPETÊNCIA) ---

def criar_link_download_pdf(pdf_output, filename):
    """
    Cria link para download do PDF a partir de um objeto bytes (output do FPDF).
    Garante que o input seja bytes para o base64.
    """
    # Garante que o input seja bytes, se for string, converte.
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    # Usa o output (garantido como bytes) para codificar em base64
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

def gerar_pdf_individual(dados, ano_competencia):
    """Gera PDF profissional para cálculo individual"""
    
    const = obter_constantes_e_tabelas(ano_competencia)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Configurar para suportar caracteres especiais (usa latin1 com fonte padrão)
    pdf.set_font('Arial', '', 12)
    
    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA - FOLHA DE PAGAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    # Informações da Empresa
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'INFORMAÇÕES GERAIS', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Data da Análise: {dados["data_analise"]}', 0, 1)
    pdf.cell(0, 6, f'Competência: {dados["competencia"]}', 0, 1)
    pdf.cell(0, 6, f'Tabelas Usadas: Ano {const["ano"]}', 0, 1) # Adiciona o ano usado
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
    
    if dados["salario_familia"] != "R$ 0,00":
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA APLICADO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA APLICADO: Não', 0, 1)
    
    if dados["irrf"] != "R$ 0,00":
        pdf.cell(0, 6, 'IRRF APLICADO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'IRRF APLICADO: Não (Isento)', 0, 1)
    
    pdf.ln(10)
    
    # --- INCLUSÃO DAS TABELAS NO PDF INDIVIDUAL (DINÂMICO PELO ANO) ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'TABELAS DE REFERÊNCIA {const["ano"]}', 0, 1)
    
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {const["ano"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(const["salario_familia_limite"]), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(const["valor_por_dependente"]), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {const["ano"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor Máx. na Faixa', 1, 1)
    
    faixas_inss_pdf = []
    
    for i, faixa in enumerate(const["tabela_inss"]):
        aliquota_percentual = f'{faixa["aliquota"] * 100:.1f}%'.replace('.', ',')
        
        if i == 0:
            limite_inferior = 0.0
            limite_superior = faixa["limite"]
            valor_max_faixa = limite_superior * faixa["aliquota"]
        else:
            limite_inferior = const["tabela_inss"][i-1]["limite"] + 0.01
            limite_superior = faixa["limite"]
            valor_max_faixa = (limite_superior - const["tabela_inss"][i-1]["limite"]) * faixa["aliquota"]
            
        faixas_inss_pdf.append((
            f'{formatar_moeda(limite_inferior)} a {formatar_moeda(limite_superior)}', 
            aliquota_percentual, 
            formatar_moeda(valor_max_faixa)
        ))
        
    for faixa, aliquota, valor in faixas_inss_pdf:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(const["teto_inss"])}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF {const["ano"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Parcela a Deduzir', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf_pdf = []
    
    for i, faixa in enumerate(const["tabela_irrf"]):
        aliquota_percentual = f'{faixa["aliquota"] * 100:.1f}%'.replace('.', ',')
        deducao = formatar_moeda(faixa["deducao"])
        
        if i == 0:
            base = f'Até {formatar_moeda(faixa["limite"])}'
            faixa_num = 'Isento'
        elif i == len(const["tabela_irrf"]) - 1:
            base = f'Acima de {formatar_moeda(const["tabela_irrf"][i-1]["limite"])}'
            faixa_num = f'{i}ª'
        else:
            base = f'{formatar_moeda(const["tabela_irrf"][i-1]["limite"] + 0.01)} a {formatar_moeda(faixa["limite"])}'
            faixa_num = f'{i}ª'
            
        faixas_irrf_pdf.append((base, aliquota_percentual, deducao, faixa_num))
        
    for base, aliquota, deducao, faixa in faixas_irrf_pdf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(const["deducao_dependente_ir"])}', 0, 1)
    pdf.ln(10)
    
    # Legislação e Metodologia
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO E METODOLOGIA', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        '- INSS: Lei 8.212/1991 e Portaria MF/MPS (Vigente para o ano)',
        '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB (Vigente para o ano)',
        f'- Vigência: Exercício {const["ano"]}'
    ]
    for item in legislacao:
        pdf.cell(0, 5, item, 0, 1)
    
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'METODOLOGIA DE CÁLCULO', 0, 1)
    pdf.set_font('Arial', '', 9)
    metodologia = [
        f'1. SALÁRIO FAMÍLIA: Verifica se salário bruto é menor ou igual a {formatar_moeda(const["salario_familia_limite"])}',
        f'2. CÁLCULO: Nº Dependentes × {formatar_moeda(const["valor_por_dependente"])} (se elegível)',
        '3. INSS: Cálculo progressivo por faixas acumulativas (Aliquota Efetiva)',
        f'4. BASE IRRF: Salário Bruto - Dependentes × {formatar_moeda(const["deducao_dependente_ir"])} - INSS - Outros Descontos',
        '5. IRRF: (Base × Alíquota) - Parcela a Deduzir (tabela progressiva)',
        '6. SALÁRIO LÍQUIDO: Salário Bruto + Salário Família - INSS - IRRF - Outros Descontos'
    ]
    for item in metodologia:
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)
    
    pdf.ln(10)
    
    # Rodapé
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, 'Este relatório foi gerado automaticamente pelo Sistema de Auditoria de Folha de Pagamento.', 0, 1, 'C')
    pdf.cell(0, 5, 'Consulte um contador para validação oficial dos cálculos.', 0, 1, 'C')
    pdf.cell(0, 5, f'Processado em: {dados["data_e_hora_processamento"]}', 0, 1, 'C')
    
    return pdf

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total, ano_competencia):
    """Gera PDF para auditoria completa"""
    
    const = obter_constantes_e_tabelas(ano_competencia)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Configurar para suportar caracteres especiais (usa latin1 com fonte padrão)
    pdf.set_font('Arial', '', 12)
    
    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA EM LOTE - FOLHA DE PAGAMENTO', 0, 1, 'C')
    pdf.ln(5)
    
    # Informações da Auditoria
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'INFORMAÇÕES DA AUDITORIA', 0, 1)
    pdf.set_font('Arial', '', 10)
    data_hora_agora = get_br_datetime_now()
    pdf.cell(0, 6, f'Data da Análise: {formatar_data(data_hora_agora)}', 0, 1)
    pdf.cell(0, 6, f'Total de Funcionários Auditados: {len(df_resultado)}', 0, 1)
    pdf.cell(0, 6, f'Arquivo Processado: {uploaded_filename}', 0, 1)
    pdf.cell(0, 6, f'Tabelas Usadas: Ano {const["ano"]}', 0, 1) # Adiciona o ano usado
    
    # Estatísticas de aplicação
    funcionarios_com_salario_familia = len(df_resultado[df_resultado['Salario_Familia'] > 0])
    funcionarios_com_irrf = len(df_resultado[df_resultado['IRRF'] > 0])
    
    pdf.cell(0, 6, f'Func. com Salário Família: {funcionarios_com_salario_familia}', 0, 1)
    pdf.cell(0, 6, f'Func. com IRRF: {funcionarios_com_irrf}', 0, 1)
    pdf.cell(0, 6, f'Func. Isentos IRRF: {len(df_resultado) - funcionarios_com_irrf}', 0, 1)
    
    pdf.ln(5)
    
    # Resumo Financeiro
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'RESUMO FINANCEIRO', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    resumo = [
        ('Total Salário Bruto', formatar_moeda(df_resultado['Salario_Bruto'].sum())),
        ('Total Salário Família', formatar_moeda(total_salario_familia)),
        ('Total INSS Recolhido', formatar_moeda(total_inss)),
        ('Total IRRF Recolhido', formatar_moeda(total_irrf)),
        ('Folha de Pagamento Líquida', formatar_moeda(folha_liquida_total))
    ]
    
    for descricao, valor in resumo:
        pdf.cell(100, 7, descricao)
        pdf.cell(0, 7, valor, 0, 1)
    
    pdf.ln(5)
    
    # Estatísticas Detalhadas
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'ESTATÍSTICAS DETALHADAS', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    estatisticas = [
        ('Média Salarial', formatar_moeda(df_resultado['Salario_Bruto'].mean())),
        ('Maior Salário', formatar_moeda(df_resultado['Salario_Bruto'].max())),
        ('Menor Salário', formatar_moeda(df_resultado['Salario_Bruto'].min())),
        ('Total de Dependentes', str(df_resultado['Dependentes'].sum())),
        ('Func. Elegíveis Salário Família', str(funcionarios_com_salario_familia)),
        ('Média de Dependentes', f"{df_resultado['Dependentes'].mean():.1f}")
    ]
    
    for descricao, valor in estatisticas:
        pdf.cell(100, 7, descricao)
        pdf.cell(0, 7, valor, 0, 1)
    
    pdf.ln(10)
    
    # Tabela de Resultados (primeiros 15 registros)
    if len(df_resultado) > 0:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'RESULTADOS DETALHADOS (Primeiros {min(15, len(df_resultado))} de {len(df_resultado)})', 0, 1)
        
        pdf.set_font('Arial', 'B', 8)
        # CORREÇÃO: Col
