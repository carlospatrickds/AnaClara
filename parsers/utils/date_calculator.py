from datetime import datetime, timedelta
import calendar

class DateCalculator:
    """Utilitário para cálculos de datas e períodos"""
    
    @staticmethod
    def calculate_period(start_date, end_date):
        """
        Calcula período entre duas datas retornando anos, meses e dias
        """
        if not start_date:
            return 0, 0, 0
        
        if not end_date:
            end_date = datetime.now()
        
        # Garantir que as datas são datetime
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%d/%m/%Y')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%d/%m/%Y')
        
        # Calcular diferença
        years = end_date.year - start_date.year
        months = end_date.month - start_date.month
        days = end_date.day - start_date.day
        
        # Ajustar se dias for negativo
        if days < 0:
            months -= 1
            # Pegar último dia do mês anterior
            if end_date.month == 1:
                last_month = 12
                year_for_last_month = end_date.year - 1
            else:
                last_month = end_date.month - 1
                year_for_last_month = end_date.year
            
            days_in_last_month = calendar.monthrange(year_for_last_month, last_month)[1]
            days += days_in_last_month
        
        # Ajustar se meses for negativo
        if months < 0:
            years -= 1
            months += 12
        
        return years, months, days
    
    @staticmethod
    def add_months(date, months):
        """Adiciona meses a uma data"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, calendar.monthrange(year, month)[1])
        return date.replace(year=year, month=month, day=day)
    
    @staticmethod
    def get_end_of_month(date):
        """Retorna o último dia do mês de uma data"""
        return date.replace(day=calendar.monthrange(date.year, date.month)[1])
    
    @staticmethod
    def parse_competencia(competencia_str):
        """
        Converte string de competência (MM/YYYY) para data (último dia do mês)
        """
        try:
            mes, ano = competencia_str.split('/')
            # Último dia do mês
            ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
            return datetime(int(ano), int(mes), ultimo_dia)
        except:
            return None
    
    @staticmethod
    def format_period(years, months, days):
        """Formata período em texto legível"""
        parts = []
        
        if years > 0:
            parts.append(f"{years} ano{'s' if years != 1 else ''}")
        
        if months > 0:
            parts.append(f"{months} mês{'es' if months != 1 else ''}")
        
        if days > 0:
            parts.append(f"{days} dia{'s' if days != 1 else ''}")
        
        if not parts:
            return "0 dias"
        
        return ", ".join(parts)
    
    @staticmethod
    def total_days(years, months, days):
        """Converte período para total de dias aproximado"""
        return years * 365 + months * 30 + days
    
    @staticmethod
    def is_date_overlap(start1, end1, start2, end2):
        """Verifica se dois períodos se sobrepõem"""
        if not all([start1, start2]):
            return False
        
        # Se não tem data fim, usar data atual
        if not end1:
            end1 = datetime.now()
        if not end2:
            end2 = datetime.now()
        
        # Verificar sobreposição
        return start1 <= end2 and start2 <= end1
    
    @staticmethod
    def get_overlap_period(start1, end1, start2, end2):
        """Calcula o período de sobreposição entre duas datas"""
        if not DateCalculator.is_date_overlap(start1, end1, start2, end2):
            return None, None, 0
        
        # Se não tem data fim, usar data atual
        if not end1:
            end1 = datetime.now()
        if not end2:
            end2 = datetime.now()
        
        # Calcular período de sobreposição
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start <= overlap_end:
            days = (overlap_end - overlap_start).days + 1
            return overlap_start, overlap_end, days
        
        return None, None, 0
