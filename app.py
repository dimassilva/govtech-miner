import cherrypy
import os
import pdfplumber
import json
from datetime import datetime
from database import init_db, db_session
from models import Diario, Oportunidade
from openai import OpenAI

# --- PASSO 1: COLE SUA NOVA CHAVE AQUI DENTRO DAS ASPAS ---
MINHA_CHAVE_OPENAI = "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" 

# Inicializa cliente
client = OpenAI(api_key=MINHA_CHAVE_OPENAI)

class GovTechAPI:
    @cherrypy.expose
    def index(self):
        return "API GovTech Online (v4 - MODO DETETIVE ATIVO)."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        print(f"\n=== [DETETIVE] INICIANDO UPLOAD: Edição {edicao} (Cód: {codigo}) ===")
        session = db_session()
        
        # 1. Verifica duplicidade
        existe = session.query(Diario).filter_by(codigo_origem=codigo).first()
        if existe:
            print(f"--- [DETETIVE] Ignorado: Já existe no banco com ID {existe.id}")
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
        print(f"--- [DETETIVE] Arquivo salvo em disco: {caminho}")

        # 3. Cria registro no Banco
        try:
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
            
            # Salvamos o ID numa variável agora
            id_gerado = novo_diario.id 
            print(f"--- [DETETIVE] Diario criado no banco. ID Gerado: {id_gerado}")
        except Exception as e:
            print(f"!!! [ERRO CRÍTICO] Falha ao criar Diario no banco: {e}")
            return {"status": "Erro Banco", "msg": str(e)}

        # 4. Extrai Texto
        texto = ""
        try:
            print("--- [DETETIVE] Iniciando leitura do PDF (pdfplumber)...")
            with pdfplumber.open(caminho) as pdf:
                total_paginas = len(pdf.pages)
                print(f"--- [DETETIVE] PDF tem {total_paginas} páginas.")
                
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text() or ""
                    
                    # LOG DE DIAGNÓSTICO DE TEXTO
                    if i == 0:
                        print(f"   > [Amostra Pág 1]: {t[:50]}...")
                    
                    # Filtro de palavras-chave
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "CONTRATAÇÃO", "ADITIVO"]):
                        texto += t + "\n"
                        # print(f"   > [Pág {i+1}] Conteúdo relevante encontrado.")
                    
            print(f"--- [DETETIVE] Total de caracteres FILTRADOS para enviar à IA: {len(texto)}")
            
            if len(texto) < 50:
                print("!!! [ALERTA VERMELHO] O texto está vazio ou muito curto!")
                print("!!! MOTIVOS POSSÍVEIS:")
                print("    1. O PDF é uma imagem (scan) e precisa de OCR.")
                print("    2. As palavras-chave (DISPENSA, LICITAÇÃO...) não foram encontradas.")

        except Exception as e:
            print(f"!!! [ERRO] Falha ao ler PDF: {e}")

        # 5. Chama a IA
        if len(texto) > 50:
            print("--- [DETETIVE] Enviando prompt para OpenAI...")
            prompt = f"""
            Analise o texto. Extraia licitações.
            Retorne JSON array puro: "objeto", "valor" (float), "favorecido", "prazo", "insight".
            Texto: {texto[:15000]}
            """
            
            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                conteudo = resp.choices[0].message.content.strip()
                print(f"--- [DETETIVE] Resposta BRUTA da IA: {conteudo[:200]}...") # Mostra o começo da resposta
                
                if conteudo.startswith("```"): 
                    conteudo = conteudo.replace("```json", "").replace("```", "")
                
                try:
                    dados_ia = json.loads(conteudo)
                    print(f"--- [DETETIVE] JSON parseado com sucesso. Itens: {len(dados_ia)}")
                except json.JSONDecodeError as json_err:
                    print(f"!!! [ERRO JSON] A IA não retornou um JSON válido: {json_err}")
                    dados_ia = []

                contador_sucesso = 0
                for item in dados_ia:
                    try:
                        val = item.get('valor', 0)
                        if isinstance(val, str): val = 0 
                        
                        op = Oportunidade(
                            diario_id=id_gerado,
                            tipo="Detectado IA",
                            objeto_resumido=str(item.get('objeto', 'N/A')),
                            valor=float(val),
                            favorecido=str(item.get('favorecido', 'N/A')),
                            prazo_vigencia=str(item.get('prazo', 'N/A')),
                            insight_venda=str(item.get('insight', ''))
                        )
                        session.add(op)
                        contador_sucesso += 1
                        print(f"   > Item salvo: {item.get('objeto')[:30]}...")
                    except Exception as e_item:
                        print(f"   ! [ERRO ITEM] Falha ao salvar oportunidade específica: {e_item}")
                
                session.commit()
                print(f"=== [SUCESSO FINAL] {contador_sucesso} oportunidades gravadas no banco! ===")

            except Exception as e:
                print(f"!!! [ERRO NA OPENAI]: {e}")
        else:
            print("--- [DETETIVE] Pulando IA (texto insuficiente).")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        
        return {"status": "Sucesso", "id": id_gerado}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        session = db_session()
        ops = session.query(Oportunidade).limit(50).all()
        return [{"id": o.id, "objeto": o.objeto_resumido, "valor": o.valor, "vencedor": o.favorecido} for o in ops]

if __name__ == '__main__':
    init_db()
    # Mantive a porta 9090 conforme seu código original
    conf = {'global': {'server.socket_host': '0.0.0.0', 'server.socket_port': 9090, 'server.max_request_body_size': 100*1024*1024}}
    print("--- SERVIDOR INICIADO NA PORTA 9090 (MODO DETETIVE) ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)
