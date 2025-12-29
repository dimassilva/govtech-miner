import os
import json
import time
import sys
from datetime import datetime
from google import genai
from google.genai import types

# Garante que o Python encontre o database.py na pasta raiz
# Adiciona o diretório pai (raiz do projeto) ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa do arquivo database.py que está na raiz
from database import db_session, Oportunidade

class BaseProcessor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("AVISO: GEMINI_API_KEY não encontrada nas variáveis de ambiente.")
        self.client = genai.Client(api_key=self.api_key)

    def limpar_valor(self, valor):
        """
        Converte inteligentemente formatos BR (1.000,00) e US (1000.00) para float.
        """
        if isinstance(valor, (int, float)):
            return float(valor)
        
        if not valor:
            return 0.0

        v = str(valor).strip().replace('R$', '').replace(' ', '')
        
        try:
            # Lógica de detecção de formato:
            # Se tem vírgula, é BR (Ex: 1.000,00 -> tira ponto, troca vírgula)
            if ',' in v:
                v = v.replace('.', '')
                v = v.replace(',', '.')
            # Se só tem ponto, é US ou IA (Ex: 1000.00 ou 90.00 -> mantém o ponto)
            
            return float(v)
        except:
            return 0.0

    def verificar_status(self, status_ia, data_sessao_str):
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
            # Se a data vier bugada, confia no status da IA
            return status_ia

    def salvar_banco(self, diario_id, dados_ia):
        session = db_session()
        try:
            itens_salvos = 0
            for item in dados_ia:
                valor_float = self.limpar_valor(item.get('valor', 0))
                data_sessao_str = item.get('data_sessao', '')
                status_final = self.verificar_status(item.get('status', 'Aberto'), data_sessao_str)
                
                insight_final = item.get('insight', '')
                if status_final == 'Encerrado' and item.get('status') == 'Aberto':
                    insight_final = "Prazo expirado. Aguarde resultado."

                op = Oportunidade(
                    diario_id=diario_id,
                    id_processo=item.get('id_processo', 'N/A'),
                    categoria=item.get('categoria', 'Geral'),
                    objeto=item.get('objeto', 'N/A')[:1000], # Limite seguro para o banco
                    valor=valor_float,
                    vencedor=item.get('vencedor', 'Em Aberto'),
                    cnpj_vencedor=item.get('cnpj', ''),
                    data_sessao=data_sessao_str,
                    status=status_final,
                    prazo=item.get('prazo', ''),
                    localizacao=item.get('localizacao', ''),
                    insight_venda=insight_final
                )
                session.add(op)
                itens_salvos += 1
            
            session.commit()
            print(f"   > [DB] Sucesso! {itens_salvos} oportunidades registradas.")
        except Exception as e:
            print(f"   > [ERRO DB] Falha ao salvar no banco: {e}")
            session.rollback()
        finally:
            session.close()

    def processar_ia(self, texto, prompt_sistema):
        """
        Envia para o Gemini com lógica de Retry Exponencial (Backoff)
        """
        max_tentativas = 2
        
        # Concatena o Prompt do Sistema com o Texto do PDF
        conteudo_completo = f"{prompt_sistema}\n\n=== TEXTO DO DIÁRIO OFICIAL ===\n{texto[:500000]}"

        for tentativa in range(max_tentativas):
            try:
                print(f"   > Gemini IA (Tentativa {tentativa+1}/{max_tentativas})...")
                
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001', 
                    contents=conteudo_completo,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        temperature=0.1
                    )
                )
                print(f"DEBUG IA RAW: {response.text}")
                
                return json.loads(response.text)

            except Exception as e:
                erro_msg = str(e)
                # Verifica erros de cota (429)
                if "429" in erro_msg or "RESOURCE_EXHAUSTED" in erro_msg:
                    tempo_espera = 30 * (2 ** tentativa) # 30s, 60s, 120s, 240s
                    print(f"   >>> COTA EXCEDIDA (429). Esperando {tempo_espera} segundos...")
                    time.sleep(tempo_espera)
                else:
                    print(f"   >>> Erro Fatal IA: {e}")
                    return [] # Retorna lista vazia em caso de erro fatal
        
        return [] # Retorna vazio se esgotar tentativas
