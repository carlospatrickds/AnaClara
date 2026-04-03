    import streamlit as st
from datetime import datetime
import pandas as pd

# PDF
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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

    # AVISO PRÉVIO
    if d["tipo"] == "Pedido":
        aviso = 0
    elif d["aviso"] == "Trabalhado":
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


def classificar_verbas(resultado, tipo):
    inc = {}
    cont = {}

    for k, v in resultado.items():

        if tipo == "Sem justa causa":
            inc[k] = v

        elif tipo == "Pedido":
            if k in ["Aviso prévio", "Multa FGTS"]:
                cont[k] = v
            else:
                inc[k] = v

        elif tipo == "Justa causa":
            if k == "Saldo salário":
                inc[k] = v
            else:
                cont[k] = v

        else:
            inc[k] = v

    return inc, cont


def gerar_memoria(resultado):
    linhas = []
    for k, v in resultado.items():
        linhas.append([k, f"{v:,.2f}"])
    return linhas


def gerar_pdf(resultado, dados):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elementos = []

    elementos.append(Paragraph("LAUDO DE CÁLCULO TRABALHISTA", styles["Title"]))
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph(f"Admissão: {dados['admissao']}", styles["Normal"]))
    elementos.append(Paragraph(f"Demissão: {dados['demissao']}", styles["Normal"]))
    elementos.append(Spacer(1, 12))

    tabela = [["Verba", "Valor (R$)"]]

    for k, v in resultado.items():
        tabela.append([k, f"{v:,.2f}"])

    t = Table(tabela)
    t.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black)
    ]))

    elementos.append(t)

    doc.build(elementos)
    buffer.seek(0)
    return buffer


# =========================
# INTERFACE
# =========================

aba1, aba2 = st.tabs(["📊 Calculadora", "📘 Guia"])

with aba1:

    st.title("Calculadora Profissional de Rescisão")

    salario = st.number_input("Salário base", value=2000.0)
    variavel = st.number_input("Média variável", value=0.0)
    adicionais = st.number_input("Adicionais", value=0.0)

    admissao = st.text_input("Admissão", "01/10/2024")
    demissao = st.text_input("Demissão", "30/03/2026")

    tipo = st.selectbox("Tipo", [
        "Sem justa causa", "Pedido", "Acordo", "Justa causa"
    ])

    aviso = st.selectbox("Aviso prévio", ["Indenizado", "Trabalhado"])

    ferias_venc = st.checkbox("Férias vencidas")
    dobro = st.checkbox("Férias em dobro")

    st.subheader("FGTS por competência")
    texto_fgts = st.text_area("Formato: 01/2020 - 2000")

    if st.button("Calcular"):

        df_fgts, total_fgts = processar_fgts_texto(texto_fgts)

        dados = {
            "salario": salario,
            "variavel": variavel,
            "adicionais": adicionais,
            "admissao": admissao,
            "demissao": demissao,
            "tipo": tipo,
            "aviso": aviso,
            "ferias_venc": ferias_venc,
            "dobro": dobro,
            "fgts": total_fgts
        }

        resultado = calcular_rescisao(dados)

        st.subheader("FGTS detalhado")
        st.dataframe(df_fgts)

        st.subheader("Resultado")
        st.dataframe(pd.DataFrame(resultado.items(), columns=["Verba", "Valor"]))

        inc, cont = classificar_verbas(resultado, tipo)

        st.subheader("✔ Incontroversas")
        st.write(inc)

        st.subheader("⚠️ Controvertidas")
        st.write(cont)

        memoria = gerar_memoria(resultado)

        st.subheader("Memória de cálculo")
        st.table(memoria)

        pdf = gerar_pdf(resultado, dados)

        st.download_button("📄 Baixar PDF", pdf, file_name="laudo.pdf")


# =========================
# GUIA
# =========================

with aba2:
    st.markdown("""
### Guia básico

**Salário base**: remuneração fixa  
**Variável**: horas extras, comissões  
**Adicionais**: insalubridade, noturno  

**Aviso prévio**:
- Trabalhado → não entra como verba
- Indenizado → entra no cálculo  

**FGTS**:
- 8% por competência  
- multa: 40% ou 20%  

**Férias**:
- Proporcional: conforme meses  
- Vencidas: pode dobrar  

⚠️ Use como base técnica. Ajustes podem ser necessários conforme o processo.
""")
