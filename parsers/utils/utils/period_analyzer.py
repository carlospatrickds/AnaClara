import pandas as pd
from datetime import datetime, timedelta
from .date_calculator import DateCalculator

class PeriodAnalyzer:
    """Analisador de períodos de vínculos e contribuições"""
    
    def __init__(self):
        self.date_calc = DateCalculator()
    
    def calculate_periods(self, df_vinculos):
        """Calcula períodos para todos os vínculos"""
        df = df_vinculos.copy()
        
        # Calcular períodos
        periods = []
        for _, vinculo in df.iterrows():
            data_inicio = vinculo['data_inicio']
            data_fim = vinculo.get('data_fim')
            
            # Se não tem data fim, tentar usar última remuneração
            if pd.isna(data_fim) and 'remuneracoes' in vinculo and vinculo['remuneracoes']:
                data_fim = self._get_last_remuneration_date(vinculo['remuneracoes'])
            
            # Calcular período
            years, months, days = self.date_calc.calculate_period(data_inicio, data_fim)
            
            periods.append({
                'periodo_anos': years,
                'periodo_meses': months,
                'periodo_dias': days,
                'data_fim_calculada': data_fim
            })
        
        # Adicionar colunas ao DataFrame
        for i, period in enumerate(periods):
            for key, value in period.items():
                df.iloc[i, df.columns.get_loc(key) if key in df.columns else len(df.columns)] = value
                if key not in df.columns:
                    df[key] = None
                    df.iloc[i, df.columns.get_loc(key)] = value
        
        return df
    
    def detect_overlaps(self, df_vinculos):
        """Detecta sobreposições entre vínculos"""
        overlaps = []
        
        # Filtrar apenas vínculos empregatícios (não benefícios)
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo'].copy()
        
        for i, vinculo1 in df_work.iterrows():
            for j, vinculo2 in df_work.iterrows():
                if i >= j:  # Evitar duplicatas
                    continue
                
                # Verificar sobreposição
                start1 = vinculo1['data_inicio']
                end1 = vinculo1.get('data_fim_calculada') or vinculo1.get('data_fim')
                start2 = vinculo2['data_inicio']
                end2 = vinculo2.get('data_fim_calculada') or vinculo2.get('data_fim')
                
                if self.date_calc.is_date_overlap(start1, end1, start2, end2):
                    overlap_start, overlap_end, days = self.date_calc.get_overlap_period(
                        start1, end1, start2, end2
                    )
                    
                    if days > 0:
                        overlaps.append({
                            'vinculo1': vinculo1.to_dict(),
                            'vinculo2': vinculo2.to_dict(),
                            'start_overlap': overlap_start,
                            'end_overlap': overlap_end,
                            'days': days
                        })
        
        return overlaps
    
    def find_gaps(self, df_vinculos, min_gap_days=30):
        """Encontra gaps (períodos sem contribuição) entre vínculos"""
        gaps = []
        
        # Filtrar e ordenar vínculos por data de início
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo'].copy()
        df_work = df_work.sort_values('data_inicio')
        
        for i in range(len(df_work) - 1):
            current_vinculo = df_work.iloc[i]
            next_vinculo = df_work.iloc[i + 1]
            
            # Data fim do vínculo atual
            current_end = current_vinculo.get('data_fim_calculada') or current_vinculo.get('data_fim')
            
            # Data início do próximo vínculo
            next_start = next_vinculo['data_inicio']
            
            if current_end and next_start:
                # Calcular gap
                gap_days = (next_start - current_end).days
                
                if gap_days > min_gap_days:
                    gaps.append({
                        'gap_start': current_end + timedelta(days=1),
                        'gap_end': next_start - timedelta(days=1),
                        'gap_days': gap_days - 1
                    })
        
        return gaps
    
    def _get_last_remuneration_date(self, remuneracoes):
        """Extrai a data da última remuneração"""
        if not remuneracoes:
            return None
        
        latest_date = None
        
        for rem in remuneracoes:
            competencia = rem.get('competencia')
            if competencia:
                date = self.date_calc.parse_competencia(competencia)
                if date and (not latest_date or date > latest_date):
                    latest_date = date
        
        return latest_date
    
    def calculate_total_contribution_time(self, df_vinculos):
        """Calcula tempo total de contribuição considerando sobreposições"""
        # Criar lista de períodos
        periods = []
        
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo'].copy()
        
        for _, vinculo in df_work.iterrows():
            start = vinculo['data_inicio']
            end = vinculo.get('data_fim_calculada') or vinculo.get('data_fim') or datetime.now()
            
            if start:
                periods.append((start, end))
        
        # Ordenar por data de início
        periods.sort(key=lambda x: x[0])
        
        # Mesclar períodos sobrepostos
        merged_periods = []
        for start, end in periods:
            if not merged_periods:
                merged_periods.append((start, end))
            else:
                last_start, last_end = merged_periods[-1]
                
                if start <= last_end:
                    # Há sobreposição, mesclar
                    merged_periods[-1] = (last_start, max(last_end, end))
                else:
                    # Sem sobreposição, adicionar novo período
                    merged_periods.append((start, end))
        
        # Calcular tempo total
        total_days = 0
        for start, end in merged_periods:
            total_days += (end - start).days
        
        # Converter para anos, meses, dias
        years = total_days // 365
        remaining_days = total_days % 365
        months = remaining_days // 30
        days = remaining_days % 30
        
        return years, months, days, merged_periods
    
    def analyze_contribution_density(self, df_vinculos):
        """Analisa densidade de contribuições ao longo do tempo"""
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo'].copy()
        
        if df_work.empty:
            return {}
        
        # Período total analisado
        first_contribution = df_work['data_inicio'].min()
        last_contribution = df_work['data_fim'].max()
        
        if pd.isna(last_contribution):
            last_contribution = datetime.now()
        
        total_period_days = (last_contribution - first_contribution).days
        
        # Calcular tempo total contributivo
        years, months, days, merged_periods = self.calculate_total_contribution_time(df_work)
        contribution_days = sum((end - start).days for start, end in merged_periods)
        
        # Densidade (% do tempo com contribuição)
        density = (contribution_days / total_period_days * 100) if total_period_days > 0 else 0
        
        return {
            'first_contribution': first_contribution,
            'last_contribution': last_contribution,
            'total_period_days': total_period_days,
            'contribution_days': contribution_days,
            'density_percentage': density,
            'contribution_years': years,
            'contribution_months': months,
            'contribution_days_remainder': days
        }
