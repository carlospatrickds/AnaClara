import streamlit as st
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo
from fpdf import FPDF
import base64
from io import BytesIO
import urllib.parse
import locale

# Configuração básica da página
st.set_page_config(
    page_title="Auditoria Folha de Pagamento",
    page_icon="💰",
    layout="wide"
)

# Configurar locale para formatação de moeda em algumas plataformas
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except locale.Error:
        pass # Ignora se não conseguir configurar o locale

# INICIALIZAR SESSION STATE
if 'df_resultado' not in st.session_state:
    st.session_state.df_resultado = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None
if 'dados_manuais' not in st.session_state:
    st.session_state.dados_manuais = []
if 'ultima_opcao' not in st.session_state:
    st.session_state.ultima_opcao = "📁 Upload de CSV"
if 'observacao_lote' not in st.session_state:
    st.session_state.observacao_lote = ""

st.title("💰 Auditoria de Folha de Pagamento - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- TABELAS LEGAIS ---

# Datas de Referência
DATA_INICIO_2024_IRRF = date(2024, 2, 1) # Início do período da MP 1.206/2024
DATA_INICIO_2025_IRRF = date(2025, 5, 1) # Início do período da MP 1.294/2025
DATA_INICIO_2023_IRRF = date(2023, 5, 1) # Início do período da alteração de 2023

# --- Salário Família & Dedução IR ---
DESCONTO_DEPENDENTE_IR = 189.59 

# Salário Família 2025 (Padrão 2025)
SF_LIMITE_2025 = 1906.04
SF_VALOR_2025 = 65.00

# Salário Família 2024
SF_LIMITE_2024 = 1819.26
SF_VALOR_2024 = 62.04

# Salário Família 2023
SF_LIMITE_2023 = 1754.18
SF_VALOR_2023 = 59.83

# --- Tabela INSS ---
TABELA_INSS_2025 = [
    {"limite": 1518.00, "aliquota": 0.075},
    {"limite": 2793.88, "aliquota": 0.09},
    {"limite": 4190.83, "aliquota": 0.12},
    {"limite": 8157.41, "aliquota": 0.14}
]

TABELA_INSS_2024 = [
    {"limite": 1412.00, "aliquota": 0.075},
    {"limite": 2666.68, "aliquota": 0.09},
    {"limite": 4000.03, "aliquota": 0.12},
    {"limite": 7786.02, "aliquota": 0.14}
]

# Tabela INSS 2023
TABELA_INSS_2023 = [
    {"limite": 1320.00, "aliquota": 0.075},
    {"limite": 2571.29, "aliquota": 0.09},
    {"limite": 3856.94, "aliquota": 0.12},
    {"limite": 7507.49, "aliquota": 0.14} 
]

# --- Desconto Simplificado (Opcional) ---
DS_MAX_FEV2024_ABR2025 = 564.80 
DS_MAX_MAI2025_DEZ2025 = 607.20 
DS_MAX_MAI2023_JAN2024 = 528.00 

# --- Tabela IRRF (01/05/2023 a 31/01/2024) ---
TABELA_IRRF_2023_MAI2024 = [
    {"limite": 2112.00, "aliquota": 0.0, "deducao": 0.00},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 158.40},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 370.40},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 651.73},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 884.96}
]

# --- Tabela IRRF (01/02/2024 a 30/04/2025 - MP 1.206/2024) ---
TABELA_IRRF_FEV2024_ABR2025 = [
    {"limite": 2259.20, "aliquota": 0.0, "deducao": 0.00},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 169.44},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 381.44},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 662.77},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 896.00}
]

# --- Tabela IRRF (01/05/2025 em diante - MP 1.294/2025) ---
TABELA_IRRF_MAI2025_DEZ2025 = [
    {"limite": 2428.80, "aliquota": 0.0, "deducao": 0.0},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 182.16},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 394.16},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 675.49},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 908.73} 
]


# --- FUNÇÕES DE UTILIDADE ---

def formatar_moeda(valor):
    """Formata valor em moeda brasileira"""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(data):
    """Formata data no padrão brasileiro"""
    if isinstance(data, str):
        return data
    if isinstance(data, date):
        return data.strftime("%d/%m/%Y")
    return data.strftime("%d/%m/%Y")

def get_br_datetime_now():
    """Retorna o objeto datetime configurado para o fuso horário de São Paulo (BRT/GMT-3)"""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# --- FUNÇÃO DE DOWNLOAD DE PDF (CORRIGIDA) ---
def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF a partir de um objeto bytes (output do FPDF)."""
    # A codificação 'latin1' é feita dentro das funções de PDF, o output já é binário (bytes)
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    # O link de download é criado
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

# --- FUNÇÕES DE CÁLCULO (MANTIDAS) ---

def selecionar_tabelas(competencia: date):
    """
    Seleciona as tabelas de INSS, IRRF e parâmetros de Salário Família e Desconto Simplificado
    com base na competência.
    """
    
    # Lógica INSS e Salário Família (Baseada no ano)
    if competencia.year == 2025:
        tabela_inss = TABELA_INSS_2025
        limite_sf = SF_LIMITE_2025
        valor_sf = SF_VALOR_2025
        ano_base = "2025"
    elif competencia.year == 2024:
        tabela_inss = TABELA_INSS_2024
        limite_sf = SF_LIMITE_2024
        valor_sf = SF_VALOR_2024
        ano_base = "2024"
    else: # 2023 ou anterior (usando 2023 como base para 2023)
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = "2023"

    # Lógica IRRF (Baseada na data específica)
    if competencia >= DATA_INICIO_2025_IRRF:
        tabela_irrf = TABELA_IRRF_MAI2025_DEZ2025
        irrf_periodo = "01/05/2025 em diante (MP 1.294/2025)"
        ds_maximo = DS_MAX_MAI2025_DEZ2025
    elif competencia >= DATA_INICIO_2024_IRRF:
        tabela_irrf = TABELA_IRRF_FEV2024_ABR2025
        irrf_periodo = "01/02/2024 a 30/04/2025 (MP 1.206/2024)"
        ds_maximo = DS_MAX_FEV2024_ABR2025
    elif competencia >= DATA_INICIO_2023_IRRF: # 01/05/2023 a 31/01/2024
        tabela_irrf = TABELA_IRRF_2023_MAI2024
        irrf_periodo = "01/05/2023 a 31/01/2024 (Tabela 2023)"
        ds_maximo = DS_MAX_MAI2023_JAN2024
    else: # Antes de 01/05/2023 (usando a tabela 2023 como fallback)
        tabela_irrf = TABELA_IRRF_2023_MAI2024
        irrf_periodo = "Tabelas Antigas (Utilizando 2023 como Referência)"
        ds_maximo = DS_MAX_MAI2023_JAN2024
        
    return tabela_inss, tabela_irrf, limite_sf, valor_sf, ano_base, irrf_periodo, ds_maximo

def selecionar_tabelas_simuladas(competencia: date):
    """
    Seleciona as tabelas do ano **anterior** à competência.
    Ex: Competência 01/2025 -> Tabela 2024
    """
    ano_simulado = competencia.year - 1
    
    # Simulação INSS e Salário Família
    if ano_simulado == 2024:
        tabela_inss = TABELA_INSS_2024
        limite_sf = SF_LIMITE_2024
        valor_sf = SF_VALOR_2024
        ano_base = "2024 (Simulação)"
    elif ano_simulado == 2023:
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = "2023 (Simulação)"
    else: # Fallback
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = f"{ano_simulado} (Simulação - Fallback 2023)"

    # Simulação IRRF
    if ano_simulado >= 2024:
        tabela_irrf = TABELA_IRRF_FEV2024_ABR2025 # Tabela de 2024 (MP 1.206/2024)
        irrf_periodo = "01/02/2024 a 30/04/2025 (Simulação)"
        ds_maximo = DS_MAX_FEV2024_ABR2025
    elif ano_simulado == 2023:
        tabela_irrf = TABELA_IRRF_2023_MAI2024 # Tabela de 2023 (após reajuste de isenção)
        irrf_periodo = "01/05/2023 a 31/01/2024 (Simulação)"
        ds_maximo = DS_MAX_MAI2023_JAN2024
    else: # Fallback
        tabela_irrf = TABELA_IRRF_2023_MAI2024 
        irrf_periodo = f"IRRF {ano_simulado} (Simulação - Fallback 2023)"
        ds_maximo = DS_MAX_MAI2023_JAN2024

    return tabela_inss, tabela_irrf, limite_sf, valor_sf, ano_base, irrf_periodo, ds_maximo

def calcular_irrf_base(base_calculo, tabela_irrf):
    """Calcula o IRRF dado uma base de cálculo específica."""
    if base_calculo <= 0:
        return 0.0
    
    irrf = 0.0
    for faixa in tabela_irrf:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(round(irrf, 2), 0.0)
    
    return 0.0

def calcular_inss(salario_bruto, tabela_inss):
    """Calcula desconto do INSS com base na tabela progressiva fornecida."""
    if salario_bruto <= 0:
        return 0.0
    
    teto_inss = tabela_inss[-1]["limite"]
    salario_calculo = min(salario_bruto, teto_inss)
    inss = 0.0
    salario_restante = salario_calculo
    
    for i, faixa in enumerate(tabela_inss):
        if salario_restante <= 0:
            break
            
        if i == 0:
            valor_faixa = min(salario_restante, faixa["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
        else:
            faixa_anterior = tabela_inss[i-1]
            limite_faixa = faixa["limite"] - faixa_anterior["limite"]
            
            valor_faixa = min(salario_restante, limite_faixa)
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
    
    return round(inss, 2)

def calcular_salario_familia(salario, dependentes, limite_sf, valor_sf):
    """Calcula salário família com base nos parâmetros de limite e valor por dependente."""
    if salario <= limite_sf:
        return dependentes * valor_sf
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos, tabela_irrf, ds_maximo):
    """
    Calcula IRRF comparando o Desconto Legal com o Desconto Simplificado
    e utilizando o método mais benéfico.
    """
    
    # 1. CÁLCULO LEGAL (Padrão)
    deducao_legal = (dependentes * DESCONTO_DEPENDENTE_IR) + inss + outros_descontos
    base_legal = salario_bruto - deducao_legal
    irrf_legal = calcular_irrf_base(base_legal, tabela_irrf)
    
    # 2. CÁLCULO SIMPLIFICADO (Simulando a forma mais benéfica encontrada em sites)
    deducao_simplificada_valor = ds_maximo
    base_simplificada_site = salario_bruto - deducao_simplificada_valor
    irrf_simplificado_site = calcular_irrf_base(base_simplificada_site, tabela_irrf)
    
    # 3. ESCOLHA DO MAIS BENÉFICO (Menor IRRF)
    
    if irrf_legal <= irrf_simplificado_site:
        return irrf_legal, "Legal", base_legal, deducao_legal
    else:
        # Retorna o cálculo do Desconto Simplificado que foi mais benéfico
        return irrf_simplificado_site, "Simplificado", base_simplificada_site, deducao_simplificada_valor

# --- FUNÇÕES DE GERAÇÃO DE PDF (CORRIGIDAS) ---

def gerar_pdf_individual(dados, obs):
    """Gera PDF profissional para cálculo individual (CORREÇÃO DE ENCODING)."""
    pdf = FPDF()
    pdf.add_page()
    
    # Garantir que a fonte padrão esteja disponível
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
    pdf.cell(0, 6, f'Tabelas INSS Aplicadas: {dados["ano_base"]}', 0, 1)
    pdf.cell(0, 6, f'Tabelas IRRF Aplicadas: {dados["irrf_periodo"]}', 0, 1)
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
    pdf.cell(0, 6, f'Dedução IRRF Aplicada: {dados["metodo_deducao"]}', 0, 1)
    pdf.cell(0, 6, f'Valor de Dedução na BC: {dados["valor_deducao"]}', 0, 1)
    
    if dados["salario_familia"] != "R$ 0,00":
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA PAGO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA PAGO: Não', 0, 1)
    
    if dados["irrf"] != "R$ 0,00":
        pdf.cell(0, 6, 'IRRF APLICADO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'IRRF APLICADO: Não (Isento)', 0, 1)
    
    pdf.ln(5)
    
    # --- NOVO: OBSERVAÇÕES ---
    if obs:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OBSERVAÇÕES DO ANALISTA', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, obs)
        pdf.ln(5)
    
    # --- INCLUSÃO DAS TABELAS NO PDF INDIVIDUAL ---
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Referência INSS: Tabelas de {dados["ano_base"]}', 0, 1)
    pdf.cell(0, 6, f'Referência IRRF: Tabela com vigência {dados["irrf_periodo"]}', 0, 1)
    pdf.ln(5)

    # Obter tabelas completas
    tabela_inss_referencia, tabela_irrf_referencia, SF_LIMITE, SF_VALOR, _, irrf_periodo_detalhado, ds_maximo = selecionar_tabelas(dados["competencia_obj"])
        
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {dados["ano_base"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(SF_LIMITE), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(SF_VALOR), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs_sf in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs_sf, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS (Exibindo a tabela aplicada)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {dados["ano_base"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor Máx. na Faixa', 1, 1)
    
    faixas_inss = []
    limite_anterior = 0.0
    for i, faixa in enumerate(tabela_inss_referencia):
        limite = faixa["limite"]
        aliquota_percentual = f"{faixa['aliquota'] * 100:.1f}%"
        
        if i == 0:
            faixa_desc = f'Até {formatar_moeda(limite)}'
            valor_max_faixa = formatar_moeda(limite * faixa["aliquota"])
        else:
            faixa_anterior = tabela_inss_referencia[i-1]
            faixa_desc = f'{formatar_moeda(limite_anterior + 0.01)} a {formatar_moeda(limite)}'
            valor_max_faixa = formatar_moeda((limite - limite_anterior) * faixa["aliquota"])
            
        faixas_inss.append((faixa_desc, aliquota_percentual, valor_max_faixa))
        limite_anterior = limite
        
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(tabela_inss_referencia[-1]["limite"])}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF (Exibindo a tabela aplicada)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF ({irrf_periodo_detalhado})', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Parcela a Deduzir', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = []
    limite_anterior = 0.0
    for i, faixa in enumerate(tabela_irrf_referencia):
        limite = faixa["limite"]
        aliquota_percentual = f"{faixa['aliquota'] * 100:.1f}%" if faixa['aliquota'] > 0 else '0%'
        deducao = formatar_moeda(faixa["deducao"])
        
        if limite == float('inf'):
            base_desc = f'Acima de {formatar_moeda(limite_anterior)}'
            faixa_num = f'{i}ª'
        elif i == 0:
            base_desc = f'Até {formatar_moeda(limite)}'
            faixa_num = 'Isento'
        else:
            base_desc = f'{formatar_moeda(limite_anterior + 0.01)} a {formatar_moeda(limite)}'
            faixa_num = f'{i+1}ª'
            
        faixas_irrf.append((base_desc, aliquota_percentual, deducao, faixa_num))
        limite_anterior = limite
    
    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(DESCONTO_DEPENDENTE_IR)}', 0, 1)
    pdf.cell(0, 6, f'Desconto Simplificado Máximo: {formatar_moeda(ds_maximo)}', 0, 1)
    pdf.ln(10)
    
    # Legislação e Metodologia
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO E METODOLOGIA', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        f'- INSS: Lei 8.212/1991 e Portaria de Referência de {dados["ano_base"]}',
        f'- IRRF: Lei 7.713/1988 e Medidas Provisórias (Ex: MP 1.206/2024 e MP 1.294/2025)',
        f'- Vigência Aplicada: INSS ({dados["ano_base"]}), IRRF ({dados["irrf_periodo"]})'
    ]
    for item in legislacao:
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)
    
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'METODOLOGIA DE CÁLCULO', 0, 1)
    pdf.set_font('Arial', '', 9)
    metodologia = [
        f'1. SALÁRIO FAMÍLIA: Aplicado se salário bruto <= {formatar_moeda(SF_LIMITE)}.',
        '2. INSS: Cálculo progressivo por faixas (Alíquota Efetiva).',
        '3. DEDUÇÃO LEGAL: Salário Bruto - INSS - Dependentes * R$ 189,59 - Outros Descontos.',
        f'4. DEDUÇÃO SIMPLIFICADA: Salário Bruto - {formatar_moeda(ds_maximo)}.',
        '5. IRRF: Calculado sobre a Base de Cálculo que resultar no **menor imposto**.',
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
    
    # CORREÇÃO ESSENCIAL: Retorna o output em bytes, codificado em latin1
    return pdf.output(dest='S').encode('latin1')

# --- FUNÇÕES DE GERAÇÃO DE PDF (COMPLETO E CORRIGIDO) ---

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total, obs_lote):
    """
    Gera PDF com o resumo da auditoria em lote e os dados detalhados (CORREÇÃO DE ENCODING).
    """
    # Usando orientação Paisagem (L) para caber mais colunas
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()

    # Configurações de fonte
    pdf.set_font('Arial', '', 10)
    
    # Obtendo a data/hora para o relatório
    data_hora_agora = get_br_datetime_now()
    data_hora_formatada = data_hora_agora.strftime("%d/%m/%Y %H:%M")
    
    # Informações das tabelas aplicadas (obter de um registro, já que é o mesmo para o lote)
    competencia_lote = df_resultado['Competencia'].iloc[0]
    # Usando selecionar_tabelas para obter as informações
    _, _, _, _, ano_base, irrf_periodo, _ = selecionar_tabelas(competencia_lote)

    # Cabeçalho
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RELATÓRIO DE AUDITORIA DE FOLHA DE PAGAMENTO - LOTE', 0, 1, 'C')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f'Arquivo/Fonte: {uploaded_filename}', 0, 1)
    pdf.cell(0, 5, f'Competência Analisada: {formatar_data(competencia_lote)}', 0, 1)
    pdf.cell(0, 5, f'Processado em: {data_hora_formatada}', 0, 1)
    pdf.cell(0, 5, f'Tabelas: INSS ({ano_base}), IRRF ({irrf_periodo})', 0, 1)
    pdf.ln(5)

    # Resumo Financeiro
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'RESUMO FINANCEIRO DO LOTE', 0, 1)
    
    pdf.set_font('Arial', '', 10)
    resumo = [
        ('Total Salário Bruto', df_resultado['Salario_Bruto'].sum()),
        ('Total Salário Família', total_salario_familia),
        ('Total INSS Descontado', total_inss),
        ('Total IRRF Descontado', total_irrf),
        ('Total Folha Líquida', folha_liquida_total),
    ]
    
    for descricao, valor in resumo:
        pdf.cell(70, 6, descricao, 1)
        pdf.cell(50, 6, formatar_moeda(valor), 1, 1)
    pdf.ln(5)

    # Observações do Lote
    if obs_lote:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OBSERVAÇÕES GERAIS DO ANALISTA', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, obs_lote)
        pdf.ln(5)

    # Tabela de Resultados
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'DETALHAMENTO POR FUNCIONÁRIO', 0, 1)

    # Prepara o DataFrame para o PDF
    df_pdf = df_resultado.copy()
    
    # Ajusta as colunas a serem exibidas no PDF (considerando a simulação, se existir)
    if 'IRRF_Sim' in df_pdf.columns:
        df_pdf = df_pdf[['Nome', 'Salario_Bruto', 'Dependentes', 'Salario_Familia', 'Salario_Familia_Sim', 
                         'INSS', 'INSS_Sim', 'IRRF', 'IRRF_Sim', 'Outros_Descontos', 'Salario_Liquido', 'Salario_Liquido_Sim', 
                         'Metodo_Deducao', 'Metodo_Deducao_Sim']]
        df_pdf.columns = ['Nome', 'Sal. Bruto', 'Deps.', 'SF Of.', 'SF Sim.', 'INSS Of.', 'INSS Sim.', 'IRRF Of.', 'IRRF Sim.', 'Outros Desc.', 'Líq. Of.', 'Líq. Sim.', 'Ded Of.', 'Ded Sim.']
        col_widths = [25, 17, 10, 16, 16, 16, 16, 16, 16, 16, 18, 18, 10, 10]
    else:
        df_pdf = df_pdf[['Nome', 'Salario_Bruto', 'Dependentes', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido', 'Metodo_Deducao']]
        df_pdf.columns = ['Nome', 'Sal. Bruto', 'Deps.', 'Sal. Fam.', 'INSS', 'IRRF', 'Outros Desc.', 'Sal. Líquido', 'Ded. IR']
        col_widths = [45, 20, 10, 20, 20, 20, 20, 20, 20] # Larguras das colunas
        
    # Títulos da tabela
    pdf.set_font('Arial', 'B', 8)
    for i, header in enumerate(df_pdf.columns):
        pdf.cell(col_widths[i], 7, header, 1, 0, 'C')
    pdf.ln()

    # Dados da tabela
    pdf.set_font('Arial', '', 7)
    for _, row in df_pdf.iterrows():
        i = 0
        
        # Nome
        pdf.cell(col_widths[i], 6, row[df_pdf.columns[i]], 1, 0); i += 1
        
        # Valores (Monetários e Dependentes)
        for col_name in df_pdf.columns[i:]:
            if col_name in ['Deps.']:
                pdf.cell(col_widths[i], 6, str(row[col_name]), 1, 0, 'C')
            elif 'Ded' in col_name or col_name in ['Ded IR Of.', 'Ded IR Sim.']:
                pdf.cell(col_widths[i], 6, row[col_name], 1, 0, 'C')
            else:
                pdf.cell(col_widths[i], 6, formatar_moeda(row[col_name].replace('R$ ', '').replace('.', '').replace(',', '.').replace('X', '')), 1, 0, 'R')
            i += 1
            
        pdf.ln()
        
        # Se a página estiver cheia, adiciona uma nova
        if pdf.get_y() > 185:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 8)
            for i, header in enumerate(df_pdf.columns):
                pdf.cell(col_widths[i], 7, header, 1, 0, 'C')
            pdf.ln()
            pdf.set_font('Arial', '', 7)

    pdf.ln(10)

    # Rodapé Legal
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 5, 'Este relatório de lote foi gerado automaticamente pelo Sistema de Auditoria de Folha de Pagamento.', 0, 1, 'C')
    pdf.cell(0, 5, 'Consulte um contador para validação oficial dos cálculos e interpretação da legislação.', 0, 1, 'C')

    # CORREÇÃO ESSENCIAL: Retorna o output em bytes, codificado em latin1
    return pdf.output(dest='S').encode('latin1')

# --- INTERFACE STREAMLIT (INÍCIO DA INTERFACE) ---

# Definição das abas
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Individual", "📊 Auditoria em Lote", "ℹ️ Informações"])

# ----------------------------------------------------------------------

with tab1:
    st.header("Cálculo Individual")
    
    col1, col2, col_comp = st.columns(3)
    
    with col1:
        nome = st.text_input("Nome do Funcionário", "João Silva")
        salario = st.number_input("Salário Bruto (R$)", 
                                  min_value=0.0, 
                                  value=3000.0, 
                                  step=100.0)
    
    with col2:
        dependentes = st.number_input("Número de Dependentes", 
                                      min_value=0, 
                                      value=1, 
                                      step=1)
        outros_descontos = st.number_input("Outros Descontos (R$)", 
                                           min_value=0.0, 
                                           value=0.0, 
                                           step=50.0)
    
    with col_comp:
        competencia = st.date_input("Competência Analisada (Padrão)", 
                                    value=date(2025, 1, 1),
                                    format="DD/MM/YYYY")

        # --- CHECKBOX DE SIMULAÇÃO ---
        simular_ano_anterior = st.checkbox(
            "Simular cálculo com tabelas do **Ano Anterior**",
            value=False,
            help=f"Ex: Se a Competência é 01/2025, simula com as tabelas de 2024. Se for 01/2024, simula com 2023."
        )

    # --- CAMPO DE OBSERVAÇÃO ---
    observacao_individual = st.text_area(
        "Observação (Opcional - Será incluída no PDF)",
        value="",
        height=100
    )
    
    if st.button("Calcular", type="primary"):
        
        # --- CÁLCULO ATUAL (OFICIAL) ---
        tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_base, irrf_periodo, ds_maximo = selecionar_tabelas(competencia)
        inss_valor = calcular_inss(salario, tabela_inss_aplicada)
        sal_familia = calcular_salario_familia(salario, dependentes, limite_sf_aplicado, valor_sf_aplicado)
        irrf_valor, metodo_deducao, base_irrf_valor, valor_deducao = calcular_irrf(salario, dependentes, inss_valor, outros_descontos, tabela_irrf_aplicada, ds_maximo)
        total_descontos = inss_valor + irrf_valor + outros_descontos
        salario_liquido = salario - total_descontos + sal_familia
        
        # --- CÁLCULO DE SIMULAÇÃO (SE MARCADO) ---
        dados_simulacao = None
        if simular_ano_anterior:
            t_inss_sim, t_irrf_sim, l_sf_sim, v_sf_sim, ano_base_sim, irrf_periodo_sim, ds_max_sim = selecionar_tabelas_simuladas(competencia)
            inss_sim = calcular_inss(salario, t_inss_sim)
            sal_familia_sim = calcular_salario_familia(salario, dependentes, l_sf_sim, v_sf_sim)
            irrf_sim, metodo_deducao_sim, base_irrf_sim, valor_deducao_sim = calcular_irrf(salario, dependentes, inss_sim, outros_descontos, t_irrf_sim, ds_max_sim)
            total_desc_sim = inss_sim + irrf_sim + outros_descontos
            salario_liquido_sim = salario - total_desc_sim + sal_familia_sim
            
            dados_simulacao = {
                "inss": inss_sim, "sal_familia": sal_familia_sim, "irrf": irrf_sim,
                "salario_liquido": salario_liquido_sim, "total_descontos": total_desc_sim,
                "metodo_deducao": metodo_deducao_sim, "ano_base": ano_base_sim,
                "irrf_periodo": irrf_periodo_sim
            }

        st.success(f"Cálculos realizados com sucesso! Tabelas Oficiais: INSS **{ano_base}**, IRRF **{irrf_periodo}** aplicadas.")
        
        # --- EXIBIÇÃO DE RESULTADOS ---
        
        st.subheader("📋 Resultados Detalhados")
        
        if dados_simulacao:
            col_atual, col_simulacao = st.columns(2)
            
            with col_atual:
                st.markdown("#### ✅ Tabela Aplicada (OFICIAL)")
                st.info(f"INSS: **{ano_base}** | IRRF: **{irrf_periodo}**")
                
                detalhes_atual = pd.DataFrame({
                    'Descrição': ['Salário Bruto', 'Salário Família', 'INSS', 'IRRF', 'Outros Descontos','Total Descontos','Salário Líquido'],
                    'Valor Oficial': [salario, sal_familia, inss_valor, irrf_valor, outros_descontos, total_descontos, salario_liquido]
                })
                detalhes_atual['Valor Oficial'] = detalhes_atual['Valor Oficial'].apply(formatar_moeda)
                st.dataframe(detalhes_atual, use_container_width=True, hide_index=True)
                st.write(f"Método Dedução IRRF: **{metodo_deducao}**")

            with col_simulacao:
                st.markdown("#### ⚠️ Simulação (Tabelas do Ano Anterior)")
                st.warning(f"INSS: **{dados_simulacao['ano_base']}** | IRRF: **{dados_simulacao['irrf_periodo']}**")
                
                detalhes_sim = pd.DataFrame({
                    'Descrição': ['Salário Bruto', 'Salário Família', 'INSS', 'IRRF', 'Outros Descontos','Total Descontos','Salário Líquido'],
                    'Valor Simulado': [salario, dados_simulacao['sal_familia'], dados_simulacao['inss'], dados_simulacao['irrf'], outros_descontos, dados_simulacao['total_descontos'], dados_simulacao['salario_liquido']]
                })
                detalhes_sim['Valor Simulado'] = detalhes_sim['Valor Simulado'].apply(formatar_moeda)
                st.dataframe(detalhes_sim, use_container_width=True, hide_index=True)
                st.write(f"Método Dedução IRRF: **{dados_simulacao['metodo_deducao']}**")
            
            # Comparativo Final (Apenas para o IRRF e Líquido)
            if irrf_valor != irrf_sim:
                st.markdown("---")
                st.error(f"**DIFERENÇA NO IRRF:** R$ {irrf_valor - irrf_sim:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.error(f"**DIFERENÇA NO LÍQUIDO:** R$ {salario_liquido - salario_liquido_sim:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            else:
                st.markdown("---")
                st.success("Não houve diferença nos cálculos entre as tabelas oficial e simulada.")


        else: # Exibição padrão se não houver simulação
            st.write(f"Tabelas de referência: **INSS {ano_base}, IRRF {irrf_periodo}**")
            st.write(f"**Método de Dedução IRRF:** **{metodo_deducao}** (Base R\$ {formatar_moeda(base_irrf_valor)[3:]} utilizada no cálculo)")
            
            detalhes = pd.DataFrame({
                'Descrição': ['Salário Bruto', 'Salário Família', 'INSS', 'IRRF', 'Outros Descontos','Total Descontos','Salário Líquido'],
                'Valor': [formatar_moeda(salario), formatar_moeda(sal_familia), formatar_moeda(inss_valor), formatar_moeda(irrf_valor), formatar_moeda(outros_descontos), formatar_moeda(total_descontos), formatar_moeda(salario_liquido)]
            })
            st.dataframe(detalhes, use_container_width=True, hide_index=True)
            
        # GERAÇÃO DE PDF (Sempre usa os dados oficiais)
        st.subheader("📄 Gerar Relatório PDF")
        
        data_hora_agora = get_br_datetime_now()
        data_hora_formatada = data_hora_agora.strftime("%d/%m/%Y %H:%M")
        
        # Prepara os dados para o PDF
        dados_pdf = {
            "data_analise": formatar_data(data_hora_agora),
            "competencia": formatar_data(competencia),
            "competencia_obj": competencia,
            "ano_base": ano_base,
            "irrf_periodo": irrf_periodo,
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
            "base_irrf": formatar_moeda(base_irrf_valor),
            "metodo_deducao": metodo_deducao,
            "valor_deducao": formatar_moeda(valor_deducao),
            "data_e_hora_processamento": data_hora_formatada 
        }
        
        try:
            # CORRIGIDO: Chama a função que agora retorna bytes codificados em latin1
            pdf_output = gerar_pdf_individual(dados_pdf, observacao_individual)
            
            st.markdown(
                criar_link_download_pdf(
                    pdf_output, 
                    f"Auditoria_Folha_{nome.replace(' ', '_')}_{data_hora_agora.strftime('%d%m%Y_%H%M')}.pdf"
                ), 
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"❌ Erro ao gerar PDF: {e}")

# ----------------------------------------------------------------------

with tab2:
    st.header("Auditoria em Lote")
    
    st.info("""
    **📊 Opções de Entrada de Dados:**
    Escolha uma das opções para carregar os dados dos funcionários.
    """)
    
    col_lote1, col_lote2 = st.columns([2, 1])
