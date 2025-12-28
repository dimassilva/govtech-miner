import cherrypy
import os
import hashlib
from datetime import datetime
from database import init_db, db_session
from models import Diario, Oportunidade
from processor import PDFProcessor

class GovTechAPI:
    def __init__(self):
        self.processor = PDFProcessor()

    def calcular_hash(self, caminho_arquivo):
        sha256 = hashlib.sha256()
        with open(caminho_arquivo, "rb") as f:
            for bloco in iter(lambda: f.read(4096), b""):
                sha256.update(bloco)
        return sha256.hexdigest()

    @cherrypy.expose
    def index(self):
        return "Servidor GovTech Ativo. Use /oportunidades para ver os dados."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf, codigo, edicao, hash_origem, data_pub):
        """Recebe o PDF do Crawler, verifica duplicidade e processa."""
        session = db_session()
        
        # 1. Verifica duplicidade pelo ID da prefeitura (Mais rápido)
        existe = session.query(Diario).filter_by(codigo_origem=codigo).first()
        if existe:
            session.close()
            return {"status": "Ignorado", "msg": f"Edição {edicao} já processada."}

        # 2. Salva o arquivo
        if not os.path.exists('uploads'): os.makedirs('uploads')
        caminho_final = os.path.join('uploads', arquivo_pdf.filename)
        
        with open(caminho_final, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 3. Hash binário (Segurança extra)
        hash_bin = self.calcular_hash(caminho_final)

        try:
            # 4. Cria o Registro Pai (Diario)
            novo_diario = Diario(
                municipio="Lençóis Paulista",
                data_publicacao=datetime.strptime(data_pub, "%Y-%m-%d").date(),
                nome_arquivo=arquivo_pdf.filename,
                codigo_origem=int(codigo),
                numero_edicao=int(edicao),
                hash_origem=hash_origem,
                hash_arquivo_binario=hash_bin,
                processado=False
            )
            session.add(novo_diario)
            session.commit()

            # 5. Processamento IA
            texto = self.processor.extrair_texto_relevante(caminho_final)
            oportunidades = self.processor.analisar_com_ia(texto)

            # 6. Salva as Oportunidades (Filhos)
            contador = 0
            if oportunidades:
                for item in oportunidades:
                    nova_op = Oportunidade(
                        diario_id=novo_diario.id,
                        tipo=item.get('tipo', 'Outros'),
                        numero_processo=item.get('numero_processo', ''),
                        objeto_resumido=item.get('objeto', ''),
                        valor=float(item.get('valor', 0)),
                        favorecido=item.get('favorecido', ''),
                        prazo_vigencia=item.get('prazo', ''),
                        insight_venda=item.get('insight', '')
                    )
                    session.add(nova_op)
                    contador += 1
                
                novo_diario.processado = True
                session.commit()

            return {
                "status": "Sucesso", 
                "diario_id": novo_diario.id, 
                "ops_encontradas": contador
            }

        except Exception as e:
            session.rollback()
            return {"status": "Erro", "erro": str(e)}
        finally:
            session.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        """API para o Frontend consumir"""
        session = db_session()
        # Traz as 50 últimas
        ops = session.query(Oportunidade).join(Diario).order_by(Diario.data_publicacao.desc()).limit(50).all()
        lista = []
        for op in ops:
            lista.append({
                "id": op.id,
                "data": str(op.diario.data_publicacao),
                "edicao": op.diario.numero_edicao,
                "objeto": op.objeto_resumido,
                "valor": op.valor,
                "insight": op.insight_venda,
                "vencedor": op.favorecido
            })
        session.close()
        return lista

if __name__ == '__main__':
    init_db()
    conf = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090,
            'server.max_request_body_size': 100 * 1024 * 1024 # 100MB
        }
    }
    cherrypy.quickstart(GovTechAPI(), '/', conf)
