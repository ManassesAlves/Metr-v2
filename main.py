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
URL_METRO = "https://www.metro.sp.gov.br/pt_BR/sua-viagem/direto-metro/"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram não configurado.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
        print("Mensagem enviada para o Telegram.")
    except Exception as e:
        print(f"Erro ao enviar telegram: {e}")

def configurar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Camuflagem de navegador real
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Script extra para ocultar webdriver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
        """
    })
    return driver

def extrair_dados(driver):
    print(f"Acessando {URL_METRO}...")
    driver.get(URL_METRO)
    time.sleep(5) # Espera fixa para garantir carregamento
    
    dados_atuais = {}
    
    try:
        wait = WebDriverWait(driver, 20)
        # Espera qualquer elemento que contenha texto 'Linha'
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Linha')]")))
        
        # Busca elementos de lista ou divs
        linhas_elementos = driver.find_elements(By.XPATH, "//li[contains(., 'Linha')] | //div[contains(., 'Linha')]")
        
        for elemento in linhas_elementos:
            texto = elemento.text.strip()
            # Filtro para pegar apenas o que parece ser status de linha
            if "Linha" in texto and any(status in texto for status in ["Normal", "Reduzida", "Paralisada", "Encerrada"]):
                partes = texto.split('\n')
                if len(partes) >= 1:
                    nome_linha = partes[0].strip()
                    # Se tiver quebra de linha, o status é a segunda parte, senão tenta inferir
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
        print("ERRO: Nenhum dado foi coletado do site. O layout pode ter mudado ou bloqueio detectado.")
        return

    # Carrega estado anterior
    dados_antigos = {}
    arquivo_existe = os.path.exists(ARQUIVO_ESTADO)
    
    if arquivo_existe:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            try:
                dados_antigos = json.load(f)
            except:
                print("Erro ao ler JSON antigo.")

    # Compara mudanças
    mudancas = []
    for linha, status in dados_novos.items():
        status_anterior = dados_antigos.get(linha)
        if status != status_anterior:
            icone = "🟢" if "Normal" in status else "🔴" if "Paralisada" in status else "🟡"
            mudancas.append(f"{icone} *{linha}*\nDe: {status_anterior}\nPara: *{status}*")

    # Lógica de Salvamento e Notificação
    # Salva se houver mudanças OU se for a primeira vez (arquivo não existe)
    if mudancas or not arquivo_existe:
        if mudancas:
            msg_final = f"🚨 *ATUALIZAÇÃO METRÔ SP* 🚨\n\n" + "\n\n".join(mudancas)
            msg_final += f"\n\n_Verificado em: {datetime.now().strftime('%H:%M')}_"
            enviar_telegram(msg_final)
        else:
            print("Primeira execução: Criando arquivo base sem enviar notificação.")
        
        # Grava o JSON
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(dados_novos, f, ensure_ascii=False, indent=4)
        print(f"Arquivo {ARQUIVO_ESTADO} atualizado.")
        
    else:
        print("Nenhuma mudança detectada.")

if __name__ == "__main__":
    main()
