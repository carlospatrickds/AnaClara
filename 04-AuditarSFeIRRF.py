import streamlit as st
import pandas as pd
from datetime import datetime
# Adicionar timezone e a função timezone() do Python 3.9+
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

# INICIALIZAR SESSION STATE - CORREÇÃO DO ERRO
if 'df_resultado' not in st.session_state:
    st.session_state.df_resultado = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None

st.title("💰 Auditoria de Folha de Pagamento 2025 - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# Dados das tabelas 2025
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

def formatar_moeda(valor):
    """Formata valor em moeda brasileira"""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data(data):
    """Formata data no padrão brasileiro"""
    if isinstance(data, str):
        return data
    return data.strftime("%d/%m/%Y")

def calcular_inss(salario_bruto):
    """Calcula desconto do INSS 2025 com a tabela correta"""
    if salario_bruto <= 0:
        return 0.0
    
    salario_calculo = min(salario_bruto, TABELA_INSS[3]["limite"])
    inss = 0.0
    salario_restante = salario_calculo
    
    for i, faixa in enumerate(TABELA_INSS):
        if salario_restante <= 0:
            break
            
        if i == 0:
            valor_faixa = min(salario_restante, faixa["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
        else:
            faixa_anterior = TABELA_INSS[i-1]
            valor_faixa = min(salario_restante, faixa["limite"] - faixa_anterior["limite"])
            inss += valor_faixa * faixa["aliquota"]
            salario_restante -= valor_faixa
    
    return round(inss, 2)
    
# --- FUNÇÃO PARA OBTER HORA CORRETA NO BRASIL (BRT/GMT-3) ---
def get_br_datetime_now():
    """Retorna o objeto get_br_datetime_now() configurado para o fuso horário de São Paulo (BRT/GMT-3)"""
    # Usando o fuso horário padrão do Brasil para a maioria dos estados, incluindo Pernambuco
    return datetime.now(ZoneInfo("America/Sao_Paulo"))
    
def calcular_salario_familia(salario, dependentes):
    """Calcula salário família"""
    if salario <= SALARIO_FAMILIA_LIMITE:
        return dependentes * VALOR_POR_DEPENDENTE
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, outros_descontos=0):
    """Calcula IRRF"""
    base_calculo = salario_bruto - (dependentes * DESCONTO_DEPENDENTE_IR) - inss - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    for faixa in TABELA_IRRF:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(irrf, 0.0)
    
    return 0.0

def gerar_pdf_individual(dados):
    """Gera PDF profissional para cálculo individual"""
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
    pdf.cell(0, 10, 'INFORMAÇÕES DA EMPRESA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Data da Análise: {dados["data_analise"]}', 0, 1)
    pdf.cell(0, 6, f'Competência: {dados["competencia"]}', 0, 1)
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
    
    # Mostrar se houve Salário Família
    if dados["salario_familia"] != "R$ 0,00":
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA APLICADO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'SALÁRIO FAMÍLIA APLICADO: Não', 0, 1)
    
    # Mostrar se houve IRRF
    if dados["irrf"] != "R$ 0,00":
        pdf.cell(0, 6, 'IRRF APLICADO: Sim', 0, 1)
    else:
        pdf.cell(0, 6, 'IRRF APLICADO: Não (Isento)', 0, 1)
    
    pdf.ln(10)
    
    # Tabelas de Referência
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA 2025', 0, 1)
    
    # Tabela Salário Família (SEMPRE MOSTRAR)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'SALÁRIO FAMÍLIA 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(SALARIO_FAMILIA_LIMITE), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(VALOR_POR_DEPENDENTE), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS (SEMPRE MOSTRAR)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA INSS 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor', 1, 1)
    
    faixas_inss = [
        (f'Até {formatar_moeda(1518.00)}', '7,5%', formatar_moeda(1518.00 * 0.075)),
        (f'{formatar_moeda(1518.01)} a {formatar_moeda(2793.88)}', '9,0%', formatar_moeda((2793.88 - 1518.00) * 0.09)),
        (f'{formatar_moeda(2793.89)} a {formatar_moeda(4190.83)}', '12,0%', formatar_moeda((4190.83 - 2793.88) * 0.12)),
        (f'{formatar_moeda(4190.84)} a {formatar_moeda(8157.41)}', '14,0%', formatar_moeda((8157.41 - 4190.83) * 0.14))
    ]
    
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(8157.41)}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF (SEMPRE MOSTRAR)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA IRRF 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Dedução', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = [
        (f'Até {formatar_moeda(2428.80)}', '0%', formatar_moeda(0), 'Isento'),
        (f'{formatar_moeda(2428.81)} a {formatar_moeda(2826.65)}', '7,5%', formatar_moeda(182.16), '1ª'),
        (f'{formatar_moeda(2826.66)} a {formatar_moeda(3751.05)}', '15%', formatar_moeda(394.16), '2ª'),
        (f'{formatar_moeda(3751.06)} a {formatar_moeda(4664.68)}', '22,5%', formatar_moeda(675.49), '3ª'),
        (f'Acima de {formatar_moeda(4664.68)}', '27,5%', formatar_moeda(916.90), '4ª')
    ]
    
    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(DESCONTO_DEPENDENTE_IR)}', 0, 1)
    pdf.ln(10)
    
    # Legislação de Referência
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    # CORREÇÃO: Substituir '•' por '-' para evitar erro de encoding no FPDF
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        '- INSS: Lei 8.212/1991 e Portaria MF/MPS 01/2024',
        '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024',
        '- Vigência: Exercício 2025 (ano-calendário 2024)'
    ]
    
    for item in legislacao:
        pdf.cell(0, 5, item, 0, 1)
    
    pdf.ln(5)
    
    # Metodologia de Cálculo
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'METODOLOGIA DE CÁLCULO', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    metodologia = [
        # CORREÇÃO: Substituir '≤' por 'é menor ou igual a'
        '1. SALÁRIO FAMÍLIA: Verifica se salário bruto é menor ou igual a R$ 1.906,04',
        '2. CÁLCULO: Nº Dependentes × R$ 65,00 (se elegível)',
        '3. INSS: Cálculo progressivo por faixas acumulativas',
        '4. BASE IRRF: Salário Bruto - Dependentes × R$ 189,59 - INSS - Outros Descontos',
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
    
    return pdf

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total):
    """Gera PDF para auditoria completa"""
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
    pdf.cell(0, 6, f'Data da Análise: {formatar_data(get_br_datetime_now())}', 0, 1)
    pdf.cell(0, 6, f'Total de Funcionários Auditados: {len(df_resultado)}', 0, 1)
    pdf.cell(0, 6, f'Arquivo Processado: {uploaded_filename}', 0, 1)
    
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
        
        # Cabeçalho da tabela
        pdf.set_font('Arial', 'B', 8)
        colunas = ['Nome', 'Salário', 'Dep', 'Sal Fam', 'INSS', 'IRRF', 'Líquido']
        larguras = [40, 25, 15, 25, 25, 25, 30]
        
        for i, coluna in enumerate(colunas):
            pdf.cell(larguras[i], 8, coluna, 1, 0, 'C')
        pdf.ln()
        
        # Dados da tabela
        pdf.set_font('Arial', '', 7)
        for _, row in df_resultado.head(15).iterrows():
            # Nome (truncado se necessário)
            nome = str(row['Nome'])[:20] + '...' if len(str(row['Nome'])) > 20 else str(row['Nome'])
            pdf.cell(larguras[0], 6, nome, 1)
            
            # Valores numéricos formatados
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
    
    # Tabelas de Referência COMPLETAS
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'TABELAS DE REFERÊNCIA 2025', 0, 1)
    
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'SALÁRIO FAMÍLIA 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(SALARIO_FAMILIA_LIMITE), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(VALOR_POR_DEPENDENTE), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA INSS 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor', 1, 1)
    
    faixas_inss = [
        (f'Até {formatar_moeda(1518.00)}', '7,5%', formatar_moeda(1518.00 * 0.075)),
        (f'{formatar_moeda(1518.01)} a {formatar_moeda(2793.88)}', '9,0%', formatar_moeda((2793.88 - 1518.00) * 0.09)),
        (f'{formatar_moeda(2793.89)} a {formatar_moeda(4190.83)}', '12,0%', formatar_moeda((4190.83 - 2793.88) * 0.12)),
        (f'{formatar_moeda(4190.84)} a {formatar_moeda(8157.41)}', '14,0%', formatar_moeda((8157.41 - 4190.83) * 0.14))
    ]
    
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {formatar_moeda(8157.41)}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'TABELA IRRF 2025', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Dedução', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    faixas_irrf = [
        (f'Até {formatar_moeda(2428.80)}', '0%', formatar_moeda(0), 'Isento'),
        (f'{formatar_moeda(2428.81)} a {formatar_moeda(2826.65)}', '7,5%', formatar_moeda(182.16), '1ª'),
        (f'{formatar_moeda(2826.66)} a {formatar_moeda(3751.05)}', '15%', formatar_moeda(394.16), '2ª'),
        (f'{formatar_moeda(3751.06)} a {formatar_moeda(4664.68)}', '22,5%', formatar_moeda(675.49), '3ª'),
        (f'Acima de {formatar_moeda(4664.68)}', '27,5%', formatar_moeda(916.90), '4ª')
    ]
    
    for base, aliquota, deducao, faixa in faixas_irrf:
        pdf.cell(60, 6, base, 1)
        pdf.cell(25, 6, aliquota, 1)
        pdf.cell(35, 6, deducao, 1)
        pdf.cell(0, 6, faixa, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(DESCONTO_DEPENDENTE_IR)}', 0, 1)
    pdf.ln(10)
    
    # Legislação de Referência
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    legislacao = [
        '- Salário Família: Lei 8.213/1991',
        '- INSS: Lei 8.212/1991 e Portaria MF/MPS 01/2024',
        '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024',
        '- Vigência: Exercício 2025 (ano-calendário 2024)'
    ]
    
    # CORREÇÃO: Substituir '•' por '-' para evitar erro de encoding no FPDF
    for item in legislacao:
        pdf.cell(0, 5, item, 0, 1)
    
    pdf.ln(5)
    
    # Metodologia de Cálculo
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'METODOLOGIA DE CÁLCULO APLICADA', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    metodologia = [
        # CORREÇÃO: Substituir '≤' por 'menores ou iguais a'
        '1. SALÁRIO FAMÍLIA: Pago para salários menores ou iguais a R$ 1.906,04, no valor de R$ 65,00 por dependente',
        '2. INSS: Cálculo progressivo por faixas conforme tabela 2025',
        '3. IRRF: Base de cálculo = Salário Bruto - Dependentes × R$ 189,59 - INSS - Outros Descontos',
        '4. Aplicadas alíquotas progressivas conforme tabela IRRF 2025',
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
    pdf.cell(0, 5, f'Processado em: {get_br_datetime_now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
    
    return pdf

def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF"""
    # Usar o output diretamente (já é bytes)
    b64 = base64.b64encode(pdf_output).decode() 
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

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
                                     value=get_br_datetime_now().replace(day=1))
    
    if st.button("Calcular", type="primary"):
        # Realizar cálculos
        inss_valor = calcular_inss(salario)
        sal_familia = calcular_salario_familia(salario, dependentes)
        irrf_valor = calcular_irrf(salario, dependentes, inss_valor, outros_descontos)
        
        # Cálculo do salário líquido
        total_descontos = inss_valor + irrf_valor + outros_descontos
        total_acrescimos = sal_familia
        salario_liquido = salario - total_descontos + total_acrescimos
        base_irrf = salario - (dependentes * DESCONTO_DEPENDENTE_IR) - inss_valor - outros_descontos
        
        # Mostrar resultados
        st.success("Cálculos realizados com sucesso!")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Salário Família", formatar_moeda(sal_familia))
        with col2:
            st.metric("INSS", formatar_moeda(inss_valor))
        with col3:
            st.metric("IRRF", formatar_moeda(irrf_valor))
        with col4:
            st.metric("Salário Líquido", formatar_moeda(salario_liquido))
        
        # Tabela de detalhes
        st.subheader("📋 Detalhamento Completo")
        detalhes = pd.DataFrame({
            'Descrição': [
                'Salário Bruto', 
                'Salário Família', 
                'INSS', 
                'IRRF', 
                'Outros Descontos',
                'Total Descontos',
                'Salário Líquido'
            ],
            'Valor': [
                formatar_moeda(salario),
                formatar_moeda(sal_familia),
                formatar_moeda(inss_valor),
                formatar_moeda(irrf_valor),
                formatar_moeda(outros_descontos),
                formatar_moeda(total_descontos),
                formatar_moeda(salario_liquido)
            ]
        })
        st.dataframe(detalhes, use_container_width=True, hide_index=True)
        
        # Informações adicionais
        st.subheader("📊 Informações Adicionais")
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.write(f"**Competência Analisada:** {formatar_data(competencia)}")
            st.write(f"**Dependentes para IRRF:** {dependentes}")
            st.write(f"**Base cálculo IRRF:** {formatar_moeda(base_irrf)}")
        
        with col_info2:
            st.write(f"**Elegível Salário Família:** {'Sim' if sal_familia > 0 else 'Não'}")
            st.write(f"**Total de Descontos:** {formatar_moeda(total_descontos)}")
            st.write(f"**Total de Acréscimos:** {formatar_moeda(total_acrescimos)}")
        
        # Gerar PDF
        st.subheader("📄 Gerar Relatório PDF")
        dados_pdf = {
            "data_analise": formatar_data(get_br_datetime_now()),
            "competencia": formatar_data(competencia),
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
            "base_irrf": formatar_moeda(base_irrf)
        }
        
        try:
            pdf = gerar_pdf_individual(dados_pdf)
            pdf_output = pdf.output(dest='S')
            
            st.markdown(
                criar_link_download_pdf(
                    pdf_output, 
                    f"Auditoria_Folha_{nome.replace(' ', '_')}_{get_br_datetime_now().strftime('%d%m%Y')}.pdf"
                ), 
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

with tab2:
    st.header("Auditoria em Lote")
    
    # Opções de entrada de dados SIMPLIFICADA
    st.info("""
    **📊 Opções de Entrada de Dados:**
    
    Escolha uma das opções abaixo:
    1. **Upload de arquivo CSV** (formato tradicional)
    2. **Google Sheets** (cole a URL - método simples)
    3. **Digitação manual** de dados
    """)
    
    opcao_entrada = st.radio(
        "Selecione a fonte dos dados:",
        ["📁 Upload de CSV", "🌐 Google Sheets", "✏️ Digitação Manual"],
        horizontal=True,
        key="opcao_entrada"  # Adicionar key única
    )
    
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
    
    # LIMPAR SESSION STATE QUANDO MUDAR DE OPÇÃO
    if 'ultima_opcao' not in st.session_state:
        st.session_state.ultima_opcao = opcao_entrada
    elif st.session_state.ultima_opcao != opcao_entrada:
        # Limpar dados anteriores quando mudar de opção
        st.session_state.df_resultado = None
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
                # Tenta ler com separador ';' e depois com ','
                try:
                    df = pd.read_csv(uploaded_file, sep=';')
                except:
                    uploaded_file.seek(0) # Volta o ponteiro do arquivo para o início
                    df = pd.read_csv(uploaded_file, sep=',')
                
                uploaded_filename = uploaded_file.name
                st.success("✅ Arquivo CSV carregado com sucesso!")
                
            except Exception as e:
                st.error(f"❌ Erro ao ler arquivo CSV: {e}")
    
    elif opcao_entrada == "🌐 Google Sheets":
        st.subheader("🔗 Integração com Google Sheets")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            sheets_url = st.text_input(
                "URL do Google Sheets:",
                value="https://docs.google.com/spreadsheets/d/1G-O5sNYWGLDYG8JG3FXom4BpBrVFRnrxVal-LwmH9Gc/edit?usp=sharing",
                help="Cole a URL completa da planilha do Google Sheets",
                key="sheets_url"  # Key única para este input
            )
        
        with col2:
            sheet_name = st.text_input(
                "Nome da Aba:",
                value="Página1",
                help="Nome da aba/worksheet (padrão: Página1)",
                key="sheet_name"  # Key única para este input
            )
        
        if sheets_url:
            try:
                # Extrair ID da planilha da URL
                if "/d/" in sheets_url:
                    sheet_id = sheets_url.split("/d/")[1].split("/")[0]
                else:
                    sheet_id = sheets_url
                
                # CORREÇÃO DO ERRO DE ENCODING - usar URL encoding para o nome da aba
                sheet_name_encoded = urllib.parse.quote(sheet_name)
                
                # URL para exportação como CSV
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}"
                
                # Ler dados do Google Sheets com encoding correto
                df = pd.read_csv(csv_url, encoding='utf-8')
                uploaded_filename = f"Google_Sheets_{sheet_name}"
                
                st.success("✅ Conexão com Google Sheets estabelecida!")
                
                # Renomear colunas para o formato esperado
                if len(df.columns) >= 3:
                    # Mapear colunas automáticas para nossos nomes
                    df.columns = ['Nome', 'Salario_Bruto', 'Dependentes'] + list(df.columns[3:])
                    
                    # Se tiver mais colunas, assumir que a quarta é Outros_Descontos
                    if len(df.columns) > 3:
                        df = df.rename(columns={df.columns[3]: 'Outros_Descontos'})
                    else:
                        df['Outros_Descontos'] = 0.0
                
            except Exception as e:
                st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
                st.info("""
                **Solução de problemas:**
                - Verifique se a planilha é pública ou compartilhada para visualização
                - Confirme o nome exato da aba
                - Certifique-se de que a URL está correta
                - A planilha deve ter pelo menos 3 colunas: Nome, Salario_Bruto, Dependentes
                """)
    
    elif opcao_entrada == "✏️ Digitação Manual":
        st.subheader("📝 Digitação Manual de Dados")
        
        # Interface para entrada manual de dados
        num_funcionarios = st.number_input(
            "Número de funcionários:",
            min_value=1,
            max_value=50,
            value=3,
            step=1,
            key="num_funcionarios"  # Key única
        )
        
        # Inicializar dados manuais no session state
        if 'dados_manuais' not in st.session_state:
            st.session_state.dados_manuais = []
        
        dados_manuais = []
        
        # Verificar se precisa re-inicializar
        if len(st.session_state.dados_manuais) != num_funcionarios:
             st.session_state.dados_manuais = [{
                'Nome': f"Funcionário {i+1}", 
                'Salario_Bruto': 2000.0, 
                'Dependentes': 1, 
                'Outros_Descontos': 0.0
            } for i in range(num_funcionarios)]
        
        for i in range(num_funcionarios):
            st.write(f"--- **Funcionário {i+1}** ---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                nome = st.text_input(f"Nome {i+1}", 
                                     value=st.session_state.dados_manuais[i]['Nome'], 
                                     key=f"nome_manual_{i}")
            with col2:
                salario = st.number_input(f"Salário {i+1}", 
                                          min_value=0.0, 
                                          value=st.session_state.dados_manuais[i]['Salario_Bruto'], 
                                          step=100.0, 
                                          key=f"salario_manual_{i}")
            with col3:
                dependentes = st.number_input(f"Dependentes {i+1}", 
                                              min_value=0, 
                                              value=st.session_state.dados_manuais[i]['Dependentes'], 
                                              step=1, 
                                              key=f"dependentes_manual_{i}")
            with col4:
                outros_desc = st.number_input(f"Outros Desc. {i+1}", 
                                              min_value=0.0, 
                                              value=st.session_state.dados_manuais[i]['Outros_Descontos'], 
                                              step=50.0, 
                                              key=f"outros_manual_{i}")
            
            dados_manuais.append({
                'Nome': nome,
                'Salario_Bruto': salario,
                'Dependentes': dependentes,
                'Outros_Descontos': outros_desc
            })
        
        # Botão para confirmar dados manuais
        col_confirmar, col_limpar = st.columns(2)
        
        with col_confirmar:
            if st.button("✅ Confirmar Dados Manuais", type="primary", key="confirmar_manual"):
                df = pd.DataFrame(dados_manuais)
                uploaded_filename = "dados_manuais"
                st.session_state.dados_manuais = dados_manuais.copy()
                st.session_state.df_resultado = None # Forçar reprocessamento
                st.success("✅ Dados manuais confirmados! Clique em 'Processar Auditoria' para calcular.")
                st.rerun()  # Forçar atualização da página
        
        with col_limpar:
            if st.button("🗑️ Limpar Dados", type="secondary", key="limpar_manual"):
                st.session_state.dados_manuais = []
                st.session_state.df_resultado = None
                st.success("🗑️ Dados limpos!")
                st.rerun()  # Forçar atualização da página
        
        # Usar dados do session state se existirem e não houve confirmação forçada
        if st.session_state.dados_manuais:
            df = pd.DataFrame(st.session_state.dados_manuais)
            uploaded_filename = "dados_manuais"
    
    # Processamento dos dados (comum para todas as opções)
    if df is not None:
        try:
            # Converter colunas numéricas para float, tratando possíveis erros
            df['Salario_Bruto'] = pd.to_numeric(df['Salario_Bruto'], errors='coerce').fillna(0)
            df['Dependentes'] = pd.to_numeric(df['Dependentes'], errors='coerce').fillna(0).astype(int)
            
            # Se a coluna Outros_Descontos existir, converter também
            if 'Outros_Descontos' in df.columns:
                df['Outros_Descontos'] = pd.to_numeric(df['Outros_Descontos'], errors='coerce').fillna(0)
            else:
                df['Outros_Descontos'] = 0.0
            
            # Verificar se as colunas necessárias existem
            colunas_necessarias = ['Nome', 'Salario_Bruto', 'Dependentes']
            colunas_faltantes = [col for col in colunas_necessarias if col not in df.columns]
            
            if colunas_faltantes:
                st.error(f"❌ Colunas faltantes: {', '.join(colunas_faltantes)}")
                st.info("""
                **Colunas necessárias:**
                - Nome
                - Salario_Bruto  
                - Dependentes
                - Outros_Descontos (opcional)
                """)
            else:
                st.write("**👀 Pré-visualização dos dados:**")
                st.dataframe(df.head(), use_container_width=True)
                
                # Estatísticas rápidas
                st.write("**📊 Estatísticas dos dados:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de Funcionários", len(df))
                with col2:
                    st.metric("Maior Salário", formatar_moeda(df['Salario_Bruto'].max()))
                with col3:
                    st.metric("Total Dependentes", df['Dependentes'].sum())
                
                # Botão para processar auditoria
                if st.button("🚀 Processar Auditoria Completa", type="primary", key="processar_auditoria"):
                    # Processar cada funcionário
                    with st.spinner("Processando auditoria..."):
                        resultados = []
                        
                        for _, row in df.iterrows():
                            # Garantir que os valores são numéricos
                            salario_bruto = float(row['Salario_Bruto'])
                            dependentes = int(row['Dependentes'])
                            outros_desc = float(row.get('Outros_Descontos', 0))
                            
                            inss = calcular_inss(salario_bruto)
                            sal_familia = calcular_salario_familia(salario_bruto, dependentes)
                            irrf = calcular_irrf(salario_bruto, dependentes, inss, outros_desc)
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
                                'Elegivel_Salario_Familia': 'Sim' if sal_familia > 0 else 'Não'
                            })
                        
                        df_resultado = pd.DataFrame(resultados)
                        
                        # Armazenar resultados no session state
                        st.session_state.df_resultado = df_resultado
                        st.session_state.uploaded_filename = uploaded_filename
                        
                        st.success("🎉 Auditoria concluída!")
                        st.rerun()  # Forçar atualização para mostrar resultados
        
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {e}")
    
    # CORREÇÃO: VERIFICAR SE EXISTE NO SESSION STATE ANTES DE USAR
    if st.session_state.df_resultado is not None:
        df_resultado = st.session_state.df_resultado
        
        # Mostrar de qual fonte vieram os dados
        st.info(f"📊 **Dados processados de:** {st.session_state.uploaded_filename}")
        
        # Botão para limpar resultados
        if st.button("🗑️ Limpar Resultados", type="secondary", key="limpar_resultados"):
            st.session_state.df_resultado = None
            st.session_state.uploaded_filename = None
            if 'dados_manuais' in st.session_state:
                st.session_state.dados_manuais = []
            st.success("🗑️ Resultados limpos!")
            st.rerun()
        
        # Resultados completos
        st.subheader("📈 Resultados da Auditoria")
        
        # Criar DataFrame formatado para exibição
        df_display = df_resultado.copy()
        
        # Formatar colunas numéricas para exibição
        colunas_monetarias = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
        for coluna in colunas_monetarias:
            df_display[coluna] = df_display[coluna].apply(formatar_moeda)
        
        st.dataframe(df_display, use_container_width=True)
        
        # Estatísticas finais
        st.subheader("📊 Resumo Financeiro")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_salario_familia = df_resultado['Salario_Familia'].sum()
            st.metric("Total Salário Família", formatar_moeda(total_salario_familia))
        with col2:
            total_inss = df_resultado['INSS'].sum()
            st.metric("Total INSS", formatar_moeda(total_inss))
        with col3:
            total_irrf = df_resultado['IRRF'].sum()
            st.metric("Total IRRF", formatar_moeda(total_irrf))
        with col4:
            folha_liquida_total = df_resultado['Salario_Liquido'].sum()
            st.metric("Folha Líquida Total", formatar_moeda(folha_liquida_total))
        
        # Download dos resultados
        st.subheader("💾 Exportar Resultados")
        col_csv, col_pdf = st.columns(2)
        
        with col_csv:
            # Criar CSV com formatação brasileira
            df_csv = df_resultado.copy()
            for coluna in colunas_monetarias:
                df_csv[coluna] = df_csv[coluna].apply(lambda x: f"{x:.2f}".replace('.', ','))
            
            csv_resultado = df_csv.to_csv(index=False, sep=';')
            st.download_button(
                label="📥 Baixar CSV",
                data=csv_resultado,
                file_name=f"auditoria_folha_{get_br_datetime_now().strftime('%d%m%Y_%H%M')}.csv",
                mime="text/csv",
                help="Baixe os resultados em CSV"
            )
        
        with col_pdf:
            # Gerar PDF da auditoria completa
            if st.button("📄 Gerar PDF Completo", type="secondary", key="gerar_pdf_completo"):
                with st.spinner("Gerando relatório PDF..."):
                    try:
                        pdf = gerar_pdf_auditoria_completa(
                            df_resultado, 
                            st.session_state.uploaded_filename,
                            total_salario_familia,
                            total_inss,
                            total_irrf,
                            folha_liquida_total
                        )
                        # CORREÇÃO: Remover .encode('latin1')
                        pdf_output = pdf.output(dest='S')
                        
                        st.markdown(
                            criar_link_download_pdf(
                                pdf_output, 
                                f"Auditoria_Completa_{get_br_datetime_now().strftime('%d%m%Y_%H%M')}.pdf"
                            ), 
                            unsafe_allow_html=True
                        )
                        st.success("📄 PDF gerado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF: {e}")

with tab3:
    st.header("Informações Técnicas 2025")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.subheader("💰 Salário Família")
        st.write(f"""
        - **Limite de salário:** {formatar_moeda(SALARIO_FAMILIA_LIMITE)}
        - **Valor por dependente:** {formatar_moeda(VALOR_POR_DEPENDENTE)}
        - **Dedução IR por dependente:** {formatar_moeda(DESCONTO_DEPENDENTE_IR)}
        - **Requisito:** Salário igual ou inferior ao limite
        - **Dependentes:** Filhos até 14 anos ou inválidos de qualquer idade
        """)
        
        st.subheader("📋 Como Calcular - Salário Família")
        # CORREÇÃO: Substituir '≤' por '<=' no código de exemplo
        st.code(f"""
Se Salário Bruto <= R$ 1.906,04:
    Salário Família = Nº Dependentes × R$ 65,00
Senão:
    Salário Família = R$ 0,00
        """)
        
        st.write("""
        **Exemplo:**
        - Salário: R$ 1.800,00
        - Dependentes: 2
        - Cálculo: 2 × R$ 65,00 = R$ 130,00
        """)
    
    with col_info2:
        st.subheader("📊 Tabela INSS 2025")
        tabela_inss_df = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1518.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1518.01) + " a " + formatar_moeda(2793.88), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2793.89) + " a " + formatar_moeda(4190.83), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4190.84) + " a " + formatar_moeda(8157.41), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df, use_container_width=True, hide_index=True)
        st.caption(f"**Teto máximo do INSS:** {formatar_moeda(8157.41)}")
        
        st.subheader("📋 Como Calcular - INSS")
        st.code("""
Fórmula Progressiva:
    1ª Faixa: R$ 1.518,00 × 7,5%
    2ª Faixa: (R$ 2.793,88 - R$ 1.518,00) × 9%
    3ª Faixa: (R$ 4.190,83 - R$ 2.793,88) × 12%
    4ª Faixa: (R$ 8.157,41 - R$ 4.190,83) × 14%
        """)

    st.subheader("📈 Tabela IRRF 2025")
    tabela_irrf_df = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Dedução": formatar_moeda(0.00), "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Dedução": formatar_moeda(182.16), "Parcela a Deduzir": formatar_moeda(182.16)},
        {"Faixa": "3ª", "Base de Cálculo": formatar_moeda(2826.66) + " a " + formatar_moeda(3751.05), "Alíquota": "15%", "Dedução": formatar_moeda(394.16), "Parcela a Deduzir": formatar_moeda(394.16)},
        {"Faixa": "4ª", "Base de Cálculo": formatar_moeda(3751.06) + " a " + formatar_moeda(4664.68), "Alíquota": "22,5%", "Dedução": formatar_moeda(675.49), "Parcela a Deduzir": formatar_moeda(675.49)},
        {"Faixa": "5ª", "Base de Cálculo": "Acima de " + formatar_moeda(4664.68), "Alíquota": "27,5%", "Dedução": formatar_moeda(916.90), "Parcela a Deduzir": formatar_moeda(916.90)}
    ])
    st.dataframe(tabela_irrf_df, use_container_width=True, hide_index=True)
    
    st.subheader("📋 Como Calcular - IRRF")
    st.code(f"""
Base de Cálculo = Salário Bruto - (Dependentes × {formatar_moeda(DESCONTO_DEPENDENTE_IR)}) - INSS - Outros Descontos
IRRF = (Base de Cálculo × Alíquota) - Parcela a Deduzir
    """)
    
    st.write(f"""
    **Dedução por Dependente:** {formatar_moeda(DESCONTO_DEPENDENTE_IR)}
    
    **Exemplo:**
    - Salário Bruto: R$ 3.000,00
    - Dependentes: 1
    - INSS: R$ 263,33
    - Base: R$ 3.000,00 - (1 × {formatar_moeda(DESCONTO_DEPENDENTE_IR)}) - R$ 263,33 = R$ 2.546,88
    - Cálculo: (R$ 2.546,88 × 7,5%) - R$ 182,16 = R$ 8,86
    """)

    st.subheader("🧮 Exemplos Práticos de Cálculo")
    
    exemplos = pd.DataFrame({
        'Cenário': [
            'Funcionário FAIXA UM + dependentes',
            'Funcionário FAIXA 2',
            'Funcionário FAIXA 3',
            'Funcionário no teto do INSS'
        ],
        'Salário Bruto': [
            formatar_moeda(1500.00),
            formatar_moeda(3500.00),
            formatar_moeda(6000.00),
            formatar_moeda(9000.00)
        ],
        'Dependentes': [2, 1, 0, 2],
        'Salário Família': [
            formatar_moeda(130.00),
            formatar_moeda(0.00),
            formatar_moeda(0.00),
            formatar_moeda(0.00)
        ],
        'INSS': [
            formatar_moeda(112.50),
            formatar_moeda(263.33),
            formatar_moeda(514.03),
            formatar_moeda(828.39)
        ],
        'IRRF': [
            formatar_moeda(0.00),
            formatar_moeda(35.52),
            formatar_moeda(505.42),
            formatar_moeda(1085.27)
        ],
        'Salário Líquido': [
            formatar_moeda(1517.50),
            formatar_moeda(3201.15),
            formatar_moeda(4980.55),
            formatar_moeda(7086.34)
        ]
    })
    
    st.dataframe(exemplos, use_container_width=True)

    st.subheader("📝 Legislação de Referência")
    st.write("""
    - **Salário Família:** Lei 8.213/1991
    - **INSS:** Lei 8.212/1991 e Portaria MF/MPS 01/2024
    - **IRRF:** Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024
    - **Vigência:** Exercício 2025 (ano-calendário 2024)
    """)
    
    st.subheader("⚠️ Observações Importantes")
    st.write("""
    1. **Salário Família:**
        - Pago apenas para salários até R$ 1.906,04
        - Dependentes: filhos até 14 anos ou inválidos de qualquer idade
    
    2. **INSS:**
        - Cálculo progressivo por faixas
        - Teto máximo de contribuição: R$ 8.157,41
        - Salários acima do teto pagam o valor máximo
    
    3. **IRRF:**
        - Dedução de R$ 189,59 por dependente
        - Base de cálculo após descontos de INSS e dependentes
        - Isenção para base até R$ 2.428,80
    
    4. **Competência:**
        - Referente ao mês de pagamento
        - Baseada na legislação vigente em 2025
    
    **Nota:** Este sistema realiza cálculos conforme a legislação vigente, 
    porém recomenda-se consulta a contador para validação oficial.
    """)

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento 2025**

Cálculos baseados na legislação vigente:
- Salário Família
- INSS (Tabela 2025)
- IRRF (Tabela 2025)

**Funcionalidades:**
- Cálculo individual
- Auditoria em lote
- Relatórios em PDF
- Tabelas atualizadas

⚠️ Consulte um contador para validação oficial.
""")

# Adicionar informações de contato no sidebar
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

# Rodapé
st.markdown("---")
col_rodape1, col_rodape2, col_rodape3 = st.columns(3)

with col_rodape1:
    st.caption(f"📅 Competência: {formatar_data(get_br_datetime_now())}")

with col_rodape2:
    st.caption("🏛 Legislação 2025 - Vigência a partir de 01/01/2025")

with col_rodape3:
    st.caption("⚡ Desenvolvido para auditoria contábil")

# Adicionar uma seção de aviso legal
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
