import streamlit as st
from datetime import datetime
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# =========================
# FUNÇÕES
# =========================

def meses_trabalhados(inicio, fim):
    meses = (fim.year - inicio.year) * 12 + (fim.month - inicio.month)
    if fim.day >= 15:
        meses += 1
    return meses


def processar_fgts_texto(texto):
    linhas = texto.strip().split("\n")
    dados = []
    total = 0

    for linha in linhas:
        if "-" in linha:
            try:
                comp, valor = linha.split("-")
                valor = float(valor.strip().replace(",", "."))
                fgts = valor * 0.08

                total += fgts

                dados.append({
                    "Competência": comp.strip(),
                    "Remuneração": valor,
                    "FGTS": fgts
                })
            except:
                continue

    return pd.DataFrame(dados), total


def calcular_rescisao(d):
    adm = datetime.strptime(d["admissao"], "%d/%m/%Y")
    dem = datetime.strptime(d["demissao"], "%d/%m/%Y")

    meses = meses_trabalhados(adm, dem)

    base = d["salario"] + d["variavel"] + d["adicionais"]

    saldo = base / 30 * dem.day

    anos = dem.year - adm.year
    aviso_dias = min(30 + anos * 3, 90)

    if d["tipo"] == "Pedido":
        aviso = 0
    elif d["tipo"] == "Acordo":
        aviso = (base / 30 * aviso_dias) / 2
    else:
        aviso = base / 30 * aviso_dias

    meses_ano = meses_trabalhados(datetime(dem.year, 1, 1), dem)
    decimo = base * (meses_ano / 12)

    ferias_prop = base * ((meses % 12) / 12)
    terco = ferias_prop / 3

    if d["ferias_venc"]:
        ferias_venc = base * (2 if d["dobro"] else 1)
    else:
        ferias_venc = 0

    terco_venc = ferias_venc / 3

    multa = 0
    if d["tipo"] == "Sem justa causa":
        multa = d["fgts"] * 0.4
    elif d["tipo"] == "Acordo":
        multa = d["fgts"] * 0.2

    total = sum([
        saldo, aviso, decimo,
        ferias_prop, terco,
        ferias_venc, terco_venc,
        multa
    ])

    return {
        "Base de cálculo": base,
        "Saldo salário": saldo,
        "Aviso prévio": aviso,
        "13º proporcional": decimo,
        "Férias proporcionais": ferias_prop,
        "1/3 férias": terco,
        "Férias vencidas": ferias_venc,
        "1/3 vencidas": terco_venc,
        "FGTS total": d["fgts"],
        "Multa FGTS": multa,
        "TOTAL": total
    }


def gerar_pdf(resultado):
    caminho = "/mnt/data/rescisao.pdf"
    doc = SimpleDocTemplate(caminho)
    styles = getSampleStyleSheet()

    elementos = []
    elementos.append(Paragraph("Relatório de Rescisão Trabalhista", styles["Title"]))
    elementos.append(Spacer(1, 12))

    for k, v in resultado.items():
        elementos.append(Paragraph(f"{k}: R$ {v:,.2f}", styles["Normal"]))

    doc.build(elementos)
    return caminho


# =========================
# INTERFACE
# =========================

st.title("📊 Calculadora Profissional de Rescisão")

salario = st.number_input("Salário base", 0.0, value=3000.0)
variavel = st.number_input("Média variável", 0.0, value=0.0)
adicionais = st.number_input("Adicionais", 0.0, value=0.0)

admissao = st.text_input("Admissão", "01/01/2020")
demissao = st.text_input("Demissão", "20/07/2024")

tipo = st.selectbox("Tipo", [
    "Sem justa causa",
    "Pedido",
    "Acordo",
    "Justa causa"
])

ferias_venc = st.checkbox("Férias vencidas")
dobro = st.checkbox("Férias em dobro")

# FGTS manual
st.subheader("FGTS por competência")
texto_fgts = st.text_area(
    "Cole no formato: 01/2020 - 2000",
    height=150
)

# =========================
# EXECUÇÃO
# =========================

if st.button("Calcular"):

    df_fgts, total_fgts = processar_fgts_texto(texto_fgts)

    dados = {
        "salario": salario,
        "variavel": variavel,
        "adicionais": adicionais,
        "admissao": admissao,
        "demissao": demissao,
        "tipo": tipo,
        "ferias_venc": ferias_venc,
        "dobro": dobro,
        "fgts": total_fgts
    }

    resultado = calcular_rescisao(dados)

    st.subheader("FGTS detalhado")
    st.dataframe(df_fgts)

    st.subheader("Resultado")
    df = pd.DataFrame(resultado.items(), columns=["Verba", "Valor"])
    st.dataframe(df)

    caminho = gerar_pdf(resultado)

    with open(caminho, "rb") as f:
        st.download_button("📄 Baixar PDF", f, file_name="rescisao.pdf")
