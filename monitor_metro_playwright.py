import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from datetime import datetime, timedelta, timezone

# =====================================================
# CONFIG
# =====================================================

URL_METRO = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
URL_VIAMOBILIDADE = "https://trilhos.motiva.com.br/viamobilidade8e9/situacao-das-linhas/"

ARQUIVO_ESTADO = "estado_transporte.json"
ARQUIVO_HISTORICO = "historico_transporte.csv"

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =====================================================
# UTIL
# =====================================================

def agora_sp():
    return datetime.now(timezone(timedelta(hours=-3)))

def enviar_telegram(msg):
    if not TOKEN or not CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
        timeout=10
    )

# =====================================================
# PERSISTÊNCIA
# =====================================================

def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {}
    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

# =====================================================
# SCRAPING
# =====================================================

def capturar_metro():
    dados = {}
    r = requests.get(URL_METRO, timeout=30)
    soup = BeautifulSoup(r.text, "lxml")

    for item in soup.select("li.linha"):
        numero = item.select_one(".linha-numero")
        nome = item.select_one(".linha-nome")
        status = item.select_one(".linha-situacao")

        if numero and nome and status:
            linha = f"Linha {numero.text.strip()} – {nome.text.strip()}"
            dados[linha] = status.text.strip()

    return dados

def capturar_viamobilidade():
    dados = {}
    r = requests.get(URL_VIAMOBILIDADE, timeout=30)
    texto = r.text.lower()

    dados["ViaMobilidade – Linha 8 Diamante"] = (
        "Operação normal" if "operação normal" in texto else "Status indefinido"
    )
    dados["ViaMobilidade – Linha 9 Esmeralda"] = (
        "Operação normal" if "operação normal" in texto else "Status indefinido"
    )

    return dados

# =====================================================
# MAIN
# =====================================================

def main():
    estado_anterior = carregar_estado()

    estado_atual = {}
    estado_atual.update(capturar_metro())
    estado_atual.update(capturar_viamobilidade())

    # 🔔 ALERTA SOMENTE SE HOUVER MUDANÇA
    for linha, status in estado_atual.items():
        status_antigo = estado_anterior.get(linha)

        if status_antigo is not None and status_antigo != status:
            enviar_telegram(
                f"🚇 **{linha}**\n"
                f"🔄 {status_antigo} ➜ **{status}**"
            )

    salvar_estado(estado_atual)

if __name__ == "__main__":
    main()
