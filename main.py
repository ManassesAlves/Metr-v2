import os
import json
import time
import requests
import pandas as pd
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURAÇÕES ---
URL_METRO = "https://www.metro.sp.gov.br/pt_BR/sua-viagem/direto-metro/"
ARQUIVO_ESTADO = "estado_metro.json"
ARQUIVO_HISTORICO = "historico_ocorrencias.csv"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except:
        pass

def configurar_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def tentar_fechar_cookies(driver):
    """ Tenta encontrar e clicar em botões de aceitar cookies/LGPD """
    try:
        # Lista de possíveis textos ou IDs para o botão de cookies
        xpath_cookies = "//button[contains(text(), 'Aceitar') or contains(text(), 'Concordar') or contains(text(), 'Prosseguir')]"
        wait = WebDriverWait(driver, 5)
        botao = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cookies)))
        botao.click()
        print("🍪 Banner de Cookies fechado com sucesso.")
        time.sleep(2) # Espera o banner sumir
    except:
        print("ℹ️ Nenhum banner de cookies impeditivo encontrado ou não foi possível clicar.")

def extrair_dados_selenium(driver):
    print(f"Acessando: {URL_METRO}")
    driver.get(URL_METRO)
    
    # 1. Tenta limpar a tela (Cookies)
    tentar_fechar_cookies(driver)
    
    # 2. Espera os dados carregarem (Aumentado para 15s)
    print("Aguardando carregamento dos dados...")
    time.sleep(15)

    dados = {}
    try:
        # Pega o HTML interno do corpo, as vezes o .text ignora coisas ocultas que o JS carrega
        body_element = driver.find_element(By.TAG_NAME, "body")
        texto_completo = body_element.get_attribute('innerText') # innerText as vezes é melhor que .text
        
        # --- ESTRATÉGIA REGEX ---
        # Procura por "Linha X... Status"
        # Ajustei o regex para ser mais flexível com espaços e quebras
        padrao = r"(Linha\s+\d+[\w\s-]+?)(Operação Normal|Velocidade Reduzida|Paralisada|Encerrada|Operação Parcial)"
        
        matches = re.findall(padrao, texto_completo, re.IGNORECASE | re.MULTILINE)
        
        if matches:
            for nome_sujo, status in matches:
                nome_limpo = nome_sujo.strip().replace("\n", " ")
                # Limpeza extra para remover lixo do nome
                nome_limpo = re.sub(r'[^\w\s-]', '', nome_limpo).strip()
                dados[nome_limpo] = status.strip()
        
        # --- DEBUG VISUAL ---
        if not dados:
            print("⚠️ AVISO: Regex não encontrou nada. Imprimindo trecho do texto para análise:")
            print(texto_completo[:1000]) # Aumentei o range do debug
            
    except Exception as e:
        print(f"Erro técnico na extração: {e}")

    return dados

def main():
    driver = configurar_driver()
    try:
        dados_novos = extrair_dados_selenium(driver)
    finally:
        driver.quit()

    # --- GARANTIA DE ARQUIVO ---
    # Se falhar a extração, criamos um JSON vazio se ele não existir
    # Isso evita o erro "fatal: pathspec..." no Git
    if not os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump({}, f)

    if not dados_novos:
        print("❌ Falha na extração. Encerrando sem atualizar histórico, mas arquivo JSON garantido.")
        return

    # --- LÓGICA DE HISTÓRICO E NOTIFICAÇÃO ---
    print(f"✅ Sucesso: {len(dados_novos)} linhas identificadas.")
    
    dados_antigos = {}
    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
        try:
            dados_antigos = json.load(f)
        except:
            pass

    mudancas = []
    historico = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for linha, status in dados_novos.items():
        status_antigo = dados_antigos.get(linha)
        
        if status != status_antigo:
            icone = "🟢" if "Normal" in status else "🔴" if "Paralisada" in status else "🟡"
            status_txt_antigo = status_antigo if status_antigo else "Sem registro"
            
            mudancas.append(f"{icone} *{linha}*\nDe: {status_txt_antigo}\nPara: *{status}*")
            
            historico.append({
                "data": agora,
                "linha": linha,
                "status_anterior": status_txt_antigo,
                "status_novo": status
            })

    # 1. Salva CSV
    if historico:
        df = pd.DataFrame(historico)
        header = not os.path.exists(ARQUIVO_HISTORICO)
        df.to_csv(ARQUIVO_HISTORICO, mode='a', index=False, header=header, sep=';', encoding='utf-8-sig')
        print("CSV atualizado.")

    # 2. Notifica e Atualiza JSON
    if mudancas:
        msg = f"🚨 *METRÔ SP* 🚨\n\n" + "\n\n".join(mudancas)
        msg += f"\n\n_Horário: {datetime.now().strftime('%H:%M')}_"
        enviar_telegram(msg)
    
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(dados_novos, f, ensure_ascii=False, indent=4)
    print("JSON atualizado.")

if __name__ == "__main__":
    main()
