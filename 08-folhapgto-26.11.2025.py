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
        pass

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
if 'mostrar_simulacao_ano_anterior' not in st.session_state:
    st.session_state.mostrar_simulacao_ano_anterior = False

st.title("💰 Auditoria de Folha de Pagamento - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- TABELAS LEGAIS ---

# Datas de Referência
DATA_INICIO_2024_IRRF = date(2024, 2, 1)
DATA_INICIO_2025_IRRF = date(2025, 5, 1)

# --- Salário Família & Dedução IR ---
DESCONTO_DEPENDENTE_IR = 189.59 

# --- NOVO: Salário Família 2023 ---
SF_LIMITE_2023 = 1754.18  # Valor aproximado baseado no salário mínimo de 2023 (R$ 1.320,00)
SF_VALOR_2023 = 56.47     # Valor por dependente em 2023

# Salário Família 2024
SF_LIMITE_2024 = 1819.26
SF_VALOR_2024 = 62.04

# Salário Família 2025
SF_LIMITE_2025 = 1906.04
SF_VALOR_2025 = 65.00

# --- Tabela INSS ---
# NOVA: Tabela INSS 2023
TABELA_INSS_2023 = [
    {"limite": 1320.00, "aliquota": 0.075},
    {"limite": 2571.29, "aliquota": 0.09},
    {"limite": 3856.94, "aliquota": 0.12},
    {"limite": 7507.49, "aliquota": 0.14}
]

TABELA_INSS_2024 = [
    {"limite": 1412.00, "aliquota": 0.075},
    {"limite": 2666.68, "aliquota": 0.09},
    {"limite": 4000.03, "aliquota": 0.12},
    {"limite": 7786.02, "aliquota": 0.14}
]

TABELA_INSS_2025 = [
    {"limite": 1518.00, "aliquota": 0.075},
    {"limite": 2793.88, "aliquota": 0.09},
    {"limite": 4190.83, "aliquota": 0.12},
    {"limite": 8157.41, "aliquota": 0.14}
]

# --- Desconto Simplificado (Opcional) ---
# Para 2023: 25% de 2.112,00 = 528,00
DS_MAX_2023 = 528.00
DS_MAX_FEV2024_ABR2025 = 564.80 
DS_MAX_MAI2025_DEZ2025 = 607.20 

# --- Tabela IRRF 2023 (01/05/2023 a 31/01/2024) ---
TABELA_IRRF_2023_JAN2024 = [
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

def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF a partir de um objeto bytes (output do FPDF)."""
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

# --- FUNÇÕES PARA SIMULAÇÃO ANO ANTERIOR ---

def selecionar_tabelas_ano_anterior(competencia: date):
    """
    Seleciona as tabelas do ano anterior para simulação.
    Para 2024 -> 2023, para 2025 -> 2024
    """
    ano_anterior = competencia.year - 1
    
    if ano_anterior == 2023:
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = "2023"
        # Para 2023, usamos a tabela IRRF de 2023
        tabela_irrf = TABELA_IRRF_2023_JAN2024
        irrf_periodo = "01/05/2023 a 31/01/2024"
        ds_maximo = DS_MAX_2023
    elif ano_anterior == 2024:
        tabela_inss = TABELA_INSS_2024
        limite_sf = SF_LIMITE_2024
        valor_sf = SF_VALOR_2024
        ano_base = "2024"
        # Para simulação com 2024 em 2025, usamos a tabela IRRF de 2024
        tabela_irrf = TABELA_IRRF_FEV2024_ABR2025
        irrf_periodo = "01/02/2024 a 30/04/2025 (MP 1.206/2024)"
        ds_maximo = DS_MAX_FEV2024_ABR2025
    else:
        # Fallback para o ano atual se não houver tabela específica
        return selecionar_tabelas(competencia)
        
    return tabela_inss, tabela_irrf, limite_sf, valor_sf, ano_base, irrf_periodo, ds_maximo

def selecionar_tabelas(competencia: date):
    """
    Seleciona as tabelas de INSS, IRRF e parâmetros de Salário Família e Desconto Simplificado
    com base na competência.
    """
    
    # Lógica INSS e Salário Família (Baseada no ano)
    if competencia.year == 2023:
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = "2023"
    elif competencia.year == 2024:
        tabela_inss = TABELA_INSS_2024
        limite_sf = SF_LIMITE_2024
        valor_sf = SF_VALOR_2024
        ano_base = "2024"
    else: # 2025 ou anos seguintes
        tabela_inss = TABELA_INSS_2025
        limite_sf = SF_LIMITE_2025
        valor_sf = SF_VALOR_2025
        ano_base = "2025"

    # Lógica IRRF (Baseada na data específica)
    if competencia >= DATA_INICIO_2025_IRRF:
        tabela_irrf = TABELA_IRRF_MAI2025_DEZ2025
        irrf_periodo = "01/05/2025 em diante (MP 1.294/2025)"
        ds_maximo = DS_MAX_MAI2025_DEZ2025
    elif competencia >= DATA_INICIO_2024_IRRF:
        tabela_irrf = TABELA_IRRF_FEV2024_ABR2025
        irrf_periodo = "01/02/2024 a 30/04/2025 (MP 1.206/2024)"
        ds_maximo = DS_MAX_FEV2024_ABR2025
    else: # Antes de 01/02/2024
        tabela_irrf = TABELA_IRRF_2023_JAN2024
        irrf_periodo = "01/05/2023 a 31/01/2024"
        ds_maximo = DS_MAX_2023 
        
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
        return irrf_simplificado_site, "Simplificado", base_simplificada_site, deducao_simplificada_valor

# --- FUNÇÃO PARA CALCULAR SIMULAÇÃO ANO ANTERIOR ---
def calcular_simulacao_ano_anterior(salario, dependentes, outros_descontos, competencia):
    """
    Calcula uma simulação usando as tabelas do ano anterior
    """
    tabela_inss_anterior, tabela_irrf_anterior, limite_sf_anterior, valor_sf_anterior, ano_base_anterior, irrf_periodo_anterior, ds_maximo_anterior = selecionar_tabelas_ano_anterior(competencia)
    
    inss_anterior = calcular_inss(salario, tabela_inss_anterior)
    sal_familia_anterior = calcular_salario_familia(salario, dependentes, limite_sf_anterior, valor_sf_anterior)
    
    irrf_anterior, metodo_deducao_anterior, base_irrf_anterior, valor_deducao_anterior = calcular_irrf(
        salario, dependentes, inss_anterior, outros_descontos, tabela_irrf_anterior, ds_maximo_anterior
    )
    
    total_descontos_anterior = inss_anterior + irrf_anterior + outros_descontos
    salario_liquido_anterior = salario - total_descontos_anterior + sal_familia_anterior
    
    return {
        "salario_familia": sal_familia_anterior,
        "inss": inss_anterior,
        "irrf": irrf_anterior,
        "total_descontos": total_descontos_anterior,
        "salario_liquido": salario_liquido_anterior,
        "ano_base": ano_base_anterior,
        "irrf_periodo": irrf_periodo_anterior,
        "metodo_deducao": metodo_deducao_anterior,
        "base_irrf": base_irrf_anterior,
        "valor_deducao": valor_deducao_anterior
    }

# --- FUNÇÕES DE GERAÇÃO DE PDF ---

def gerar_pdf_individual(dados, obs):
    """Gera PDF profissional para cálculo individual (MODIFICADO para incluir OBS e DEDUÇÃO)"""
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
    
    return pdf

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total, obs_lote):
    """
    Gera PDF com o resumo da auditoria em lote e os dados detalhados.
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
    df_pdf = df_pdf[['Nome', 'Salario_Bruto', 'Dependentes', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido', 'Metodo_Deducao']]
    df_pdf.columns = ['Nome', 'Sal. Bruto', 'Deps.', 'Sal. Fam.', 'INSS', 'IRRF', 'Outros Desc.', 'Sal. Líquido', 'Ded. IR']

    # Títulos da tabela
    col_widths = [45, 20, 10, 20, 20, 20, 20, 20, 20] # Larguras das colunas
    pdf.set_font('Arial', 'B', 8)
    for i, header in enumerate(df_pdf.columns):
        pdf.cell(col_widths[i], 7, header, 1, 0, 'C')
    pdf.ln()

    # Dados da tabela
    pdf.set_font('Arial', '', 7)
    for _, row in df_pdf.iterrows():
        # Nome
        pdf.cell(col_widths[0], 6, row['Nome'], 1, 0)
        # Salário Bruto
        pdf.cell(col_widths[1], 6, formatar_moeda(row['Sal. Bruto']), 1, 0, 'R')
        # Dependentes
        pdf.cell(col_widths[2], 6, str(row['Deps.']), 1, 0, 'C')
        # Salário Família
        pdf.cell(col_widths[3], 6, formatar_moeda(row['Sal. Fam.']), 1, 0, 'R')
        # INSS
        pdf.cell(col_widths[4], 6, formatar_moeda(row['INSS']), 1, 0, 'R')
        # IRRF
        pdf.cell(col_widths[5], 6, formatar_moeda(row['IRRF']), 1, 0, 'R')
        # Outros Descontos
        pdf.cell(col_widths[6], 6, formatar_moeda(row['Outros Desc.']), 1, 0, 'R')
        # Salário Líquido
        pdf.cell(col_widths[7], 6, formatar_moeda(row['Sal. Líquido']), 1, 0, 'R')
        # Dedução IR
        pdf.cell(col_widths[8], 6, row['Ded. IR'], 1, 1, 'C') # 1, 1 para quebrar linha
        
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

    return pdf

# --- INTERFACE STREAMLIT ---

# Definição das abas
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Individual", "📊 Auditoria em Lote", "ℹ️ Informações"])

# ----------------------------------------------------------------------

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
                                    value=date(2025, 1, 1),
                                    format="DD/MM/YYYY")
    
    # --- NOVO: CHECKBOX PARA SIMULAÇÃO DO ANO ANTERIOR ---
    mostrar_simulacao = st.checkbox(
        "📊 Mostrar simulação com tabelas do ano anterior", 
        value=st.session_state.mostrar_simulacao_ano_anterior,
        help="Compara os cálculos atuais com uma simulação usando as tabelas do ano anterior"
    )
    st.session_state.mostrar_simulacao_ano_anterior = mostrar_simulacao
    
    observacao_individual = st.text_area(
        "Observação (Opcional - Será incluída no PDF)",
        value="",
        height=100
    )
    
    if st.button("Calcular", type="primary"):
        
        # 1. CÁLCULO COM TABELAS ATUAIS
        tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_base, irrf_periodo, ds_maximo = selecionar_tabelas(competencia)
        
        inss_valor = calcular_inss(salario, tabela_inss_aplicada)
        sal_familia = calcular_salario_familia(salario, dependentes, limite_sf_aplicado, valor_sf_aplicado)
        
        irrf_valor, metodo_deducao, base_irrf_valor, valor_deducao = calcular_irrf(salario, dependentes, inss_valor, outros_descontos, tabela_irrf_aplicada, ds_maximo)
        
        total_descontos = inss_valor + irrf_valor + outros_descontos
        total_acrescimos = sal_familia
        salario_liquido = salario - total_descontos + total_acrescimos
        
        st.success(f"Cálculos realizados com sucesso! Dedução IRRF: {metodo_deducao}. Tabelas INSS: {ano_base}, IRRF: {irrf_periodo} aplicadas.")
        
        # 2. SE SOLICITADO, CALCULA SIMULAÇÃO COM ANO ANTERIOR
        if mostrar_simulacao:
            simulacao_anterior = calcular_simulacao_ano_anterior(salario, dependentes, outros_descontos, competencia)
            
            st.subheader("🔄 Comparativo: Ano Atual vs Ano Anterior")
            
            col_comp1, col_comp2 = st.columns(2)
            
            with col_comp1:
                st.markdown("### 📅 Cálculo Atual")
                st.metric("Salário Família", formatar_moeda(sal_familia))
                st.metric("INSS", formatar_moeda(inss_valor))
                st.metric("IRRF", formatar_moeda(irrf_valor))
                st.metric("Salário Líquido", formatar_moeda(salario_liquido), 
                         delta=formatar_moeda(salario_liquido - simulacao_anterior["salario_liquido"]))
                st.caption(f"Tabelas: INSS {ano_base}, IRRF {irrf_periodo}")
            
            with col_comp2:
                st.markdown(f"### 📅 Simulação {simulacao_anterior['ano_base']}")
                st.metric("Salário Família", formatar_moeda(simulacao_anterior["salario_familia"]))
                st.metric("INSS", formatar_moeda(simulacao_anterior["inss"]))
                st.metric("IRRF", formatar_moeda(simulacao_anterior["irrf"]))
                st.metric("Salário Líquido", formatar_moeda(simulacao_anterior["salario_liquido"]),
                         delta=formatar_moeda(simulacao_anterior["salario_liquido"] - salario_liquido))
                st.caption(f"Tabelas: INSS {simulacao_anterior['ano_base']}, IRRF {simulacao_anterior['irrf_periodo']}")
            
            # Tabela comparativa detalhada
            st.subheader("📋 Detalhamento Comparativo")
            comparativo = pd.DataFrame({
                'Descrição': ['Salário Bruto', 'Salário Família', 'INSS', 'IRRF', 'Outros Descontos', 'Total Descontos', 'Salário Líquido'],
                'Atual': [
                    formatar_moeda(salario), 
                    formatar_moeda(sal_familia), 
                    formatar_moeda(inss_valor), 
                    formatar_moeda(irrf_valor), 
                    formatar_moeda(outros_descontos),
                    formatar_moeda(total_descontos),
                    formatar_moeda(salario_liquido)
                ],
                f'Simulação {simulacao_anterior["ano_base"]}': [
                    formatar_moeda(salario),
                    formatar_moeda(simulacao_anterior["salario_familia"]),
                    formatar_moeda(simulacao_anterior["inss"]),
                    formatar_moeda(simulacao_anterior["irrf"]),
                    formatar_moeda(outros_descontos),
                    formatar_moeda(simulacao_anterior["total_descontos"]),
                    formatar_moeda(simulacao_anterior["salario_liquido"])
                ],
                'Diferença': [
                    formatar_moeda(0),
                    formatar_moeda(sal_familia - simulacao_anterior["salario_familia"]),
                    formatar_moeda(inss_valor - simulacao_anterior["inss"]),
                    formatar_moeda(irrf_valor - simulacao_anterior["irrf"]),
                    formatar_moeda(0),
                    formatar_moeda(total_descontos - simulacao_anterior["total_descontos"]),
                    formatar_moeda(salario_liquido - simulacao_anterior["salario_liquido"])
                ]
            })
            st.dataframe(comparativo, use_container_width=True, hide_index=True)
            
        else:
            # Exibição normal sem comparação
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Salário Família", formatar_moeda(sal_familia))
            with col_m2:
                st.metric("INSS", formatar_moeda(inss_valor))
            with col_m3:
                st.metric("IRRF", formatar_moeda(irrf_valor))
            with col_m4:
                st.metric("Salário Líquido", formatar_moeda(salario_liquido))
            
            st.subheader("📋 Detalhamento Completo")
            st.write(f"Tabelas de referência: **INSS {ano_base}, IRRF {irrf_periodo}**")
            st.write(f"**Método de Dedução IRRF:** **{metodo_deducao}** (Base R\$ {formatar_moeda(base_irrf_valor)[3:]} utilizada no cálculo)")
            
            detalhes = pd.DataFrame({
                'Descrição': ['Salário Bruto', 'Salário Família', 'INSS', 'IRRF', 'Outros Descontos','Total Descontos','Salário Líquido'],
                'Valor': [formatar_moeda(salario), formatar_moeda(sal_familia), formatar_moeda(inss_valor), formatar_moeda(irrf_valor), formatar_moeda(outros_descontos), formatar_moeda(total_descontos), formatar_moeda(salario_liquido)]
            })
            st.dataframe(detalhes, use_container_width=True, hide_index=True)
        
        st.subheader("📄 Gerar Relatório PDF")
        
        data_hora_agora = get_br_datetime_now()
        data_hora_formatada = data_hora_agora.strftime("%d/%m/%Y %H:%M")
        
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
            # Envia a observação para o PDF
            pdf = gerar_pdf_individual(dados_pdf, observacao_individual)
            pdf_output = pdf.output(dest='S')
            
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
    
    opcao_entrada = st.radio(
        "Selecione a fonte dos dados:",
        ["📁 Upload de CSV", "🌐 Google Sheets", "✏️ Digitação Manual"],
        horizontal=True,
        key="opcao_entrada"
    )
    
    # Campo para a competência na aba de lote
    competencia_lote = st.date_input("Competência Analisada (Aplicável a todo o lote)", 
                                     value=date(2025, 1, 1),
                                     format="DD/MM/YYYY", key="competencia_lote")
    
    # Campo de observação em lote
    observacao_lote = st.text_area(
        "Observação Geral (Opcional - Será incluída no PDF Completo)",
        value=st.session_state.observacao_lote,
        height=100,
        key="observacao_lote_input"
    )
    st.session_state.observacao_lote = observacao_lote # Salva no session state

    # Template para download
    template_data = {
        'Nome': ['João Silva', 'Maria Santos', 'Pedro Oliveira', 'Ana Costa', 'Carlos Lima'],
        'Salario_Bruto': [1500.00, 2800.00, 4200.00, 1800.50, 6000.00],
        'Dependentes': [2, 1, 0, 3, 1],
        'Outros_Descontos': [0.00, 100.00, 200.50, 50.00, 300.00]
    }
    template_df = pd.DataFrame(template_data)
    
    with st.expander("📝 Estrutura do Arquivo Esperado"):
        st.dataframe(template_df, use_container_width=True)
        csv_template = template_df.to_csv(index=False, sep=';')
        st.download_button(
            label="📥 Baixar Template CSV",
            data=csv_template,
            file_name="template_funcionarios.csv",
            mime="text/csv",
        )
    
    df = None
    uploaded_filename = "dados_manuais"
    
    if st.session_state.ultima_opcao != opcao_entrada:
        st.session_state.df_resultado = None
        st.session_state.dados_manuais = []
        st.session_state.ultima_opcao = opcao_entrada
    
    if opcao_entrada == "📁 Upload de CSV":
        st.subheader("📤 Upload de Arquivo CSV")
        uploaded_file = st.file_uploader(
            "Escolha um arquivo CSV", 
            type="csv",
            help="Arquivo deve ter as colunas: Nome, Salario_Bruto, Dependentes, Outros_Descontos"
        )
        
        if uploaded_file is not None:
            try:
                try:
                    # Tenta ponto e vírgula
                    df = pd.read_csv(uploaded_file, sep=';')
                except:
                    # Tenta vírgula se o primeiro falhar
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',')
                
                uploaded_filename = uploaded_file.name
                st.success("✅ Arquivo CSV carregado com sucesso!")
                
            except Exception as e:
                st.error(f"❌ Erro ao ler arquivo CSV: {e}")
    
    elif opcao_entrada == "🌐 Google Sheets":
        st.subheader("🔗 Integração com Google Sheets")
        st.warning("⚠️ **Aviso:** A integração com Google Sheets depende da URL pública do arquivo. Certifique-se de que o link esteja configurado para acesso irrestrito.")
        col_sheet1, col_sheet2 = st.columns([2, 1])
        with col_sheet1:
            sheets_url = st.text_input("URL do Google Sheets:",value="https://docs.google.com/spreadsheets/d/1G-O5sNYWGLDYG8JG3FXom4BpBrVFRnrxVal-LwmH9Gc/edit?usp=sharing",key="sheets_url")
        with col_sheet2:
            sheet_name = st.text_input("Nome da Aba:",value="Página1",key="sheet_name")
        
        if sheets_url and 'processar_sheets' not in st.session_state:
             st.session_state.processar_sheets = False

        if st.button("Carregar Google Sheets"):
            st.session_state.processar_sheets = True

        if st.session_state.processar_sheets and sheets_url:
            with st.spinner("Conectando e lendo o Google Sheets..."):
                try:
                    if "/d/" in sheets_url:
                        sheet_id = sheets_url.split("/d/")[1].split("/")[0]
                    else:
                        sheet_id = sheets_url
                    
                    sheet_name_encoded = urllib.parse.quote(sheet_name)
                    # URL de exportação direta como CSV
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}"
                    
                    df = pd.read_csv(csv_url, encoding='utf-8')
                    uploaded_filename = f"Google_Sheets_{sheet_name}"
                    st.success("✅ Conexão com Google Sheets estabelecida!")
                    
                    # Renomeia colunas para o padrão esperado
                    if len(df.columns) >= 3:
                        df.columns = ['Nome', 'Salario_Bruto', 'Dependentes'] + list(df.columns[3:])
                        if len(df.columns) > 3:
                            df = df.rename(columns={df.columns[3]: 'Outros_Descontos'})
                        else:
                            df['Outros_Descontos'] = 0.0
                    else:
                         st.warning("O Google Sheet precisa de pelo menos 3 colunas (Nome, Salario_Bruto, Dependentes).")
                         df = None
                except Exception as e:
                    st.error(f"❌ Erro ao conectar com Google Sheets. Verifique a URL e se a aba '{sheet_name}' existe e está pública. Erro: {e}")
    
    elif opcao_entrada == "✏️ Digitação Manual":
        st.subheader("📝 Digitação Manual de Dados")
        num_funcionarios = st.number_input("Número de funcionários:",min_value=1,max_value=50,value=max(3, len(st.session_state.dados_manuais)) if st.session_state.dados_manuais else 3,step=1,key="num_funcionarios")
        
        # Ajusta o tamanho da lista de dados manuais
        if len(st.session_state.dados_manuais) < num_funcionarios:
            diferenca = num_funcionarios - len(st.session_state.dados_manuais)
            novos_dados = [{'Nome': f"Funcionário {i+1+len(st.session_state.dados_manuais)}", 'Salario_Bruto': 2000.0, 'Dependentes': 1, 'Outros_Descontos': 0.0} for i in range(diferenca)]
            st.session_state.dados_manuais.extend(novos_dados)
        elif len(st.session_state.dados_manuais) > num_funcionarios:
            st.session_state.dados_manuais = st.session_state.dados_manuais[:num_funcionarios]
            
        dados_manuais_input = []
        for i in range(num_funcionarios):
            st.write(f"--- **Funcionário {i+1}** ---")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            # Garante que os valores iniciais vêm do session state
            current_data = st.session_state.dados_manuais[i]
            
            with col_m1:
                nome = st.text_input(f"Nome {i+1}", value=current_data['Nome'], key=f"nome_manual_{i}")
            with col_m2:
                salario = st.number_input(f"Salário {i+1}", min_value=0.0, value=current_data['Salario_Bruto'], step=100.0, key=f"salario_manual_{i}")
            with col_m3:
                dependentes = st.number_input(f"Dependentes {i+1}", min_value=0, value=current_data['Dependentes'], step=1, key=f"dependentes_manual_{i}")
            with col_m4:
                outros_desc = st.number_input(f"Outros Desc. {i+1}", min_value=0.0, value=current_data['Outros_Descontos'], step=50.0, key=f"outros_manual_{i}")
            
            dados_manuais_input.append({'Nome': nome, 'Salario_Bruto': salario, 'Dependentes': dependentes, 'Outros_Descontos': outros_desc})
            
        st.session_state.dados_manuais = dados_manuais_input
        df = pd.DataFrame(st.session_state.dados_manuais)
        uploaded_filename = "dados_manuais"
        st.success("✅ Dados manuais prontos! Clique em 'Processar Auditoria' para calcular.")

    # --- PROCESSAMENTO ---
    if df is not None and not df.empty:
        try:
            # Garante a conversão correta de tipos
            df['Salario_Bruto'] = pd.to_numeric(df['Salario_Bruto'], errors='coerce').fillna(0)
            df['Dependentes'] = pd.to_numeric(df['Dependentes'], errors='coerce').fillna(0).astype(int)
            if 'Outros_Descontos' in df.columns:
                df['Outros_Descontos'] = pd.to_numeric(df['Outros_Descontos'], errors='coerce').fillna(0)
            else:
                df['Outros_Descontos'] = 0.0
            
            if st.button("🚀 Processar Auditoria Completa", type="primary", key="processar_auditoria"):
                with st.spinner("Processando auditoria..."):
                    
                    # Seleciona as tabelas APENAS UMA VEZ para o lote
                    tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_base, irrf_periodo, ds_maximo = selecionar_tabelas(competencia_lote)

                    resultados = []
                    for _, row in df.iterrows():
                        salario_bruto = float(row['Salario_Bruto'])
                        dependentes = int(row['Dependentes'])
                        outros_desc = float(row.get('Outros_Descontos', 0))
                        
                        # Usa as tabelas selecionadas
                        inss = calcular_inss(salario_bruto, tabela_inss_aplicada)
                        sal_familia = calcular_salario_familia(salario_bruto, dependentes, limite_sf_aplicado, valor_sf_aplicado)
                        
                        # Calcula IRRF e DEDUÇÃO MAIS BENÉFICA
                        irrf, metodo_deducao, base_irrf_valor, valor_deducao = calcular_irrf(salario_bruto, dependentes, inss, outros_desc, tabela_irrf_aplicada, ds_maximo)
                        
                        salario_liquido = salario_bruto + sal_familia - inss - irrf - outros_desc
                        
                        resultados.append({
                            'Nome': row['Nome'], 
                            'Salario_Bruto': salario_bruto, 
                            'Dependentes': dependentes, 
                            'Salario_Familia': sal_familia, 
                            'INSS': inss, 
                            'IRRF': irrf, 
                            'Outros_Descontos': outros_desc, 
                            'Salario_Liquido': salario_liquido, 
                            'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não', 
                            'Competencia': competencia_lote,
                            'Metodo_Deducao': metodo_deducao
                        })
                        
                    df_resultado = pd.DataFrame(resultados)
                    st.session_state.df_resultado = df_resultado
                    st.session_state.uploaded_filename = uploaded_filename
                    st.session_state.processar_sheets = False # Reseta a flag do Sheets
                    st.success(f"🎉 Auditoria concluída! Tabelas INSS: {ano_base}, IRRF: {irrf_periodo} aplicadas.")
                    st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {e}")
    
    # Exibir resultados
    if st.session_state.df_resultado is not None:
        df_resultado = st.session_state.df_resultado
        st.info(f"📊 **Dados processados de:** {st.session_state.uploaded_filename}")
        
        col_limpar, col_vazio = st.columns([1, 3])
        with col_limpar:
            if st.button("🗑️ Limpar Resultados", type="secondary", key="limpar_resultados"):
                st.session_state.df_resultado = None
                st.session_state.uploaded_filename = None
                st.session_state.dados_manuais = []
                st.session_state.observacao_lote = ""
                st.session_state.processar_sheets = False
                st.success("🗑️ Resultados limpos!")
                st.rerun()
        
        st.subheader("📈 Resultados da Auditoria")
        df_display = df_resultado.copy()
        colunas_monetarias = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
        for coluna in colunas_monetarias:
            df_display[coluna] = df_display[coluna].apply(formatar_moeda)
        
        st.dataframe(
            df_display.drop(columns=['Competencia']).rename(columns={'Metodo_Deducao': 'Ded. IR'}), 
            use_container_width=True
        ) 
        
        st.subheader("📊 Resumo Financeiro")
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        total_salario_familia = df_resultado['Salario_Familia'].sum()
        total_inss = df_resultado['INSS'].sum()
        total_irrf = df_resultado['IRRF'].sum()
        folha_liquida_total = df_resultado['Salario_Liquido'].sum()
        with col_r1:
            st.metric("Total Salário Família", formatar_moeda(total_salario_familia))
        with col_r2:
            st.metric("Total INSS", formatar_moeda(total_inss))
        with col_r3:
            st.metric("Total IRRF", formatar_moeda(total_irrf))
        with col_r4:
            st.metric("Folha Líquida Total", formatar_moeda(folha_liquida_total))
        
        st.subheader("💾 Exportar Resultados")
        col_csv, col_pdf = st.columns(2)
        
        with col_csv:
            df_csv = df_resultado.copy()
            # Garante que o CSV usa vírgula como decimal para facilitar a abertura no Excel/sistemas
            for coluna in colunas_monetarias:
                df_csv[coluna] = df_csv[coluna].apply(lambda x: f"{x:.2f}".replace('.', ','))
            csv_resultado = df_csv.to_csv(index=False, sep=';', encoding='utf-8')
            st.download_button(label="📥 Baixar CSV",data=csv_resultado,file_name=f"auditoria_folha_{get_br_datetime_now().strftime('%d%m%Y_%H%M')}.csv",mime="text/csv",help="Baixe os resultados em CSV (separador ponto e vírgula, decimal vírgula)")
        
        with col_pdf:
            if st.button("📄 Gerar PDF Completo", type="secondary", key="gerar_pdf_completo"):
                with st.spinner("Gerando relatório PDF..."):
                    try:
                        # Envia a observação do lote para o PDF
                        pdf = gerar_pdf_auditoria_completa(df_resultado, st.session_state.uploaded_filename,total_salario_familia,total_inss,total_irrf,folha_liquida_total, st.session_state.observacao_lote)
                        pdf_output = pdf.output(dest='S')
                        
                        st.markdown(
                            criar_link_download_pdf(pdf_output, f"Auditoria_Completa_{get_br_datetime_now().strftime('%d%m%Y_%H%M')}.pdf"), 
                            unsafe_allow_html=True
                        )
                        st.success("📄 PDF gerado com sucesso!")
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar PDF: {e}")

# ----------------------------------------------------------------------

with tab3:
    st.header("Informações Técnicas")
    st.markdown("### 📊 Tabelas Legais - INSS e IRRF")
    
    st.subheader("📅 Regra de Vigência (Competência)")
    st.info("""
    O sistema utiliza as seguintes tabelas com base na **Competência Analisada**:
    - **INSS/Salário Família:** Selecionado pelo ano (2023, 2024 ou 2025).
    - **IRRF:** Selecionado pela data específica da competência (três períodos de vigência).
    - **Dedução IRRF:** O sistema compara o Desconto Legal (INSS + Ded. Dependente) com o Desconto Simplificado Opcional e aplica o que resultar no **menor imposto**.
    - **Simulação Ano Anterior:** Permite comparar os cálculos atuais com as tabelas do ano anterior.
    """)
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Regras de Dedução IRRF")
        st.markdown(f"""
        #### **Dedução Legal**
        - **Fórmula:** Salário Bruto - INSS - (Dependentes * {formatar_moeda(DESCONTO_DEPENDENTE_IR)}) - Outros Descontos
        
        #### **Desconto Simplificado Opcional**
        - **2023:** Máximo de **{formatar_moeda(DS_MAX_2023)}**
        - **Vigência 01/02/2024 a 30/04/2025:** Máximo de **{formatar_moeda(DS_MAX_FEV2024_ABR2025)}**
        - **Vigência 01/05/2025 em diante:** Máximo de **{formatar_moeda(DS_MAX_MAI2025_DEZ2025)}**
        - **Fórmula:** Salário Bruto - Desconto Simplificado (Valor Máximo)
        
        *O sistema escolhe o método que resulta no **menor imposto**.*
        """)
    
    with col_info2:
        st.subheader("📋 Tabela INSS 2025 (Alíquota Efetiva)")
        tabela_inss_df_2025 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1518.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1518.01) + " a " + formatar_moeda(2793.88), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2793.89) + " a " + formatar_moeda(4190.83), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4190.84) + " a " + formatar_moeda(8157.41), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2025, use_container_width=True, hide_index=True)
        st.caption(f"**Teto máximo do INSS 2025:** {formatar_moeda(8157.41)}")

    st.subheader("📈 Tabela IRRF - Vigências Específicas")
    
    st.markdown("#### **Vigência: 01/05/2025 em diante** (MP 1.294/2025)")
    tabela_irrf_df_mai2025 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(182.16)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Parcela a Deduzir": formatar_moeda(394.16)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Parcela a Deduzir": formatar_moeda(675.49)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Parcela a Deduzir": formatar_moeda(908.73)}
    ])
    st.dataframe(tabela_irrf_df_mai2025, use_container_width=True, hide_index=True)

    st.markdown("#### **Vigência: 01/02/2024 a 30/04/2025** (MP 1.206/2024)")
    tabela_irrf_df_fev2024 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2259.20), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2259.21) + " a " + formatar_moeda(2826.65), "Aliquota": "7,5%", "Parcela a Deduzir": formatar_moeda(169.44)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Aliquota": "15%", "Parcela a Deduzir": formatar_moeda(381.44)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Aliquota": "22,5%", "Parcela a Deduzir": formatar_moeda(662.77)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Aliquota": "27,5%", "Parcela a Deduzir": formatar_moeda(896.00)}
    ])
    st.dataframe(tabela_irrf_df_fev2024, use_container_width=True, hide_index=True)
    
    st.markdown("#### **Vigência: 01/05/2023 a 31/01/2024** (Tabela 2023)")
    tabela_irrf_df_2023 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2112.00), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2112.01) + " a " + formatar_moeda(2826.65), "Aliquota": "7,5%", "Parcela a Deduzir": formatar_moeda(158.40)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Aliquota": "15%", "Parcela a Deduzir": formatar_moeda(370.40)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Aliquota": "22,5%", "Parcela a Deduzir": formatar_moeda(651.73)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Aliquota": "27,5%", "Parcela a Deduzir": formatar_moeda(884.96)}
    ])
    st.dataframe(tabela_irrf_df_2023, use_container_width=True, hide_index=True)
    
    st.subheader("📝 Legislação de Referência")
    st.write("""
    - **Salário Família:** Lei 8.213/1991
    - **INSS 2023/2024/2025:** Lei 8.212/1991 e Portarias Ministeriais
    - **IRRF (2023):** Lei nº 14.663/2023
    - **IRRF (Fev/2024):** MP Nº 1.206, DE 6 DE FEVEREIRO DE 2024.
    - **IRRF (Atual):** MP Nº 1.294, de maio de 2025 (e alterações posteriores, se houver).
    """)

# ----------------------------------------------------------------------

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento**

Cálculos dinâmicos com base na **Competência** informada:
- Salário Família (2023, 2024 e 2025)
- INSS (Tabela 2023, 2024 e 2025)
- IRRF (Tabelas multi-período)
- **Comparativo Desconto Legal vs. Desconto Simplificado** (mais benéfico)
- **Simulação com tabelas do ano anterior**

⚠️ Consulte um contador para validação oficial.
""")

st.sidebar.header("📞 Suporte")
st.sidebar.write("""
**Dúvidas técnicas:**
- Consulte as informações na aba ℹ️ Informações
- Verifique as fórmulas de cálculo
- Confira os exemplos práticos

**Problemas com o sistema:**
- Verifique o formato do arquivo CSV
- Confirme os valores de entrada
- Recarregue a página se necessário
""")

st.markdown("---")
col_rodape1, col_rodape2, col_rodape3 = st.columns(3)

with col_rodape1:
    st.caption(f"📅 Data da Consulta: {formatar_data(get_br_datetime_now())}")

with col_rodape2:
    st.caption("🏛 Legislação 2023/2024/2025 - Vigência a partir da competência")

with col_rodape3:
    st.caption("⚡ Desenvolvido para auditoria contábil")

st.markdown("""
<style>
.aviso-legal {
    font-size: 0.8em;
    color: #666;
    text-align: center;
    margin-top: 20px;
}
</style>
<div class="aviso-legal">
⚠️ AVISO LEGAL: Este sistema realiza cálculos com base na legislação vigente e tem caráter informativo. 
Recomenda-se a validação dos resultados por profissional contábil habilitado. 
Os valores podem sofrer alterações conforme atualizações legais.
</div>
""", unsafe_allow_html=True)
