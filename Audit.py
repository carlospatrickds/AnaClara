import math

# =========================================================================
# I. CONSTANTES E TABELAS INTEGRADAS
# =========================================================================

# --- Tabela de Salário Família (Baseado nas imagens) ---
# Estrutura: {ano: [(limite_salario, valor_cota)]}
TABELAS_SALARIO_FAMILIA = {
    # Referência Janeiro / 2024 (Imagem 1000066428.png)
    2024: [
        (1819.26, 62.04)  # Até 1819.26, cota de R$ 62.04. Acima, é R$ 0.00
    ],
    # Referência Janeiro / 2025 (Imagem 1000066427.png)
    2025: [
        (1906.04, 65.00)  # Até 1906.04, cota de R$ 65.00. Acima, é R$ 0.00
    ],
}

# --- Tabela de INSS Progressivo (Baseado nas imagens, usando a oficial de 2024) ---
# Estrutura: {ano: [(limite_inferior, limite_superior, aliquota_percentual)]}
# Nota: A tabela de INSS deve ser progressiva (faixas).
TABELAS_INSS = {
    # Referência Janeiro / 2024 (Imagem 1000066425.png) - Progressiva
    2024: [
        (0.00, 1412.00, 0.075),
        (1412.01, 2666.68, 0.09),
        (2666.69, 4000.03, 0.12),
        (4000.04, 7786.02, 0.14),  # Teto de contribuição 2024
    ],
    # Referência Janeiro / 2025 (Imagem 1000066423.png) - *ATENÇÃO: A tabela 2025 na imagem é por deduções,
    # mas o cálculo deve ser progressivo como o de 2024. Usaremos a tabela de 2025 da imagem (1000066423.png)
    # APENAS para os limites de faixas, convertendo para cálculo progressivo*
    2025: [
        (0.00, 1518.00, 0.075),
        (1518.01, 2793.88, 0.09),
        (2793.89, 4190.83, 0.12),
        (4190.84, 8157.41, 0.14), # Teto de contribuição 2025 (8.157,41)
    ],
}
# As deduções do INSS são usadas apenas para conferência ou cálculo simplificado
DEDUCAO_INSS_2024 = [21.18, 101.18, 181.18] # Imagem 1000066425.png
DEDUCAO_INSS_2025 = [22.77, 106.59, 190.40] # Imagem 1000066423.png


# --- Tabela de IRRF (Baseado nas imagens) ---
# Estrutura: {ano: [(limite_inferior, limite_superior, aliquota_percentual, parcela_deduzir)]}
TABELAS_IRRF = {
    # Referência 2024 (Imagem 1000066419.png)
    2024: [
        (0.00, 2112.00, 0.00, 0.00),    # Isento
        (2112.01, 2826.65, 0.075, 158.40),
        (2826.66, 3751.05, 0.15, 370.40),
        (3751.06, 4664.68, 0.225, 651.73),
        (4664.69, 999999.99, 0.275, 894.96),
    ],
    # Referência Maio / 2025 (Imagem 1000066422.png)
    2025: [
        (0.00, 2428.80, 0.00, 0.00),    # Isento
        (2428.81, 2826.65, 0.075, 182.16),
        (2826.66, 3751.06, 0.15, 394.16),
        (3751.07, 4664.68, 0.225, 675.49),
        (4664.69, 999999.99, 0.275, 908.73),
    ],
}

# --- Deduções Fiscais (Baseado na imagem 1000066419.png e 1000066422.png) ---
DEDUCOES = {
    2024: {
        'DEPENDENTE': 189.59,
        'SIMPLIFICADA': 528.00,
        'TETO_INSS': 7786.02, # Usado apenas para INSS
    },
    2025: {
        'DEPENDENTE': 189.59, # Assumindo manutenção do valor (Imagem 1000066422.png)
        'SIMPLIFICADA': 528.00, # Valor a ser confirmado para 2025
        'TETO_INSS': 8157.41, # Usado apenas para INSS
    },
}

# =========================================================================
# II. FUNÇÕES DE CÁLCULO
# =========================================================================

def calcular_salario_familia(salario_bruto: float, num_filhos: int, ano: int) -> float:
    """
    Calcula o valor do Salário Família com base no Salário Bruto e número de filhos.
    """
    if ano not in TABELAS_SALARIO_FAMILIA:
        raise ValueError(f"Tabela de Salário Família para o ano {ano} não está definida.")
        
    tabela = TABELAS_SALARIO_FAMILIA[ano]
    limite_salario, valor_cota = tabela[0] # A tabela geralmente só tem uma faixa
    
    if salario_bruto <= limite_salario:
        valor_total = num_filhos * valor_cota
    else:
        valor_total = 0.0
        
    return round(valor_total, 2)


def calcular_inss(salario_bruto: float, ano: int) -> float:
    """
    Calcula o valor CORRETO do INSS com base no Salário Bruto usando o cálculo progressivo.
    """
    if ano not in TABELAS_INSS:
        raise ValueError(f"Tabela de INSS para o ano {ano} não está definida.")

    df_inss = TABELAS_INSS[ano]
    teto_contribuicao = DEDUCOES[ano]['TETO_INSS']
    
    # Se o salário for maior que o teto, usamos o teto como base de cálculo
    base_calculo = min(salario_bruto, teto_contribuicao)
    valor_inss = 0.0
    
    # 3. Iterar sobre as faixas para o cálculo progressivo
    for limite_inf, limite_sup, aliquota_pct in df_inss:
        aliquota = aliquota_pct # A alíquota já está como decimal (e.g., 0.075)
        
        if base_calculo > limite_inf:
            
            if limite_sup > teto_contribuicao: # Garante que a última faixa usa o teto real
                 limite_sup = teto_contribuicao

            # Faixa completa
            if base_calculo > limite_sup:
                base_faixa = limite_sup - limite_inf
            
            # Última faixa (onde a base de cálculo para)
            else:
                base_faixa = base_calculo - limite_inf
                
            valor_inss += base_faixa * aliquota
            
            if base_calculo <= limite_sup:
                break
                
    return round(valor_inss, 2)


def calcular_irrf(salario_bruto: float, inss_pago: float, dependentes: int, optar_simplificado: bool, ano: int) -> float:
    """
    Calcula o valor CORRETO do IRRF com base nos dados.
    """
    if ano not in TABELAS_IRRF or ano not in DEDUCOES:
        raise ValueError(f"Tabela de IRRF ou Deduções para o ano {ano} não está definida.")
        
    df_ir = TABELAS_IRRF[ano]
    deducoes_ano = DEDUCOES[ano]
    
    # 1. Base de Cálculo (BC)
    
    # Deduções Legais
    deducao_dependente_total = dependentes * deducoes_ano['DEPENDENTE']
    deducao_legal = inss_pago + deducao_dependente_total
    
    # Base de Cálculo Padrão (Salário - Deduções Legais)
    bc_padrao = salario_bruto - deducao_legal
    
    # Opção por Simplificação Mensal (se aplicável)
    if optar_simplificado:
        # A nova regra permite abater o valor simplificado
        base_calculo = salario_bruto - deducoes_ano['SIMPLIFICADA']
    else:
        base_calculo = bc_padrao
    
    # Certifica-se que a base de cálculo não é negativa
    base_calculo = max(0.0, base_calculo)

    # 2. Aplicação da Tabela Progressiva
    valor_irrf = 0.0
    
    for limite_inf, limite_sup, aliquota_pct, deducao_fixa in df_ir:
        aliquota = aliquota_pct # A alíquota já está como decimal (e.g., 0.075)
        
        # Encontra a faixa onde a BC se encaixa
        if base_calculo >= limite_inf and base_calculo <= limite_sup:
            # Cálculo = (BC * Alíquota) - Parcela a Deduzir
            valor_irrf = (base_calculo * aliquota) - deducao_fixa
            break
            
    # Certifica-se que o IRRF não é negativo
    return round(max(0.0, valor_irrf), 2)
    
