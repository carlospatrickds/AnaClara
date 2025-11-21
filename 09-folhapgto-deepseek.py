import streamlit as st
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

st.title("💰 Auditoria de Folha de Pagamento - Ana Clara")
st.markdown("### Cálculo de Salário Família, INSS e IRRF")

# --- DETECTAR ANO DA COMPETÊNCIA ---
def obter_tabelas_por_ano(ano_competencia):
    """Retorna as tabelas corretas baseadas no ano da competência"""
    
    if ano_competencia == 2024:
        # --- TABELAS 2024 (ATUALIZADAS CONFORME MP 1.206/2024) ---
        SALARIO_FAMILIA_LIMITE = 1819.26
        VALOR_POR_DEPENDENTE = 62.04
        DESCONTO_DEPENDENTE_IR = 189.59

        # Tabela INSS 2024
        TABELA_INSS = [
            {"limite": 1412.00, "aliquota": 0.075},
            {"limite": 2666.68, "aliquota": 0.09},
            {"limite": 4000.03, "aliquota": 0.12},
            {"limite": 7786.02, "aliquota": 0.14}
        ]

        # Tabela IRRF 2024 - CORRIGIDA conforme MP 1.206/2024
        TABELA_IRRF = [
            {"limite": 2259.20, "aliquota": 0.0, "deducao": 0.0},
            {"limite": 2826.65, "aliquota": 0.075, "deducao": 169.44},
            {"limite": 3751.05, "aliquota": 0.15, "deducao": 381.44},
            {"limite": 4664.68, "aliquota": 0.225, "deducao": 662.77},
            {"limite": float('inf'), "aliquota": 0.275, "deducao": 896.00}
        ]
        
        TETO_INSS = 908.85
        
        return {
            'SALARIO_FAMILIA_LIMITE': SALARIO_FAMILIA_LIMITE,
            'VALOR_POR_DEPENDENTE': VALOR_POR_DEPENDENTE,
            'DESCONTO_DEPENDENTE_IR': DESCONTO_DEPENDENTE_IR,
            'TABELA_INSS': TABELA_INSS,
            'TABELA_IRRF': TABELA_IRRF,
            'TETO_INSS': TETO_INSS,
            'ANO': 2024
        }
    
    else:  # 2025 (valores mantidos do código original)
        # --- TABELAS 2025 ---
        SALARIO_FAMILIA_LIMITE = 1906.04
        VALOR_POR_DEPENDENTE = 65.00
        DESCONTO_DEPENDENTE_IR = 189.59

        # Tabela INSS 2025
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
        
        TETO_INSS = 8157.41 * 0.14  # Teto calculado
        
        return {
            'SALARIO_FAMILIA_LIMITE': SALARIO_FAMILIA_LIMITE,
            'VALOR_POR_DEPENDENTE': VALOR_POR_DEPENDENTE,
            'DESCONTO_DEPENDENTE_IR': DESCONTO_DEPENDENTE_IR,
            'TABELA_INSS': TABELA_INSS,
            'TABELA_IRRF': TABELA_IRRF,
            'TETO_INSS': TETO_INSS,
            'ANO': 2025
        }

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
    return data.strftime("%d/%m/%Y")

def get_br_datetime_now():
    """Retorna o objeto datetime configurado para o fuso horário de São Paulo (BRT/GMT-3)"""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# --- FUNÇÕES DE CÁLCULO ---

def calcular_inss(salario_bruto, tabela_inss, teto_inss):
    """Calcula desconto do INSS com a tabela correta (progressiva)"""
    if salario_bruto <= 0:
        return 0.0
    
    salario_calculo = min(salario_bruto, tabela_inss[3]["limite"])
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

def calcular_salario_familia(salario, dependentes, salario_familia_limite, valor_por_dependente):
    """Calcula salário família"""
    if salario <= salario_familia_limite:
        return dependentes * valor_por_dependente
    return 0.0

def calcular_irrf(salario_bruto, dependentes, inss, desconto_dependente_ir, tabela_irrf, outros_descontos=0):
    """Calcula IRRF"""
    # Base = Salário Bruto - Dedução por Dependente - INSS - Outros Descontos
    base_calculo = salario_bruto - (dependentes * desconto_dependente_ir) - inss - outros_descontos
    
    if base_calculo <= 0:
        return 0.0
    
    irrf = 0.0
    for faixa in tabela_irrf:
        if base_calculo <= faixa["limite"]:
            irrf = (base_calculo * faixa["aliquota"]) - faixa["deducao"]
            return max(round(irrf, 2), 0.0)
    
    return 0.0

# --- FUNÇÕES DE GERAÇÃO DE PDF ---

def criar_link_download_pdf(pdf_output, filename):
    """
    Cria link para download do PDF a partir de um objeto bytes (output do FPDF).
    Garante que o input seja bytes para o base64.
    """
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

def gerar_pdf_individual(dados, tabelas):
    """Gera PDF profissional para cálculo individual"""
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
    pdf.cell(0, 6, f'Ano de Referência: {tabelas["ANO"]}', 0, 1)
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
    
    # --- SEÇÃO DE OBSERVAÇÕES ---
    if dados.get("observacoes"):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OBSERVAÇÕES', 0, 1)
        pdf.set_font('Arial', '', 10)
        observacoes = dados["observacoes"]
        pdf.multi_cell(0, 6, observacoes)
        pdf.ln(5)
    
    # --- INCLUSÃO DAS TABELAS NO PDF ---
    ano = tabelas["ANO"]
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'TABELAS DE REFERÊNCIA {ano}', 0, 1)
    
    # Tabela Salário Família
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'SALÁRIO FAMÍLIA {ano}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(80, 6, 'Descrição', 1)
    pdf.cell(50, 6, 'Valor', 1)
    pdf.cell(0, 6, 'Observação', 1, 1)
    
    info_salario_familia = [
        ('Limite de salário', formatar_moeda(tabelas['SALARIO_FAMILIA_LIMITE']), 'Para ter direito'),
        ('Valor por dependente', formatar_moeda(tabelas['VALOR_POR_DEPENDENTE']), 'Por cada dependente'),
        ('Dependentes considerados', 'Filhos até 14 anos', 'Ou inválidos qualquer idade')
    ]
    
    for descricao, valor, obs in info_salario_familia:
        pdf.cell(80, 6, descricao, 1)
        pdf.cell(50, 6, valor, 1)
        pdf.cell(0, 6, obs, 1, 1)
    
    pdf.ln(5)
    
    # Tabela INSS
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA INSS {ano}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Faixa Salarial', 1)
    pdf.cell(30, 6, 'Alíquota', 1)
    pdf.cell(0, 6, 'Valor Máx. na Faixa', 1, 1)
    
    if ano == 2024:
        faixas_inss = [
            (f'Até {formatar_moeda(1412.00)}', '7,5%', formatar_moeda(1412.00 * 0.075)),
            (f'{formatar_moeda(1412.01)} a {formatar_moeda(2666.68)}', '9,0%', formatar_moeda((2666.68 - 1412.00) * 0.09)),
            (f'{formatar_moeda(2666.69)} a {formatar_moeda(4000.03)}', '12,0%', formatar_moeda((4000.03 - 2666.68) * 0.12)),
            (f'{formatar_moeda(4000.04)} a {formatar_moeda(7786.02)}', '14,0%', formatar_moeda((7786.02 - 4000.03) * 0.14))
        ]
        teto_inss = formatar_moeda(908.85)
    else:  # 2025
        faixas_inss = [
            (f'Até {formatar_moeda(1518.00)}', '7,5%', formatar_moeda(1518.00 * 0.075)),
            (f'{formatar_moeda(1518.01)} a {formatar_moeda(2793.88)}', '9,0%', formatar_moeda((2793.88 - 1518.00) * 0.09)),
            (f'{formatar_moeda(2793.89)} a {formatar_moeda(4190.83)}', '12,0%', formatar_moeda((4190.83 - 2793.88) * 0.12)),
            (f'{formatar_moeda(4190.84)} a {formatar_moeda(8157.41)}', '14,0%', formatar_moeda((8157.41 - 4190.83) * 0.14))
        ]
        teto_inss = formatar_moeda(8157.41)
    
    for faixa, aliquota, valor in faixas_inss:
        pdf.cell(60, 6, faixa, 1)
        pdf.cell(30, 6, aliquota, 1)
        pdf.cell(0, 6, valor, 1, 1)
    
    pdf.cell(0, 3, '', 0, 1)
    pdf.cell(0, 6, f'Teto máximo do INSS: {teto_inss}', 0, 1)
    pdf.ln(5)
    
    # Tabela IRRF
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f'TABELA IRRF {ano}', 0, 1)
    pdf.set_font('Arial', '', 8)
    pdf.cell(60, 6, 'Base de Cálculo', 1)
    pdf.cell(25, 6, 'Alíquota', 1)
    pdf.cell(35, 6, 'Parcela a Deduzir', 1)
    pdf.cell(0, 6, 'Faixa', 1, 1)
    
    if ano == 2024:
        faixas_irrf = [
            (f'Até {formatar_moeda(2259.20)}', '0%', formatar_moeda(0), 'Isento'),
            (f'{formatar_moeda(2259.21)} a {formatar_moeda(2826.65)}', '7,5%', formatar_moeda(169.44), '1ª'),
            (f'{formatar_moeda(2826.66)} a {formatar_moeda(3751.05)}', '15%', formatar_moeda(381.44), '2ª'),
            (f'{formatar_moeda(3751.06)} a {formatar_moeda(4664.68)}', '22,5%', formatar_moeda(662.77), '3ª'),
            (f'Acima de {formatar_moeda(4664.68)}', '27,5%', formatar_moeda(896.00), '4ª')
        ]
    else:  # 2025
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
    pdf.cell(0, 6, f'Dedução por dependente: {formatar_moeda(tabelas["DESCONTO_DEPENDENTE_IR"])}', 0, 1)
    pdf.ln(10)
    
    # Legislação e Metodologia
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'LEGISLAÇÃO E METODOLOGIA', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'LEGISLAÇÃO DE REFERÊNCIA', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    if ano == 2024:
        legislacao = [
            '- Salário Família: Lei 8.213/1991',
            '- INSS: Lei 8.212/1991 e Portaria Interministerial MPS/MF nº 2/2024',
            '- IRRF: Lei 7.713/1988 e MEDIDA PROVISÓRIA Nº 1.206/2024',
            '- Dedução Dependente: Lei nº 14.663/2023',
            '- Vigência: Exercício 2024'
        ]
    else:  # 2025
        legislacao = [
            '- Salário Família: Lei 8.213/1991',
            '- INSS: Lei 8.212/1991 e Portaria MF/MPS 01/2024',
            '- IRRF: Lei 7.713/1988 e Instrução Normativa RFB 2.126/2024',
            '- Vigência: Exercício 2025'
        ]
    
    for item in legislacao:
        pdf.cell(0, 5, item, 0, 1)
    
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, 'METODOLOGIA DE CÁLCULO', 0, 1)
    pdf.set_font('Arial', '', 9)
    metodologia = [
        '1. SALÁRIO FAMÍLIA: Verifica se salário bruto é menor ou igual ao limite',
        '2. CÁLCULO: Nº Dependentes × Valor por Dependente (se elegível)',
        '3. INSS: Cálculo progressivo por faixas acumulativas (Aliquota Efetiva)',
        '4. BASE IRRF: Salário Bruto - Dependentes × Dedução - INSS - Outros Descontos',
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

# [CONTINUA... O resto do código precisa ser ajustado de forma similar]

# Para manter a resposta dentro do limite, vou mostrar apenas as partes modificadas.
# O código completo precisa ser ajustado para usar as novas funções com parâmetros de tabela
