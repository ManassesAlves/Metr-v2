import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from datetime import datetime, timedelta, timezone

# =====================================================
# URLS
# =====================================================

URL_METRO = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
URL_VIAMOBILIDADE = "https://trilhos.motiva.com.br/viamobilidade8e9/situacao-das-linhas/"

# =====================================================
# CONFIG
# =====================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARQUIVO_ESTADO = "estado_transporte.json"
ARQUIVO_HISTORICO = "historico_transporte.csv"

# =====================================================
# UTIL
# =====================================================

def agora_sp():
    return datetime.now(timezone(timedelta(hours=-3)))

def log(msg):
    print(f"[LOG] {msg}")

def enviar_telegram(msg):
    if not TOKEN or not CHAT_ID:
        log("Telegram não configurado (TOKEN ou CHAT_ID ausente)")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        log("Mensagem enviada ao Telegram")
    except Exception as e:
        log(f"Erro ao enviar Telegram: {e}")

# =====================================================
# PERSISTÊNCIA
# =====================================================

def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        log("Arquivo de estado não existe (primeira execução)")
        return {}
    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    log("Arquivo JSON salvo com sucesso")

def garantir_csv_existe():
    if not os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Data",
                "Hora",
                "Linha",
                "Status Novo",
                "Status Antigo",
            ])
        log("CSV histórico criado")

def salvar_historico(linha, novo, antigo):
    garantir_csv_existe()
    t = agora_sp()
    with open(ARQUIVO_HISTORICO, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            t.strftime("%Y-%m-%d"),
            t.strftime("%H:%M:%S"),
            linha,
            novo,
            antigo,
        ])

# =====================================================
# SCRAPING METRÔ (HTML ESTÁTICO)
# =====================================================

def capturar_metro():
    dados = {}
    log("Capturando dados do Metrô")

    try:
        r = requests.get(URL_METRO, timeout=30)
        r.raise_for_status()
    except Exception as e:
        log(f"Erro ao acessar site do Metrô: {e}")
        return dados

    soup = BeautifulSoup(r.text, "lxml")

    for item in soup.select("li.linha"):
        numero = item.select_one(".linha-numero")
        nome = item.select_one(".linha-nome")
        status = item.select_one(".linha-situacao")

        if numero and nome and status:
            linha = f"Linha {numero.text.strip()} – {nome.text.strip()}"
            dados[linha] = status.text.strip()

    log(f"Metrô capturado: {len(dados)} linhas")
    return dados

# =====================================================
# SCRAPING VIAMOBILIDADE (GARANTIDO)
# =====================================================

def capturar_viamobilidade():
    dados = {
        "ViaMobilidade – Linha 8 Diamante": "Status não identificado",
        "ViaMobilidade – Linha 9 Esmeralda": "Status não identificado",
    }

    log("Capturando ViaMobilidade")

    try:
        r = requests.get(URL_VIAMOBILIDADE, timeout=30)
        r.raise_for_status()
    except Exception as e:
        log(f"Erro ao acessar ViaMobilidade: {e}")
        return dados

    texto = r.text.lower()

    if "operação normal" in texto:
        dados["ViaMobilidade – Linha 8 Diamante"] = "Operação normal"
        dados["ViaMobilidade – Linha 9 Esmeralda"] = "Operação normal"

    log("ViaMobilidade processada")
    return dados

# =====================================================
# MAIN
# =====================================================

def main():
    log("Iniciando monitoramento")

    estado_anterior = carregar_estado()
    estado_atual = {}

    dados = {}
    dados.update(capturar_metro())
    dados.update(capturar_viamobilidade())

    if not dados:
        log("Nenhum dado capturado — abortando")
        return

    for linha, status in dados.items():
        antigo = estado_anterior.get(linha)

        # 🔔 PRIMEIRA EXECUÇÃO OU MUDANÇA
        if antigo != status:
            enviar_telegram(
                f"🚇 **{linha}**\n"
                f"➡️ Status: **{status}**"
                + (f"\n🔄 Antes: {antigo}" if antigo else "")
            )

            if antigo:
                salvar_historico(linha, status, antigo)

        estado_atual[linha] = status

    salvar_estado(estado_atual)
    log("Monitoramento finalizado com sucesso")

# =====================================================
# ENTRYPOINT
# =====================================================

if __name__ == "__main__":
    main()
