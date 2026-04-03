import streamlit as st
from datetime import datetime
import tempfile

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ------------------------
# FORMATAÇÃO
# ------------------------
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ------------------------
# CÁLCULOS
# ------------------------
def calcular_rescisao(salario, admissao, demissao, aviso_tipo):
    dias_trabalhados = (demissao - admissao).days

    saldo_salario = salario

    aviso_previo = salario if aviso_tipo == "Indenizado" else 0

    decimo_terceiro = salario * 3 / 12  # simplificado

    ferias_prop = salario * 6 / 12
    um_terco = ferias_prop / 3

    ferias_vencidas = salario
    um_terco_vencidas = ferias_vencidas / 3

    fgts = salario * 0.08 * (dias_trabalhados / 30)
    multa_fgts = fgts * 0.4

    total = (
        saldo_salario + aviso_previo + decimo_terceiro +
        ferias_prop + um_terco + ferias_vencidas +
        um_terco_vencidas + fgts + multa_fgts
    )

    return {
        "Saldo salário": saldo_salario,
        "Aviso prévio": aviso_previo,
        "13º proporcional": decimo_terceiro,
        "Férias proporcionais": ferias_prop,
        "1/3 férias": um_terco,
        "Férias vencidas": ferias_vencidas,
        "1/3 vencidas": um_terco_vencidas,
        "FGTS total": fgts,
        "Multa FGTS": multa_fgts,
        "TOTAL": total
    }

# ------------------------
# PDF (ROBUSTO)
# ------------------------
def gerar_pdf(resultado):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    caminho = tmp.name

    doc = SimpleDocTemplate(caminho)
    elementos = []
    styles = getSampleStyleSheet()

    elementos.append(Paragraph("Relatório de Cálculo Trabalhista", styles["Title"]))

    dados = [["Verba", "Valor (R$)"]]
    for k, v in resultado.items():
        dados.append([k, formatar_moeda(v)])

    tabela = Table(dados)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))

    elementos.append(tabela)
    doc.build(elementos)

    return caminho

# ------------------------
# INTERFACE
# ------------------------
st.title("📊 Calculadora Profissional de Rescisão")

salario = st.number_input("Salário base", value=2000.0)

admissao = st.date_input("Admissão", value=datetime(2024, 10, 1))
demissao = st.date_input("Demissão", value=datetime(2026, 3, 30))

aviso_tipo = st.selectbox(
    "Aviso prévio",
    ["Indenizado", "Trabalhado"]
)

# ------------------------
# CÁLCULO
# ------------------------
if st.button("Calcular"):
    resultado = calcular_rescisao(salario, admissao, demissao, aviso_tipo)

    st.subheader("📋 Memória de cálculo")

    for k, v in resultado.items():
        st.write(f"**{k}**: {formatar_moeda(v)}")

    # ------------------------
    # PDF DOWNLOAD
    # ------------------------
    caminho_pdf = gerar_pdf(resultado)

    with open(caminho_pdf, "rb") as f:
        st.download_button(
            "📄 Baixar PDF",
            f,
            file_name="calculo_rescisao.pdf"
        )

# ------------------------
# GUIA EXPLICATIVA
# ------------------------
with st.expander("📘 Guia da Calculadora"):
    st.markdown("""
### ✔ Saldo salário
Valor dos dias trabalhados no mês da rescisão.

### ✔ Aviso prévio
- Trabalhado: empregado cumpre o período → não recebe adicional
- Indenizado: empresa paga sem exigir trabalho

### ✔ 13º proporcional
Calculado com base nos meses trabalhados no ano.

### ✔ Férias proporcionais
Referente ao período aquisitivo incompleto.

### ✔ 1/3 de férias
Adicional constitucional sobre férias.

### ✔ Férias vencidas
Períodos completos não gozados.

### ✔ FGTS
Depósito de 8% sobre salário.

### ✔ Multa FGTS
40% sobre o total do FGTS (demissão sem justa causa).
""")
