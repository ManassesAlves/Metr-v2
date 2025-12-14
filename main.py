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
    # User-Agent comum para evitar bloqueios
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extrair_dados_selenium(driver):
    print(f"Acessando: {URL_METRO}")
    driver.get(URL_METRO)
    
    # Aumentei o tempo de espera para garantir (Servers do GitHub as vezes são lentos)
    time.sleep(10)

    dados = {}
    try:
        # Pega TODO o texto da página
        body = driver.find_element(By.TAG_NAME, "body")
        texto_completo = body.text
        
        # --- ESTRATÉGIA REGEX (Mais robusta) ---
        # Procura por: "Linha" + (espaço/numero/hifen/texto) + (Status conhecido)
        # Ex: "Linha 1-Azul Operação Normal"
        padrao = r"(Linha\s+\d+[\w\s-]+?)(Operação Normal|Velocidade Reduzida|Paralisada|Encerrada|Operação Parcial)"
        
        matches = re.findall(padrao, texto_completo, re.IGNORECASE | re.MULTILINE)
        
        if matches:
            for nome_sujo, status in matches:
                # Limpeza do nome (tira espaços extras e quebras de linha)
                nome_limpo = nome_sujo.strip().replace("\n", " ")
                dados[nome_limpo] = status.strip()
        
        # --- DIAGNÓSTICO DE ERRO (O "Dedo-Duro") ---
        if not dados:
            print("⚠️ AVISO: Nenhuma linha encontrada via Regex.")
            print("--- O QUE O ROBÔ VIU (Primeiros 500 caracteres) ---")
            print(texto_completo[:500])
            print("--- FIM DO TEXTO ---")
            
    except Exception as e:
        print(f"Erro técnico na extração: {e}")

    return dados

def main():
    driver = configurar_driver()
    try:
        dados_novos = extrair_dados_selenium(driver)
    finally:
        driver.quit()

    # --- LÓGICA DE PERSISTÊNCIA ---
    dados_antigos = {}
    
    # Lê arquivo anterior se existir e não estiver vazio
    if os.path.exists(ARQUIVO_ESTADO):
        try:
            with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
                conteudo = f.read()
                if conteudo:
                    dados_antigos = json.loads(conteudo)
        except:
            print("Erro ao ler JSON antigo (pode estar corrompido).")

    mudancas = []
    historico = []
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Se a extração falhou (dados_novos vazio), NÃO atualizamos nada para não estragar o histórico
    if dados_novos:
        print(f"✅ Sucesso: {len(dados_novos)} linhas identificadas.")
        
        for linha, status in dados_novos.items():
            status_antigo = dados_antigos.get(linha)
            
            # Detecta mudança
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

        # 1. Salva CSV se houver histórico
        if historico:
            df = pd.DataFrame(historico)
            header = not os.path.exists(ARQUIVO_HISTORICO)
            df.to_csv(ARQUIVO_HISTORICO, mode='a', index=False, header=header, sep=';', encoding='utf-8-sig')
            print("CSV Histórico atualizado.")

        # 2. Salva JSON (Sempre que houver dados válidos)
        # Se tiver mudança notificamos, se não, apenas salvamos o estado atual
        if mudancas:
            msg = f"🚨 *METRÔ SP* 🚨\n\n" + "\n\n".join(mudancas)
            msg += f"\n\n_Horário: {datetime.now().strftime('%H:%M')}_"
            enviar_telegram(msg)
            print("Notificação enviada.")
        
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(dados_novos, f, ensure_ascii=False, indent=4)
        print("Estado JSON salvo com sucesso.")
        
    else:
        print("❌ Falha: Não há dados novos para salvar. O arquivo JSON não será tocado.")
        # Se for a primeira vez e falhou, cria um JSON vazio só para o Git não dar erro fatal
        if not os.path.exists(ARQUIVO_ESTADO):
             with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
                json.dump({}, f)

if __name__ == "__main__":
    main()
