import pandas as pd
import os

# Define a pasta onde estão os arquivos de dados (assumindo a estrutura)
DATA_PATH = os.path.join(os.path.pardir, 'data')

def carregar_tabela_inss(ano: int) -> pd.DataFrame:
    """
    Carrega a tabela de INSS do ano especificado.
    """
    try:
        # Tenta carregar o arquivo CSV. O separador é o ponto e vírgula (;)
        df = pd.read_csv(os.path.join(DATA_PATH, f'tabelas_inss_{ano}.csv'), sep=';')
        return df
    except FileNotFoundError:
        raise Exception(f"Erro: O arquivo de tabelas INSS para {ano} não foi encontrado.")

def calcular_inss(salario_bruto: float, ano: int) -> float:
    """
    Calcula o valor CORRETO do INSS com base no Salário Bruto e no ano.
    Usa o cálculo progressivo por faixas.
    """
    df_inss = carregar_tabela_inss(ano)
    
    # 1. Obter o teto da contribuição para o ano
    teto_contribuicao = df_inss['limite_superior'].max()
    
    # 2. Se o salário for maior que o teto, usamos o teto como base de cálculo
    base_calculo = min(salario_bruto, teto_contribuicao)
    valor_inss = 0.0
    
    # 3. Iterar sobre as faixas para o cálculo progressivo
    for _, row in df_inss.iterrows():
        limite_inf = row['limite_inferior']
        limite_sup = row['limite_superior']
        aliquota = row['aliquota']
        
        # Verifica se a base de cálculo atinge ou ultrapassa a faixa atual
        if base_calculo > limite_inf:
            
            # A base para cálculo nesta faixa é o menor valor entre:
            # a) O Salário Bruto (limitado ao TETO)
            # b) O limite superior da faixa
            
            # Faixa completa: Se o salário está acima do limite superior desta faixa,
            # usamos a diferença entre o limite superior e o inferior.
            if base_calculo > limite_sup:
                base_faixa = limite_sup - limite_inf
            
            # Última faixa: Se o salário está dentro desta faixa,
            # usamos a diferença entre o salário e o limite inferior.
            else:
                base_faixa = base_calculo - limite_inf
                
            # Calcula e acumula o valor do INSS
            valor_inss += base_faixa * aliquota
            
            # Se já passamos do salário ou chegamos na última faixa, paramos.
            if base_calculo <= limite_sup:
                break
                
    # O valor final é arredondado para duas casas decimais
    return round(valor_inss, 2)
