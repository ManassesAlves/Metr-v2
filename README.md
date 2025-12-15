🚇 Monitoramento de Transporte – SP (Metrô, CPTM e ViaMobilidade)

Este projeto realiza o monitoramento automático da situação operacional das linhas de transporte sobre trilhos da Região Metropolitana de São Paulo, abrangendo:

🚇 Metrô de São Paulo

🚈 CPTM

🚆 ViaMobilidade (Linhas 8 e 9)

O sistema verifica periodicamente o status das linhas, detecta mudanças, registra histórico e envia notificações via Telegram somente quando ocorre alteração no status, evitando alertas repetitivos ou falsos positivos.

🎯 Objetivo

Fornecer um monitoramento confiável, automatizado e resiliente do transporte ferroviário de SP, com foco em:

Detecção de problemas operacionais

Notificações em tempo quase real

Persistência de histórico

Baixa dependência de scraping frágil

Execução contínua via GitHub Actions

⚙️ Como funciona
🔄 Execução automática

O script é executado periodicamente através do GitHub Actions, em intervalos configuráveis via cron.

🔍 Coleta de dados

Metrô SP
Scraping direto de HTML, com timeout e fallback para evitar falhas do pipeline.

ViaMobilidade (Linhas 8 e 9)
Leitura de informações públicas do site oficial.

CPTM
Monitoramento em modo global, assumindo Operação Normal como padrão e alterando o status somente quando o site menciona explicitamente problemas, evitando interpretações incorretas (como confundir nome/cor da linha com status).

📊 Padronização de status

✅ Operação normal

⚠️ Qualquer outro status (velocidade reduzida, operação parcial, falha, etc.)

🔔 Notificações

As notificações são enviadas via Telegram

Um alerta só é disparado quando há mudança real no status

Sempre que possível, a descrição do problema é incluída na mensagem

📲 Exemplo de notificação
🚇⚠️ Linha 3 – Vermelha
🔄 De: Operação normal
➡️ Para: Velocidade reduzida
📝 Motivo: Falha em equipamento de sinalização

💾 Persistência de dados

O projeto mantém dois arquivos versionados no repositório:

estado_transporte.json
Guarda o último estado conhecido de cada linha.

historico_transporte.csv
Registra o histórico de mudanças, com data, hora, linha, status antigo, status novo e descrição.

Esses arquivos garantem:

Continuidade entre execuções

Comparação correta de estados

Auditoria e análise posterior

🛡️ Resiliência e boas práticas

Timeouts configurados para evitar travamentos

Tratamento de exceções por operador

Fallback seguro quando um site está fora do ar

Uso de User-Agent adequado

Baixa frequência de acesso (baixo risco de bloqueio)

Compatibilidade com versões antigas do JSON (migração automática)

🔐 Variáveis de ambiente

O envio de notificações requer as seguintes variáveis configuradas como Secrets no GitHub:

TELEGRAM_TOKEN — Token do bot do Telegram

TELEGRAM_CHAT_ID — ID do chat ou canal de destino

🚀 Tecnologias utilizadas

Python 3.11+

requests

BeautifulSoup (bs4)

GitHub Actions

Telegram Bot API

📌 Observações importantes

Este projeto utiliza apenas dados públicos, sem autenticação ou acesso restrito.

O monitoramento da CPTM é propositalmente conservador, priorizando confiabilidade e ausência de falsos positivos.

Caso a CPTM disponibilize uma API pública no futuro, o código está preparado para migração.

📈 Possíveis evoluções futuras

Classificação automática de severidade

Alertas apenas ao sair de “Operação normal”

Resumo diário via Telegram

Dashboard de visualização

Integração com API oficial da CPTM (quando disponível)
