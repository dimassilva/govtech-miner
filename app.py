import cherrypy
import os
import pdfplumber
import json
from datetime import datetime
from database import init_db, db_session
from models import Diario, Oportunidade
from openai import OpenAI

# --- CORREÇÃO AQUI ---
# Cole sua chave dentro das aspas abaixo
MINHA_CHAVE_OPENAI = "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"  # <--- COLE SUA CHAVE AQUI

# Inicializa o cliente forçando a chave
client = OpenAI(api_key=MINHA_CHAVE_OPENAI)

class GovTechAPI:
    @cherrypy.expose
    def index(self):
        return "API GovTech Online (v3 - Key Hardcoded)."

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

        # 4. Extrai Texto
        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "CONTRATAÇÃO", "ADITIVO"]):
                        texto += t + "\n"
        except Exception as e:
            print(f"Erro ao ler PDF: {e}")

        # 5. Chama a IA
        if len(texto) > 50:
            prompt = f"""
            Analise o texto de Diário Oficial abaixo.
            Extraia licitações, dispensas ou contratos.
            Retorne APENAS um JSON array puro (sem ```json no inicio) com os campos:
            "objeto" (resumo), "valor" (numero float), "favorecido", "prazo", "insight" (dica curta).
            
            Texto: {texto[:15000]}
            """
            
            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                conteudo = resp.choices[0].message.content.strip()
                if conteudo.startswith("```json"): 
                    conteudo = conteudo[7:-3]
                elif conteudo.startswith("```"):
                    conteudo = conteudo[3:-3]
                
                dados_ia = json.loads(conteudo)
                
                contador = 0
                for item in dados_ia:
                    op = Oportunidade(
                        diario_id=novo_diario.id,
                        tipo="Detectado IA",
                        objeto_resumido=item.get('objeto', 'N/A'),
                        valor=float(item.get('valor', 0) or 0),
                        favorecido=item.get('favorecido', 'N/A'),
                        prazo_vigencia=item.get('prazo', 'N/A'),
                        insight_venda=item.get('insight', '')
                    )
                    session.add(op)
                    contador += 1
                
                session.commit()
                print(f"--- SUCESSO: {contador} oportunidades salvas via OpenAI ---")

            except Exception as e:
                print(f"ERRO NA OPENAI: {e}")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        
        return {"status": "Sucesso", "id": novo_diario.id}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        session = db_session()
        ops = session.query(Oportunidade).limit(50).all()
        return [{"id": o.id, "objeto": o.objeto_resumido, "valor": o.valor, "vencedor": o.favorecido} for o in ops]

if __name__ == '__main__':
    init_db()
    # MANTENHA A PORTA 8080 PARA O COOLIFY (Padrão)
    conf = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090, 
            'server.max_request_body_size': 100 * 1024 * 1024
        }
    }
    cherrypy.quickstart(GovTechAPI(), '/', conf)
