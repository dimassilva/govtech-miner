import time
import schedule
import requests
import base64
import os
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings()

# No Coolify, a URL vem da configuração. Se não tiver, usa localhost.
API_URL = os.getenv("API_URL", "http://a0okwgosoc4oookw8s40cwco.104.168.4.3.sslip.io/upload")

def buscar_diarios():
    print(f"--- INICIANDO BUSCA DE DIÁRIOS (Enviando para {API_URL}) ---")
    
    # Busca dinâmica: Últimos 5 dias até hoje
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=5)
    
    params = {
        "dataInicial": data_inicial.strftime("%Y-%m-%dT00:00:00"),
        "dataFinal": data_final.strftime("%Y-%m-%dT00:00:00")
    }
    
    try:
        url_lista = "https://lencois.mentor.metaway.com.br/recurso/diario/lista"
        resp = requests.get(url_lista, params=params, verify=False)
        itens = resp.json()
        print(f"Encontrados: {len(itens)}")

        for item in itens:
            codigo = item['codigo']
            # Verifica detalhe para pegar PDF Base64
            r_detalhe = requests.get(f"https://lencois.mentor.metaway.com.br/recurso/diario/editar/{codigo}", verify=False)
            b64 = r_detalhe.json().get('arquivoPdf')
            
            if b64:
                nome_arq = f"diario_{codigo}.pdf"
                with open(nome_arq, "wb") as f:
                    f.write(base64.b64decode(b64))
                
                # ENVIA PARA A API (APP.PY)
                try:
                    with open(nome_arq, 'rb') as f_send:
                        files = {'arquivo_pdf': (nome_arq, f_send, 'application/pdf')}
                        data = {
                            'codigo': str(codigo),
                            'edicao': str(item['edicao']),
                            'hash_origem': item.get('hash', ''),
                            'data_pub': item['dataPublicacao'].split('T')[0]
                        }
                        # Timeout maior para garantir que a IA processe
                        requests.post(API_URL, files=files, data=data, timeout=120)
                        print(f"Enviado código {codigo} para API.")
                except Exception as e:
                    print(f"Erro ao enviar para API: {e}")
                
                if os.path.exists(nome_arq):
                    os.remove(nome_arq) # Limpa disco

    except Exception as e:
        print(f"Erro no Worker: {e}")

# --- AGENDAMENTO DO ROBÔ ---
# Roda imediatamente ao ligar
buscar_diarios()

# Agenda para rodar a cada 6 horas
schedule.every(6).hours.do(buscar_diarios)

# Loop Infinito (Necessário para o Coolify não matar o processo)
while True:
    schedule.run_pending()
    time.sleep(60)
