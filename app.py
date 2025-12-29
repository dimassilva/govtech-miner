import cherrypy
import os
import pdfplumber
import json
import re
import time # <--- IMPORTANTE PARA ESPERAR
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade, Usuario, Alerta, Favorito

# --- IMPORT DA NOVA BIBLIOTECA DO GOOGLE ---
from google import genai
from google.genai import types

# --- CONFIGURAÇÃO GEMINI ---
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# ==========================================
# FERRAMENTA DE CORS (BLINDADA)
# ==========================================
def cors():
    cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
    cherrypy.response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'

    if cherrypy.request.method == 'OPTIONS':
        cherrypy.response.status = 200
        return True

cherrypy.tools.cors = cherrypy.Tool('before_handler', cors)

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def limpar_valor(valor):
    """
    Converte inteligentemente formatos BR (1.000,00) e US (1000.00) para float.
    """
    if isinstance(valor, (int, float)):
        return float(valor)
    
    if not valor:
        return 0.0

    v = str(valor).strip().replace('R$', '').strip()
    
    try:
        # Se tiver vírgula, assumimos formato BR (ex: 1.200,50 ou 90,00)
        if ',' in v:
            v = v.replace('.', '')  # Remove ponto de milhar
            v = v.replace(',', '.') # Troca vírgula por ponto decimal
        # Se NÃO tiver vírgula e tiver ponto, assumimos formato US/IA (ex: 90.00)
        # Nesse caso, não removemos o ponto, pois ele é decimal!
        
        return float(v)
    except:
        return 0.0

def verificar_status_real(status_ia, data_sessao_str):
    if not data_sessao_str:
        return status_ia
    try:
        dt_sessao = datetime.strptime(data_sessao_str, "%d/%m/%Y")
        hoje = datetime.now()
        if dt_sessao < hoje and status_ia == 'Aberto':
            return 'Encerrado'
        return status_ia
    except:
        return status_ia

# ==========================================
# 1. CONTROLLER DE USUÁRIOS
# ==========================================
class UsuarioController:
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        if cherrypy.request.method == 'OPTIONS': return {}
        data = cherrypy.request.json
        session = db_session()
        try:
            user = session.query(Usuario).filter_by(email=data.get('email')).first()
            if user and user.senha_hash == data.get('senha_hash'):
                return {
                    "id": user.id,
                    "nome": user.nome,
                    "email": user.email,
                    "empresa_cnpj": user.empresa_cnpj,
                    "tema": user.tema
                }
            cherrypy.response.status = 401
            return {"message": "Email ou senha inválidos."}
        finally:
            session.close()

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        if cherrypy.request.method == 'OPTIONS': return {}
        data = cherrypy.request.json
        session = db_session()
        try:
            if session.query(Usuario).filter_by(email=data.get('email')).first():
                cherrypy.response.status = 409
                return {"message": "E-mail já cadastrado."}
            
            novo_user = Usuario(
                nome=data.get('nome'),
                email=data.get('email'),
                senha_hash=data.get('senha_hash'),
                empresa_cnpj=data.get('empresa_cnpj'),
                tema='light'
            )
            session.add(novo_user)
            session.commit()
            return {"id": novo_user.id, "nome": novo_user.nome}
        except Exception as e:
            cherrypy.response.status = 500
            return {"message": str(e)}
        finally:
            session.close()

# ==========================================
# 2. CONTROLLER DE KEYWORDS & FAVORITOS
# ==========================================
class KeywordController:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self, usuario_id=None, termo=None):
        if cherrypy.request.method == 'OPTIONS': return {}
        session = db_session()
        try:
            if cherrypy.request.method == 'GET' and usuario_id:
                alerts = session.query(Alerta).filter_by(usuario_id=usuario_id).all()
                return [{"id": a.id, "termo": a.termo} for a in alerts]
            elif cherrypy.request.method == 'POST':
                data = json.loads(cherrypy.request.body.read())
                session.add(Alerta(usuario_id=data['usuario_id'], termo=data['termo']))
                session.commit()
                return {"status": "ok"}
            elif cherrypy.request.method == 'DELETE':
                session.query(Alerta).filter_by(usuario_id=usuario_id, termo=termo).delete()
                session.commit()
                return {"status": "deleted"}
        finally:
            session.close()

class FavoritoController:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self, usuario_id=None):
        if cherrypy.request.method == 'OPTIONS': return {}
        session = db_session()
        try:
            if cherrypy.request.method == 'GET':
                favs = session.query(Favorito).join(Oportunidade).filter(Favorito.usuario_id == usuario_id).all()
                return [{
                    "id": f.oportunidade.id,
                    "processo": f.oportunidade.id_processo,
                    "objeto": f.oportunidade.objeto,
                    "valor": f.oportunidade.valor,
                    "status": f.oportunidade.status
                } for f in favs]
            elif cherrypy.request.method == 'POST':
                data = json.loads(cherrypy.request.body.read())
                uid, oid = data['usuario_id'], data['oportunidade_id']
                existente = session.query(Favorito).filter_by(usuario_id=uid, oportunidade_id=oid).first()
                if existente:
                    session.delete(existente)
                    msg = "removido"
                else:
                    session.add(Favorito(usuario_id=uid, oportunidade_id=oid))
                    msg = "adicionado"
                session.commit()
                return {"status": msg}
        finally:
            session.close()

# ==========================================
# 3. API PRINCIPAL (COM RETRY AUTOMÁTICO)
# ==========================================
class GovTechAPI:
    usuarios = UsuarioController()
    keywords = KeywordController()
    favoritos = FavoritoController()

    @cherrypy.expose
    def index(self):
        return "GovTech API v9.5 (Auto-Retry Enabled)"

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        print(f"\n>>> PROCESSANDO EDICAO {edicao} ({data_pub})")
        session = db_session()

        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            return {"status": "Ignorado", "msg": "Edição já processada."}

        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

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
        id_pai = novo_diario.id

        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    texto += (page.extract_text() or "") + "\n"
        except Exception as e:
            print(f"Erro PDF: {e}")

        # 5. IA (COM LOOP DE RETENTATIVA)
        if len(texto) > 100:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            
            prompt = f"""
            ATUE COMO: Especialista em Licitações Públicas (B2G).
            CONTEXTO: Hoje é {hoje_str}. Analise o texto do Diário Oficial.
            
            REGRAS DE FILTRAGEM (CRÍTICO):
            1. IGNORE TOTALMENTE: 
               - "Processo Seletivo", "Concurso Público", "Nomeações", "Conselhos", "Leis".
               - "Chamamento Público para ARTESÃOS/FEIRANTES".
               - Tabelas dentro de "DECRETOS DE SUPLEMENTAÇÃO".

            2. CAPTURE APENAS VENDAS REAIS (B2G):
               - Aquisição de produtos, obras, serviços, TI, etc.

            3. REGRAS DE STATUS:
               - "Aviso de Licitação" (Futuro) -> "Aberto"
               - "Homologação/Extrato" -> "Contratado"
               - "Aditivo" -> "Renovação"
               - "Deserta/Fracassada" -> "Fracassada"

            4. DATAS: Extraia DD/MM/AAAA.

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

            # --- LÓGICA DE RETRY (Blindagem contra erro 429) ---
            max_tentativas = 3
            for tentativa in range(max_tentativas):
                try:
                    print(f"   > Enviando para IA (Tentativa {tentativa+1}/{max_tentativas})...")
                    
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-001', 
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type='application/json',
                            temperature=0.1
                        )
                    )
                    
                    raw_json = response.text
                    dados_ia = json.loads(raw_json)

                    # Se chegou aqui, deu certo! Processa e sai do loop
                    for item in dados_ia:
                        valor_float = limpar_valor(item.get('valor', 0))
                        data_sessao_str = item.get('data_sessao', '')
                        status_final = verificar_status_real(item.get('status', 'Aberto'), data_sessao_str)
                        
                        insight_final = item.get('insight', '')
                        if status_final == 'Encerrado' and item.get('status') == 'Aberto':
                            insight_final = "Prazo expirado. Aguarde resultado."

                        op = Oportunidade(
                            diario_id=id_pai,
                            id_processo=item.get('id_processo', 'N/A'),
                            categoria=item.get('categoria', 'Geral'),
                            objeto=item.get('objeto', 'N/A')[:500],
                            valor=valor_float,
                            vencedor=item.get('vencedor', 'Em Aberto'),
                            cnpj_vencedor=item.get('cnpj', ''),
                            data_sessao=data_sessao_str,
                            status=status_final,
                            insight_venda=insight_final
                        )
                        session.add(op)
                    
                    session.commit()
                    print("   > Sucesso na IA!")
                    break # Sai do loop de tentativas

                except Exception as e:
                    erro_msg = str(e)
                    # Verifica se é erro de cota (429)
                    if "429" in erro_msg or "RESOURCE_EXHAUSTED" in erro_msg:
                        print(f"   >>> COTA EXCEDIDA (429). Esperando 30 segundos...")
                        time.sleep(60) # Espera 30s e tenta de novo
                    else:
                        print(f"   >>> Erro fatal na IA: {e}")
                        break # Se for outro erro, não adianta tentar de novo

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        return {"status": "Processado", "id": id_pai}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self, status=None, categoria=None, municipio=None):
        if cherrypy.request.method == 'OPTIONS': return []
        session = db_session()
        
        query = session.query(Oportunidade).join(Diario)
        
        if status and status not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.status == status)
        if categoria and categoria not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.categoria.like(f"%{categoria}%"))
        
        ops = query.order_by(
            Oportunidade.status == 'Aberto', 
            Diario.data_publicacao.desc()
        ).limit(100).all()

        lista = []
        for o in ops:
            link_limpo = f"https://lencois.mentor.metaway.com.br/recurso/diario/editar/{o.diario.codigo_origem}"
            lista.append({
                "id": o.id,
                "municipio": o.diario.municipio,
                "data_publicacao": str(o.diario.data_publicacao),
                "link_documento": link_limpo,
                "edicao": o.diario.numero_edicao,
                "processo": o.id_processo,
                "categoria": o.categoria,
                "objeto": o.objeto,
                "valor": o.valor,
                "vencedor": o.vencedor,
                "cnpj": o.cnpj_vencedor,
                "status": o.status,
                "data_sessao": o.data_sessao,
                "insight": o.insight_venda
            })
        
        session.close()
        return lista

if __name__ == '__main__':
    init_db()
    conf = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090,
            'server.max_request_body_size': 100 * 1024 * 1024
        },
        '/': { 'tools.cors.on': True },
        '/usuarios': { 'tools.cors.on': True },
        '/keywords': { 'tools.cors.on': True },
        '/favoritos': { 'tools.cors.on': True }
    }
    print("\n--- GOVTECH BACKEND (COM AUTO-RETRY 429) RODANDO ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)
