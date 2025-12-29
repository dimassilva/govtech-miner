import pdfplumber
from datetime import datetime
from .base import BaseProcessor

class LencoisProcessor(BaseProcessor):
    def extrair_texto(self, caminho_pdf):
        texto = ""
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for page in pdf.pages:
                    # Lençóis tem layout de coluna única ou bloco simples
                    texto += (page.extract_text() or "") + "\n"
        except Exception as e:
            print(f"   > Erro ao ler PDF Lençóis: {e}")
        return texto

    def executar(self, caminho_pdf, diario_id):
        print("   > [PROCESSADOR] Iniciando Análise: Lençóis Paulista")
        texto = self.extrair_texto(caminho_pdf)
        
        if len(texto) > 100:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            
            prompt = f"""
            ATUE COMO: Especialista em Licitações Públicas (B2G).
            CONTEXTO: Hoje é {hoje_str}. Analise o texto do Diário Oficial.
            
            REGRAS DE FILTRAGEM (CRÍTICO):
            1. IGNORE TOTALMENTE: 
               - "Processo Seletivo", "Concurso Público", "Nomeações", "Conselhos", "Leis".
               - tabelas financeiras com títulos como: "Dotação", "Suplementação", "Anulação", "Crédito Suplementar", "Decreto Executivo". (Isso é contabilidade interna).
               - "Chamamento Público para ARTESÃOS/FEIRANTES".
               - "Processo Seletivo" (RH) e "Concurso Público".
               - Tabelas dentro de "DECRETOS DE SUPLEMENTAÇÃO".

            2. CAPTURE APENAS VENDAS REAIS (B2G)(OURO):
               - Aquisição de produtos, obras, serviços, TI, etc.
               - Busque por "Ratificação", "Homologação", "Adjudicação", "Extrato de Contrato", "Inexigibilidade", "Dispensa".
               - Busque por "Aviso de Licitação", "Pregão".

            3. REGRAS DE STATUS:
               - "Aviso de Licitação" (Futuro) -> "Aberto"
               - "Homologação/Extrato" -> "Contratado"
               - "Aditivo" -> "Renovação"
               - "Deserta/Fracassada" -> "Fracassada"

            4. DATAS: Extraia DD/MM/AAAA.

            IMPORTANTE: Verifique o documento até a ÚLTIMA PÁGINA. As compras diretas (Dispensas/Inexigibilidade) costumam ficar no final.

            FORMATO DE SAÍDA (JSON ARRAY):
            [
              {{
                "id_processo": "Pregão 90/2025",
                "categoria": "Obras",
                "objeto": "Resumo",
                "valor": 1200.00,
                "vencedor": "Nome ou 'Em Aberto'",
                "cnpj": "XX",
                "data_sessao": "DD/MM/AAAA", 
                "status": "Aberto",
                "insight": "Frase"
              }}
            ]
            
            Texto (30k chars):
            {texto[:30000]}
            """
        
        dados = self.processar_ia(texto, prompt)
        
        if dados:
            self.salvar_banco(diario_id, dados)
        else:
            print("   > [AVISO] Nenhuma oportunidade encontrada ou erro na IA.")