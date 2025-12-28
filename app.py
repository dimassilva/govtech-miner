import cherrypy
import os
import pdfplumber
import json
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade, Usuario, Alerta, Favorito
from openai import OpenAI

# --- IMPORTANTE: SUA CHAVE AQUI ---
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# ==========================================
# FERRAMENTA DE CORS (CORRIGIDA E BLINDADA)
# ==========================================
def cors():
    # Adiciona os headers em TODAS as respostas (Sucesso ou Erro)
    cherrypy.response.headers['Access-Control-Allow-Origin'] = '*'
    cherrypy.response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'

    # Se for OPTIONS (Pre-flight), encerra aqui com SUCESSO
    if cherrypy.request.method == 'OPTIONS':
        cherrypy.response.status = 200
        # Isso impede que o CherryPy tente executar o método 'login' ou 'register'
        # que quebraria por falta de JSON no body.
        return True

# Registra a ferramenta
cherrypy.tools.cors = cherrypy.Tool('before_handler', cors)

# ==========================================
# 1. CONTROLLER DE USUÁRIOS (/usuarios)
# ==========================================
class UsuarioController:
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        # Para requisições OPTIONS, não faz nada (o cors tool já resolveu)
        if cherrypy.request.method == 'OPTIONS': return {}

        data = cherrypy.request.json
        session = db_session()
        
        try:
            user = session.query(Usuario).filter_by(email=data.get('email')).first()
            if user and user.senha_hash == data.get('senha_hash'):
                response = {
                    "id": user.id,
                    "nome": user.nome,
                    "email": user.email,
                    "empresa_cnpj": user.empresa_cnpj,
                    "tema": user.tema
                }
                return response
            else:
                cherrypy.response.status = 401
                return {"message": "Email ou senha inválidos."}
        except Exception as e:
            cherrypy.response.status = 500
            return {"message": str(e)}
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
                return {"message": "Este e-mail já está cadastrado."}
            
            novo_user = Usuario(
                nome=data.get('nome'),
                email=data.get('email'),
                senha_hash=data.get('senha_hash'),
                empresa_cnpj=data.get('empresa_cnpj', None),
                tema='light'
            )
            session.add(novo_user)
            session.commit()
            
            response = {
                "id": novo_user.id,
                "nome": novo_user.nome,
                "email": novo_user.email,
                "tema": novo_user.tema
            }
            return response
        except Exception as e:
            cherrypy.response.status = 500
            return {"message": f"Erro ao criar conta: {str(e)}"}
        finally:
            session.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def default(self, id_usuario):
        if cherrypy.request.method == 'OPTIONS': return {}
        
        if cherrypy.request.method == 'DELETE':
            session = db_session()
            try:
                user = session.query(Usuario).filter_by(id=id_usuario).first()
                if user:
                    session.delete(user)
                    session.commit()
                    return {"status": "Conta excluída"}
                else:
                    cherrypy.response.status = 404
                    return {"message": "Usuário não encontrado"}
            finally:
                session.close()

# ==========================================
# 2. CONTROLLER DE KEYWORDS (/keywords)
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
                res = [{"id": a.id, "termo": a.termo} for a in alerts]
                return res
            
            elif cherrypy.request.method == 'POST':
                raw_body = cherrypy.request.body.read()
                if not raw_body: return []
                data = json.loads(raw_body)
                
                novo = Alerta(usuario_id=data['usuario_id'], termo=data['termo'])
                session.add(novo)
                session.commit()
                return {"status": "Adicionado", "termo": data['termo']}
                
            elif cherrypy.request.method == 'DELETE' and usuario_id and termo:
                alert = session.query(Alerta).filter_by(usuario_id=usuario_id, termo=termo).first()
                if alert:
                    session.delete(alert)
                    session.commit()
                return {"status": "Removido"}
        finally:
            session.close()

# ==========================================
# 3. CONTROLLER DE FAVORITOS (/favoritos)
# ==========================================
class FavoritoController:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self, usuario_id=None):
        if cherrypy.request.method == 'OPTIONS': return {}
        
        session = db_session()
        try:
            if cherrypy.request.method == 'GET' and usuario_id:
                favs = session.query(Favorito).join(Oportunidade).join(Diario)\
                              .filter(Favorito.usuario_id == usuario_id).all()
                lista = []
                for f in favs:
                    op = f.oportunidade
                    lista.append({
                        "id": op.id,
                        "processo": op.id_processo,
                        "objeto": op.objeto,
                        "valor": op.valor,
                        "status": op.status,
                        "municipio": op.diario.municipio,
                        "nota": f.notas_comerciais
                    })
                return lista
            
            elif cherrypy.request.method == 'POST':
                raw_body = cherrypy.request.body.read()
                data = json.loads(raw_body)
                uid = data['usuario_id']
                oid = data['oportunidade_id']
                nota = data.get('notas_comerciais', '')
                
                existente = session.query(Favorito).filter_by(usuario_id=uid, oportunidade_id=oid).first()
                if existente:
                    session.delete(existente)
                    msg = "Removido"
                else:
                    novo = Favorito(usuario_id=uid, oportunidade_id=oid, notas_comerciais=nota)
                    session.add(novo)
                    msg = "Adicionado"
                session.commit()
                return {"status": msg}
        finally:
            session.close()

# ==========================================
# 4. API PRINCIPAL (Root /)
# ==========================================
class GovTechAPI:
    usuarios = UsuarioController()
    keywords = KeywordController()
    favoritos = FavoritoController()

    @cherrypy.expose
    def index(self):
        return "API GovTech Gold (SaaS Ativo - v8 CORRIGIDA)."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        # (Código de Upload mantido igual ao anterior...)
        print(f"\n=== [DETETIVE] PROCESSANDO EDIÇÃO {edicao} ===")
        session = db_session()
        
        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            return {"status": "Ignorado", "msg": "Já existe."}

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
                    t = page.extract_text() or ""
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "PREGÃO", "CONTRATO", "ADITIVO", "RATIFICAÇÃO", "AVISO"]):
                        texto += t + "\n"
        except Exception as e:
            print(f"Erro ao ler PDF: {e}")

        if len(texto) > 50:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            prompt = f"""
            Analise o texto do Diário Oficial.
            CONTEXTO: Hoje é dia {hoje_str}.
            OBJETIVO: Extrair oportunidades comerciais reais.
            REGRAS DE OURO:
            1. IGNORAR REPASSES.
            2. ADITIVOS NÃO SÃO VENDAS (Status="Renovação").
            3. AVISOS DE LICITAÇÃO (Futuro="Aberto", Passado="Encerrado").
            4. RESULTADOS/CONTRATOS (Com CNPJ="Contratado").
            5. VALOR: Procure o valor total.
            
            Retorne JSON array: "id_processo", "categoria", "objeto", "valor" (float), "vencedor", "cnpj", "data_sessao", "status", "insight".
            Texto: {texto[:15000]}
            """
            
            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                conteudo = resp.choices[0].message.content.strip()
                if "```" in conteudo: 
                    conteudo = conteudo.replace("```json", "").replace("```", "")
                
                dados_ia = json.loads(conteudo)
                
                for item in dados_ia:
                    try:
                        val = float(item.get('valor', 0) if isinstance(item.get('valor'), (int, float, str)) else 0)
                        op = Oportunidade(
                            diario_id=id_pai,
                            id_processo=str(item.get('id_processo', 'N/A')),
                            categoria=str(item.get('categoria', 'Geral')),
                            objeto=str(item.get('objeto', 'N/A')),
                            valor=val,
                            vencedor=str(item.get('vencedor', 'Em Aberto')),
                            cnpj_vencedor=str(item.get('cnpj', '')),
                            data_sessao=str(item.get('data_sessao', '')),
                            prazo=str(item.get('prazo', '')),
                            status=str(item.get('status', 'Detectado')),
                            insight_venda=str(item.get('insight', ''))
                        )
                        session.add(op)
                    except Exception: pass
                session.commit()
            except Exception as e: print(f"ERRO OPENAI: {e}")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        return {"status": "Sucesso", "id": id_pai}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self, status=None, categoria=None, municipio=None, edicao=None):
        if cherrypy.request.method == 'OPTIONS': return []
        
        session = db_session()
        query = session.query(Oportunidade).join(Diario)
        
        if status and status not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.status == status)
        if categoria and categoria not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.categoria.like(f"%{categoria}%"))
        if municipio:
            query = query.filter(Diario.municipio == municipio)
        if edicao:
            query = query.filter(Diario.numero_edicao == edicao)

        ops = query.order_by(Diario.data_publicacao.desc()).limit(100).all()
        
        lista = []
        for o in ops:
            link_original = f"[https://lencois.mentor.metaway.com.br/recurso/diario/editar/](https://lencois.mentor.metaway.com.br/recurso/diario/editar/){o.diario.codigo_origem}"
            lista.append({
                "id": o.id,
                "municipio": o.diario.municipio,
                "data_publicacao": str(o.diario.data_publicacao),
                "link_documento": link_original,
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
    
    # CONFIGURAÇÃO DE CORS GLOBAL (CRUCIAL)
    conf = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090,
            'server.max_request_body_size': 100*1024*1024
        },
        '/': {
            'tools.cors.on': True  # Habilita a ferramenta que criamos
        },
        '/usuarios': {
            'tools.cors.on': True
        },
        '/keywords': {
            'tools.cors.on': True
        },
        '/favoritos': {
            'tools.cors.on': True
        }
    }
    print("--- API GOVTECH (CORS BLINDADO) RODANDO NA PORTA 9090 ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)
