import os
import json
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
# URL Direta descoberta (muito mais estável)
URL_ENDPOINT = "https://www.metro.sp.gov.br/wp-content/themes/metrosp/direto-metro.php"
ARQUIVO_ESTADO = "estado_metro.json"
ARQUIVO_HISTORICO = "historico_ocorrencias.csv"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram não configurado.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def extrair_dados():
    print(f"Consultando endpoint direto: {URL_ENDPOINT}...")
    
    # Headers para simular que somos o site oficial pedindo os dados
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.metro.sp.gov.br/sua-viagem/direto-metro/',
        'X-Requested-With': 'XMLHttpRequest' # Importante para endpoints PHP/AJAX
    }
    
    try:
        response = requests.get(URL_ENDPOINT, headers=headers, timeout=15)
        response.raise_for_status() # Garante que não deu erro 404/500
        
        # O endpoint provavelmente retorna HTML puro (<ul>...</ul>) ou JSON.
        # Vamos assumir HTML pois é um arquivo .php de tema WP.
        soup = BeautifulSoup(response.content, 'html.parser')
        
        dados_atuais = {}
        
        # Estratégia Genérica: Pega todos os itens de lista (li)
        # Geralmente a estrutura é <li> <span>Linha X</span> <span>Status</span> </li>
        itens = soup.find_all('li')
        
        for item in itens:
            texto = item.get_text(" ", strip=True) # Pega o texto limpo
            
            # Filtra apenas se parecer uma linha de metrô
            if "Linha" in texto:
                # Exemplo de texto: "Linha 1-Azul Operação Normal"
                # Vamos tentar separar o nome da linha do status
                partes = texto.split('Linha')
                if len(partes) > 1:
                    # Reconstrói "Linha 1-Azul..."
                    conteudo = "Linha" + partes[1]
                    
                    # Identifica o status conhecido
                    status_possiveis = ["Normal", "Reduzida", "Paralisada", "Encerrada", "Parcial"]
                    status_detectado = "Status Desconhecido"
                    
                    for s in status_possiveis:
                        if s in conteudo:
                            status_detectado = s
                            # Remove o status do nome para ficar limpo (opcional)
                            # nome_linha = conteudo.replace(s, "").strip() 
                            break
                    
                    # Vamos usar o texto completo da linha como chave para garantir unicidade
                    # Ex: "Linha 1-Azul" -> "Operação Normal"
                    # Como a string vem suja, vamos simplificar:
                    
                    # Lógica de extração segura:
                    nome_linha = conteudo.split("Operação")[0].strip() if "Operação" in conteudo else conteudo[:15]
                    status_final = "Operação " + status_detectado if "Operação" not in status_detectado else status_detectado
                    
                    # Refinamento final do nome
                    if "-" in nome_linha:
                        dados_atuais[nome_linha] = status_final

        # Fallback: Se não achou <li>, tenta pegar divs (caso o layout mude)
        if not dados_atuais:
            divs = soup.find_all('div')
            for div in divs:
                texto = div.get_text(strip=True)
                if "Linha" in texto and any(s in texto for s in ["Normal", "Reduzida"]):
                     dados_atuais[texto[:20]] = texto # Salva cru se não conseguir parsear bonito

        return dados_atuais

    except Exception as e:
        print(f"Erro na requisição: {e}")
        return {}

def main():
    dados_novos = extrair_dados()

    if not dados_novos:
        print("❌ Não foi possível extrair dados do endpoint. Verifique se a URL mudou.")
        return

    print(f"Dados extraídos com sucesso: {len(dados_novos)} linhas.")
    
    # Carrega estado anterior
    dados_antigos = {}
    arquivo_existe = os.path.exists(ARQUIVO_ESTADO)
    if arquivo_existe:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            try:
                dados_antigos = json.load(f)
            except:
                pass

    mudancas_notificacao = []
    registros_historico = []
    timestamp_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for linha, status_novo in dados_novos.items():
        # Tenta achar a linha no estado anterior (fuzzy matching simples ou chave exata)
        status_anterior = dados_antigos.get(linha)
        
        if status_novo != status_anterior:
            icone = "🟢" if "Normal" in status_novo else "🔴" if "Paralisada" in status_novo else "🟡"
            status_exibicao_antigo = status_anterior if status_anterior else "Monitoramento Iniciado"
            
            mudancas_notificacao.append(f"{icone} *{linha}*\nDe: {status_exibicao_antigo}\nPara: *{status_novo}*")
            
            registros_historico.append({
                "data_hora": timestamp_agora,
                "linha": linha,
                "status_anterior": status_exibicao_antigo,
                "status_novo": status_novo
            })

    # Salva CSV
    if registros_historico:
        df_hist = pd.DataFrame(registros_historico)
        csv_existe = os.path.isfile(ARQUIVO_HISTORICO)
        df_hist.to_csv(ARQUIVO_HISTORICO, mode='a', index=False, header=not csv_existe, encoding='utf-8-sig', sep=';')
        print("Histórico CSV atualizado.")

    # Notifica e Atualiza JSON
    if mudancas_notificacao or not arquivo_existe:
        if mudancas_notificacao:
            msg = f"🚨 *ATUALIZAÇÃO METRÔ SP* 🚨\n\n" + "\n\n".join(mudancas_notificacao)
            msg += f"\n\n_Fonte: Direto do Metrô_"
            enviar_telegram(msg)
        
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(dados_novos, f, ensure_ascii=False, indent=4)
        print("Estado JSON atualizado.")
    else:
        print("Sem mudanças de status.")

if __name__ == "__main__":
    main()
