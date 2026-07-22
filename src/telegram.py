"""
Envio das vagas para o Telegram.

Usa a API HTTP do bot direto, sem biblioteca extra: e uma chamada POST.
"""
import html
import time

import requests

import config
import filtro_data

TIMEOUT = 20


def _idade_texto(vaga):
    idade = filtro_data.idade_em_dias(vaga)
    if idade is None:
        return None
    if idade <= 0:
        return "publicada hoje"
    if idade == 1:
        return "publicada ontem"
    return f"publicada ha {idade} dias"


def _escapar(texto):
    """O parse_mode HTML do Telegram exige escapar &, < e >."""
    return html.escape(str(texto), quote=False)


def _escapar_atributo(texto):
    """Para dentro de href="...": tambem precisa escapar aspas."""
    return html.escape(str(texto), quote=True)


def _montar_mensagem(vaga):
    linhas = [
        f"<b>{_escapar(vaga['titulo'])}</b>",
        f"🏢 {_escapar(vaga['empresa'])}",
        f"📍 {_escapar(vaga['local'])}",
        f"🔎 {_escapar(vaga['fonte'])}",
    ]

    idade = _idade_texto(vaga)
    if idade:
        linhas.append(f"🗓️ {_escapar(idade)}")

    if "nota" in vaga:
        linhas.append(f"⭐ Nota {vaga['nota']}/10 — {_escapar(vaga.get('motivo', ''))}")

    linhas.append("")
    linhas.append(f'<a href="{_escapar_atributo(vaga["url"])}">Ver vaga e se candidatar</a>')

    return "\n".join(linhas)


def _montar_mensagem_simples(vaga):
    """Sem tags HTML - usada quando o Telegram rejeita a versao formatada."""
    linhas = [
        vaga["titulo"],
        f"Empresa: {vaga['empresa']}",
        f"Local: {vaga['local']}",
        f"Fonte: {vaga['fonte']}",
    ]

    idade = _idade_texto(vaga)
    if idade:
        linhas.append(idade.capitalize())

    if "nota" in vaga:
        linhas.append(f"Nota {vaga['nota']}/10 - {vaga.get('motivo', '')}")

    linhas.append("")
    linhas.append(vaga["url"])

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
        if resposta.status_code == 400:
            # Provavelmente o HTML da mensagem ficou malformado (titulo/URL
            # com caractere inesperado). Tenta de novo como texto puro para
            # nao perder a vaga so por causa da formatacao.
            print(f"    HTML rejeitado pelo Telegram ({resposta.text[:200]}), tentando sem formatacao")
            corpo_simples = {
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": _montar_mensagem_simples(vaga),
                "disable_web_page_preview": False,
            }
            resposta = requests.post(url, json=corpo_simples, timeout=TIMEOUT)
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
