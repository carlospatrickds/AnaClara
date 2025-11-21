import streamlit as st
import pandas as pd
from datetime import datetime, date
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
if 'observacao_lote' not in st.session_state:
    st.session_state.observacao_lote = ""

st.title("💰 Auditoria de Folha de Pagamento - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- TABELAS LEGAIS ---

# Datas de Referência
DATA_INICIO_2024_IRRF = date(2024, 2, 1) # Início do período da MP 1.206/2024
DATA_INICIO_2025_IRRF = date(2025, 5, 1) # Início do período da MP 1.294/2025

# --- Salário Família & Dedução IR ---
DESCONTO_DEPENDENTE_IR = 189.59 

# Salário Família 2025 (Padrão 2025)
SF_LIMITE_2025 = 1906.04
SF_VALOR_2025 = 65.00

# Salário Família 2024
SF_LIMITE_2024 = 1819.26
SF_VALOR_2024 = 62.04

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

# --- Desconto Simplificado (Opcional) ---
# Periodo 01/02/2024 a 30/04/2025: 25% de 2.259,20 = 564,80
DS_MAX_FEV2024_ABR2025 = 564.80 
# Periodo 01/05/2025 em diante: 25% de 2.428,80 = 607,20
DS_MAX_MAI2025_DEZ2025 = 607.20 

# --- Tabela IRRF (01/05/2023 a 31/01/2024) ---
TABELA_IRRF_2023_JAN2024 = [
    {"limite": 2112.00, "aliquota": 0.0, "deducao": 0.00},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 158.40},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 370.40},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 651.73},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 884.96}
]

# --- Tabela IRRF (01/02/2024 a 30/04/2025 - MP 1.206/2024) ---
# MP 1.206/2024
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

# --- FUNÇÃO DE DOWNLOAD DE PDF (ESSENCIAL NO TOPO PARA VISIBILIDADE) ---
def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF a partir de um objeto bytes (output do FPDF)."""
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

# --- FUNÇÕES DE CÁLCULO ---

def selecionar_tabelas(competencia: date):
    """
    Seleciona as tabelas de INSS, IRRF e parâmetros de Salário Família e Desconto Simplificado
    com base na competência.
    """
    
    # Lógica INSS e Salário Família (Baseada no ano)
    if competencia.year == 2024:
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
        ds_maximo = DS_MAX_FEV2024_ABR2025
        
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
    # Ded simplificada: Valor fixo que substitui Ded. Dependente e Outras Deduções da BC.
    # Base Simplificada (Simulação Site): Salário Bruto - Desconto Simplificado Máximo
    deducao_simplificada_valor = ds_maximo
    base_simplificada_site = salario_bruto - deducao_simplificada_valor
    irrf_simplificado_site = calcular_irrf_base(base_simplificada_site, tabela_irrf)
    
    # 3. ESCOLHA DO MAIS BENÉFICO (Menor IRRF)
    
    if irrf_legal <= irrf_simplificado_site:
        return irrf_legal, "Legal", base_legal, deducao_legal
    else:
        # Retorna o cálculo do Desconto Simplificado que foi mais benéfico
        return irrf_simplificado_site, "Simplificado", base_simplificada_site, deducao_simplificada_valor

# --- FUNÇÕES DE GERAÇÃO DE PDF ---

def gerar_pdf_individual(dados, obs):
    """Gera PDF profissional para cálculo individual (MODIFICADO para incluir OBS e DEDUÇÃO)"""
    pdf = FPDF()
    pdf.add_page()
    
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
    """Gera PDF para auditoria completa (MODIFICADO para incluir OBS e DEDUÇÃO)"""
    pdf = FPDF()
    pdf.add_page()
    
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
    
    # Tabela Aplicada (Assume-se que a competência é a mesma para todo o lote)
    primeira_competencia = df_resultado.iloc[0]['Competencia']
    tabela_inss_ref, tabela_irrf_ref, SF_LIMITE, SF_VALOR, ano_base, irrf_periodo, ds_maximo = selecionar_tabelas(primeira_competencia)

    pdf.cell(0, 6, f'Tabelas INSS Aplicadas: {ano_base}', 0, 1)
    pdf.cell(0, 6, f'Tabelas IRRF Aplicadas: {irrf_periodo}', 0, 1)
    
    # Estatísticas de aplicação
    funcionarios_com_salario_familia = len(df_resultado[df_resultado['Salario_Familia'] > 0])
    funcionarios_com_irrf = len(df_resultado[df_resultado['IRRF'] > 0])
    
    pdf.cell(0, 6, f'Func. com Salário Família: {funcionarios_com_salario_familia}', 0, 1)
    pdf.cell(0, 6, f'Func. com IRRF: {funcionarios_com_irrf}', 0, 1)
    pdf.cell(0, 6, f'Func. Isentos IRRF: {len(df_resultado) - funcionarios_com_irrf}', 0, 1)
    
    # Contagem de método de dedução
    func_legal = len(df_resultado[df_resultado['Metodo_Deducao'] == 'Legal'])
    func_simplificado = len(df_resultado[df_resultado['Metodo_Deducao'] == 'Simplificado'])
    pdf.cell(0, 6, f'Func. com Dedução Legal: {func_legal}', 0, 1)
    pdf.cell(0, 6, f'Func. com Dedução Simplificada: {func_simplificado}', 0, 1)

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

    # --- NOVO: OBSERVAÇÕES EM LOTE ---
    if obs_lote:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OBSERVAÇÕES DO ANALISTA', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, obs_lote)
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
        
        pdf.set_font('Arial', 'B', 7)
        colunas = ['Nome', 'Salário', 'Dep', 'Sal Fam', 'INSS', 'IRRF', 'Dedução', 'Líquido']
        larguras = [30, 21, 10, 21, 21, 21, 18, 28]
        
        for i, coluna in enumerate(colunas):
            pdf.cell(larguras[i], 8, coluna, 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font('Arial', '', 7)
        for _, row in df_resultado.head(15).iterrows():
            nome = str(row['Nome'])[:15] + '...' if len(str(row['Nome'])) > 15 else str(row['Nome'])
            pdf.cell(larguras[0], 6, nome, 1)
            pdf.cell(larguras[1], 6, formatar_moeda(row['Salario_Bruto']), 1, 0, 'R')
            pdf.cell(larguras[2], 6, str(row['Dependentes']), 1, 0, 'C')
            pdf.cell(larguras[3], 6, formatar_moeda(row['Salario_Familia']), 1, 0, 'R')
            pdf.cell(larguras[4], 6, formatar_moeda(row['INSS']), 1, 0, 'R')
            pdf.cell(larguras[5], 6, formatar_moeda(row['IRRF']), 1, 0, 'R')
            pdf.cell(larguras[6], 6, row['Metodo_Deducao'][0], 1, 0, 'C') # L ou S
            pdf.cell(larguras[7], 6, formatar_moeda(row['Salario_Liquido']), 1, 0, 'R')
            pdf.ln()
            
        if len(df_resultado) > 15:
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(0, 6, f'... e mais {len(df_resultado) - 15} registros', 0, 1)
    
    pdf.ln(10)

    # --- INCLUSÃO DAS TABELAS NO PDF EM LOTE ---
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Referência INSS: Tabelas de {ano_base}', 0, 1)
    pdf.cell(0, 6, f'Referência IRRF: Tabela com vigência {irrf_periodo}', 0, 1)
    pdf.ln(5)

    
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {ano_base}', 0, 1)
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
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {ano_base}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor Máx. na Faixa', 1, 1)
    
    faixas_inss = []
    limite_anterior = 0.0
    for i, faixa in enumerate(tabela_inss_ref):
        limite = faixa["limite"]
        aliquota_percentual = f"{faixa['aliquota'] * 100:.1f}%"
        
        if i == 0:
            faixa_desc = f'Até {formatar_moeda(limite)}'
            valor_max_faixa = formatar_moeda(limite * faixa["aliquota"])
        else:
            faixa_desc = f'{formatar_moeda(limite_anterior + 0.01)} a {formatar_moeda(limite)}'
            valor_max_faixa = formatar_moeda((limite - limite_anterior) * faixa["aliquota"])
            
        faixas_inss.append((faixa_desc, aliquota_percentual, valor_max_faixa))
        limite_anterior = limite
        
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(tabela_inss_ref[-1]["limite"])}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF ({irrf_periodo})', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Parcela a Deduzir', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = []
    limite_anterior = 0.0
    for i, faixa in enumerate(tabela_irrf_ref):
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
        f'- INSS: Lei 8.212/1991 e Portaria de Referência de {ano_base}',
        f'- IRRF: Lei 7.713/1988 e Medidas Provisórias (Ex: MP 1.206/2024 e MP 1.294/2025)',
        f'- Vigência Aplicada: INSS ({ano_base}), IRRF ({irrf_periodo})'
    ]
    for item in legislacao:
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)
    
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'METODOLOGIA DE CÁLCULO APLICADA', 0, 1)
    pdf.set_font('Arial', '', 9)
    metodologia = [
        f'1. SALÁRIO FAMÍLIA: Pago para salários menores ou iguais a {formatar_moeda(SF_LIMITE)}, no valor de {formatar_moeda(SF_VALOR)} por dependente',
        '2. INSS: Cálculo progressivo por faixas conforme tabela do ano aplicável (Alíquota Efetiva)',
        '3. IRRF: Comparado Desconto Legal (INSS + Dependente) e Desconto Simplificado (Opcional)',
        '4. Aplicado o método que resulta no **menor IRRF devido** (Mais benéfico ao contribuinte)',
        '5. Salário Líquido = Salário Bruto + Salário Família - INSS - IRRF - Outros Descontos'
    ]
    for item in metodologia:
        pdf.multi_cell(0, 5, item)
        pdf.ln(1)
    
    pdf.ln(10)
    
    # Rodapé
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, 'Relatório gerado automaticamente pelo Sistema de Auditoria de Folha de Pagamento.', 0, 1, 'C')
    pdf.cell(0, 5, 'Consulte um contador para validação oficial dos cálculos.', 0, 1, 'C')
    pdf.cell(0, 5, f'Processado em: {data_hora_agora.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
    
    return pdf


# --- INTERFACE STREAMLIT (FINAL) ---

with tab3:
    st.header("Informações Técnicas")
    st.markdown("### 📊 Tabelas Legais - INSS e IRRF")
    
    st.subheader("📅 Regra de Vigência (Competência)")
    st.info("""
    O sistema utiliza as seguintes tabelas com base na **Competência Analisada**:
    - **INSS/Salário Família:** Selecionado pelo ano (2024 ou 2025).
    - **IRRF:** Selecionado pela data específica da competência (três períodos de vigência).
    - **Dedução IRRF:** O sistema compara o Desconto Legal (INSS + Ded. Dependente) com o Desconto Simplificado Opcional (Max R$ 564,80 ou R$ 607,20, dependendo da data) e aplica o que resultar no **menor imposto**.
    """)
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Regras de Dedução IRRF")
        st.markdown(f"""
        #### **Dedução Legal**
        - **Fórmula:** Salário Bruto - INSS - (Dependentes * {formatar_moeda(DESCONTO_DEPENDENTE_IR)}) - Outros Descontos
        
        #### **Desconto Simplificado Opcional**
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
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2259.21) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(169.44)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Parcela a Deduzir": formatar_moeda(381.44)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Parcela a Deduzir": formatar_moeda(662.77)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Parcela a Deduzir": formatar_moeda(896.00)}
    ])
    st.dataframe(tabela_irrf_df_fev2024, use_container_width=True, hide_index=True)
    
    st.subheader("📝 Legislação de Referência")
    st.write("""
    - **Salário Família:** Lei 8.213/1991
    - **INSS 2024/2025:** Lei 8.212/1991 e Portarias Ministeriais
    - **IRRF (Fev/2024):** MP Nº 1.206, DE 6 DE FEVEREIRO DE 2024.
    - **IRRF (Atual):** MP Nº 1.294, de maio de 2025 (e alterações posteriores, se houver).
    """)

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento**

Cálculos dinâmicos com base na **Competência** informada:
- Salário Família (2024 e 2025)
- INSS (Tabela 2024 e 2025)
- IRRF (Tabelas multi-período)
- **Comparativo Desconto Legal vs. Desconto Simplificado** (mais benéfico)

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
    st.caption("🏛 Legislação 2024/2025 - Vigência a partir da competência")

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
