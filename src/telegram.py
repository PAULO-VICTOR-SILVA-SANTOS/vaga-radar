"""
Envio das vagas para o Telegram.

Usa a API HTTP do bot direto, sem biblioteca extra: e uma chamada POST.
"""
import html
import time

import requests

import config

TIMEOUT = 20


def _escapar(texto):
    """O parse_mode HTML do Telegram exige escapar &, < e >."""
    return html.escape(str(texto), quote=False)


def _montar_mensagem(vaga):
    linhas = [
        f"<b>{_escapar(vaga['titulo'])}</b>",
        f"🏢 {_escapar(vaga['empresa'])}",
        f"📍 {_escapar(vaga['local'])}",
        f"🔎 {_escapar(vaga['fonte'])}",
    ]

    if "nota" in vaga:
        linhas.append(f"⭐ Nota {vaga['nota']}/10 — {_escapar(vaga.get('motivo', ''))}")

    linhas.append("")
    linhas.append(f'<a href="{_escapar(vaga["url"])}">Ver vaga e se candidatar</a>')

    return "\n".join(linhas)


def enviar_vaga(vaga):
    """Envia uma vaga. Retorna True se deu certo."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("    telegram nao configurado, pulando envio")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    corpo = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": _montar_mensagem(vaga),
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resposta = requests.post(url, json=corpo, timeout=TIMEOUT)
        resposta.raise_for_status()
        return True
    except Exception as erro:
        print(f"    falha ao enviar '{vaga['titulo'][:40]}': {erro}")
        return False


def enviar_lote(vagas):
    """Envia varias vagas com pausa, para nao bater no rate limit do Telegram."""
    enviadas = 0
    for vaga in vagas:
        if enviar_vaga(vaga):
            enviadas += 1
        time.sleep(1.2)
    return enviadas


def enviar_aviso(texto):
    """Mensagem simples de status ou erro."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": texto},
            timeout=TIMEOUT,
        )
        return True
    except Exception:
        return False
