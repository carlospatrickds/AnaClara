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
# Usando valor e limite de 2023 (até dezembro), reajustado em jan/2023 e novo reajuste em mai/2023
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

# Tabela INSS 2023 (Base: Portaria Interministerial MPS/MF Nº 27/2023 - a partir de maio/2023)
TABELA_INSS_2023 = [
    {"limite": 1320.00, "aliquota": 0.075},
    {"limite": 2571.29, "aliquota": 0.09},
    {"limite": 3856.94, "aliquota": 0.12},
    {"limite": 7507.49, "aliquota": 0.14} # Teto
]

# --- Desconto Simplificado (Opcional) ---
# Periodo 01/02/2024 a 30/04/2025: 25% de 2.259,20 = 564,80
DS_MAX_FEV2024_ABR2025 = 564.80 
# Periodo 01/05/2025 em diante: 25% de 2.428,80 = 607,20
DS_MAX_MAI2025_DEZ2025 = 607.20 
# Periodo 01/05/2023 a 31/01/2024: 25% de 2.112,00 = 528,00 (Para fins de simulação/comparação)
DS_MAX_MAI2023_JAN2024 = 528.00 

# --- Tabela IRRF (01/05/2023 a 31/01/2024) ---
# Tabela de 2023 (após reajuste de isenção)
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

def criar_link_download_pdf(pdf_output, filename):
    """Cria link para download do PDF a partir de um objeto bytes (output do FPDF)."""
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
        
    b64 = base64.b64encode(pdf_output).decode('utf-8')
    
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">📄 Clique aqui para baixar o PDF</a>'
    return href

# --- FUNÇÕES DE CÁLCULO E SELEÇÃO DE TABELAS ---

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
        ds_maximo = DS_MAX_MAI2023_JAN2024 # Usando o valor de 2023
        
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
    else: # Fallback para o caso de simular 2022 em 2023 (usando 2023 como teto)
        tabela_inss = TABELA_INSS_2023
        limite_sf = SF_LIMITE_2023
        valor_sf = SF_VALOR_2023
        ano_base = f"{ano_simulado} (Simulação - Fallback 2023)"

    # Simulação IRRF (Usa a tabela IRRF do ano anterior, válida no período mais recente daquele ano)
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

# --- FUNÇÕES DE GERAÇÃO DE PDF (MANTIDAS) ---
# ... (As funções gerar_pdf_individual e gerar_pdf_auditoria_completa não foram alteradas em seu conteúdo,
# mas dependem das tabelas e dados calculados)

# Para evitar repetição excessiva, as funções de PDF serão apenas mencionadas, pois não houve alteração
# na lógica interna delas, exceto o tratamento de mais um ano base (2023).

def gerar_pdf_individual(dados, obs):
     """Gera PDF profissional para cálculo individual - Conteúdo mantido."""
     pdf = FPDF()
     pdf.add_page()
     
     # ... (Lógica FPDF) ...
     
     # Exibindo tabelas de 2023 (se aplicável)
     tabela_inss_referencia, tabela_irrf_referencia, SF_LIMITE, SF_VALOR, _, irrf_periodo_detalhado, ds_maximo = selecionar_tabelas(dados["competencia_obj"])
     # ... (Lógica FPDF) ...
     
     return pdf.output(dest='S') # Retorna como bytes

def gerar_pdf_auditoria_completa(df_resultado, uploaded_filename, total_salario_familia, total_inss, total_irrf, folha_liquida_total, obs_lote):
    """Gera PDF com o resumo da auditoria em lote - Conteúdo mantido."""
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    # ... (Lógica FPDF) ...
    return pdf.output(dest='S') # Retorna como bytes


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

        # --- NOVO: CHECKBOX DE SIMULAÇÃO ---
        simular_ano_anterior = st.checkbox(
            "Simular cálculo com tabelas do **Ano Anterior**",
            value=False,
            help=f"Ex: Se a Competência é 01/2025, simula com as tabelas de 2024. Se for 01/2024, simula com 2023."
        )

    # --- NOVO CAMPO DE OBSERVAÇÃO ---
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
            # A função gerar_pdf_individual foi ajustada para aceitar o retorno de pdf.output(dest='S')
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
    with col_lote1:
        opcao_entrada = st.radio(
            "Selecione a fonte dos dados:",
            ["📁 Upload de CSV", "🌐 Google Sheets", "✏️ Digitação Manual"],
            horizontal=True,
            key="opcao_entrada_lote"
        )
    
    with col_lote2:
        # Campo para a competência na aba de lote
        competencia_lote = st.date_input("Competência Analisada", 
                                        value=date(2025, 1, 1),
                                        format="DD/MM/YYYY", key="competencia_lote_input")

    # --- NOVO: CHECKBOX DE SIMULAÇÃO EM LOTE ---
    simular_lote_ano_anterior = st.checkbox(
        "Simular cálculo com tabelas do **Ano Anterior**",
        value=False,
        key="simular_lote_ano_anterior_checkbox",
        help=f"Ex: Se a Competência é 01/2025, simula com as tabelas de 2024. Se for 01/2024, simula com 2023."
    )
    
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

        if st.button("Carregar Google Sheets", key="carregar_sheets_lote"):
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
                    
                    # Seleciona as tabelas OFICIAIS
                    tabela_inss_aplicada, tabela_irrf_aplicada, limite_sf_aplicado, valor_sf_aplicado, ano_base, irrf_periodo, ds_maximo = selecionar_tabelas(competencia_lote)

                    # Seleciona as tabelas SIMULADAS (se a checkbox estiver marcada)
                    if simular_lote_ano_anterior:
                         t_inss_sim, t_irrf_sim, l_sf_sim, v_sf_sim, ano_base_sim, irrf_periodo_sim, ds_max_sim = selecionar_tabelas_simuladas(competencia_lote)
                    
                    resultados = []
                    for _, row in df.iterrows():
                        salario_bruto = float(row['Salario_Bruto'])
                        dependentes = int(row['Dependentes'])
                        outros_desc = float(row.get('Outros_Descontos', 0))
                        
                        # CÁLCULO OFICIAL
                        inss_oficial = calcular_inss(salario_bruto, tabela_inss_aplicada)
                        sal_familia_oficial = calcular_salario_familia(salario_bruto, dependentes, limite_sf_aplicado, valor_sf_aplicado)
                        irrf_oficial, metodo_deducao_oficial, _, _ = calcular_irrf(salario_bruto, dependentes, inss_oficial, outros_desc, tabela_irrf_aplicada, ds_maximo)
                        salario_liquido_oficial = salario_bruto + sal_familia_oficial - inss_oficial - irrf_oficial - outros_desc
                        
                        registro = {
                            'Nome': row['Nome'], 
                            'Salario_Bruto': salario_bruto, 
                            'Dependentes': dependentes, 
                            'Outros_Descontos': outros_desc, 
                            'Salario_Familia': sal_familia_oficial, 
                            'INSS': inss_oficial, 
                            'IRRF': irrf_oficial, 
                            'Salario_Liquido': salario_liquido_oficial, 
                            'Metodo_Deducao': metodo_deducao_oficial,
                            'Competencia': competencia_lote
                        }

                        # ADICIONA CÁLCULO DE SIMULAÇÃO
                        if simular_lote_ano_anterior:
                            inss_sim = calcular_inss(salario_bruto, t_inss_sim)
                            sal_familia_sim = calcular_salario_familia(salario_bruto, dependentes, l_sf_sim, v_sf_sim)
                            irrf_sim, metodo_deducao_sim, _, _ = calcular_irrf(salario_bruto, dependentes, inss_sim, outros_desc, t_irrf_sim, ds_max_sim)
                            salario_liquido_sim = salario_bruto + sal_familia_sim - inss_sim - irrf_sim - outros_desc
                            
                            registro['Salario_Familia_Sim'] = sal_familia_sim
                            registro['INSS_Sim'] = inss_sim
                            registro['IRRF_Sim'] = irrf_sim
                            registro['Salario_Liquido_Sim'] = salario_liquido_sim
                            registro['Metodo_Deducao_Sim'] = metodo_deducao_sim
                            registro['Ano_Base_Sim'] = ano_base_sim
                            registro['IRRF_Periodo_Sim'] = irrf_periodo_sim
                            
                        resultados.append(registro)
                        
                    df_resultado = pd.DataFrame(resultados)
                    st.session_state.df_resultado = df_resultado
                    st.session_state.uploaded_filename = uploaded_filename
                    st.session_state.processar_sheets = False # Reseta a flag do Sheets
                    
                    if simular_lote_ano_anterior:
                        st.success(f"🎉 Auditoria e **Simulação** concluídas! Tabelas Oficiais: INSS **{ano_base}**, Simulação: INSS **{ano_base_sim}**.")
                    else:
                        st.success(f"🎉 Auditoria concluída! Tabelas INSS: {ano_base}, IRRF: {irrf_periodo} aplicadas.")
                    st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {e}")
    
    # Exibir resultados
    if st.session_state.df_resultado is not None:
        df_resultado = st.session_state.df_resultado
        st.info(f"📊 **Dados processados de:** {st.session_state.uploaded_filename}")
        
        # ... (Lógica de Limpar Resultados) ...
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
        
        # Prepara o DataFrame para exibição (Simulação incluída)
        if 'IRRF_Sim' in df_resultado.columns:
            # Seleciona as colunas para o display (Oficial e Simulado)
            colunas_display = ['Nome', 'Salario_Bruto', 'Dependentes', 'Outros_Descontos', 
                               'Salario_Familia', 'Salario_Familia_Sim', 
                               'INSS', 'INSS_Sim', 
                               'IRRF', 'IRRF_Sim', 
                               'Salario_Liquido', 'Salario_Liquido_Sim', 
                               'Metodo_Deducao', 'Metodo_Deducao_Sim']
            
            df_display = df_display[colunas_display]
            df_display.columns = ['Nome', 'Sal. Bruto', 'Deps.', 'Outros Desc.', 
                                  'SF Of.', 'SF Sim.', 
                                  'INSS Of.', 'INSS Sim.', 
                                  'IRRF Of.', 'IRRF Sim.', 
                                  'Líq. Of.', 'Líq. Sim.', 
                                  'Ded IR Of.', 'Ded IR Sim.']
            
            colunas_monetarias_display = ['Sal. Bruto', 'Outros Desc.', 'SF Of.', 'SF Sim.', 'INSS Of.', 'INSS Sim.', 'IRRF Of.', 'IRRF Sim.', 'Líq. Of.', 'Líq. Sim.']
            for coluna in colunas_monetarias_display:
                 df_display[coluna] = df_display[coluna].apply(formatar_moeda)
            
            st.warning(f"Comparativo Ativo: Oficial (INSS {df_resultado['Competencia'].iloc[0].year}) vs. Simulado (INSS {df_resultado['Competencia'].iloc[0].year - 1})")
        else:
            colunas_monetarias = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
            for coluna in colunas_monetarias:
                df_display[coluna] = df_display[coluna].apply(formatar_moeda)
            df_display = df_display.drop(columns=['Competencia']).rename(columns={'Metodo_Deducao': 'Ded. IR'})
            st.info("Simulação de ano anterior desativada. Exibindo apenas resultados oficiais.")

        st.dataframe(df_display, use_container_width=True, hide_index=True) 
        
        st.subheader("📊 Resumo Financeiro")
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        total_salario_familia = df_resultado['Salario_Familia'].sum()
        total_inss = df_resultado['INSS'].sum()
        total_irrf = df_resultado['IRRF'].sum()
        folha_liquida_total = df_resultado['Salario_Liquido'].sum()

        with col_r1:
            st.metric("Total Salário Família (Oficial)", formatar_moeda(total_salario_familia))
            if 'Salario_Familia_Sim' in df_resultado.columns:
                sf_sim = df_resultado['Salario_Familia_Sim'].sum()
                st.metric("Total Salário Família (Simulado)", formatar_moeda(sf_sim), delta=formatar_moeda(total_salario_familia - sf_sim).replace('R$ ', ''))
        with col_r2:
            st.metric("Total INSS (Oficial)", formatar_moeda(total_inss))
            if 'INSS_Sim' in df_resultado.columns:
                inss_sim = df_resultado['INSS_Sim'].sum()
                st.metric("Total INSS (Simulado)", formatar_moeda(inss_sim), delta=formatar_moeda(total_inss - inss_sim).replace('R$ ', ''))
        with col_r3:
            st.metric("Total IRRF (Oficial)", formatar_moeda(total_irrf))
            if 'IRRF_Sim' in df_resultado.columns:
                irrf_sim = df_resultado['IRRF_Sim'].sum()
                st.metric("Total IRRF (Simulado)", formatar_moeda(irrf_sim), delta=formatar_moeda(total_irrf - irrf_sim).replace('R$ ', ''))
        with col_r4:
            st.metric("Folha Líquida Total (Oficial)", formatar_moeda(folha_liquida_total))
            if 'Salario_Liquido_Sim' in df_resultado.columns:
                liq_sim = df_resultado['Salario_Liquido_Sim'].sum()
                st.metric("Folha Líquida Total (Simulado)", formatar_moeda(liq_sim), delta=formatar_moeda(folha_liquida_total - liq_sim).replace('R$ ', ''))
        
        st.subheader("💾 Exportar Resultados")
        col_csv, col_pdf = st.columns(2)
        
        with col_csv:
            df_csv = df_resultado.copy()
            # Garante que o CSV usa vírgula como decimal para facilitar a abertura no Excel/sistemas
            colunas_monetarias_export = ['Salario_Bruto', 'Salario_Familia', 'INSS', 'IRRF', 'Outros_Descontos', 'Salario_Liquido']
            if 'IRRF_Sim' in df_resultado.columns:
                colunas_monetarias_export.extend(['Salario_Familia_Sim', 'INSS_Sim', 'IRRF_Sim', 'Salario_Liquido_Sim'])
            
            for coluna in colunas_monetarias_export:
                df_csv[coluna] = df_csv[coluna].apply(lambda x: f"{x:.2f}".replace('.', ','))
            
            csv_resultado = df_csv.to_csv(index=False, sep=';', encoding='utf-8')
            st.download_button(label="📥 Baixar CSV",data=csv_resultado,file_name=f"auditoria_folha_{get_br_datetime_now().strftime('%d%m%Y_%H%M')}.csv",mime="text/csv",help="Baixe os resultados em CSV (separador ponto e vírgula, decimal vírgula)")
        
        with col_pdf:
            if st.button("📄 Gerar PDF Completo", type="secondary", key="gerar_pdf_completo"):
                with st.spinner("Gerando relatório PDF..."):
                    try:
                        # A função gerar_pdf_auditoria_completa foi ajustada para aceitar o retorno de pdf.output(dest='S')
                        pdf_output = gerar_pdf_auditoria_completa(df_resultado, st.session_state.uploaded_filename,total_salario_familia,total_inss,total_irrf,folha_liquida_total, st.session_state.observacao_lote)
                        
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
    - **IRRF:** Selecionado pela data específica da competência (quatro períodos de vigência, incluindo o reajuste de 01/05/2023).
    - **Dedução IRRF:** O sistema compara o Desconto Legal (INSS + Ded. Dependente) com o Desconto Simplificado Opcional e aplica o que resultar no **menor imposto**.
    - **Simulação Ativa:** Se marcada, a simulação utiliza as tabelas do **ano imediatamente anterior** (Ex: Comp. 2025 -> Tabela 2024).
    """)
    
    col_info1, col_info2, col_info3 = st.columns(3)
    
    with col_info1:
        st.subheader("📋 Tabela INSS 2025")
        tabela_inss_df_2025 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1518.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1518.01) + " a " + formatar_moeda(2793.88), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2793.89) + " a " + formatar_moeda(4190.83), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4190.84) + " a " + formatar_moeda(8157.41), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2025, use_container_width=True, hide_index=True)
        st.caption(f"**Teto 2025:** {formatar_moeda(8157.41)}")
    
    with col_info2:
        st.subheader("📋 Tabela INSS 2024")
        tabela_inss_df_2024 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1412.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1412.01) + " a " + formatar_moeda(2666.68), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2666.69) + " a " + formatar_moeda(4000.03), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(4000.04) + " a " + formatar_moeda(7786.02), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2024, use_container_width=True, hide_index=True)
        st.caption(f"**Teto 2024:** {formatar_moeda(7786.02)}")

    with col_info3:
        st.subheader("📋 Tabela INSS 2023")
        tabela_inss_df_2023 = pd.DataFrame([
            {"Faixa": "1ª", "Salário de Contribuição": "Até " + formatar_moeda(1320.00), "Alíquota": "7,5%"},
            {"Faixa": "2ª", "Salário de Contribuição": formatar_moeda(1320.01) + " a " + formatar_moeda(2571.29), "Alíquota": "9,0%"},
            {"Faixa": "3ª", "Salário de Contribuição": formatar_moeda(2571.30) + " a " + formatar_moeda(3856.94), "Alíquota": "12,0%"},
            {"Faixa": "4ª", "Salário de Contribuição": formatar_moeda(3856.95) + " a " + formatar_moeda(7507.49), "Alíquota": "14,0%"}
        ])
        st.dataframe(tabela_inss_df_2023, use_container_width=True, hide_index=True)
        st.caption(f"**Teto 2023:** {formatar_moeda(7507.49)}")

    st.subheader("📈 Tabela IRRF - Vigências Específicas")
    
    st.markdown("#### **Vigência: 01/05/2025 em diante** (MP 1.294/2025)")
    tabela_irrf_df_mai2025 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2428.80), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2428.81) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(182.16)},
        # ... (Outras faixas 2025)
    ])
    st.dataframe(tabela_irrf_df_mai2025.head(2), use_container_width=True, hide_index=True)
    
    st.markdown("#### **Vigência: 01/02/2024 a 30/04/2025** (MP 1.206/2024)")
    tabela_irrf_df_fev2024 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2259.20), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2259.21) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(169.44)},
        # ... (Outras faixas 2024)
    ])
    st.dataframe(tabela_irrf_df_fev2024.head(2), use_container_width=True, hide_index=True)

    st.markdown("#### **Vigência: 01/05/2023 a 31/01/2024** (Lei nº 14.663/2023)")
    tabela_irrf_df_2023 = pd.DataFrame([
        {"Faixa": "1ª", "Base de Cálculo": "Até " + formatar_moeda(2112.00), "Alíquota": "0%", "Parcela a Deduzir": formatar_moeda(0.00)},
        {"Faixa": "2ª", "Base de Cálculo": formatar_moeda(2112.01) + " a " + formatar_moeda(2826.65), "Alíquota": "7,5%", "Parcela a Deduzir": formatar_moeda(158.40)},
        # ... (Outras faixas 2023)
    ])
    st.dataframe(tabela_irrf_df_2023.head(2), use_container_width=True, hide_index=True)

    st.subheader("📝 Legislação de Referência")
    st.write("""
    - **INSS 2023:** Portaria Interministerial MPS/MF Nº 27/2023.
    - **IRRF (Mai/2023 a Jan/2024):** Lei nº 14.663/2023.
    - **IRRF (Fev/2024 a Abr/2025):** MP Nº 1.206/2024.
    - **IRRF (Mai/2025 em diante):** MP Nº 1.294/2025.
    """)

# ----------------------------------------------------------------------

st.sidebar.header("ℹ️ Sobre")
st.sidebar.info("""
**Auditoria Folha de Pagamento**

Cálculos dinâmicos com base na **Competência** informada:
- Salário Família (2023, 2024 e 2025)
- INSS (Tabelas 2023, 2024 e 2025)
- IRRF (Tabelas multi-período)
- **Comparativo Desconto Legal vs. Desconto Simplificado** (mais benéfico)
- **NOVO:** Simulação com tabelas do ano anterior.

⚠️ Consulte um contador para validação oficial.
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
