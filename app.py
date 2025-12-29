import cherrypy
import os
import json
import time
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade, Usuario, Alerta, Favorito

# --- IMPORTA OS PROCESSADORES ---
# Certifique-se de que a pasta 'processors' tem um arquivo vazio __init__.py
from processors.lencois import LencoisProcessor
from processors.bauru import BauruProcessor

# Inicializa os processadores (Fábrica)
bot_lencois = LencoisProcessor()
bot_bauru = BauruProcessor()

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
# 3. API PRINCIPAL (MODULARIZADA)
# ==========================================
class GovTechAPI:
    usuarios = UsuarioController()
    keywords = KeywordController()
    favoritos = FavoritoController()

    @cherrypy.expose
    def index(self):
        return "GovTech API v11.0 (Modular Multi-City)"

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub, municipio="Lençóis Paulista"):
        # Nota: 'municipio' tem valor padrão. Se o worker não enviar, assume Lençóis.
        
        print(f"\n>>> RECEBIDO: {municipio.upper()} - ED. {edicao}")
        session = db_session()

        # 1. Verifica duplicidade (Considerando município agora)
        if session.query(Diario).filter_by(codigo_origem=codigo, municipio=municipio).first():
            session.close()
            return {"status": "Ignorado", "msg": "Edição já processada."}

        # 2. Salva PDF Temporário
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Registra Diario no Banco
        novo_diario = Diario(
            municipio=municipio,
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
        session.close()

        # 4. CHAMA O ESPECIALISTA CERTO (Strategy Pattern)
        try:
            # Se for Bauru (case insensitive), chama o bot de Bauru
            if "bauru" in municipio.lower():
                bot_bauru.executar(caminho, id_pai)
            else:
                # Padrão: Lençóis Paulista
                bot_lencois.executar(caminho, id_pai)
                
        except Exception as e:
            print(f"   > [ERRO CRÍTICO] Falha no processamento: {e}")

        # Limpeza
        if os.path.exists(caminho): os.remove(caminho)
        return {"status": "Processado", "id": id_pai, "cidade": municipio}

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
        
        # Filtro por Município (Novo)
        if municipio:
            query = query.filter(Diario.municipio == municipio)
        
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
    print("\n--- GOVTECH BACKEND (MODULAR v11) RODANDO ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)