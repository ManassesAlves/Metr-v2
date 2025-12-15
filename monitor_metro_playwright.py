from playwright.sync_api import sync_playwright
import os
from datetime import datetime, timedelta, timezone

URL = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"

ARQUIVO_DEBUG_HTML = "debug_direto_metro.html"


def get_horario_sp():
    fuso_sp = timezone(timedelta(hours=-3))
    return datetime.now(fuso_sp)


def main():
    print("Iniciando captura HTML Direto do Metrô (DEBUG)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, timeout=60000)

        # Tentar aceitar cookies (se existir)
        try:
            page.click("button:has-text('Aceitar')", timeout=5000)
            print("Cookies aceitos.")
        except Exception:
            print("Popup de cookies não encontrado ou já aceito.")

        page.wait_for_timeout(5000)

        html = page.content()

        with open(ARQUIVO_DEBUG_HTML, "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    print(f"HTML salvo com sucesso em {ARQUIVO_DEBUG_HTML}")
    print("Execução concluída.")


if __name__ == "__main__":
    main()
