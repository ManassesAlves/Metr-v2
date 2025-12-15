import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from datetime import datetime, timedelta, timezone

# =====================================================
# URLs
# =====================================================

URL_METRO = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
URL_VIAMOBILIDADE_STATUS = "https://trilhos.motiva.com.br/viamobilidade8e9/situacao-das-linhas/"

# =====================================================
# Config
# =====================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARQUIVO_ESTADO = "estado_transporte.json"
ARQUIVO_HISTORICO = "historico_transporte.csv"

# =====================================================
# Utilities
# =====================================================

def agora_sp():
    return datetime.now(timezone(timedelta(hours=-3)))

def enviar_telegram(msg):
    if not TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

def garantir_csv_existe():
    if not os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Data","Hora","Linha","Status Novo","Status Antigo"])

def salvar_historico(linha, novo, antigo):
    garantir_csv_existe()
    t = agora_sp()
    with open(ARQUIVO_HISTORICO, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            t.strftime("%Y-%m-%d"),
            t.strftime("%H:%M:%S"),
            linha, novo, antigo
        ])

def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {}
    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

def emoji_status(status):
    if not status:
        return "❓"
    s = status.lower()
    if "normal" in s:
        return "✅"
    if "encerrada" in s:
        return "❌"
    if "atividade programada" in s or "impacto" in s:
        return "⚠️"
    return "ℹ️"

# =====================================================
# Crawl ViaMobilidade (HTML)
# =====================================================

def capturar_viamobilidade_html():
    try:
        res = requests.get(URL_VIAMOBILIDADE_STATUS, timeout=30)
        res.raise_for_status()
    except Exception as e:
        print("Erro ao acessar ViaMobilidade:", e)
        return {}

    soup = BeautifulSoup(res.text, "lxml")
    text = soup.get_text("\n", strip=True)

    dados = {}
    for linha in ["Linha 8-Diamante", "Linha 9-Esmeralda"]:
        if linha in text:
            # encontra a posição do nome e pega o status mais próximo depois
            idx = text.find(linha)
            fragment = text[idx:idx+200]
            # status é a primeira linha significativa após o nome
            partes = fragment.split("\n")
            if len(partes) > 1:
                status = partes[1].strip()
            else:
                status = ""
            dados[f"ViaMobilidade – {linha}"] = status
        else:
            dados[f"ViaMobilidade – {linha}"] = "Status não encontrado"

    print(f"🚆 ViaMobilidade capturada (HTML): {len(dados)}")
    return dados

# =====================================================
# You can keep your capturar_metro() function here unchanged...
# =====================================================

def main():
    print("🔍 Iniciando monitoramento...")

    estado_anterior = carregar_estado()
    estado_atual = {}

    dados = {}
    # ➤ Metrô (mantém sua função se já tiver)
    # dados.update(capturar_metro())

    # ➤ ViaMobilidade (HTML parsing)
    dados.update(capturar_viamobilidade_html())

    for linha, status in dados.items():
        antigo = estado_anterior.get(linha)
        if antigo is not None and antigo != status:
            enviar_telegram(
                f"{emoji_status(status)} **{linha}**\n"
                f"De: {antigo}\nPara: **{status}**"
            )
            salvar_historico(linha, status, antigo)
        estado_atual[linha] = status

    salvar_estado(estado_atual)
    print("✅ Estado atualizado com sucesso")

if __name__ == "__main__":
    main()
