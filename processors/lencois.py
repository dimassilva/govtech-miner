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
            ATUE COMO: Especialista em Licitações Públicas (B2G) e Auditor de Dados.
            CONTEXTO: Hoje é {hoje_str}. Analise o texto completo do Diário Oficial fornecido abaixo.
            
            OBJETIVO: Extrair oportunidades de vendas para o governo (Licitações, Dispensas, Contratos) e ignorar ruídos administrativos.

            === REGRAS DE EXCLUSÃO (CRÍTICO - O QUE IGNORAR) ===
            1. RH e PESSOAL: Ignore "Processo Seletivo", "Concurso Público", "Nomeações", "Exonerações", "Convocação de Professor/Estagiário". Se houver lista de nomes de pessoas físicas (CPFs), IGNORE.
            2. CONTABILIDADE INTERNA: Ignore tabelas de "Suplementação", "Dotação Orçamentária", "Crédito Suplementar", "Decreto de Abertura de Crédito", "Anulação de Verbas". (Dica: Se o texto fala apenas de remanejamento de verba entre secretarias, NÃO é venda).
            3. ASSISTENCIALISMO/POLÍTICA: Ignore "Chamamento Público para Artesãos", "Feirantes", "Subvenção Social", "Repasse ao Terceiro Setor", "Conselhos Municipais".
            4. LEGISLATIVO: Ignore "Indicações de Vereadores", "Moções", "Leis" (exceto se for lei autorizando compra específica).
            5. Ignore 'Abre Crédito Especial', 'Crédito Adicional', 'Crédito Suplementar' e qualquer Decreto que trate apenas de orçamento.

            === O QUE CAPTURAR (OURO - VENDAS B2G) ===
            Capture qualquer transação onde a prefeitura compra produtos ou contrata empresas:
            - MODALIDADES: Pregão (Eletrônico/Presencial), Concorrência, Tomada de Preços, Dispensa de Licitação (Art. 75), Inexigibilidade (Art. 74), Credenciamento (para serviços).
            - DOCUMENTOS: Aviso de Licitação, Edital, Homologação, Adjudicação, Extrato de Contrato, Ata de Registro de Preços, Termo Aditivo (apenas se tiver valor monetário relevante).
            - CATEGORIAS: Obras, Reformas, Medicamentos, TI (Software/Hardware), Limpeza, Segurança, Merenda, Uniformes, Locação de Veículos/Máquinas, Consultoria.

            === REGRAS DE STATUS ===
            - "Aviso de Licitação" / "Abertura" -> "Aberto" (Data futura)
            - "Homologação" / "Adjudicação" / "Extrato de Contrato" -> "Contratado" (Já ocorreu)
            - "Aditivo de Prazo/Valor" -> "Renovação"
            - "Deserta" / "Fracassada" / "Revogada" -> "Fracassada"
            - "Suspensão" -> "Suspenso"

            === FORMATO DE SAÍDA (JSON PURO) ===
            Responda APENAS com um Array JSON válido. Não use Markdown (```json). Não use explicações antes ou depois.
            
            [
            {{
                "id_processo": "Pregão 90/2025",
                "categoria": "Obras" (ou TI, Serviços, Compras, Saúde, Outros),
                "objeto": "Descrição resumida do que está sendo comprado (máx 200 chars)",
                "valor": 1200.50,  (IMPORTANTE: Retorne FLOAT. Converta '1.200,50' para 1200.50. Se não houver valor exato, use 0.0),
                "vencedor": "Nome da Empresa ou 'Em Aberto' se for Aviso",
                "cnpj": "XX.XXX.XXX/0001-XX" (ou vazio se não houver),
                "data_sessao": "DD/MM/AAAA",
                "prazo": "12 meses" (ou "60 dias", "Imediato"),
                "localizacao": "Local de entrega ou execução (ex: Almoxarifado Central)",
                "status": "Aberto",
                "insight": "Frase destacando a oportunidade (ex: 'Compra direta de TI sem licitação')"
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