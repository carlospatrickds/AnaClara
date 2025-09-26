import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd

class TimelineChart:
    """Gerador de gráficos de linha do tempo para vínculos"""
    
    def __init__(self):
        self.colors = {
            'vinculo': '#2E86AB',
            'beneficio': '#A23B72',
            'overlap': '#F18F01',
            'gap': '#C73E1D'
        }
    
    def create_timeline(self, df_vinculos):
        """Cria gráfico de linha do tempo dos vínculos"""
        if df_vinculos.empty:
            return None
        
        fig = go.Figure()
        
        # Processar vínculos
        for _, vinculo in df_vinculos.iterrows():
            self._add_vinculo_to_timeline(fig, vinculo)
        
        # Configurar layout
        fig.update_layout(
            title="Linha do Tempo dos Vínculos Empregatícios e Benefícios",
            xaxis_title="Período",
            yaxis_title="Vínculos",
            height=max(400, len(df_vinculos) * 40),
            showlegend=True,
            hovermode='closest'
        )
        
        # Configurar eixo Y
        fig.update_yaxis(
            tickmode='array',
            tickvals=list(range(len(df_vinculos))),
            ticktext=[f"Seq {row['seq']}" for _, row in df_vinculos.iterrows()]
        )
        
        return fig
    
    def _add_vinculo_to_timeline(self, fig, vinculo):
        """Adiciona um vínculo à linha do tempo"""
        seq = vinculo['seq']
        data_inicio = vinculo['data_inicio']
        data_fim = vinculo.get('data_fim_calculada') or vinculo.get('data_fim')
        categoria = vinculo.get('categoria', 'vinculo')
        
        # Se não tem data fim, usar data atual
        if not data_fim:
            data_fim = datetime.now()
            is_active = True
        else:
            is_active = False
        
        # Cor baseada na categoria
        color = self.colors.get(categoria, self.colors['vinculo'])
        
        # Texto do hover
        hover_text = self._create_hover_text(vinculo, is_active)
        
        # Adicionar barra ao gráfico
        fig.add_trace(go.Scatter(
            x=[data_inicio, data_fim],
            y=[seq - 1, seq - 1],
            mode='lines+markers',
            line=dict(color=color, width=8),
            marker=dict(size=8, color=color),
            name=f"Seq {seq} - {vinculo.get('empresa', 'N/A')[:30]}",
            hovertext=hover_text,
            hoverinfo='text',
            showlegend=False
        ))
        
        # Adicionar marcador especial para vínculos ativos
        if is_active:
            fig.add_trace(go.Scatter(
                x=[data_fim],
                y=[seq - 1],
                mode='markers',
                marker=dict(
                    size=12,
                    color='red',
                    symbol='circle-open',
                    line=dict(width=2)
                ),
                name='Ativo',
                hovertext=f"Vínculo ativo até {data_fim.strftime('%d/%m/%Y')}",
                hoverinfo='text',
                showlegend=False
            ))
    
    def _create_hover_text(self, vinculo, is_active):
        """Cria texto do hover para um vínculo"""
        lines = [
            f"<b>Seq {vinculo['seq']}</b>",
            f"Empresa: {vinculo.get('empresa', 'N/A')}",
            f"CNPJ: {vinculo.get('cnpj', 'N/A')}",
            f"Tipo: {vinculo.get('tipo', 'N/A')}",
            f"Início: {vinculo['data_inicio'].strftime('%d/%m/%Y') if vinculo['data_inicio'] else 'N/A'}"
        ]
        
        data_fim = vinculo.get('data_fim_calculada') or vinculo.get('data_fim')
        if data_fim:
            lines.append(f"Fim: {data_fim.strftime('%d/%m/%Y')}")
        else:
            lines.append("Fim: Em andamento")
        
        # Adicionar período se disponível
        if 'periodo_anos' in vinculo:
            anos = vinculo.get('periodo_anos', 0)
            meses = vinculo.get('periodo_meses', 0)
            dias = vinculo.get('periodo_dias', 0)
            lines.append(f"Período: {anos}a {meses}m {dias}d")
        
        # Adicionar status ativo
        if is_active:
            lines.append("<b>Status: ATIVO</b>")
        
        return "<br>".join(lines)
    
    def create_overlap_chart(self, overlaps):
        """Cria gráfico específico para sobreposições"""
        if not overlaps:
            return None
        
        fig = go.Figure()
        
        for i, overlap in enumerate(overlaps):
            # Adicionar período do primeiro vínculo
            fig.add_trace(go.Scatter(
                x=[overlap['vinculo1']['data_inicio'], overlap['vinculo1']['data_fim']],
                y=[i, i],
                mode='lines',
                line=dict(color='blue', width=10),
                name=f"Vínculo {overlap['vinculo1']['seq']}",
                opacity=0.7
            ))
            
            # Adicionar período do segundo vínculo
            fig.add_trace(go.Scatter(
                x=[overlap['vinculo2']['data_inicio'], overlap['vinculo2']['data_fim']],
                y=[i + 0.1, i + 0.1],
                mode='lines',
                line=dict(color='green', width=10),
                name=f"Vínculo {overlap['vinculo2']['seq']}",
                opacity=0.7
            ))
            
            # Destacar período de sobreposição
            fig.add_trace(go.Scatter(
                x=[overlap['start_overlap'], overlap['end_overlap']],
                y=[i + 0.05, i + 0.05],
                mode='lines',
                line=dict(color='red', width=15),
                name=f"Sobreposição {overlap['days']} dias",
                opacity=0.9
            ))
        
        fig.update_layout(
            title="Sobreposições de Vínculos Detectadas",
            xaxis_title="Período",
            yaxis_title="Sobreposições",
            height=max(300, len(overlaps) * 80)
        )
        
        return fig
    
    def create_contribution_density_chart(self, df_vinculos):
        """Cria gráfico de densidade de contribuições por ano"""
        if df_vinculos.empty:
            return None
        
        # Calcular contribuições por ano
        df_work = df_vinculos[df_vinculos.get('categoria', 'vinculo') == 'vinculo'].copy()
        
        if df_work.empty:
            return None
        
        # Criar range de anos
        first_year = df_work['data_inicio'].min().year
        last_year = datetime.now().year
        
        years_data = []
        
        for year in range(first_year, last_year + 1):
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31)
            
            # Contar dias de contribuição no ano
            contribution_days = 0
            
            for _, vinculo in df_work.iterrows():
                v_start = vinculo['data_inicio']
                v_end = vinculo.get('data_fim_calculada') or vinculo.get('data_fim') or datetime.now()
                
                # Calcular interseção com o ano
                overlap_start = max(v_start, year_start)
                overlap_end = min(v_end, year_end)
                
                if overlap_start <= overlap_end:
                    contribution_days += (overlap_end - overlap_start).days + 1
            
            # Densidade (máximo 365 dias por ano)
            density = min(contribution_days / 365.0 * 100, 100)
            
            years_data.append({
                'ano': year,
                'dias_contribuicao': contribution_days,
                'densidade_pct': density
            })
        
        df_years = pd.DataFrame(years_data)
        
        # Criar gráfico de barras
        fig = px.bar(
            df_years,
            x='ano',
            y='densidade_pct',
            title='Densidade de Contribuições por Ano (%)',
            labels={'densidade_pct': 'Densidade (%)', 'ano': 'Ano'},
            color='densidade_pct',
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(height=400)
        
        return fig
