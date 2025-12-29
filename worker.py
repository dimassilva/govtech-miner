import time
import schedule
import requests
import base64
import os
import urllib3
from datetime import datetime, timedelta

# Desabilita avisos de certificado SSL (comum em sites de prefeitura)
urllib3.disable_warnings()

# CONFIGURAÇÃO DA API
# Ajuste o IP conforme seu servidor (localhost se rodar junto, ou IP externo)
API_URL = os.getenv("API_URL", "http://a0okwgosoc4oookw8s40cwco.104.168.4.3.sslip.io/upload")

# ==============================================================================
# ROBÔ 1: LENÇÓIS PAULISTA (Via API JSON + Base64)
# ==============================================================================
def job_lencois():
    print(f"\n[{datetime.now().strftime('%H:%M')}] ROBÔ LENÇÓIS INICIADO...")
    
    # Busca últimos 60 dias para garantir
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=60)
    
    params = {
        "dataInicial": data_inicial.strftime("%Y-%m-%dT00:00:00"),
        "dataFinal": data_final.strftime("%Y-%m-%dT00:00:00")
    }
    
    try:
        url_lista = "https://lencois.mentor.metaway.com.br/recurso/diario/lista"
        resp = requests.get(url_lista, params=params, verify=False, timeout=30)
        
        if resp.status_code != 200:
            print(f"   [ERRO LENÇÓIS] Falha ao buscar lista: {resp.status_code}")
            return

        itens = resp.json()
        total = len(itens)
        print(f"--- ENCONTRADOS {total} DIÁRIOS (LENÇÓIS) ---")

        for i, item in enumerate(itens):
            codigo = item['codigo']
            edicao = item['edicao']
            data_pub = item['dataPublicacao'].split('T')[0]
            
            print(f"\n[LENÇÓIS {i+1}/{total}] Edição {edicao} (Cód {codigo})...")
            
            try:
                # 1. Baixa o detalhe para pegar o Base64
                r_detalhe = requests.get(f"https://lencois.mentor.metaway.com.br/recurso/diario/editar/{codigo}", verify=False, timeout=30)
                b64 = r_detalhe.json().get('arquivoPdf')
                
                if b64:
                    nome_arq = f"lencois_{codigo}.pdf"
                    # Salva o PDF localmente
                    with open(nome_arq, "wb") as f:
                        f.write(base64.b64decode(b64))

                    # 2. Envia para sua API GovTech
                    with open(nome_arq, 'rb') as f_send:
                        files = {'arquivo_pdf': (nome_arq, f_send, 'application/pdf')}
                        payload = {
                            'codigo': str(codigo),
                            'edicao': str(edicao),
                            'hash_origem': item.get('hash', ''),
                            'data_pub': data_pub,
                            'municipio': 'Lençóis Paulista' # <--- IDENTIFICADOR CRÍTICO
                        }
                        
                        # Timeout alto (300s) para dar tempo da IA processar
                        r = requests.post(API_URL, files=files, data=payload, timeout=300)
                        
                        if r.status_code == 200:
                            resp_api = r.json()
                            if resp_api.get('status') == 'Ignorado':
                                print(f"   [PULOU] Já processado.")
                                time.sleep(1) # Rápido se já existe
                            else:
                                print(f"   [SUCESSO] Processado! ID: {resp_api.get('id')}")
                                print("   ... Resfriando motor (120s) para não bloquear a IA ...")
                                time.sleep(120) 
                        else:
                            print(f"   [ERRO API] Código {r.status_code}")
                            time.sleep(5)
                    
                    # Limpa arquivo temporário
                    if os.path.exists(nome_arq): os.remove(nome_arq)
                else:
                    print("   [AVISO] PDF não encontrado no JSON.")

            except Exception as e_item:
                print(f"   [FALHA NO ITEM] {e_item}")
                time.sleep(2)

    except Exception as e:
        print(f"Erro Geral Worker Lençóis: {e}")

# ==============================================================================
# ROBÔ 2: BAURU (Via Download Direto de PDF)
# ==============================================================================
def job_bauru():
    print(f"\n[{datetime.now().strftime('%H:%M')}] ROBÔ BAURU INICIADO...")
    
    # Exemplo de lógica para Bauru:
    # Vamos supor que você tenha a URL do PDF.
    # Em um cenário real, você teria que varrer uma página HTML para achar o link do dia.
    # Aqui está o CÓDIGO BASE para baixar e enviar, assim que tiver o link.
    
    # --- EXEMPLO: Tenta baixar o diário de HOJE ---
    hoje = datetime.now()
    ano = hoje.year
    mes = hoje.month
    dia = hoje.day
    
    # URL HIPOTÉTICA (Você deve ajustar conforme o padrão real do site de Bauru)
    # Ex: https://www2.bauru.sp.gov.br/arquivos/sist_diariooficial/2025/12/do_20251223_4075.pdf
    # Se você tiver a URL exata, coloque aqui ou faça um loop para descobrir.
    
    # Para teste, vou simular que encontramos uma URL válida:
    url_pdf_bauru = None # Coloque a URL aqui quando tiver o padrão
    edicao_bauru = "0000" # Precisa extrair do site
    codigo_bauru = f"{ano}{mes:02d}{dia:02d}" # Ex: 20251229
    
    if not url_pdf_bauru:
        print("   [BAURU] URL não definida. Configure o crawler de Bauru no worker.py.")
        return

    try:
        print(f"   [BAURU] Baixando: {url_pdf_bauru}...")
        resp = requests.get(url_pdf_bauru, verify=False, timeout=60)
        
        if resp.status_code == 200:
            nome_arq = f"bauru_{codigo_bauru}.pdf"
            
            # 1. Salva o PDF baixado
            with open(nome_arq, "wb") as f:
                f.write(resp.content)
            
            # 2. Envia para a API GovTech
            with open(nome_arq, 'rb') as f_send:
                files = {'arquivo_pdf': (nome_arq, f_send, 'application/pdf')}
                payload = {
                    'codigo': str(codigo_bauru),
                    'edicao': str(edicao_bauru),
                    'hash_origem': 'download_direto',
                    'data_pub': hoje.strftime("%Y-%m-%d"),
                    'municipio': 'Bauru' # <--- ACIONA O PROCESSADOR DE BAURU NA API
                }
                
                print("   [BAURU] Enviando para análise IA...")
                r = requests.post(API_URL, files=files, data=payload, timeout=300)
                
                if r.status_code == 200:
                    status = r.json().get('status')
                    print(f"   [BAURU] Resultado: {status}")
                    if status != 'Ignorado':
                        print("   ... Resfriando motor (120s) ...")
                        time.sleep(120)
                else:
                    print(f"   [ERRO API] {r.status_code}")
            
            if os.path.exists(nome_arq): os.remove(nome_arq)
        else:
            print(f"   [BAURU] Erro ao baixar PDF: {resp.status_code}")

    except Exception as e:
        print(f"Erro Geral Worker Bauru: {e}")

# ==============================================================================
# AGENDAMENTO (Executa ambos)
# ==============================================================================

# Executa uma vez ao iniciar para teste
job_lencois()
# job_bauru() # Descomente quando configurar a URL real de Bauru

# Agenda para rodar a cada 6 horas
#schedule.every(6).hours.do(job_lencois)
#schedule.every(6).hours.do(job_bauru)

print("--- WORKER HÍBRIDO RODANDO (AGUARDANDO AGENDAMENTO) ---")

while True:
    schedule.run_pending()
    time.sleep(10)