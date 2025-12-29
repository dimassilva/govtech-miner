import cherrypy
import os
import pdfplumber
import json
import re
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade, Usuario, Alerta, Favorito
from openai import OpenAI

# --- CONFIGURAÇÃO ---
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# ==========================================
# FERRAMENTA DE CORS (BLINDADA)
# ==========================================
def cors():
    # Permite acesso de qualquer origem (Frontend Vite/React)
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
def limpar_valor(valor_str):
    """Converte strings como 'R$ 1.200,50' ou '1.200,50' para float 1200.50"""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    try:
        # Remove R$, espaços e pontos de milhar
        limpo = str(valor_str).replace('R$', '').replace(' ', '').replace('.', '')
        # Troca vírgula decimal por ponto
        limpo = limpo.replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def verificar_status_real(status_ia, data_sessao_str):
    """O Python é o juiz final do tempo. A IA pode errar, o relógio não."""
    if not data_sessao_str:
        return status_ia
    
    try:
        # Tenta converter DD/MM/YYYY
        dt_sessao = datetime.strptime(data_sessao_str, "%d/%m/%Y")
        hoje = datetime.now()

        # Se a data já passou e o status ainda é 'Aberto', encerra.
        if dt_sessao < hoje and status_ia == 'Aberto':
            return 'Encerrado'
        return status_ia
    except:
        # Se a data vier bugada, confia no status da IA ou define como Informativo
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
# 3. API PRINCIPAL (Processamento IA)
# ==========================================
class GovTechAPI:
    usuarios = UsuarioController()
    keywords = KeywordController()
    favoritos = FavoritoController()

    @cherrypy.expose
    def index(self):
        return "GovTech API v9.0 (Data Logic Fix Applied)"

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        print(f"\n>>> PROCESSANDO EDICAO {edicao} ({data_pub})")
        session = db_session()

        # 1. Verifica duplicidade
        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            return {"status": "Ignorado", "msg": "Edição já processada."}

        # 2. Salva PDF temporário
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Registra Diário
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

        # 4. Extrai Texto
        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    texto += (page.extract_text() or "") + "\n"
        except Exception as e:
            print(f"Erro PDF: {e}")

        # 5. IA (PROMPT CORRIGIDO E BLINDADO)
        if len(texto) > 100:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            
            prompt = f"""
            ATUE COMO: Especialista em Licitações Públicas (B2G).
            CONTEXTO: Hoje é {hoje_str}. Analise o texto do Diário Oficial.
            
            REGRAS DE FILTRAGEM (CRÍTICO):
            1. IGNORE TOTALMENTE (Não retorne JSON para estes): 
               - "Processo Seletivo (Empregos/Estágio)"
               - "Concurso Público"
               - "Nomeações/Exonerações"
               - "Conselhos Municipais"
               - "Leis e Decretos Legislativos"
               - "Chamamento Público para ARTESÃOS, FEIRANTES ou PESSOAS FÍSICAS" (Isto não é B2G).
               - "Termo de Fomento" ou "Subvenção Social".

            2. CAPTURE APENAS VENDAS REAIS (B2G):
               - Aquisição de produtos, obras, serviços de engenharia, limpeza, TI, alimentação, etc.

            3. REGRAS DE STATUS:
               - "Aviso de Licitação" (Data futura) -> Status: "Aberto"
               - "Homologação/Adjudicação/Extrato" -> Status: "Contratado"
               - "Prorrogação/Aditivo" -> Status: "Renovação"
               - "Licitação Deserta/Fracassada" -> Status: "Fracassada"
               - "Suspensão" -> Status: "Suspenso"

            4. DATAS: Extraia a data da sessão no formato DD/MM/AAAA. Se houver intervalo, pegue a data FINAL.

            RETORNE UM JSON ARRAY:
            [
              {{
                "id_processo": "Pregão 90/2025",
                "categoria": "Obras",
                "objeto": "Resumo do que está sendo comprado",
                "valor": "1200.00" (Número ou 0),
                "vencedor": "Nome da Empresa ou 'Em Aberto'",
                "cnpj": "XX.XXX.XXX/0001-XX (ou VAZIO)",
                "data_sessao": "DD/MM/AAAA", 
                "status": "Aberto",
                "insight": "Frase estratégica"
              }}
            ]
            
            Texto para análise (Primeiros 15k caracteres):
            {texto[:15000]}
            """

            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                raw_json = resp.choices[0].message.content.strip()
                # Limpeza de markdown caso a IA mande ```json ... ```
                if "```" in raw_json:
                    raw_json = raw_json.replace("```json", "").replace("```", "")
                
                dados_ia = json.loads(raw_json)

                for item in dados_ia:
                    # 1. Limpeza de Valor
                    valor_float = limpar_valor(item.get('valor', 0))
                    
                    # 2. Correção Temporal (PYTHON SOBRESCREVE IA)
                    data_sessao_str = item.get('data_sessao', '')
                    status_final = verificar_status_real(item.get('status', 'Aberto'), data_sessao_str)
                    
                    insight_final = item.get('insight', '')
                    if status_final == 'Encerrado' and item.get('status') == 'Aberto':
                        insight_final = "Prazo expirado. Aguarde resultado."

                    op = Oportunidade(
                        diario_id=id_pai,
                        id_processo=item.get('id_processo', 'N/A'),
                        categoria=item.get('categoria', 'Geral'),
                        objeto=item.get('objeto', 'N/A')[:500], # Limite seguro
                        valor=valor_float,
                        vencedor=item.get('vencedor', 'Em Aberto'),
                        cnpj_vencedor=item.get('cnpj', ''),
                        data_sessao=data_sessao_str,
                        status=status_final,
                        insight_venda=insight_final
                    )
                    session.add(op)
                
                session.commit()
            except Exception as e:
                print(f"Erro IA/Parser: {e}")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        return {"status": "Processado", "id": id_pai}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self, status=None, categoria=None, municipio=None):
        if cherrypy.request.method == 'OPTIONS': return []
        session = db_session()
        
        query = session.query(Oportunidade).join(Diario)
        
        # Filtros
        if status and status not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.status == status)
        if categoria and categoria not in ['Todos', 'Todas']:
            query = query.filter(Oportunidade.categoria.like(f"%{categoria}%"))
        
        # Ordenação: Abertos primeiro, depois data de publicação
        ops = query.order_by(
            Oportunidade.status == 'Aberto', # True vem depois no MySQL? Depende. Melhor ordenar por data PUB.
            Diario.data_publicacao.desc()
        ).limit(100).all()

        lista = []
        for o in ops:
            # Link limpo para o frontend
            link_limpo = f"[https://lencois.mentor.metaway.com.br/recurso/diario/editar/](https://lencois.mentor.metaway.com.br/recurso/diario/editar/){o.diario.codigo_origem}"
            
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

# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == '__main__':
    init_db()
    
    conf = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090,
            'server.max_request_body_size': 100 * 1024 * 1024 # 100MB Upload
        },
        '/': { 'tools.cors.on': True },
        '/usuarios': { 'tools.cors.on': True },
        '/keywords': { 'tools.cors.on': True },
        '/favoritos': { 'tools.cors.on': True }
    }
    
    print("\n--- GOVTECH BACKEND INICIADO (PORTA 9090) ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)
