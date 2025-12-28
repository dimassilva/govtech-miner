import requests
import base64
import os
import time
from datetime import datetime, timedelta

# URLs da API da Prefeitura de Lençóis
URL_LISTA = "https://lencois.mentor.metaway.com.br/recurso/diario/lista"
URL_DETALHE = "https://lencois.mentor.metaway.com.br/recurso/diario/editar/"

# Seu servidor local
API_LOCAL = "http://localhost:9090/upload"

def capturar_diarios(dias_atras=90):
    # Define intervalo de busca
    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=dias_atras)
    
    params = {
        "dataInicial": data_inicial.strftime("%Y-%m-%dT00:00:00"),
        "dataFinal": data_final.strftime("%Y-%m-%dT00:00:00")
    }
    
    print(f"--- Iniciando Busca: {params['dataInicial']} até Hoje ---")

    try:
        # 1. Pega a LISTA
        # Ignora verificação SSL para evitar erros com certificados governamentais
        resp_lista = requests.get(URL_LISTA, params=params, verify=False)
        if resp_lista.status_code != 200:
            print(f"Erro ao acessar lista: {resp_lista.status_code}")
            return

        itens = resp_lista.json()
        print(f"-> {len(itens)} diários encontrados na lista.")

        for item in itens:
            codigo = item['codigo']
            edicao = item['edicao']
            hash_origem = item.get('hash', '')
            data_pub = item['dataPublicacao'].split('T')[0]

            print(f"   > Processando Edição {edicao} (ID: {codigo})...")

            # 2. Pega o PDF (Base64)
            url_pdf = f"{URL_DETALHE}{codigo}"
            resp_detalhe = requests.get(url_pdf, verify=False)
            dados_detalhe = resp_detalhe.json()

            b64_pdf = dados_detalhe.get('arquivoPdf')
            
            if b64_pdf:
                # Decodifica Base64 -> Binário
                pdf_bytes = base64.b64decode(b64_pdf)
                
                # Salva Temporário
                nome_arq = f"diario_{data_pub}_ed{edicao}.pdf"
                if not os.path.exists("temp"): os.makedirs("temp")
                path_temp = os.path.join("temp", nome_arq)
                
                with open(path_temp, "wb") as f:
                    f.write(pdf_bytes)

                # 3. Envia para o CherryPy
                # Enviamos os metadados junto para salvar no banco
                files = {'arquivo_pdf': (nome_arq, open(path_temp, 'rb'), 'application/pdf')}
                payload = {
                    'codigo': str(codigo),
                    'edicao': str(edicao),
                    'hash_origem': hash_origem,
                    'data_pub': data_pub
                }

                try:
                    r = requests.post(API_LOCAL, files=files, data=payload)
                    retorno = r.json()
                    
                    if retorno.get('status') == 'Sucesso':
                        print(f"     [SUCESSO] {retorno['ops_encontradas']} oportunidades gravadas!")
                    elif retorno.get('status') == 'Ignorado':
                        print(f"     [IGNORADO] Já existe no banco.")
                    else:
                        print(f"     [ERRO] {retorno}")
                except Exception as err:
                    print(f"     [FALHA CONEXÃO] O servidor CherryPy está rodando? {err}")

                # Limpeza
                files['arquivo_pdf'][1].close()
                os.remove(path_temp)
                
                # Pausa para não bloquear IP (Good Citizen)
                time.sleep(1) 
            else:
                print("     [AVISO] Nenhum PDF nesta edição.")

    except Exception as e:
        print(f"Erro fatal no crawler: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    capturar_diarios()
