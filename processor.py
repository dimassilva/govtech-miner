import pdfplumber
import openai
import json
import os

# Configure sua chave da OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

class PDFProcessor:
    def extrair_texto_relevante(self, pdf_path):
        texto_candidato = ""
        palavras_chave = ["DISPENSA DE LICITAÇÃO", "INEXIGIBILIDADE", "CONTRATAÇÃO DIRETA", "ADITIVO"]
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                texto_pagina = page.extract_text()
                if texto_pagina:
                    # HEURÍSTICA DE ECONOMIA:
                    # Só processa a página se tiver palavras-chave em caixa alta (títulos comuns)
                    if any(p in texto_pagina for p in palavras_chave):
                        texto_candidato += f"--- PÁGINA {i+1} ---\n{texto_pagina}\n"
        
        return texto_candidato

    def analisar_com_ia(self, texto_bruto):
        if not texto_bruto:
            return []

        prompt = f"""
        Você é um especialista em licitações públicas. Analise o texto abaixo extraído de um Diário Oficial.
        Identifique TODAS as compras, contratações, dispensas ou aditivos.
        
        Retorne APENAS um JSON array válido, sem markdown, com este formato para cada item:
        {{
            "tipo": "Dispensa/Licitação/Aditivo",
            "numero_processo": "nº do processo ou edital",
            "objeto": "Resumo curto do que foi comprado",
            "valor": 0.00 (número float, converta o texto),
            "favorecido": "Nome da empresa vencedora (se houver)",
            "prazo": "Vigência do contrato",
            "insight": "Uma frase curta explicando por que isso é uma oportunidade de venda futura"
        }}

        Texto:
        {texto_bruto}
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0125", # Modelo mais barato e rápido para JSON
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        try:
            conteudo = response.choices[0].message.content
            return json.loads(conteudo)
        except:
            return []
