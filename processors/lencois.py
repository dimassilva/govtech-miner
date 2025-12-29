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
        
        # ... dentro do método de processamento ...

        if len(texto) > 100:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            
            # MELHORIA 1: Aumentamos o limite para 500.000 (Gemini Flash aguenta tranquilo)
            # Isso garante que a IA leia a página 33 e além.
            texto_limitado = texto[:500000]

            prompt = f"""
                ATUE COMO: Auditor Sênior de Contratações Públicas e Especialista em B2G.
                CONTEXTO: Hoje é {hoje_str}. Sua tarefa é minerar dados do Diário Oficial.
                
                === SUA MISSÃO (AUTO-AUDITORIA) ===
                Você deve aplicar um filtro de "Ceticismo Extremo". Seu objetivo NÃO é encher o banco de dados, mas sim encontrar APENAS oportunidades de vendas REAIS e VALIDAS.
                Prefira retornar uma lista vazia [] a retornar dados incorretos (Falsos Positivos).
                
                === PASSO A PASSO MENTAL (Faça isso para cada item antes de extrair) ===
                1. Li um trecho com valor monetário ou número de contrato?
                2. VERIFICAÇÃO DE "LIXO":
                   - O texto fala de "Designar Fiscal", "Gestor", "Nomear servidor"? -> SE SIM, DESCARTE IMEDIATAMENTE.
                   - O texto fala de "Abertura de Crédito", "Suplementação", "Remanejamento"? -> SE SIM, DESCARTE IMEDIATAMENTE.
                   - O texto fala de "Processo Seletivo", "Concurso", "Estagiário"? -> SE SIM, DESCARTE IMEDIATAMENTE.
                3. Se passou pelos filtros acima, é uma compra de produto/serviço externo? -> ENTÃO EXTRAIA.
                
                === REGRAS DE EXCLUSÃO (LISTA NEGRA) ===
                IGNORE ABSOLUTAMENTE se o texto contiver:
                - "Designa servidor", "Atribuições de fiscal", "Gestão e fiscalização".
                - "Crédito Adicional", "Superávit Financeiro", "Dotação Orçamentária".
                - "Concede licença", "Prorroga afastamento", "Readaptação".
                - "Subvenção Social", "Repasse ao Terceiro Setor".
                
                === O QUE CAPTURAR (LISTA BRANCA - VENDAS B2G) ===
                Capture apenas quando a PREFEITURA PAGA para UMA EMPRESA:
                - Licitações (Pregão, Concorrência, Tomada de Preços).
                - Compras Diretas (Dispensa Art. 75, Inexigibilidade).
                - Contratos e Aditivos (Apenas se for compra/serviço, não convênios).
                - Atas de Registro de Preços (Mesmo com valor R$ 0,00 ou unitário).
                
                === FORMATO DE SAÍDA (JSON PURO) ===
                Responda APENAS com um Array JSON válido. Sem Markdown. Sem explicações.
                
                [
                  {{
                    "id_processo": "Pregão 90/2025",
                    "categoria": "Obras" (ou TI, Serviços, Compras, Saúde, Outros),
                    "objeto": "Descrição resumida (ex: Aquisição de 100 computadores)",
                    "valor": 1200.50, (Use 0.0 se for Registro de Preços ou não informado),
                    "vencedor": "Nome da Empresa ou 'Em Aberto'",
                    "cnpj": "XX.XXX.XXX/0001-XX",
                    "data_sessao": "DD/MM/AAAA",
                    "prazo": "12 meses",
                    "localizacao": "Almoxarifado Central",
                    "status": "Aberto",
                    "insight": "Frase curta (ex: 'Compra direta de TI'). Se for Ata, use: 'Ata de Registro de Preços. Valor sob demanda.'"
                  }}
                ]
                
                === TEXTO DO DIÁRIO OFICIAL (LEIA ATÉ O FIM) ===
                {texto_limitado}
                """
        
        dados = self.processar_ia(texto, prompt)
        
        if dados:
            self.salvar_banco(diario_id, dados)
        else:
            print("   > [AVISO] Nenhuma oportunidade encontrada ou erro na IA.")
