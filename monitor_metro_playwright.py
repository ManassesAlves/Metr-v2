import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from datetime import datetime, timedelta, timezone

# =====================================================
# PATH BASE
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_ESTADO = os.path.join(BASE_DIR, "estado_transporte.json")
ARQUIVO_HISTORICO = os.path.join(BASE_DIR, "historico_transporte.csv")

# =====================================================
# URLS
# =====================================================

URL_METRO = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
URL_VIAMOBILIDADE = "https://trilhos.motiva.com.br/viamobilidade8e9/situacao-das-linhas/"
URL_CPTM = "https://www.cptm.sp.gov.br/cptm"

# =====================================================
# TELEGRAM
# =====================================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =====================================================
# PADRÕES DE STATUS (CENTRALIZADO)
# =====================================================

PADROES_ENCERRADA = [
    "operação encerrada",
    "circulação encerrada",
    "serviço encerrado",
]

PADROES_PROBLEMA = [
    "velocidade reduzida",
    "operação parcial",
    "operação interrompida",
    "operação prejudicada",
    "circulação com restrições",
    "circulação alterada",
    "intervalos maiores",
    "falha",
    "problema",
]

PADROES_NORMAL = [
    "operação normal",
    "circulação normal",
    "operação normalizada",
]

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
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )


def identificar_operador(linha):
    if linha.startswith("Linha"):
        return "metro"
    if linha.startswith("ViaMobilidade"):
        return "viamobilidade"
    if linha.startswith("CPTM"):
        return "cptm"
    return "desconhecido"


def emoji_status(status, operador):
    s = status.lower()

    if operador == "metro":
        if "encerrada" in s:
            return "🚇⛔"
        return "🚇✅" if "normal" in s else "🚇⚠️"

    if operador == "viamobilidade":
        if "encerrada" in s:
            return "🚆⛔"
        return "🚆✅" if "normal" in s else "🚆⚠️"

    if operador == "cptm":
        if "encerrada" in s:
            return "🚈⛔"
        return "🚈✅" if "normal" in s else "🚈⚠️"

    return "❓"


def classificar_status(texto):
    """
    Retorna (status, descricao) com prioridade:
    Encerrada > Problema > Normal
    """
    t = texto.lower()

    for p in PADROES_ENCERRADA:
        if p in t:
            return "Operação Encerrada", "Operação Encerrada"

    for p in PADROES_PROBLEMA:
        if p in t:
            return p.title(), p.title()

    for p in PADROES_NORMAL:
        if p in t:
            return "Operação normal", None

    return "Operação normal", None


def obter_status_antigo(valor):
    if isinstance(valor, dict):
        return valor.get("status")
    if isinstance(valor, str):
        return valor
    return None

# =====================================================
# PERSISTÊNCIA
# =====================================================

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
                "Descricao",
            ])


def carregar_estado():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {}
    with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def salvar_historico(linha, novo, antigo, descricao):
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
            descricao or "",
        ])

# =====================================================
# SCRAPING METRÔ
# =====================================================

def capturar_metro():
    dados = {}

    try:
        r = requests.get(
            URL_METRO,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (MonitorTransporte)"}
        )
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Falha ao acessar Metrô: {e}")
        return dados

    soup = BeautifulSoup(r.text, "lxml")

    for item in soup.select("li.linha"):
        numero = item.select_one(".linha-numero")
        nome = item.select_one(".linha-nome")
        status = item.select_one(".linha-situacao")

        if numero and nome and status:
            linha = f"Linha {numero.text.strip()} – {nome.text.strip()}"
            status_txt = status.text.strip()

            dados[linha] = {
                "status": status_txt,
                "descricao": None,
            }

    return dados

# =====================================================
# SCRAPING VIAMOBILIDADE (ROBUSTO)
# =====================================================

def capturar_viamobilidade():
    linhas = {
        "ViaMobilidade – Linha 8 Diamante": "linha 8",
        "ViaMobilidade – Linha 9 Esmeralda": "linha 9",
    }

    dados = {
        linha: {"status": "Operação normal", "descricao": None}
        for linha in linhas
    }

    try:
        r = requests.get(URL_VIAMOBILIDADE, timeout=30)
        texto = r.text.lower()
    except Exception as e:
        print(f"⚠️ Falha ao acessar ViaMobilidade: {e}")
        return dados

    for linha, chave in linhas.items():
        trecho = texto.split(chave, 1)[1][:500] if chave in texto else texto
        status, desc = classificar_status(trecho)
        dados[linha] = {"status": status, "descricao": desc}

    return dados

# =====================================================
# SCRAPING CPTM (GLOBAL)
# =====================================================

def capturar_cptm():
    linhas_cptm = {
        "CPTM – Linha 7 – Rubi",
        "CPTM – Linha 8 – Diamante",
        "CPTM – Linha 9 – Esmeralda",
        "CPTM – Linha 10 – Turquesa",
        "CPTM – Linha 11 – Coral",
        "CPTM – Linha 12 – Safira",
        "CPTM – Linha 13 – Jade",
    }

    dados = {
        linha: {"status": "Operação normal", "descricao": None}
        for linha in linhas_cptm
    }

    try:
        r = requests.get(
            URL_CPTM,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (MonitorTransporte)"}
        )
        r.raise_for_status()
    except Exception as e:
        print(f"⚠️ Falha ao acessar CPTM: {e}")
        return dados

    texto = r.text.lower()
    status, desc = classificar_status(texto)

    for linha in dados:
        dados[linha] = {"status": status, "descricao": desc}

    return dados

# =====================================================
# MAIN
# =====================================================

def main():
    garantir_csv_existe()
    estado_anterior = carregar_estado()

    estado_atual = {}
    estado_atual.update(capturar_metro())
    estado_atual.update(capturar_viamobilidade())
    estado_atual.update(capturar_cptm())

    for linha, info in estado_atual.items():
        novo_status = info["status"]
        descricao = info.get("descricao")

        antigo_status = obter_status_antigo(estado_anterior.get(linha))

        if antigo_status is not None and antigo_status != novo_status:
            operador = identificar_operador(linha)
            emoji = emoji_status(novo_status, operador)

            mensagem = (
                f"{emoji} **{linha}**\n"
                f"🔄 De: {antigo_status}\n"
                f"➡️ Para: **{novo_status}**"
            )

            if descricao:
                mensagem += f"\n📝 Motivo: {descricao}"

            enviar_telegram(mensagem)
            salvar_historico(linha, novo_status, antigo_status, descricao)

    salvar_estado(estado_atual)

# =====================================================
# ENTRYPOINT
# =====================================================

if __name__ == "__main__":
    main()
