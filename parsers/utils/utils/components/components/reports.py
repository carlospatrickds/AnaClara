import pandas as pd
from datetime import datetime
from utils.period_analyzer import PeriodAnalyzer
from utils.date_calculator import DateCalculator

class ReportGenerator:
    """Gerador de relatórios completos para análise CNIS"""
    
    def __init__(self):
        self.analyzer = PeriodAnalyzer()
        self.date_calc = DateCalculator()
    
    def generate_full_report(self, df_vinculos, overlaps):
        """Gera relatório completo de análise"""
        
        # Análise de densidade de contribuição
        density_analysis = self.analyzer.analyze_contribution_density(df_vinculos)
        
        # Calcular tempo total de contribuição
        years, months, days, merged_periods = self.analyzer.calculate_total_contribution_time(df_vinculos)
        
        # Estatísticas gerais
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo']
        df_benefits = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'beneficio']
        
        # Resumo executivo
        resumo = {
            'Total de Vínculos': len(df_work),
            'Total de Benefícios': len(df_benefits),
            'Primeira Contribuição': density_analysis.get('first_contribution', 'N/A'),
            'Última Contribuição': density_analysis.get('last_contribution', 'N/A'),
            'Tempo Total Contributivo': f"{years}a {months}m {days}d",
            'Densidade de Contribuição': f"{density_analysis.get('density_percentage', 0):.1f}%",
            'Sobreposições Detectadas': len(overlaps),
            'Empresas Diferentes': df_work['empresa'].nunique() if not df_work.empty else 0
        }
        
        # Detalhamento dos vínculos
        vinculos_detalhados = self._create_detailed_vinculos_table(df_vinculos)
        
        # Análise de remunerações
        remuneracoes_analysis = self._analyze_remuneracoes(df_vinculos)
        
        return {
            'resumo': resumo,
            'vinculos_detalhados': vinculos_detalhados,
            'sobreposicoes': overlaps,
            'density_analysis': density_analysis,
            'remuneracoes_analysis': remuneracoes_analysis,
            'merged_periods': merged_periods
        }
    
    def _create_detailed_vinculos_table(self, df_vinculos):
        """Cria tabela detalhada dos vínculos para relatório"""
        
        columns_mapping = {
            'seq': 'Sequência',
            'empresa': 'Empresa',
            'cnpj': 'CNPJ',
            'data_inicio': 'Data Início',
            'data_fim': 'Data Fim',
            'tipo': 'Tipo',
            'periodo_anos': 'Anos',
            'periodo_meses': 'Meses',
            'periodo_dias': 'Dias',
            'categoria': 'Categoria'
        }
        
        # Selecionar e renomear colunas
        df_report = df_vinculos.copy()
        
        # Formatar datas
        for col in ['data_inicio', 'data_fim', 'data_fim_calculada']:
            if col in df_report.columns:
                df_report[col] = df_report[col].apply(
                    lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else 'N/A'
                )
        
        # Usar data_fim_calculada se data_fim não estiver disponível
        if 'data_fim_calculada' in df_report.columns:
            df_report['data_fim'] = df_report['data_fim'].fillna(df_report['data_fim_calculada'])
        
        # Selecionar colunas existentes
        available_columns = [col for col in columns_mapping.keys() if col in df_report.columns]
        df_final = df_report[available_columns].copy()
        
        # Renomear colunas
        df_final.rename(columns={k: v for k, v in columns_mapping.items() if k in available_columns}, inplace=True)
        
        return df_final
    
    def _analyze_remuneracoes(self, df_vinculos):
        """Analisa remunerações dos vínculos"""
        analysis = {
            'total_remuneracoes': 0,
            'valor_total': 0.0,
            'maior_remuneracao': 0.0,
            'menor_remuneracao': float('inf'),
            'remuneracao_media': 0.0,
            'vinculos_com_remuneracao': 0
        }
        
        all_remuneracoes = []
        
        for _, vinculo in df_vinculos.iterrows():
            if 'remuneracoes' in vinculo and vinculo['remuneracoes']:
                analysis['vinculos_com_remuneracao'] += 1
                
                for rem in vinculo['remuneracoes']:
                    if 'valor' in rem and rem['valor'] > 0:
                        valor = rem['valor']
                        all_remuneracoes.append(valor)
                        
                        analysis['total_remuneracoes'] += 1
                        analysis['valor_total'] += valor
                        analysis['maior_remuneracao'] = max(analysis['maior_remuneracao'], valor)
                        analysis['menor_remuneracao'] = min(analysis['menor_remuneracao'], valor)
        
        # Calcular média
        if analysis['total_remuneracoes'] > 0:
            analysis['remuneracao_media'] = analysis['valor_total'] / analysis['total_remuneracoes']
        
        # Tratar caso onde não há remunerações
        if analysis['menor_remuneracao'] == float('inf'):
            analysis['menor_remuneracao'] = 0.0
        
        # Adicionar análise temporal das remunerações
        if all_remuneracoes:
            analysis['evolucao_remuneracoes'] = self._analyze_remuneration_evolution(df_vinculos)
        
        return analysis
    
    def _analyze_remuneration_evolution(self, df_vinculos):
        """Analisa evolução das remunerações ao longo do tempo"""
        temporal_data = []
        
        for _, vinculo in df_vinculos.iterrows():
            if 'remuneracoes' in vinculo and vinculo['remuneracoes']:
                for rem in vinculo['remuneracoes']:
                    if 'competencia' in rem and 'valor' in rem:
                        try:
                            # Parse da competência MM/YYYY
                            mes, ano = rem['competencia'].split('/')
                            data = datetime(int(ano), int(mes), 1)
                            
                            temporal_data.append({
                                'data': data,
                                'valor': rem['valor'],
                                'competencia': rem['competencia'],
                                'vinculo_seq': vinculo['seq']
                            })
                        except:
                            continue
        
        # Ordenar por data
        temporal_data.sort(key=lambda x: x['data'])
        
        if len(temporal_data) < 2:
            return {'tendencia': 'Dados insuficientes'}
        
        # Calcular tendência simples
        primeiro_valor = temporal_data[0]['valor']
        ultimo_valor = temporal_data[-1]['valor']
        
        if ultimo_valor > primeiro_valor:
            tendencia = 'Crescente'
        elif ultimo_valor < primeiro_valor:
            tendencia = 'Decrescente'
        else:
            tendencia = 'Estável'
        
        return {
            'tendencia': tendencia,
            'primeira_remuneracao': primeiro_valor,
            'ultima_remuneracao': ultimo_valor,
            'variacao_percentual': ((ultimo_valor - primeiro_valor) / primeiro_valor * 100) if primeiro_valor > 0 else 0,
            'total_competencias': len(temporal_data)
        }
    
    def generate_summary_text(self, df_vinculos, overlaps):
        """Gera texto resumo da análise"""
        report_data = self.generate_full_report(df_vinculos, overlaps)
        
        lines = [
            "## RESUMO EXECUTIVO DA ANÁLISE CNIS",
            "",
            f"**Total de vínculos analisados:** {report_data['resumo']['Total de Vínculos']}",
            f"**Período de contribuição:** {report_data['resumo']['Primeira Contribuição']} a {report_data['resumo']['Última Contribuição']}",
            f"**Tempo total contributivo:** {report_data['resumo']['Tempo Total Contributivo']}",
            f"**Densidade de contribuição:** {report_data['resumo']['Densidade de Contribuição']}",
            ""
        ]
        
        if overlaps:
            lines.extend([
                "### ⚠️ ALERTAS",
                f"- {len(overlaps)} sobreposição(ões) de vínculos detectada(s)",
                ""
            ])
        
        # Análise de remunerações
        rem_analysis = report_data['remuneracoes_analysis']
        if rem_analysis['total_remuneracoes'] > 0:
            lines.extend([
                "### 💰 ANÁLISE DE REMUNERAÇÕES",
                f"- Total de competências: {rem_analysis['total_remuneracoes']}",
                f"- Maior remuneração: R$ {rem_analysis['maior_remuneracao']:,.2f}",
                f"- Menor remuneração: R$ {rem_analysis['menor_remuneracao']:,.2f}",
                f"- Remuneração média: R$ {rem_analysis['remuneracao_media']:,.2f}",
                ""
            ])
        
        return "\n".join(lines)
