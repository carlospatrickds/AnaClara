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

# --- TABELAS LEGAIS 2025 (JÁ EXISTENTES) ---
SF_LIMITE_2025 = 1906.04
SF_VALOR_2025 = 65.00
DESCONTO_DEPENDENTE_IR = 189.59

TABELA_INSS_2025 = [
    {"limite": 1518.00, "aliquota": 0.075},
    {"limite": 2793.88, "aliquota": 0.09},
    {"limite": 4190.83, "aliquota": 0.12},
    {"limite": 8157.41, "aliquota": 0.14}
]

TABELA_IRRF_2025 = [
    {"limite": 2428.80, "aliquota": 0.0, "deducao": 0.0},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 182.16},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 394.16},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 675.49},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 916.90}
]

# --- NOVAS TABELAS LEGAIS 2024 (DO ANEXO E SOLICITAÇÃO) ---
# Salário Família 2024 (Regra solicitada)
SF_LIMITE_2024 = 1819.26
SF_VALOR_2024 = 62.04

# Tabela INSS 2024 (Do anexo)
TABELA_INSS_2024 = [
    {"limite": 1412.00, "aliquota": 0.075},
    {"limite": 2666.68, "aliquota": 0.09},
    {"limite": 4000.03, "aliquota": 0.12},
    {"limite": 7786.02, "aliquota": 0.14}
]

# Tabela IRRF 2024 (Do anexo)
# OBS: O limite de isenção no anexo está 2.112,00. O limite de 2.428,80 (2025) será considerado para 2025.
# O DESCONTO_DEPENDENTE_IR de R$ 189,59 é o mesmo nos dois anexos/tabelas e será mantido.
TABELA_IRRF_2024 = [
    {"limite": 2112.00, "aliquota": 0.0, "deducao": 0.00},
    {"limite": 2826.65, "aliquota": 0.075, "deducao": 158.40},
    {"limite": 3751.05, "aliquota": 0.15, "deducao": 370.40},
    {"limite": 4664.68, "aliquota": 0.225, "deducao": 651.73},
    {"limite": float('inf'), "aliquota": 0.275, "deducao": 884.96}
]

# --- FUNÇÕES DE UTILIDADE (SEM ALTERAÇÃO) ---

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

# --- FUNÇÕES DE CÁLCULO MODIFICADAS ---

def selecionar_tabelas(competencia: date):
    """Seleciona as tabelas de INSS, IRRF e parâmetros de Salário Família com base na competência."""
    if competencia.year == 2024:
        return TABELA_INSS_2024, TABELA_IRRF_2024, SF_LIMITE_2024, SF_VALOR_2024, "2024"
    # Padrão para 2025 ou anos futuros
    return TABELA_INSS_2025, TABELA_IRRF_2025, SF_LIMITE_2025, SF_VALOR_2025, "2025"

def calcular_inss(salario_bruto, tabela_inss):
    """Calcula desconto do INSS com base na tabela progressiva fornecida."""
    if salario_bruto <= 0:
        return 0.0
    
    # O limite máximo é o limite da última faixa
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
            # O limite da faixa é a diferença entre o limite atual e o limite anterior
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

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos, tabela_irrf):
    """Calcula IRRF com base na tabela IRRF fornecida."""
    # Base = Salário Bruto - Dedução por Dependente - INSS - Outros Descontos
    base_calculo = salario_bruto - (dependentes * DESCONTO_DEPENDENTE_IR) - inss - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    irrf = 0.0
    for faixa in tabela_irrf:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(round(irrf, 2), 0.0)
    
    return 0.0 # Caso extremo (não deve ocorrer com float('inf'))

# --- FUNÇÕES DE GERAÇÃO DE PDF MODIFICADAS ---

def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF a partir de um objeto bytes (output do FPDF)."""
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

def gerar_pdf_individual(dados, obs):
    """Gera PDF profissional para cálculo individual (MODIFICADO para incluir OBS)"""
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
    pdf.cell(0, 6, f'Tabelas Aplicadas: {dados["tabelas_aplicadas"]}', 0, 1)
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
    
    pdf.ln(5)
    
    # --- NOVO: OBSERVAÇÕES ---
    if obs:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OBSERVAÇÕES DO ANALISTA', 0, 1)
        pdf.set_font('Arial', '', 10)
        # Multi_cell para quebra de linha em textos longos
        pdf.multi_cell(0, 6, obs)
        pdf.ln(5)
    
    # --- INCLUSÃO DAS TABELAS NO PDF INDIVIDUAL ---
    # (Manter a lógica original de exibição de tabelas para não quebrar a estrutura)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Referência: Tabelas de {dados["tabelas_aplicadas"]}', 0, 1)
    pdf.ln(5)

    # Lógica para mostrar a tabela correta no PDF (simplificada aqui para não duplicar muito código, mas mantendo a informação da versão)
    
    # Tabela Salário Família
    if dados["tabelas_aplicadas"] == "2025":
        SF_LIMITE, SF_VALOR = SF_LIMITE_2025, SF_VALOR_2025
    else:
        SF_LIMITE, SF_VALOR = SF_LIMITE_2024, SF_VALOR_2024
        
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {dados["tabelas_aplicadas"]}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(SF_LIMITE), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(SF_VALOR), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS (Exibindo a tabela aplicada)
    tabela_inss_referencia = TABELA_INSS_2025 if dados["tabelas_aplicadas"] == "2025" else TABELA_INSS_2024
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {dados["tabelas_aplicadas"]}', 0, 1)
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
    tabela_irrf_referencia = TABELA_IRRF_2025 if dados["tabelas_aplicadas"] == "2025" else TABELA_IRRF_2024
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF {dados["tabelas_aplicadas"]}', 0, 1)
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
            faixa_num = f'{i}ª'
            
        faixas_irrf.append((base_desc, aliquota_percentual, deducao, faixa_num))
        limite_anterior = limite

    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(DESCONTO_DEPENDENTE_IR)}', 0, 1)
    pdf.ln(10)
    
    # Legislação e Metodologia
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO E METODOLOGIA', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        '- INSS: Lei 8.212/1991 e Portaria MF/MPS 01/2024 (2025) / Portaria INTERMINISTERIAL MPS/MF Nº 2, DE 11 DE JANEIRO DE 2024 (2024)',
        '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024 (2025) / Lei nº 14.663, de 28 de agosto de 2023 (2024)',
        f'- Vigência Aplicada: Exercício {dados["tabelas_aplicadas"]}'
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
        f'2. CÁLCULO: Nº Dependentes × {formatar_moeda(SF_VALOR)} (se elegível)',
        '3. INSS: Cálculo progressivo por faixas acumulativas (Alíquota Efetiva)',
        f'4. BASE IRRF: Salário Bruto - Dependentes × {formatar_moeda(DESCONTO_DEPENDENTE_IR)} - INSS - Outros Descontos',
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

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total, obs_lote):
    """Gera PDF para auditoria completa (MODIFICADO para incluir OBS)"""
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
    
    # Tabela Aplicada (Assume-se que a competência é a mesma para todo o lote, usando a primeira linha)
    primeira_competencia = df_resultado.iloc[0]['Competencia']
    _, _, _, _, ano_aplicado = selecionar_tabelas(primeira_competencia)
    pdf.cell(0, 6, f'Tabelas Aplicadas: {ano_aplicado}', 0, 1)
    
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
        
        pdf.set_font('Arial', 'B', 8)
        colunas = ['Nome', 'Salário', 'Dep', 'Sal Fam', 'INSS', 'IRRF', 'Líquido']
        larguras = [40, 25, 15, 25, 25, 25, 30]
        
        for i, coluna in enumerate(colunas):
            pdf.cell(larguras[i], 8, coluna, 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font('Arial', '', 7)
        for _, row in df_resultado.head(15).iterrows():
            nome = str(row['Nome'])[:20] + '...' if len(str(row['Nome'])) > 20 else str(row['Nome'])
            pdf.cell(larguras[0], 6, nome, 1)
            pdf.cell(larguras[1], 6, formatar_moeda(row['Salario_Bruto']), 1, 0, 'R')
            pdf.cell(larguras[2], 6, str(row['Dependentes']), 1, 0, 'C')
            pdf.cell(larguras[3], 6, formatar_moeda(row['Salario_Familia']), 1, 0, 'R')
            pdf.cell(larguras[4], 6, formatar_moeda(row['INSS']), 1, 0, 'R')
            pdf.cell(larguras[5], 6, formatar_moeda(row['IRRF']), 1, 0, 'R')
            pdf.cell(larguras[6], 6, formatar_moeda(row['Salario_Liquido']), 1, 0, 'R')
            pdf.ln()
            
        if len(df_resultado) > 15:
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(0, 6, f'... e mais {len(df_resultado) - 15} registros', 0, 1)
    
    pdf.ln(10)

    # --- INCLUSÃO DAS TABELAS NO PDF EM LOTE ---
    # (Mantendo a lógica original, mas referenciando o ano correto)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Referência: Tabelas de {ano_aplicado}', 0, 1)
    pdf.ln(5)

    if ano_aplicado == "2025":
        SF_LIMITE, SF_VALOR = SF_LIMITE_2025, SF_VALOR_2025
        TAB_INSS_REF = TABELA_INSS_2025
        TAB_IRRF_REF = TABELA_IRRF_2025
    else:
        SF_LIMITE, SF_VALOR = SF_LIMITE_2024, SF_VALOR_2024
        TAB_INSS_REF = TABELA_INSS_2024
        TAB_IRRF_REF = TABELA_IRRF_2024
    
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {ano_aplicado}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(SF_LIMITE), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(SF_VALOR), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {ano_aplicado}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor Máx. na Faixa', 1, 1)
    
    faixas_inss = []
    limite_anterior = 0.0
    for i, faixa in enumerate(TAB_INSS_REF):
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
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(TAB_INSS_REF[-1]["limite"])}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF {ano_aplicado}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Parcela a Deduzir', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = []
    limite_anterior = 0.0
    for i, faixa in enumerate(TAB_IRRF_REF):
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
            faixa_num = f'{i}ª'
            
        faixas_irrf.append((base_desc, aliquota_percentual, deducao, faixa_num))
        limite_anterior = limite
    
    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(DESCONTO_DEPENDENTE_IR)}', 0, 1)
    pdf.ln(10)
    
    # Legislação e Metodologia
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO E METODOLOGIA', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        '- INSS: Lei 8.212/1991 e Portaria MF/MPS 01/2024 (2025) / Portaria INTERMINISTERIAL MPS/MF Nº 2, DE 11 DE JANEIRO DE 2024 (2024)',
        '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024 (2025) / Lei nº 14.663, de 28 de agosto de 2023 (2024)',
        f'- Vigência Aplicada: Exercício {ano_aplicado}'
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
        f'3. IRRF: Base de cálculo = Salário Bruto - Dependentes × {formatar_moeda(DESCONTO_DEPENDENTE_IR)} - INSS - Outros Descontos',
        '4. Aplicadas alíquotas progressivas conforme tabela IRRF do ano aplicável',
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


# --- INTERFACE STREAMLIT MODIFICADA ---

# Interface principal
tab1, tab2, tab3 = st.tabs(["🧮 Cálculo Individual", "📊 Auditoria em Lote", "ℹ️ Informações"])

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
                                    value=get_br_datetime_now().date().replace(day=1),
                                    format="DD/MM/YYYY")
    
    # --- NOVO CAMPO DE OBSERVAÇÃO ---
    observacao_individual = st.text_area(
        "Observação (Opcional - Será incluída no PDF)",
        value="",
        height=100
    )
    
    if st.button("Calcular", type="primary"):
        
        # 1. SELECIONA AS TABELAS CORRETAS
        tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_aplicado = selecionar_tabelas(competencia)
        
        # 2. CALCULA COM AS TABELAS SELECIONADAS
        inss_valor = calcular_inss(salario, tabela_inss_aplicada)
        sal_familia = calcular_salario_familia(salario, dependentes, limite_sf_aplicado, valor_sf_aplicado)
        irrf_valor = calcular_irrf(salario, dependentes, inss_valor, outros_descontos, tabela_irrf_aplicada)
        
        total_descontos = inss_valor + irrf_valor + outros_descontos
        total_acrescimos = sal_familia
        salario_liquido = salario - total_descontos + total_acrescimos
        base_irrf = salario - (dependentes * DESCONTO_DEPENDENTE_IR) - inss_valor - outros_descontos
        
        st.success(f"Cálculos realizados com sucesso! Tabelas de {ano_aplicado} aplicadas.")
        
        # ... [Métricas e Detalhamento na interface] ...
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
        st.write(f"Tabelas de referência: **{ano_aplicado}**")
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
            "tabelas_aplicadas": ano_aplicado, # Novo
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
            "base_irrf": formatar_moeda(base_irrf),
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
                                    value=get_br_datetime_now().date().replace(day=1),
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
                    df = pd.read_csv(uploaded_file, sep=';')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',')
                
                uploaded_filename = uploaded_file.name
                st.success("✅ Arquivo CSV carregado com sucesso!")
                
            except Exception as e:
                st.error(f"❌ Erro ao ler arquivo CSV: {e}")
    
    elif opcao_entrada == "🌐 Google Sheets":
        st.subheader("🔗 Integração com Google Sheets")
        col_sheet1, col_sheet2 = st.columns([2, 1])
        with col_sheet1:
            sheets_url = st.text_input("URL do Google Sheets:",value="https://docs.google.com/spreadsheets/d/1G-O5sNYWGLDYG8JG3FXom4BpBrVFRnrxVal-LwmH9Gc/edit?usp=sharing",key="sheets_url")
        with col_sheet2:
            sheet_name = st.text_input("Nome da Aba:",value="Página1",key="sheet_name")
        
        if sheets_url:
            with st.spinner("Conectando e lendo o Google Sheets..."):
                try:
                    if "/d/" in sheets_url:
                        sheet_id = sheets_url.split("/d/")[1].split("/")[0]
                    else:
                        sheet_id = sheets_url
                    
                    sheet_name_encoded = urllib.parse.quote(sheet_name)
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}"
                    
                    df = pd.read_csv(csv_url, encoding='utf-8')
                    uploaded_filename = f"Google_Sheets_{sheet_name}"
                    st.success("✅ Conexão com Google Sheets estabelecida!")
                    if len(df.columns) >= 3:
                        df.columns = ['Nome', 'Salario_Bruto', 'Dependentes'] + list(df.columns[3:])
                        if len(df.columns) > 3:
                            df = df.rename(columns={df.columns[3]: 'Outros_Descontos'})
                        else:
                            df['Outros_Descontos'] = 0.0
                except Exception as e:
                    st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
    
    elif opcao_entrada == "✏️ Digitação Manual":
        st.subheader("📝 Digitação Manual de Dados")
        num_funcionarios = st.number_input("Número de funcionários:",min_value=1,max_value=50,value=max(3, len(st.session_state.dados_manuais)) if st.session_state.dados_manuais else 3,step=1,key="num_funcionarios")
        
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
            with col_m1:
                nome = st.text_input(f"Nome {i+1}", value=st.session_state.dados_manuais[i]['Nome'], key=f"nome_manual_{i}")
            with col_m2:
                salario = st.number_input(f"Salário {i+1}", min_value=0.0, value=st.session_state.dados_manuais[i]['Salario_Bruto'], step=100.0, key=f"salario_manual_{i}")
            with col_m3:
                dependentes = st.number_input(f"Dependentes {i+1}", min_value=0, value=st.session_state.dados_manuais[i]['Dependentes'], step=1, key=f"dependentes_manual_{i}")
            with col_m4:
                outros_desc = st.number_input(f"Outros Desc. {i+1}", min_value=0.0, value=st.session_state.dados_manuais[i]['Outros_Descontos'], step=50.0, key=f"outros_manual_{i}")
            
            dados_manuais_input.append({'Nome': nome, 'Salario_Bruto': salario, 'Dependentes': dependentes, 'Outros_Descontos': outros_desc})
            
        st.session_state.dados_manuais = dados_manuais_input
        df = pd.DataFrame(st.session_state.dados_manuais)
        uploaded_filename = "dados_manuais"
        st.success("✅ Dados manuais prontos! Clique em 'Processar Auditoria' para calcular.")

    if df is not None and not df.empty:
        try:
            df['Salario_Bruto'] = pd.to_numeric(df['Salario_Bruto'], errors='coerce').fillna(0)
            df['Dependentes'] = pd.to_numeric(df['Dependentes'], errors='coerce').fillna(0).astype(int)
            if 'Outros_Descontos' in df.columns:
                df['Outros_Descontos'] = pd.to_numeric(df['Outros_Descontos'], errors='coerce').fillna(0)
            else:
                df['Outros_Descontos'] = 0.0
            
            if st.button("🚀 Processar Auditoria Completa", type="primary", key="processar_auditoria"):
                with st.spinner("Processando auditoria..."):
                    
                    # Seleciona as tabelas APENAS UMA VEZ para o lote
                    tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_aplicado = selecionar_tabelas(competencia_lote)

                    resultados = []
                    for _, row in df.iterrows():
                        salario_bruto = float(row['Salario_Bruto'])
                        dependentes = int(row['Dependentes'])
                        outros_desc = float(row.get('Outros_Descontos', 0))
                        
                        # Usa as tabelas selecionadas
                        inss = calcular_inss(salario_bruto, tabela_inss_aplicada)
                        sal_familia = calcular_salario_familia(salario_bruto, dependentes, limite_sf_aplicado, valor_sf_aplicado)
                        irrf = calcular_irrf(salario_bruto, dependentes, inss, outros_desc, tabela_irrf_aplicada)
                        salario_liquido = salario_bruto + sal_familia - inss - irrf - outros_desc
                        
                        resultados.append({'Nome': row['Nome'], 'Salario_Bruto': salario_bruto, 'Dependentes': dependentes, 'Salario_Familia': sal_familia, 'INSS': inss, 'IRRF': irrf, 'Outros_Descontos': outros_desc, 'Salario_Liquido': salario_liquido, 'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não', 'Competencia': competencia_lote}) # Adiciona a competência
                        
                    df_resultado = pd.DataFrame(resultados)
                    st.session_state.df_resultado = df_resultado
                    st.session_state.uploaded_filename = uploaded_filename
                    st.success(f"🎉 Auditoria concluída! Tabelas de {ano_aplicado} aplicadas.")
                    st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {e}")
    
    # Exibir resultados
    if st.session_state.df_resultado is not None:
        df_resultado = st.session_state.df_resultado
        st.info(f"📊 **Dados processados de:** {st.session_state.uploaded_filename}")
        
        if st.button("🗑️ Limpar Resultados", type="secondary", key="limpar_resultados"):
            st.session_state.df_resultado = None
            st.session_state.uploaded_filename = None
            st.session_state.dados_manuais = []
            st.session_state.observacao_lote = ""
            st.success("🗑️ Resultados limpos!")
            st.rerun()
        
        st.subheader("📈 Resultados da Auditoria")
        df_display = df_resultado.copy()
        colunas_monetarias = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
        for coluna in colunas_monetarias:
            df_display[coluna] = df_display[coluna].apply(formatar_moeda)
        st.dataframe(df_display.drop(columns=['Competencia']), use_container_width=True) # Remove Competencia da exibição
        
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
            for coluna in colunas_monetarias:
                df_csv[coluna] = df_csv[coluna].apply(lambda x: f"{x:.2f}".replace('.', ','))
            csv_resultado = df_csv.to_csv(index=False, sep=';')
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

# --- ABA 3 E RODAPÉ (AJUSTADOS PARA INCLUIR 2024) ---

with tab3:
    st.header("Informações Técnicas")
    st.markdown("### 📊 Tabelas Legais - INSS e IRRF")
    
    st.subheader("📅 Regra de Vigência (Competência)")
    st.info("""
    O sistema utiliza as seguintes tabelas com base na **Competência Analisada**:
    - **Competência em 2024:** Aplica as tabelas de INSS, IRRF e Salário Família de 2024.
    - **Competência em 2025 ou Anos Seguintes:** Aplica as tabelas de INSS, IRRF e Salário Família de 2025.
    """)
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Salário Família (Regras)")
        st.markdown(f"""
        #### **Vigência 2025**
        - **Limite Salário:** {formatar_moeda(SF_LIMITE_2025)}
        - **Valor por Dependente:** {formatar_moeda(SF_VALOR_2025)}
        
        #### **Vigência 2024**
        - **Limite Salário:** {formatar_moeda(SF_LIMITE_2024)}
        - **Valor por Dependente:** {formatar_moeda(SF_VALOR_2024)}
        
        - **Dedução IR por Dependente (Ambos os anos):** {formatar_moeda(DESCONTO_DEPENDENTE_IR)}
        - **Requisito:** Salário **<=** ao limite (para Salário Família)
        """)
    
    with col_info2:
        st.subheader("📋 INSS 2025 (Alíquota Efetiva)")
        tabela_inss_df_2025 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1518.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1518.01) + " a " + formatar_moeda(2793.88), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2793.89) + " a " + formatar_moeda(4190.83), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4190.84) + " a " + formatar_moeda(8157.41), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2025, use_container_width=True, hide_index=True)
        st.caption(f"**Teto máximo do INSS 2025:** {formatar_moeda(8157.41)}")
        
        st.subheader("📋 INSS 2024 (Alíquota Efetiva)")
        tabela_inss_df_2024 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1412.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1412.01) + " a " + formatar_moeda(2666.68), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2666.69) + " a " + formatar_moeda(4000.03), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4000.04) + " a " + formatar_moeda(7786.02), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2024, use_container_width=True, hide_index=True)
        st.caption(f"**Teto máximo do INSS 2024:** {formatar_moeda(7786.02)}")

    st.subheader("📈 Tabela IRRF 2025")
    tabela_irrf_df_2025 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(182.16)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Parcela a Deduzir": formatar_moeda(394.16)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Parcela a Deduzir": formatar_moeda(675.49)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Parcela a Deduzir": formatar_moeda(916.90)}
    ])
    st.dataframe(tabela_irrf_df_2025, use_container_width=True, hide_index=True)

    st.subheader("📈 Tabela IRRF 2024")
    tabela_irrf_df_2024 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2112.00), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2112.01) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(158.40)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Parcela a Deduzir": formatar_moeda(370.40)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Parcela a Deduzir": formatar_moeda(651.73)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Parcela a Deduzir": formatar_moeda(884.96)}
    ])
    st.dataframe(tabela_irrf_df_2024, use_container_width=True, hide_index=True)
    
    st.subheader("📝 Legislação de Referência")
    st.write("""
    - **Salário Família:** Lei 8.213/1991
    - **INSS 2025:** Lei 8.212/1991 e Portaria MF/MPS 01/2024
    - **INSS 2024:** Lei 8.212/1991 e Portaria INTERMINISTERIAL MPS/MF Nº 2, DE 11 DE JANEIRO DE 2024
    - **IRRF 2025:** Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024
    - **IRRF 2024:** Lei 7.713/1988 e Lei nº 14.663, de 28 de agosto de 2023
    """)

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento**

Cálculos dinâmicos com base na **Competência** informada:
- Salário Família (2024 e 2025)
- INSS (Tabela 2024 e 2025)
- IRRF (Tabela 2024 e 2025)

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
