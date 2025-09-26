import re
import pandas as pd
from datetime import datetime
import io

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pdfplumber
        PDF_AVAILABLE = True
        USE_PDFPLUMBER = True
    except ImportError:
        PDF_AVAILABLE = False
        USE_PDFPLUMBER = False

class CNISParser:
    """Parser para arquivos CNIS do INSS em formato PDF e TXT"""
    
    def __init__(self):
        # Padrões regex para extração de dados
        self.patterns = {
            'header': r'NIT:\s*([\d\.-]+)\s*CPF:\s*([\d\.-]+)\s*Nome:\s*([A-Z\s]+)',
            'vinculo': r'(\d+)\s+([\d\.-]+)\s+([\d\/\.-]+)\s+([A-Z\s&,]+(?:LTDA|S/A|EPP)?)\s+(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})?\s*(Empregado|Contribuinte Individual|Empresário)',
            'remuneracao': r'(\d{2}/\d{4})\s+([\d\.,]+)',
            'beneficio': r'(\d+)\s+([\d\.-]+)\s+(\d+)\s+Benefício\s+(\d+)\s*-\s*([A-Z\s]+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})?\s*(ATIVO|CESSADO)',
            'data_nascimento': r'Data de nascimento:\s*(\d{2}/\d{2}/\d{4})',
            'nome_mae': r'Nome da mãe:\s*([A-Z\s]+)'
        }
    
    def parse_pdf(self, uploaded_file):
        """Parse de arquivo PDF"""
        if not PDF_AVAILABLE:
            raise Exception("Biblioteca para PDF não disponível. Instale PyPDF2 ou pdfplumber.")
        
        try:
            if USE_PDFPLUMBER:
                return self._parse_pdf_pdfplumber(uploaded_file)
            else:
                return self._parse_pdf_pypdf2(uploaded_file)
        except Exception as e:
            raise Exception(f"Erro ao processar PDF: {str(e)}")
    
    def _parse_pdf_pdfplumber(self, uploaded_file):
        """Parse usando pdfplumber"""
        import pdfplumber
        
        text_content = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text_content += page.extract_text() + "\n"
        
        return self._parse_text_content(text_content)
    
    def _parse_pdf_pypdf2(self, uploaded_file):
        """Parse usando PyPDF2"""
        import PyPDF2
        
        text_content = ""
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        
        for page in pdf_reader.pages:
            text_content += page.extract_text() + "\n"
        
        return self._parse_text_content(text_content)
    
    def parse_txt(self, uploaded_file):
        """Parse de arquivo TXT"""
        try:
            # Ler conteúdo do arquivo
            content = uploaded_file.read()
            
            # Tentar decodificar em diferentes encodings
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = content.decode('latin-1')
                except UnicodeDecodeError:
                    text_content = content.decode('cp1252')
            
            return self._parse_text_content(text_content)
            
        except Exception as e:
            raise Exception(f"Erro ao processar TXT: {str(e)}")
    
    def _parse_text_content(self, text_content):
        """Parse do conteúdo de texto extraído"""
        try:
            data = []
            
            # Extrair informações do cabeçalho
            header_info = self._extract_header_info(text_content)
            
            # Extrair vínculos
            vinculos = self._extract_vinculos(text_content)
            
            # Extrair remunerações para cada vínculo
            for vinculo in vinculos:
                vinculo.update(header_info)
                vinculo['remuneracoes'] = self._extract_remuneracoes(text_content, vinculo['seq'])
                data.append(vinculo)
            
            # Extrair benefícios separadamente
            beneficios = self._extract_beneficios(text_content)
            for beneficio in beneficios:
                beneficio.update(header_info)
                data.append(beneficio)
            
            return data
            
        except Exception as e:
            raise Exception(f"Erro ao processar conteúdo: {str(e)}")
    
    def _extract_header_info(self, text):
        """Extrai informações do cabeçalho"""
        info = {}
        
        # Buscar NIT, CPF e Nome
        header_match = re.search(self.patterns['header'], text)
        if header_match:
            info['nit'] = header_match.group(1)
            info['cpf'] = header_match.group(2)
            info['nome'] = header_match.group(3).strip()
        
        # Buscar data de nascimento
        nascimento_match = re.search(self.patterns['data_nascimento'], text)
        if nascimento_match:
            info['data_nascimento'] = self._parse_date(nascimento_match.group(1))
        
        # Buscar nome da mãe
        mae_match = re.search(self.patterns['nome_mae'], text)
        if mae_match:
            info['nome_mae'] = mae_match.group(1).strip()
        
        return info
    
    def _extract_vinculos(self, text):
        """Extrai informações dos vínculos empregatícios"""
        vinculos = []
        
        # Dividir texto em linhas para processamento sequencial
        lines = text.split('\n')
        current_vinculo = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Procurar início de vínculo (linha com Seq.)
            if 'Seq.' in line and 'NIT' in line and 'Código Emp.' in line:
                continue
            
            # Padrão para linha de vínculo
            vinculo_pattern = r'(\d+)\s+([\d\.-]+)\s+([\d\/\.-]+)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})?\s*(Empregado|Contribuinte Individual|Empresário)'
            
            match = re.search(vinculo_pattern, line)
            if match:
                vinculo = {
                    'seq': int(match.group(1)),
                    'nit_vinculo': match.group(2),
                    'cnpj': match.group(3),
                    'empresa': self._clean_empresa_name(match.group(4)),
                    'data_inicio': self._parse_date(match.group(5)),
                    'data_fim': self._parse_date(match.group(6)) if match.group(6) else None,
                    'tipo': match.group(7),
                    'categoria': 'vinculo'
                }
                vinculos.append(vinculo)
        
        return vinculos
    
    def _extract_beneficios(self, text):
        """Extrai informações dos benefícios"""
        beneficios = []
        
        # Padrão para benefícios
        lines = text.split('\n')
        
        for line in lines:
            if 'Benefício' in line:
                # Padrão mais flexível para benefícios
                beneficio_pattern = r'(\d+)\s+([\d\.-]+)\s+(\d+)\s+Benefício\s+(\d+)\s*-\s*([A-Z\s]+)\s+(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})?\s*(ATIVO|CESSADO)'
                
                match = re.search(beneficio_pattern, line)
                if match:
                    beneficio = {
                        'seq': int(match.group(1)),
                        'nit_vinculo': match.group(2),
                        'nb': match.group(3),
                        'especie': f"{match.group(4)} - {match.group(5).strip()}",
                        'empresa': f"BENEFÍCIO: {match.group(5).strip()}",
                        'data_inicio': self._parse_date(match.group(6)),
                        'data_fim': self._parse_date(match.group(7)) if match.group(7) else None,
                        'situacao': match.group(8),
                        'tipo': 'Benefício',
                        'categoria': 'beneficio'
                    }
                    beneficios.append(beneficio)
        
        return beneficios
    
    def _extract_remuneracoes(self, text, seq_vinculo):
        """Extrai remunerações para um vínculo específico"""
        remuneracoes = []
        
        # Buscar seção de remunerações após o vínculo
        lines = text.split('\n')
        in_remuneracoes = False
        
        for line in lines:
            line = line.strip()
            
            # Detectar início da seção de remunerações
            if 'Remunerações' in line:
                in_remuneracoes = True
                continue
            
            # Parar se encontrar outro vínculo ou seção
            if in_remuneracoes and ('Seq.' in line or 'Benefício' in line):
                break
            
            if in_remuneracoes:
                # Buscar padrões de competência e valor
                matches = re.findall(r'(\d{2}/\d{4})\s+([\d\.,]+)', line)
                for match in matches:
                    competencia, valor = match
                    try:
                        valor_float = float(valor.replace('.', '').replace(',', '.'))
                        remuneracoes.append({
                            'competencia': competencia,
                            'valor': valor_float,
                            'valor_formatado': valor
                        })
                    except ValueError:
                        continue
        
        return remuneracoes
    
    def _clean_empresa_name(self, name):
        """Limpa e padroniza nome da empresa"""
        # Remover espaços extras e caracteres especiais
        name = re.sub(r'\s+', ' ', name.strip())
        
        # Remover códigos e números no final
        name = re.sub(r'\s+\d+/\d+$', '', name)
        
        return name.strip()
    
    def _parse_date(self, date_str):
        """Converte string de data para datetime"""
        if not date_str:
            return None
        
        try:
            # Formato brasileiro: DD/MM/YYYY
            return datetime.strptime(date_str.strip(), '%d/%m/%Y')
        except ValueError:
            try:
                # Tentar outros formatos
                return datetime.strptime(date_str.strip(), '%d/%m/%y')
            except ValueError:
                return None
    
    def _extract_ultima_remuneracao(self, text, seq_vinculo):
        """Extrai a data da última remuneração para um vínculo"""
        remuneracoes = self._extract_remuneracoes(text, seq_vinculo)
        
        if not remuneracoes:
            return None
        
        # Encontrar a competência mais recente
        competencias = []
        for rem in remuneracoes:
            try:
                # Converter MM/YYYY para data (último dia do mês)
                mes, ano = rem['competencia'].split('/')
                data_competencia = datetime(int(ano), int(mes), 1)
                
                # Último dia do mês
                if int(mes) == 12:
                    ultimo_dia = datetime(int(ano) + 1, 1, 1) - timedelta(days=1)
                else:
                    ultimo_dia = datetime(int(ano), int(mes) + 1, 1) - timedelta(days=1)
                
                competencias.append(ultimo_dia)
            except:
                continue
        
        return max(competencias) if competencias else None
