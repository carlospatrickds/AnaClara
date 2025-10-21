import streamlit as st
import pandas as pd
import locale
from datetime import datetime

# Configura moeda brasileira
def moeda(valor):
    try:
        return locale.currency(valor, grouping=True, symbol=True)
    except:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------- Função de Cálculo ---------------- #
def calc_values():
    salario_base = float(st.session_state.salario_base)
    divisor_jornada = float(st.session_state.divisor_jornada)
    salario_minimo = float(st.session_state.salario_minimo)
    grau_pct = st.session_state.grau_pct
    periculosidade = st.session_state.periculosidade

    horas_noturnas = st.session_state.horas_noturnas
    percentual_noturno = st.session_state.percentual_noturno

    horas_extra_50 = st.session_state.horas_extra_50
    horas_extra_100 = st.session_state.horas_extra_100
    horas_extra_custom = st.session_state.horas_extra_custom
    percentual_extra_custom = st.session_state.percentual_extra_custom

    # cálculos
    hora_base = salario_base / divisor_jornada
    perc = salario_base * 0.3 if periculosidade else 0
    insal = max(salario_base, salario_minimo) * (grau_pct / 100)

    adicional_noturno = horas_noturnas * hora_base * (percentual_noturno / 100)
    extra_50 = horas_extra_50 * hora_base * 0.5
    extra_100 = horas_extra_100 * hora_base * 1.0
    extra_custom = horas_extra_custom * hora_base * (percentual_extra_custom / 100)

    total_adicionais = perc + insal + adicional_noturno + extra_50 + extra_100 + extra_custom
    salario_bruto = salario_base + total_adicionais

    return {
        "Salário Base (R$)": salario_base,
        "Hora base (R$)": hora_base,
        "Periculosidade (R$)": perc,
        "Insalubridade (R$)": insal,
        "Adicional Noturno (R$)": adicional_noturno,
        "Horas Extra 50% (Adicional) (R$)": extra_50,
        "Horas Extra 100% (Adicional) (R$)": extra_100,
        "Horas Extra Custom (Adicional) (R$)": extra_custom,
        "Total Adicionais (R$)": total_adicionais,
        "Salário Bruto Estimado (R$)": salario_bruto
    }

# ---------------- Configuração da Página ---------------- #
st.set_page_config("Cálculo Fácil", layout="wide")

# ---------------- Abas Principais ---------------- #
aba_tutorial, aba_calculadora = st.tabs(["📘 Tutorial", "💼 Calculadora"])

# ---------------- Conteúdo da Aba Tutorial ---------------- #
with aba_tutorial:
    st.title("📘 Tutorial - Como usar a Calculadora")
    st.markdown("""
    ### Bem-vindo ao tutorial da Calculadora de Vantagens e Adicionais!
    
    Esta ferramenta foi desenvolvida para ajudar no cálculo do salário bruto de um funcionário, considerando diversos adicionais previstos na legislação trabalhista brasileira.
    
    #### Passo a Passo:
    
    1. **Acesse a aba "Calculadora"**: Lá você encontrará todos os campos para preenchimento.
    
    2. **Preencha os dados básicos**:
        - **Salário Base (R$)**: Informe o salário base do funcionário.
        - **Divisor de Jornada**: Normalmente 220 (para 220 horas mensais). Pode variar conforme a jornada.
        - **Salário Mínimo (R$)**: Informe o valor atual do salário mínimo (usado para cálculo da insalubridade).
    
    3. **Selecione os adicionais**:
        - **Periculosidade**: Marque se o funcionário tem direito a este adicional (30% sobre o salário base).
        - **Grau de Insalubridade**: Escolha entre 0%, 10%, 20% ou 40%. O cálculo é feito sobre o maior valor entre o salário base e o salário mínimo.
    
    4. **Informe as horas noturnas**:
        - **Horas Noturnas**: Quantidade de horas trabalhadas no período noturno.
        - **Percentual Adicional Noturno**: Normalmente 20% (padrão), mas pode ser ajustado.
    
    5. **Informe as horas extras**:
        - **Horas Extra 50%**: Horas extras com adicional de 50%.
        - **Horas Extra 100%**: Horas extras com adicional de 100% (ex: feriados).
        - **Horas Extra Personalizadas**: Para percentuais diferentes, informe a quantidade e o percentual.
    
    6. **Clique em "Calcular"**: O sistema irá processar e exibir os resultados em duas abas:
        - **Resumo**: Visão geral com métricas principais e tabela detalhada. Você também pode exportar os dados em CSV.
        - **Detalhamento passo a passo**: Explicação de como cada valor foi calculado.
    
    #### Observações:
    - O cálculo da hora base é feito dividindo o salário base pelo divisor de jornada.
    - O adicional noturno é calculado sobre a hora base, multiplicando pelas horas noturnas e pelo percentual.
    - As horas extras são calculadas sobre a hora base, multiplicando pelo percentual adicional (50%, 100% ou personalizado).
    - O total de adicionais é a soma de periculosidade, insalubridade, adicional noturno e horas extras.
    - O salário bruto é a soma do salário base com o total de adicionais.
    
    #### Dúvidas?
    Consulte a legislação trabalhista ou um especialista em cálculos trabalhistas para casos específicos.
    """)

# ---------------- Conteúdo da Aba Calculadora ---------------- #
with aba_calculadora:
    st.title("💼 Cálculo Fácil - Vantagens e Adicionais")

    with st.sidebar:
        st.header("⚙️ Parâmetros de Entrada")

        st.number_input("Salário Base (R$)", min_value=0.0, step=100.0, key="salario_base")
        st.number_input("Divisor de Jornada", min_value=1, value=220, step=1, key="divisor_jornada")
        st.number_input("Salário Mínimo (R$)", min_value=0.0, step=10.0, key="salario_minimo")

        st.checkbox("Periculosidade (30%)", key="periculosidade")
        st.selectbox("Grau de Insalubridade", [0, 10, 20, 40], index=1, key="grau_pct")

        st.divider()
        st.number_input("Horas Noturnas", min_value=0.0, step=0.5, key="horas_noturnas")
        st.slider("Percentual Adicional Noturno (%)", 0, 50, 20, key="percentual_noturno")

        st.divider()
        st.number_input("Horas Extra 50%", min_value=0.0, step=0.5, key="horas_extra_50")
        st.number_input("Horas Extra 100%", min_value=0.0, step=0.5, key="horas_extra_100")
        st.number_input("Horas Extra Personalizadas", min_value=0.0, step=0.5, key="horas_extra_custom")
        st.slider("Percentual Extra Personalizado (%)", 0, 200, 70, key="percentual_extra_custom")

        calc_clicked = st.button("Calcular 💰")

    # ---------------- Resultados ---------------- #
    if calc_clicked:
        with st.spinner("Calculando…"):
            result = calc_values()

        if result:
            st.success("✅ Cálculo completo")

            tab1, tab2 = st.tabs(["📊 Resumo", "🧮 Detalhamento passo a passo"])

            # --- Aba 1: Resumo --- #
            with tab1:
                col1, col2, col3 = st.columns(3)
                col1.metric("Salário Base (R$)", moeda(result['Salário Base (R$)']))
                col2.metric("Total Adicionais (R$)", moeda(result['Total Adicionais (R$)']))
                col3.metric("Salário Bruto Estimado (R$)", moeda(result['Salário Bruto Estimado (R$)']))

                st.markdown("---")
                st.subheader("📋 Detalhamento dos valores")

                df = pd.DataFrame(result.items(), columns=["Descrição", "Valor (R$)"])
                df["Valor (R$)"] = df["Valor (R$)"].apply(moeda)
                st.table(df)

                csv = pd.DataFrame(result.items(), columns=["Descrição", "Valor"]).to_csv(
                    index=False, sep=";", encoding="utf-8"
                )
                st.download_button(
                    "💾 Exportar detalhamento (CSV)",
                    csv.encode("utf-8"),
                    file_name=f"detalhamento_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )

            # --- Aba 2: Detalhamento --- #
            with tab2:
                st.subheader("🧮 Como cada valor foi obtido")

                def render_card(title, formula, result_txt):
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #f9fafb;
                            border-left: 6px solid #10b981;
                            padding: 14px 18px;
                            border-radius: 8px;
                            margin-bottom: 12px;
                            font-size: 1rem;
                            line-height: 1.6;
                        ">
                            <b>{title}</b><br>
                            <span style="color:#374151;">{formula}</span><br>
                            <span style="color:#111827; font-weight:600;">➡ {result_txt}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # Cards de detalhamento
                salario_base = st.session_state.salario_base
                divisor_jornada = st.session_state.divisor_jornada
                salario_minimo = st.session_state.salario_minimo
                grau_pct = st.session_state.grau_pct
                horas_noturnas = st.session_state.horas_noturnas
                percentual_noturno = st.session_state.percentual_noturno
                horas_extra_50 = st.session_state.horas_extra_50
                horas_extra_100 = st.session_state.horas_extra_100
                horas_extra_custom = st.session_state.horas_extra_custom
                percentual_extra_custom = st.session_state.percentual_extra_custom

                render_card(
                    "Hora Base",
                    f"{moeda(salario_base)} ÷ {divisor_jornada} = {moeda(result['Hora base (R$)'])}",
                    moeda(result['Hora base (R$)'])
                )

                render_card(
                    "Periculosidade (30% do Salário Base, se marcado)",
                    f"30% × {moeda(salario_base)}",
                    moeda(result['Periculosidade (R$)'])
                )

                render_card(
                    f"Insalubridade ({grau_pct}% do maior entre Salário Base e Salário Mínimo)",
                    f"{grau_pct}% × {moeda(max(salario_base, salario_minimo))}",
                    moeda(result['Insalubridade (R$)'])
                )

                render_card(
                    f"Adicional Noturno ({percentual_noturno:.0f}%)",
                    f"{horas_noturnas:.2f} h × {moeda(result['Hora base (R$)'])} × {percentual_noturno:.0f}%",
                    moeda(result['Adicional Noturno (R$)'])
                )

                render_card(
                    "Horas Extra 50%",
                    f"{horas_extra_50:.2f} h × {moeda(result['Hora base (R$)'])} × 50%",
                    moeda(result['Horas Extra 50% (Adicional) (R$)'])
                )

                render_card(
                    "Horas Extra 100%",
                    f"{horas_extra_100:.2f} h × {moeda(result['Hora base (R$)'])} × 100%",
                    moeda(result['Horas Extra 100% (Adicional) (R$)'])
                )

                render_card(
                    f"Horas Extra Personalizadas ({percentual_extra_custom:.0f}%)",
                    f"{horas_extra_custom:.2f} h × {moeda(result['Hora base (R$)'])} × {percentual_extra_custom:.0f}%",
                    moeda(result['Horas Extra Custom (Adicional) (R$)'])
                )

                st.markdown("---")
                render_card(
                    "💰 Total de Adicionais",
                    "Soma de todos os adicionais",
                    moeda(result['Total Adicionais (R$)'])
                )
                render_card(
                    "💵 Salário Bruto Estimado",
                    "Salário Base + Total de Adicionais",
                    moeda(result['Salário Bruto Estimado (R$)'])
                )
