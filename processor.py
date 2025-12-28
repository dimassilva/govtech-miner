import pdfplumber
import openai
import json
import os

# --- CONFIGURE SUA CHAVE AQUI ---
openai.api_key = "sk-proj-S-vEB_S0e0q7Qp2e3Hl74icD73JwnvSKjMLbgCU27HNEEVY4OqLNCxNPsbG4bES4S7IT3O0Z-RT3BlbkFJ9doD3kTGK7npJpGKR4wVKeOorTbrfWDrTaTyu_ArJORaBetjK0MSDXPjDhrnyZ-mIKZ1-YG_oAsk-..." # Coloque sua chave da OpenAI aqui ou use os.getenv("OPENAI_API_KEY")

class PDFProcessor:
    def extrair_texto_relevante(self, pdf_path):
        """Extrai apenas páginas com palavras-chave para economizar tokens."""
        texto_filtrado = ""
        # Palavras-chave que indicam compras/contratos
        gatilhos = ["DISPENSA DE LICITAÇÃO", "INEXIGIBILIDADE", "CONTRATAÇÃO DIRETA", 
                    "ADITIVO", "EXTRATO DE CONTRATO", "HOMOLOGAÇÃO"]
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                texto = page.extract_text() or ""
                # Heurística: Só pega a página se tiver algum gatilho em MAIÚSCULO
                if any(g in texto for g in gatilhos):
                    texto_filtrado += f"--- PÁGINA {i+1} ---\n{texto}\n"
        
        return texto_filtrado

    def analisar_com_ia(self, texto_bruto):
        if not texto_bruto or len(texto_bruto) < 50:
            return []

        prompt = f"""
        Você é um especialista em licitações públicas. Analise o texto abaixo extraído de um Diário Oficial.
        Identifique TODAS as compras, contratações, dispensas ou aditivos.
        
        Retorne APENAS um JSON array válido (sem markdown ```json), com este formato para cada item:
        {{
            "tipo": "Classifique (Dispensa/Licitação/Aditivo/Homologação)",
            "numero_processo": "nº do processo/edital ou 'N/A'",
            "objeto": "Resumo curto do que foi comprado",
            "valor": 0.00 (número float, converta o texto, se não tiver use 0),
            "favorecido": "Nome da empresa vencedora ou 'N/A'",
            "prazo": "Vigência do contrato ou 'N/A'",
            "insight": "Frase curta: Por que isso é uma oportunidade de venda ou monitoramento?"
        }}

        Texto do Diário:
        {texto_bruto}
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0125", # Modelo rápido e barato
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            conteudo = response.choices[0].message.content.strip()
            # Remove crases de markdown se a IA colocar
            if conteudo.startswith("```json"): conteudo = conteudo[7:-3]
            return json.loads(conteudo)
        except Exception as e:
            print(f"Erro na IA: {e}")
            return []
