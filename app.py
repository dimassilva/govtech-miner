import cherrypy
import os
from database import init_db, db_session
from models import Diario, Oportunidade
from processor import PDFProcessor
from datetime import date

class GovTechAPI:
    def __init__(self):
        self.processor = PDFProcessor()

    @cherrypy.expose
    def index(self):
        return "GovTech API Online - Use /upload para enviar Diários."

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload(self, arquivo_pdf):
        # 1. Salvar arquivo localmente
        upload_path = os.path.join('uploads', arquivo_pdf.filename)
        with open(upload_path, 'wb') as out:
            while True:
                data = arquivo_pdf.file.read(8192)
                if not data: break
                out.write(data)

        # 2. Registrar no Banco
        session = db_session()
        novo_diario = Diario(
            municipio="Lençóis Paulista", # Em prod, viria do form
            data_publicacao=date.today(),
            nome_arquivo=arquivo_pdf.filename
        )
        session.add(novo_diario)
        session.commit()

        # 3. Processar (Isso poderia ser async/background task no futuro)
        texto_filtrado = self.processor.extrair_texto_relevante(upload_path)
        dados_ia = self.processor.analisar_com_ia(texto_filtrado)

        # 4. Salvar Oportunidades
        oportunidades_salvas = 0
        for item in dados_ia:
            nova_op = Oportunidade(
                diario_id=novo_diario.id,
                tipo=item.get('tipo'),
                numero_processo=item.get('numero_processo'),
                objeto_resumido=item.get('objeto'),
                valor=item.get('valor'),
                favorecido=item.get('favorecido'),
                prazo_vigencia=item.get('prazo'),
                insight_venda=item.get('insight')
            )
            session.add(nova_op)
            oportunidades_salvas += 1
        
        novo_diario.processado = True
        session.commit()
        session.close()

        return {
            "status": "Sucesso",
            "diario_id": novo_diario.id,
            "oportunidades_encontradas": oportunidades_salvas,
            "dados": dados_ia
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def oportunidades(self):
        # Endpoint para seu Frontend React consumir
        session = db_session()
        ops = session.query(Oportunidade).all()
        lista = []
        for op in ops:
            lista.append({
                "id": op.id,
                "objeto": op.objeto_resumido,
                "valor": op.valor,
                "insight": op.insight_venda
            })
        session.close()
        return lista

if __name__ == '__main__':
    # Inicializa banco
    init_db()
    
    # Configuração CherryPy
    config = {
        'global': {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': 9090,
            'server.thread_pool': 10  # Importante para uploads
        }
    }
    
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
        
    cherrypy.quickstart(GovTechAPI(), '/', config)
