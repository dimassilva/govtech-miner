import cherrypy
import os
import pdfplumber
import json
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

class GovTechAPI:
    @cherrypy.expose
    def index(self):
        return "API GovTech (Estrutura Completa v5)."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        print(f"\n=== PROCESSANDO EDIÇÃO {edicao} (COMPLETO) ===")
        session = db_session()
        
        # 1. Verifica duplicidade
        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            return {"status": "Ignorado", "msg": "Já existe."}

        # 2. Salva arquivo
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Cria registro do DIÁRIO (Arquivo)
        novo_diario = Diario(
            municipio="Lençóis Paulista",
            data_publicacao=datetime.strptime(data_pub, "%Y-%m-%d").date(),
            nome_arquivo=arquivo_pdf.filename,
            codigo_origem=int(codigo),
            numero_edicao=int(edicao),
            hash_origem=hash_origem,
            tipo_documento_geral="Diário Oficial",
            processado=True
        )
        session.add(novo_diario)
        session.commit()
        id_pai = novo_diario.id 

        # 4. Extrai Texto
        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    # Filtro inteligente: Pega páginas com indícios de compras
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "CONTRATO", "ADITIVO", "RATIFICAÇÃO", "HOMOLOGAÇÃO"]):
                        texto += t + "\n"
        except Exception as e:
            print(f"Erro PDF: {e}")

        # 5. Chama a IA com PROMPT RICO
        if len(texto) > 50:
            prompt = f"""
            Analise o texto deste Diário Oficial.
            Identifique cada Compra, Licitação, Dispensa, Contrato ou Aditivo.
            
            Retorne APENAS um JSON array. Use EXATAMENTE estas chaves:
            - "id_processo": (Ex: "Dispensa 014/2025")
            - "categoria": (Ex: "Limpeza", "Obras", "TI", "Imobiliário")
            - "objeto": (Descrição completa do que foi comprado)
            - "valor": (Número float, valor total. Se for mensal, multiplique pelo prazo ou estime. Ex: 553677.78)
            - "vencedor": (Razão Social da empresa)
            - "cnpj": (O CNPJ do vencedor, se houver no texto)
            - "prazo": (Vigência do contrato)
            - "status": ("Contratado", "Aberto", "Cancelado", "Ratificado")
            - "localizacao": (Endereço, se for aluguel ou obra. Senão null)
            - "insight": (Uma frase curta estratégica para um vendedor sobre isso)

            Texto para análise:
            {texto[:15000]}
            """
            
            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                conteudo = resp.choices[0].message.content.strip()
                # Limpeza de Markdown
                if "```" in conteudo: 
                    conteudo = conteudo.replace("```json", "").replace("```", "")
                
                dados_ia = json.loads(conteudo)
                
                contador = 0
                for item in dados_ia:
                    try:
                        # Tratamento de segurança para o valor float
                        val_raw = item.get('valor', 0)
                        if isinstance(val_raw, str): 
                            val_float = 0.0 # Se vier texto sujo, zera pra não quebrar
                        else:
                            val_float = float(val_raw)

                        op = Oportunidade(
                            diario_id=id_pai,
                            id_processo=str(item.get('id_processo', 'N/A')),
                            categoria=str(item.get('categoria', 'Geral')),
                            objeto=str(item.get('objeto', 'N/A')),
                            valor=val_float,
                            vencedor=str(item.get('vencedor', 'N/A')),
                            cnpj_vencedor=str(item.get('cnpj', '')), # Novo campo
                            prazo=str(item.get('prazo', '')),
                            status=str(item.get('status', 'Detectado')),
                            localizacao=str(item.get('localizacao', '')),
                            insight_venda=str(item.get('insight', ''))
                        )
                        session.add(op)
                        contador += 1
                    except Exception as e_item:
                        print(f"Erro ao salvar item: {e_item}")

                session.commit()
                print(f"--- SUCESSO: {contador} oportunidades completas salvas! ---")

            except Exception as e:
                print(f"ERRO OPENAI: {e}")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        
        return {"status": "Sucesso", "id": id_pai}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        session = db_session()
        # Retorna o JSON completo para seu Frontend
        ops = session.query(Oportunidade).join(Diario).order_by(Diario.data_publicacao.desc()).limit(50).all()
        lista = []
        for o in ops:
            lista.append({
                "id": o.id,
                "data": str(o.diario.data_publicacao),
                "edicao": o.diario.numero_edicao,
                "processo": o.id_processo,
                "categoria": o.categoria,
                "objeto": o.objeto,
                "valor": o.valor,
                "vencedor": o.vencedor,
                "cnpj": o.cnpj_vencedor,
                "status": o.status,
                "insight": o.insight_venda
            })
        session.close()
        return lista

if __name__ == '__main__':
    init_db()
    conf = {'global': {'server.socket_host': '0.0.0.0', 'server.socket_port': 8080}}
    cherrypy.quickstart(GovTechAPI(), '/', conf)
