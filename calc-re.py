import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar

# ------------------------------------------------------------
# CONFIGURAÇÕES INICIAIS
# ------------------------------------------------------------
st.set_page_config(page_title="Calculadora Trabalhista", layout="wide")
st.title("⚖️ Calculadora de Rescisão e FGTS")
st.markdown("---")

# ------------------------------------------------------------
# TABELAS DE INSS (vigência a partir da data informada)
# ------------------------------------------------------------
TABELAS_INSS = {
    datetime(2020, 3, 1): [
        (0, 1045.00, 0.075),
        (1045.01, 2089.60, 0.09),
        (2089.61, 3134.40, 0.12),
        (3134.41, 6101.06, 0.14),
    ],
    datetime(2021, 1, 1): [
        (0, 1100.00, 0.075),
        (1100.01, 2203.48, 0.09),
        (2203.49, 3305.22, 0.12),
        (3305.23, 6433.57, 0.14),
    ],
    datetime(2022, 1, 1): [
        (0, 1212.00, 0.075),
        (1212.01, 2427.35, 0.09),
        (2427.36, 3641.03, 0.12),
        (3641.04, 7087.22, 0.14),
    ],
    datetime(2023, 1, 1): [
        (0, 1302.00, 0.075),
        (1302.01, 2571.29, 0.09),
        (2571.30, 3856.94, 0.12),
        (3856.95, 7507.49, 0.14),
    ],
    datetime(2023, 5, 1): [
        (0, 1320.00, 0.075),
        (1320.01, 2571.29, 0.09),
        (2571.30, 3856.94, 0.12),
        (3856.95, 7507.49, 0.14),
    ],
    datetime(2024, 1, 1): [
        (0, 1412.00, 0.075),
        (1412.01, 2666.68, 0.09),
        (2666.69, 4000.03, 0.12),
        (4000.04, 7786.02, 0.14),
    ],
    datetime(2025, 1, 1): [
        (0, 1518.00, 0.075),
        (1518.01, 2793.88, 0.09),
        (2793.89, 4190.83, 0.12),
        (4190.84, 8157.41, 0.14),
    ],
    datetime(2026, 1, 1): [
        (0, 1621.00, 0.075),
        (1621.01, 2902.84, 0.09),
        (2902.85, 4354.27, 0.12),
        (4354.28, 8475.55, 0.14),
    ],
}

def get_inss_aliquotas(data_referencia):
    """Retorna a tabela de INSS vigente na data fornecida."""
    datas_ordenadas = sorted(TABELAS_INSS.keys(), reverse=True)
    for data in datas_ordenadas:
        if data_referencia >= data:
            return TABELAS_INSS[data]
    return TABELAS_INSS[datetime(2020, 3, 1)]

def calcular_inss(base, data):
    """Calcula o INSS conforme a tabela progressiva."""
    aliquotas = get_inss_aliquotas(data)
    imposto = 0.0
    for faixa in aliquotas:
        limite_inf, limite_sup, aliquota = faixa
        if base > limite_inf:
            if base > limite_sup:
                imposto += (limite_sup - limite_inf) * aliquota
            else:
                imposto += (base - limite_inf) * aliquota
                break
    return round(imposto, 2)

# ------------------------------------------------------------
# FUNÇÕES DE CÁLCULO DE RESCISÃO
# ------------------------------------------------------------
def dias_aviso_indenizado(data_admissao, data_demissao):
    """Calcula dias de aviso prévio indenizado (30 + 3 por ano completo)."""
    anos = relativedelta(data_demissao, data_admissao).years
    dias = 30 + (3 * anos)
    return min(dias, 90)  # máximo 90 dias

def data_projetada(data_demissao, dias_aviso):
    """Data fim do contrato considerando aviso indenizado."""
    return data_demissao + timedelta(days=dias_aviso)

def meses_proporcionais(data_inicio, data_fim):
    """
    Retorna quantidade de meses proporcionais (1/12 por mês com pelo menos 15 dias).
    Para 13º e férias proporcionais.
    """
    if data_inicio > data_fim:
        return 0
    # primeiro mês: se começou após o dia 15, desconsidera
    # último mês: se terminou antes do dia 15, desconsidera
    # simplificação: conta meses cheios e ajusta
    meses = (data_fim.year - data_inicio.year) * 12 + (data_fim.month - data_inicio.month)
    # dias do mês inicial
    if data_inicio.day > 15:
        meses -= 1
    # dias do mês final
    ultimo_dia_mes = calendar.monthrange(data_fim.year, data_fim.month)[1]
    if data_fim.day < 15:
        meses -= 1
    # acrescenta 1 se o período for maior que zero
    total = max(meses + 1, 0)
    return total

def calcular_ferias_proporcionais(data_admissao, data_fim_projetada, salario):
    """Férias proporcionais (aviso conta no período)."""
    # data do último aniversário de admissão
    ultimo_aniversario = datetime(data_fim_projetada.year, data_admissao.month, data_admissao.day)
    if ultimo_aniversario > data_fim_projetada:
        ultimo_aniversario = datetime(data_fim_projetada.year - 1, data_admissao.month, data_admissao.day)
    meses = meses_proporcionais(ultimo_aniversario, data_fim_projetada)
    if meses < 0:
        meses = 0
    proporcao = meses / 12
    valor = salario * proporcao
    adicional = valor / 3
    return valor, adicional

def calcular_decimo_terceiro_proporcional(data_admissao, data_fim_projetada, salario):
    """13º proporcional considerando meses trabalhados no ano."""
    # data de início do ano: max(01/01/ano, data_admissão)
    inicio_ano = datetime(data_fim_projetada.year, 1, 1)
    if data_admissao > inicio_ano:
        inicio_ano = data_admissao
    meses = meses_proporcionais(inicio_ano, data_fim_projetada)
    if meses < 0:
        meses = 0
    return (salario / 12) * meses

def calcular_fgts_acumulado(data_admissao, data_demissao, salario_mensal, aviso_dias=0):
    """
    Simula o total de FGTS depositado (8% sobre salário mensal + 13º)
    entre a admissão e a data projetada (com aviso).
    Retorna o valor total depositado.
    """
    data_fim = data_demissao + timedelta(days=aviso_dias)
    total_fgts = 0.0
    # Mês a mês
    data_corrente = datetime(data_admissao.year, data_admissao.month, 1)
    data_fim_mes = datetime(data_fim.year, data_fim.month, 1)
    while data_corrente <= data_fim_mes:
        # depósito mensal
        total_fgts += salario_mensal * 0.08
        # 13º do ano corrente? Depósito apenas em dezembro de cada ano completo ou proporcional na rescisão
        # Para simplicidade, na rescisão o FGTS do 13º é pago junto. Vamos considerar que o 13º proporcional é depositado na rescisão.
        # Mas para evitar duplicidade, faremos uma lógica separada: incluímos 13º apenas no mês de dezembro de cada ano
        # se o funcionário ainda estiver ativo naquele dezembro.
        # Vamos pular essa complexidade e usar a mesma lógica da aba FGTS.
        data_corrente += relativedelta(months=1)
    # Adicionar 13º proporcional na rescisão
    decimo = calcular_decimo_terceiro_proporcional(data_admissao, data_fim, salario_mensal)
    total_fgts += decimo * 0.08
    return total_fgts

# ------------------------------------------------------------
# INTERFACE PRINCIPAL (ABAS)
# ------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Calculadora de Rescisão", "📚 Guia Trabalhista", "💰 Calculadora de FGTS"])

# -------------------- ABA 1: RESCISÃO --------------------
with tab1:
    st.subheader("Dados do Contrato e Rescisão")
    col1, col2 = st.columns(2)
    with col1:
        data_adm = st.date_input("Data de Admissão", datetime(2021, 3, 15))
        data_dem = st.date_input("Data de Desligamento", datetime(2024, 10, 20))
        salario = st.number_input("Salário Bruto Mensal (R$)", min_value=0.0, value=3000.0, step=100.0, format="%.2f")
        motivo = st.selectbox("Motivo da Rescisão", ["Sem justa causa", "Pedido de demissão", "Acordo (Lei 13.467/2017)"])
    with col2:
        tipo_aviso = st.radio("Aviso Prévio", ["Indenizado (não trabalhado)", "Trabalhado", "Dispensado"])
        ferias_vencidas = st.number_input("Períodos de férias vencidas (não gozadas)", min_value=0, value=1, step=1)
        faltas = st.number_input("Dias de falta injustificada (desconto)", min_value=0, value=0, step=1)

    calcular = st.button("Calcular Rescisão", type="primary")

    if calcular:
        if data_adm >= data_dem:
            st.error("Data de desligamento deve ser posterior à data de admissão.")
        else:
            # 1. Saldo de salário
            dias_no_mes = calendar.monthrange(data_dem.year, data_dem.month)[1]
            saldo_salario = (salario / dias_no_mes) * (data_dem.day - faltas)
            if saldo_salario < 0:
                saldo_salario = 0

            # 2. Aviso prévio
            if tipo_aviso == "Indenizado (não trabalhado)":
                dias_aviso = dias_aviso_indenizado(data_adm, data_dem)
                valor_aviso = (salario / 30) * dias_aviso
                aviso_dias = dias_aviso
            elif tipo_aviso == "Trabalhado":
                dias_aviso = 30  # padrão, mas não pago indenizado
                valor_aviso = 0.0
                aviso_dias = 30  # conta como tempo de serviço
            else:  # dispensado
                dias_aviso = 0
                valor_aviso = 0.0
                aviso_dias = 0

            # Data projetada para 13º e férias proporcionais
            if tipo_aviso == "Indenizado (não trabalhado)":
                data_proj = data_projetada(data_dem, dias_aviso)
            else:
                data_proj = data_dem  # aviso trabalhado ou dispensado não estende o contrato

            # 3. 13º proporcional
            decimo_terceiro = calcular_decimo_terceiro_proporcional(data_adm, data_proj, salario)

            # 4. Férias vencidas
            valor_ferias_vencidas = ferias_vencidas * (salario + salario/3)

            # 5. Férias proporcionais
            ferias_prop, adicional_prop = calcular_ferias_proporcionais(data_adm, data_proj, salario)
            valor_ferias_prop = ferias_prop + adicional_prop

            # 6. FGTS e multa (apenas para sem justa causa ou acordo)
            if motivo == "Sem justa causa":
                fgts_total = calcular_fgts_acumulado(data_adm, data_dem, salario, aviso_dias)
                multa_fgts = fgts_total * 0.40
                if motivo == "Acordo (Lei 13.467/2017)":
                    multa_fgts = fgts_total * 0.20
            elif motivo == "Acordo (Lei 13.467/2017)":
                fgts_total = calcular_fgts_acumulado(data_adm, data_dem, salario, aviso_dias)
                multa_fgts = fgts_total * 0.20
            else:
                fgts_total = 0.0
                multa_fgts = 0.0

            # 7. Base para INSS e desconto
            base_inss = saldo_salario + valor_aviso + decimo_terceiro
            # férias (vencidas e proporcionais) não entram no INSS
            inss = calcular_inss(base_inss, data_dem)

            # 8. Total bruto e líquido (IRRF simplificado - apenas informativo)
            total_bruto = saldo_salario + valor_aviso + decimo_terceiro + valor_ferias_vencidas + valor_ferias_prop + multa_fgts
            total_descontos = inss
            # Aviso prévio trabalhado não tem verba, mas se o empregado pediu demissão e não cumpriu, há desconto.
            # Vamos ignorar essa complexidade por enquanto.
            liquido = total_bruto - total_descontos

            # Exibir resultados
            st.subheader("Verbas Rescisórias")
            resultados = {
                "Saldo de salário": saldo_salario,
                "Aviso prévio indenizado" if tipo_aviso == "Indenizado (não trabalhado)" else "Aviso prévio (trabalhado/dispensado)": valor_aviso,
                "13º salário proporcional": decimo_terceiro,
                "Férias vencidas": valor_ferias_vencidas,
                "Férias proporcionais + 1/3": valor_ferias_prop,
                "Multa 40% FGTS" if motivo == "Sem justa causa" else "Multa 20% FGTS (acordo)": multa_fgts,
            }
            if motivo == "Pedido de demissão":
                resultados.pop("Multa 40% FGTS" if "Multa" in list(resultados.keys())[-1] else "Multa 20% FGTS (acordo)", None)

            df_verbas = pd.DataFrame(list(resultados.items()), columns=["Verba", "Valor (R$)"])
            df_verbas["Valor (R$)"] = df_verbas["Valor (R$)"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(df_verbas, use_container_width=True)

            st.subheader("Descontos")
            descontos = {"INSS (sobre verbas salariais)": inss}
            df_desc = pd.DataFrame(list(descontos.items()), columns=["Desconto", "Valor (R$)"])
            df_desc["Valor (R$)"] = df_desc["Valor (R$)"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(df_desc, use_container_width=True)

            st.subheader("Resumo Final")
            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("Total Bruto", f"R$ {total_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col_res2.metric("Total Descontos", f"R$ {total_descontos:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col_res3.metric("Valor Líquido a Receber", f"R$ {liquido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            st.info("⚠️ O IRRF não foi calculado automaticamente. Consulte um contador para verificar a necessidade de retenção.")

# -------------------- ABA 2: GUIA TRABALHISTA --------------------
with tab2:
    st.header("📖 Guia Trabalhista – Como Calcular Rescisão")
    st.markdown("""
    ### 1. Informações essenciais
    - Data de admissão e data de desligamento
    - Último salário bruto
    - Motivo da rescisão (sem justa causa, pedido, acordo)
    - Tipo de aviso prévio (indenizado, trabalhado, dispensado)
    - Saldo de férias vencidas e período aquisitivo

    ### 2. Verbas devidas por tipo de rescisão

    **Dispensa sem justa causa** (mais comum):
    - **Saldo de salário**: (salário ÷ 30) × dias trabalhados no mês
    - **Aviso prévio indenizado**: 30 dias + 3 dias por ano trabalhado (máx. 90 dias)
    - **13º salário proporcional**: (salário ÷ 12) × meses trabalhados no ano (inclui aviso indenizado)
    - **Férias vencidas**: salário + 1/3
    - **Férias proporcionais**: (salário ÷ 12) × meses do período aquisitivo + 1/3
    - **Multa de 40% sobre o FGTS** (total depositado durante o contrato)

    **Pedido de demissão**:
    - Mesmas verbas (exceto aviso indenizado e multa do FGTS)

    **Acordo (Lei 13.467/2017)**:
    - Metade do aviso prévio indenizado e metade da multa do FGTS (20%)

    ### 3. Descontos obrigatórios
    - **INSS** sobre: saldo de salário, aviso prévio indenizado, 13º proporcional (férias indenizadas **não** entram)
    - **IRRF** se ultrapassar a faixa de isenção (tabela progressiva)

    ### 4. Exemplo prático
    Admissão: 15/03/2021 | Demissão: 20/10/2024 | Salário R$ 3.000
    - Saldo salário: R$ 2.000 (20 dias)
    - Aviso indenizado: 39 dias → R$ 3.900
    - 13º proporcional (11 meses) → R$ 2.750
    - Férias vencidas (1 período) → R$ 4.000
    - Férias proporcionais (8/12 + 1/3) → R$ 2.666,67
    - Multa 40% FGTS sobre total depositado

    O valor líquido é obtido após o desconto do INSS (conforme tabela vigente).
    """)

# -------------------- ABA 3: CALCULADORA DE FGTS --------------------
with tab3:
    st.subheader("Simulação de FGTS Mensal")
    col_fgts1, col_fgts2 = st.columns(2)
    with col_fgts1:
        data_adm_fgts = st.date_input("Data de Admissão (FGTS)", datetime(2021, 3, 15), key="adm_fgts")
    with col_fgts2:
        data_dem_fgts = st.date_input("Data de Desligamento (FGTS)", datetime(2024, 10, 20), key="dem_fgts")

    if st.button("Gerar Competências", key="gerar_fgts"):
        if data_adm_fgts >= data_dem_fgts:
            st.error("Data de admissão deve ser anterior ao desligamento.")
        else:
            # Gerar lista de meses entre admissão e demissão (incluindo ambos)
            start = datetime(data_adm_fgts.year, data_adm_fgts.month, 1)
            end = datetime(data_dem_fgts.year, data_dem_fgts.month, 1)
            meses = []
            current = start
            while current <= end:
                meses.append(current)
                current += relativedelta(months=1)

            # Criar DataFrame com competências e salários (inicialmente iguais ao último salário informado)
            # Para simplificar, pediremos um salário base e permitiremos edição
            salario_base = st.number_input("Salário mensal padrão (R$)", min_value=0.0, value=3000.0, step=100.0, key="salario_fgts")

            df_fgts = pd.DataFrame({
                "Competência": [m.strftime("%m/%Y") for m in meses],
                "Remuneração (R$)": [salario_base] * len(meses)
            })
            st.write("Edite os valores de remuneração conforme necessário:")
            df_editado = st.data_editor(df_fgts, use_container_width=True, num_rows="dynamic")

            if st.button("Calcular FGTS", key="calc_fgts"):
                total_fgts = 0.0
                for _, row in df_editado.iterrows():
                    remun = row["Remuneração (R$)"]
                    total_fgts += remun * 0.08
                # Adicionar 13º salário (um salário por ano completo ou proporcional na rescisão)
                # Simples: adiciona 8% sobre o 13º proporcional no último ano
                ultimo_mes = datetime(data_dem_fgts.year, data_dem_fgts.month, 1)
                decimo = calcular_decimo_terceiro_proporcional(data_adm_fgts, data_dem_fgts, salario_base)
                total_fgts += decimo * 0.08

                st.success(f"Total depositado (FGTS mensal + 13º): **R$ {total_fgts:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))
                st.info("Multa de 40% (demissão sem justa causa) seria: "
                        f"R$ {total_fgts * 0.40:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.caption("Observação: o valor do 13º foi calculado proporcionalmente até a data de desligamento, conforme legislação.")
