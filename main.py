import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURAÇÕES ---
ARQUIVO_ESTADO = "estado_metro.json"
ARQUIVO_HISTORICO = "historico_ocorrencias.csv" # Nome do novo arquivo
URL_METRO = "https://www.metro.sp.gov.br/pt_BR/sua-viagem/direto-metro/"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def configurar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def extrair_dados(driver):
    print(f"Acessando {URL_METRO}...")
    driver.get(URL_METRO)
    time.sleep(5)
    
    dados_atuais = {}
    try:
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Linha')]")))
        linhas_elementos = driver.find_elements(By.XPATH, "//li[contains(., 'Linha')] | //div[contains(., 'Linha')]")
        
        for elemento in linhas_elementos:
            texto = elemento.text.strip()
            if "Linha" in texto and any(status in texto for status in ["Normal", "Reduzida", "Paralisada", "Encerrada"]):
                partes = texto.split('\n')
                if len(partes) >= 1:
                    nome_linha = partes[0].strip()
                    status_linha = partes[1].strip() if len(partes) > 1 else "Status desconhecido"
                    dados_atuais[nome_linha] = status_linha
    except Exception as e:
        print(f"Erro na extração: {e}")
    
    return dados_atuais

def main():
    driver = configurar_driver()
    try:
        dados_novos = extrair_dados(driver)
    finally:
        driver.quit()

    if not dados_novos:
        print("ERRO: Nenhum dado coletado.")
        return

    # Carrega estado anterior
    dados_antigos = {}
    arquivo_existe = os.path.exists(ARQUIVO_ESTADO)
    if arquivo_existe:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            try:
                dados_antigos = json.load(f)
            except:
                pass

    mudancas_notificacao = [] # Lista para o Telegram
    registros_historico = []  # Lista para o CSV

    timestamp_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for linha, status_novo in dados_novos.items():
        status_anterior = dados_antigos.get(linha)
        
        # Se houve mudança (ou se é a primeira vez que vemos essa linha)
        if status_novo != status_anterior:
            # 1. Prepara notificação Telegram
            icone = "🟢" if "Normal" in status_novo else "🔴" if "Paralisada" in status_novo else "🟡"
            mudancas_notificacao.append(f"{icone} *{linha}*\nDe: {status_anterior}\nPara: *{status_novo}*")
            
            # 2. Prepara registro para CSV
            registros_historico.append({
                "data_hora": timestamp_agora,
                "linha": linha,
                "status_anterior": status_anterior if status_anterior else "Monitoramento Iniciado",
                "status_novo": status_novo
            })

    # --- BLOCO DE AÇÃO ---
    
    # A. Salvar Histórico CSV (Append mode)
    if registros_historico:
        df_hist = pd.DataFrame(registros_historico)
        csv_existe = os.path.isfile(ARQUIVO_HISTORICO)
        
        # Salva appendando ao final do arquivo (mode='a')
        # header=not csv_existe significa: só escreve o cabeçalho se o arquivo for novo
        df_hist.to_csv(ARQUIVO_HISTORICO, mode='a', index=False, header=not csv_existe, encoding='utf-8-sig', sep=';')
        print(f"{len(registros_historico)} registros adicionados ao histórico.")

    # B. Notificar e Atualizar JSON
    # A lógica aqui é: notificamos se mudou algo OU se é a primeira vez rodando (para criar o arquivo base)
    if mudancas_notificacao or not arquivo_existe:
        if mudancas_notificacao:
            msg = f"🚨 *ATUALIZAÇÃO METRÔ SP* 🚨\n\n" + "\n\n".join(mudancas_notificacao)
            msg += f"\n\n_Verificado em: {datetime.now().strftime('%H:%M')}_"
            enviar_telegram(msg)
        
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(dados_novos, f, ensure_ascii=False, indent=4)
        print("Estado JSON atualizado.")
    else:
        print("Sem mudanças de status.")

if __name__ == "__main__":
    main()
