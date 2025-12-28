import cherrypy
import os
import pdfplumber
# MUDANÇA 1: Importação atualizada para a versão nova
from openai import OpenAI
import json
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade

# MUDANÇA 2: Inicialização do Cliente
# Se estiver usando variável de ambiente no Coolify, ele pega automático.
# Se for colocar a chave direta, substitua o os.getenv(...) pela string "sk-..."
api_key = os.getenv("OPENAI_API_KEY", "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") # <--- COLOQUE SUA CHAVE AQUI SE NÃO USAR ENV
client = OpenAI(api_key=api_key)

class GovTechAPI:
    @cherrypy.expose
    def index(self):
        return "API GovTech Online (v1.1 - OpenAI Updated)."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        session = db_session()
        
        # 1. Verifica se já existe
        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            return {"status": "Ignorado", "msg": "Já existe."}

        # 2. Salva arquivo local
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Cria registro no Banco
        novo_diario = Diario(
            municipio="Lençóis Paulista",
            data_publicacao=datetime.strptime(data_pub, "%Y-%m-%d").date(),
            nome_arquivo=arquivo_pdf.filename,
            codigo_origem=int(codigo),
            numero_edicao=int(edicao),
            hash_origem=hash_origem,
            processado=True
        )
        session.add(novo_diario)
        session.commit()

        # 4. Extrai Texto do PDF
        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    # Filtro simples para economizar tokens
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "CONTRATAÇÃO", "ADITIVO"]):
                        texto += t + "\n"
        except Exception as e:
            print(f"Erro ao ler PDF: {e}")

        # 5. Chama a IA (SINTAXE NOVA)
        # Só chama se tiver texto suficiente
        if len(texto) > 50:
            prompt = f"""
            Extraia as oportunidades de negócio deste Diário Oficial em JSON.
            Retorne APENAS um array JSON puro (sem ```json) com chaves:
            "objeto" (resumo), "valor" (numero float), "favorecido", "prazo", "insight" (dica de venda).
            Texto: {texto[:15000]}
            """
            
            try:
                # MUDANÇA 3: Chamada atualizada para client.chat.completions.create
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                conteudo = resp.choices[0].message.content.strip()
                # Limpeza caso a IA mande markdown
                if conteudo.startswith("```json"): conteudo = conteudo[7:-3]
                
                dados_ia = json.loads(conteudo)
                
                contador = 0
                for item in dados_ia:
                    op = Oportunidade(
                        diario_id=novo_diario.id,
                        tipo="IA Detectada",
                        objeto_resumido=item.get('objeto', 'N/A'),
                        valor=float(item.get('valor', 0)),
                        favorecido=item.get('favorecido', 'N/A'),
                        prazo_vigencia=item.get('prazo', 'N/A'),
                        insight_venda=item.get('insight', '')
                    )
                    session.add(op)
                    contador += 1
                
                session.commit()
                print(f"--- SUCESSO: {contador} oportunidades salvas! ---")
                
            except Exception as e:
                print(f"Erro CRÍTICO na OpenAI: {e}")
                # Log extra para debug
                if 'resp' in locals(): print(resp)

        session.close()
        # Remove arquivo para não encher o disco
        if os.path.exists(caminho): os.remove(caminho)
        
        return {"status": "Sucesso", "id": novo_diario.id}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        session = db_session()
        # Traz as mais recentes primeiro
        ops = session.query(Oportunidade).join(Diario).order_by(Diario.data_publicacao.desc()).limit(50).all()
        lista = []
        for o in ops:
            lista.append({
                "id": o.id,
                "data": str(o.diario.data_publicacao),
                "edicao": o.diario.numero_edicao,
                "objeto": o.objeto_resumido,
                "valor": o.valor,
                "vencedor": o.favorecido,
                "insight": o.insight_venda
            })
        session.close()
        return lista

if __name__ == '__main__':
    init_db()
    cherrypy.quickstart(GovTechAPI(), '/', {'global': {'server.socket_host': '0.0.0.0', 'server.socket_port': 8080}})
