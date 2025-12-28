import cherrypy
import os
import pdfplumber
import json
from datetime import datetime
from database import init_db, db_session, Diario, Oportunidade
from openai import OpenAI

# --- IMPORTANTE: SUA CHAVE AQUI ---
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

class GovTechAPI:
    @cherrypy.expose
    def index(self):
        return "API GovTech Gold (Porta 9090)."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        print(f"\n=== [DETETIVE] PROCESSANDO EDIÇÃO {edicao} ===")
        session = db_session()
        
        # 1. Verifica duplicidade
        if session.query(Diario).filter_by(codigo_origem=codigo).first():
            session.close()
            print("--- [DETETIVE] Ignorado: Já existe.")
            return {"status": "Ignorado", "msg": "Já existe."}

        # 2. Salva arquivo
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho = os.path.join('uploads', arquivo_pdf.filename)
        with open(caminho, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Cria Diário no Banco
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

        # 4. Extrai Texto (Com filtro amplo)
        texto = ""
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    # Filtro que pega tanto Compras (Passado) quanto Licitações (Futuro)
                    if any(x in t.upper() for x in ["DISPENSA", "LICITAÇÃO", "PREGÃO", "CONTRATO", "ADITIVO", "RATIFICAÇÃO", "AVISO"]):
                        texto += t + "\n"
            
            print(f"--- [DETETIVE] Caracteres extraídos: {len(texto)}")
        except Exception as e:
            print(f"Erro ao ler PDF: {e}")

        # 5. Inteligência Artificial (COM LÓGICA TEMPORAL CORRIGIDA)
        if len(texto) > 50:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            
            prompt = f"""
            Analise o texto do Diário Oficial.
            CONTEXTO: Hoje é dia {hoje_str}.
            
            OBJETIVO: Extrair oportunidades comerciais reais para fornecedores.
            
            REGRAS DE OURO (Siga estritamente):
            1. IGNORAR REPASSES: Se for "Termo de Fomento", "Subvenção", "Repasse" ou "Convênio" com ONG/Associação, defina Categoria="Repasse" e Status="Informativo".
            2. ADITIVOS NÃO SÃO VENDAS: Se for "Termo Aditivo", "Prorrogação de Contrato" ou "Supressão", o Status DEVE ser "Renovação" (nunca "Aberto"). O vencedor é a empresa citada.
            3. AVISOS DE LICITAÇÃO:
               - Se a data da sessão for FUTURA -> Status="Aberto".
               - Se a data JÁ PASSOU -> Status="Encerrado".
               - Vencedor -> "Em Aberto".
            4. RESULTADOS/CONTRATOS:
               - Se tiver CNPJ e Valor definidos -> Status="Contratado".
            5. VALOR: Esforce-se para encontrar o valor total (Global) ou estimado. Se for Registro de Preços, procure o valor total da ata.
            
            Retorne JSON array:
            - "id_processo": (Ex: "Pregão 90/2025", "Aditivo 01/24")
            - "categoria": (Ex: "Limpeza", "Obras", "TI", "Repasse")
            - "objeto": (Resumo claro do que é)
            - "valor": (Float. Se não achar, 0)
            - "vencedor": (Nome da empresa. Se for Aviso, "Em Aberto")
            - "cnpj": (CNPJ ou null)
            - "data_sessao": (Data da disputa DD/MM/AAAA HH:MM. Se for contrato, null)
            - "status": ("Aberto", "Encerrado", "Contratado", "Renovação", "Informativo")
            - "insight": (Dica curta. Ex: "Renovação de contrato por 12 meses" ou "Oportunidade nova! Prepare documentação")

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
                print(f"--- [DETETIVE] IA encontrou {len(dados_ia)} itens.")
                
                contador = 0
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
                            data_sessao=str(item.get('data_sessao', '')), # CAMPO NOVO
                            prazo=str(item.get('prazo', '')),
                            status=str(item.get('status', 'Detectado')),
                            insight_venda=str(item.get('insight', ''))
                        )
                        session.add(op)
                        contador += 1
                    except Exception as ex:
                        print(f"Erro ao salvar item: {ex}")

                session.commit()
                print(f"--- [SUCESSO] {contador} oportunidades salvas! ---")

            except Exception as e:
                print(f"ERRO OPENAI: {e}")

        session.close()
        if os.path.exists(caminho): os.remove(caminho)
        return {"status": "Sucesso", "id": id_pai}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    # 1. Adicionamos 'edicao' na lista de parâmetros aceitos
    def oportunidades(self, status=None, categoria=None, municipio=None, edicao=None):
        session = db_session()
        
        # Inicia a query ligando Oportunidade e Diário
        query = session.query(Oportunidade).join(Diario)
        
        # --- BLOCO DE FILTROS ---
        
        # Filtro de Status
        if status:
            query = query.filter(Oportunidade.status == status)
            
        # Filtro de Categoria (Busca parcial)
        if categoria:
            query = query.filter(Oportunidade.categoria.like(f"%{categoria}%"))
            
        # Filtro de Município
        if municipio:
            query = query.filter(Diario.municipio == municipio)
            
        # [NOVO] Filtro de Edição
        if edicao:
            # O número vem como string da URL, o banco converte automático ou usamos int()
            query = query.filter(Diario.numero_edicao == edicao)

        # ------------------------

        # Ordena e limita
        ops = query.order_by(Diario.data_publicacao.desc()).limit(50).all()
        
        lista = []
        for o in ops:
            link_original = f"https://lencois.mentor.metaway.com.br/recurso/diario/editar/{o.diario.codigo_origem}"

            lista.append({
                "id": o.id,
                "municipio": o.diario.municipio,
                "data_publicacao": str(o.diario.data_publicacao),
                "link_documento": link_original,
                "edicao": o.diario.numero_edicao, # O número da edição
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
    # RODANDO NA PORTA 9090
    conf = {'global': {'server.socket_host': '0.0.0.0', 'server.socket_port': 9090, 'server.max_request_body_size': 100*1024*1024}}
    print("--- API GOVTECH INICIADA NA PORTA 9090 ---")
    cherrypy.quickstart(GovTechAPI(), '/', conf)
