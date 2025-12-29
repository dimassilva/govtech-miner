import time
import schedule
import requests
import base64
import os
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings()

# Aponta para a API (ajuste o IP se necessário)
API_URL = os.getenv("API_URL", "http://a0okwgosoc4oookw8s40cwco.104.168.4.3.sslip.io/upload")

def job_lencois():
    print(f"\n[{datetime.now().strftime('%H:%M')}] ROBÔ LENÇÓIS INICIADO...")
    
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=59)
    
    params = {
        "dataInicial": data_inicial.strftime("%Y-%m-%dT00:00:00"),
        "dataFinal": data_final.strftime("%Y-%m-%dT00:00:00")
    }
    
    try:
        url_lista = "https://lencois.mentor.metaway.com.br/recurso/diario/lista"
        resp = requests.get(url_lista, params=params, verify=False)
        itens = resp.json()
        total = len(itens)
        print(f"--- ENCONTRADOS {total} DIÁRIOS (LENÇÓIS) ---")

        for i, item in enumerate(itens):
            codigo = item['codigo']
            edicao = item['edicao']
            
            print(f"\n[LENÇÓIS {i+1}/{total}] Edição {edicao} (Cód {codigo})...")
            
            try:
                r_detalhe = requests.get(f"https://lencois.mentor.metaway.com.br/recurso/diario/editar/{codigo}", verify=False, timeout=30)
                b64 = r_detalhe.json().get('arquivoPdf')
                
                if b64:
                    nome_arq = f"lencois_{codigo}.pdf"
                    with open(nome_arq, "wb") as f:
                        f.write(base64.b64decode(b64))

                    with open(nome_arq, 'rb') as f_send:
                        files = {'arquivo_pdf': (nome_arq, f_send, 'application/pdf')}
                        payload = {
                            'codigo': str(codigo),
                            'edicao': str(edicao),
                            'hash_origem': item.get('hash', ''),
                            'data_pub': item['dataPublicacao'].split('T')[0],
                            'municipio': 'Lençóis Paulista' # IMPORTANTE
                        }
                        
                        r = requests.post(API_URL, files=files, data=payload, timeout=300)
                        
                        if r.status_code == 200:
                            resp_api = r.json()
                            if resp_api.get('status') == 'Ignorado':
                                print(f"   [PULOU] Já processado.")
                                time.sleep(1)
                            else:
                                print(f"   [SUCESSO] Processado! ID: {resp_api.get('id')}")
                                print("   ... Resfriando motor (120s) ...")
                                time.sleep(120) 
                        else:
                            print(f"   [ERRO API] Código {r.status_code}")
                            time.sleep(5)
                    
                    if os.path.exists(nome_arq): os.remove(nome_arq)
                else:
                    print("   [AVISO] Sem PDF.")

            except Exception as e_item:
                print(f"   [FALHA NO ITEM] {e_item}")
                time.sleep(2)

    except Exception as e:
        print(f"Erro Geral Lençóis: {e}")

def job_bauru():
    # Placeholder para quando você implementar o scraper de Bauru
    print(f"\n[{datetime.now().strftime('%H:%M')}] ROBÔ BAURU (Aguardando implementação do crawler)...")
    pass

# Executa Lençóis agora
job_lencois()

# Agenda
schedule.every(6).hours.do(job_lencois)
schedule.every(6).hours.do(job_bauru)

while True:
    schedule.run_pending()
    time.sleep(10)