import pdfplumber
from datetime import datetime
from .base import BaseProcessor

class BauruProcessor(BaseProcessor):
    def extrair_texto(self, caminho_pdf):
        texto = ""
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for page in pdf.pages:
                    # AJUSTE PARA COLUNAS DE BAURU
                    # x_tolerance e y_tolerance ajudam a manter a leitura na ordem correta das colunas
                    texto += (page.extract_text(x_tolerance=3, y_tolerance=3) or "") + "\n"
        except Exception as e:
            print(f"   > Erro ao ler PDF Bauru: {e}")
        return texto

    def executar(self, caminho_pdf, diario_id):
        print("   > [PROCESSADOR] Iniciando Análise: Bauru")
        texto = self.extrair_texto(caminho_pdf)
        
        if len(texto) < 100:
            print("   > [AVISO] Texto do PDF insuficiente ou vazio.")
            return

        hoje_str = datetime.now().strftime("%d/%m/%Y")
        
        # PROMPT ESPECÍFICO PARA BAURU (ANTI-VEREADOR)
        prompt = f"""
        ATUE COMO: Especialista em Licitações de Bauru.
        CONTEXTO: Hoje é {hoje_str}.
        
        CRÍTICO - REGRAS DE EXCLUSÃO (BAURU):
        1. "EMENTÁRIO DAS PROPOSIÇÕES": IGNORE TUDO NESTA SEÇÃO. São pedidos de vereadores.
        2. "SOLICITA À PREFEITA/EMDURB": IGNORE. É tapa-buraco, lombada, capinação.
        3. "EDITAL DE CONCURSO": IGNORE listas de nomes de pessoas físicas.
        
        CAPTURAR APENAS (OURO):
        - Pregão Eletrônico/Presencial, Concorrência, Dispensa, Inexigibilidade.
        - Extratos de Contrato e Atas de Registro de Preços.
        
        FORMATO DE SAÍDA (JSON ARRAY):
        [
          {{
            "id_processo": "Pregão 4050/2025",
            "categoria": "Serviços",
            "objeto": "Resumo claro do item",
            "valor": 5000.00,
            "vencedor": "Nome da Empresa ou 'Em Aberto'",
            "cnpj": "XX",
            "data_sessao": "DD/MM/AAAA", 
            "status": "Aberto",
            "insight": "Frase curta"
          }}
        ]
        NOTA SOBRE VALOR: Retorne como NÚMERO (Float) JSON puro. Use ponto para decimal.
        """
        
        dados = self.processar_ia(texto, prompt)
        
        # FILTRO EXTRA DO PYTHON (Segurança adicional contra vereadores)
        dados_limpos = []
        if dados:
            for item in dados:
                obj = str(item.get('objeto', '')).lower()
                # Se tiver palavras típicas de indicação política, remove
                if "solicita" in obj and ("prefeita" in obj or "emdurb" in obj or "secretaria" in obj):
                    continue 
                dados_limpos.append(item)
            
            self.salvar_banco(diario_id, dados_limpos)
        else:
            print("   > [AVISO] Nenhuma oportunidade encontrada ou erro na IA.")