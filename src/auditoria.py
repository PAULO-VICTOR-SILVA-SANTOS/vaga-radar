"""
Auditoria e saude do sistema.

Duas coisas, ambas persistidas em log_auditoria.json (o GitHub Actions
commita o arquivo de volta, como faz com vagas_vistas.json):

  1. LOG: uma entrada por execucao, com quantas vagas passaram em cada
     camada, o estado de cada fonte e a nota/motivo que a IA deu a cada
     vaga avaliada (aprovada ou nao).

  2. SAUDE: contadores que atravessam execucoes. Quando algo foge do
     normal, devolve avisos para o Telegram, para voce so precisar agir
     quando houver alerta:
       - fonte com 0 vagas por N execucoes seguidas (ou falhando N vezes);
       - IA falhando (erro, cota 429, chave ausente) N vezes seguidas.
     Um alerta persistente e repetido no maximo a cada REALERTA_HORAS.

Nada aqui altera o que e filtrado ou notificado: so observa.
Nunca grava URL de requisicao nem texto de excecao (podem carregar chave
ou token na URL): so o nome do tipo do erro ou o status HTTP.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import config

VERSAO = 1


def _agora():
    return datetime.now(timezone.utc)


def _vazio():
    return {
        "versao": VERSAO,
        "saude": {"fontes": {}, "ia": {"falhas_seguidas": 0}, "alertas": {}},
        "execucoes": [],
    }


def carregar():
    """Le o arquivo; se nao existe ou esta corrompido, comeca do zero."""
    if not os.path.exists(config.ARQUIVO_AUDITORIA):
        return _vazio()
    try:
        with open(config.ARQUIVO_AUDITORIA, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        print("  log de auditoria ilegivel, comecando do zero")
        return _vazio()

    if not isinstance(dados, dict):
        return _vazio()
    base = _vazio()
    base["saude"].update(dados.get("saude") or {})
    for chave in ("fontes", "alertas"):
        base["saude"].setdefault(chave, {})
    base["saude"].setdefault("ia", {"falhas_seguidas": 0})
    base["execucoes"] = dados.get("execucoes") or []
    return base


def salvar(dados):
    """Grava de forma atomica e poda o que passou do limite configurado."""
    execucoes = dados["execucoes"][-config.AUDITORIA_MAX_EXECUCOES:]
    # Detalhe vaga a vaga so nas execucoes mais recentes; nas antigas ficam
    # os numeros (o arquivo e commitado a cada rodada e nao pode crescer sem fim).
    corte = len(execucoes) - config.AUDITORIA_DETALHE_ULTIMAS
    for indice, execucao in enumerate(execucoes):
        if indice < corte and execucao.get("ia", {}).get("avaliacoes"):
            execucao["ia"]["avaliacoes"] = []
    dados["execucoes"] = execucoes

    temporario = config.ARQUIVO_AUDITORIA + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=1, ensure_ascii=False)
    os.replace(temporario, config.ARQUIVO_AUDITORIA)


def nova_execucao():
    return {
        "inicio": _agora().isoformat(),
        "duracao_s": None,
        "fontes": {},
        "camadas": {
            "brutas": 0,
            "camada0_data": 0,
            "novas": 0,
            "camada1_keyword": 0,
            "camada2_ia_avaliadas": 0,
            "camada2_ia_aprovadas": 0,
            "enviadas": 0,
        },
        "ia": {
            "ativa": bool(config.USE_AI),
            "chamadas": 0,
            "falhas": 0,
            "erros_429": 0,
            "ultimo_erro": None,
            "avaliacoes": [],
        },
        "avisos": [],
        "erro_fatal": None,
    }


def _falhas_no_final(resultados):
    """Quantas chamadas de IA falharam consecutivas ate o fim da execucao."""
    total = 0
    for ok in reversed(resultados):
        if ok:
            break
        total += 1
    return total


def avaliar_saude(dados, execucao, resultados_ia):
    """
    Atualiza os contadores de saude com esta execucao e devolve a lista de
    alertas que devem ser mostrados AGORA, como [(chave, texto), ...].

    resultados_ia: lista de bool (True = chamada da IA funcionou), na ordem.
    """
    agora = _agora()
    saude = dados["saude"]
    ativos = {}  # chave -> texto, tudo que esta fora do normal neste momento

    # --- fontes ---------------------------------------------------------
    for nome, info in execucao["fontes"].items():
        estado = saude["fontes"].setdefault(
            nome, {"zeros_seguidos": 0, "erros_seguidos": 0, "ultimo_ok": None}
        )
        if info.get("erro"):
            estado["erros_seguidos"] += 1
        else:
            estado["erros_seguidos"] = 0
            estado["zeros_seguidos"] = estado["zeros_seguidos"] + 1 if info["vagas"] == 0 else 0
        if info["vagas"] > 0:
            estado["ultimo_ok"] = agora.isoformat()

        limite = config.LIMITE_ZEROS_POR_FONTE.get(nome, config.LIMITE_ZEROS_FONTE)
        if estado["erros_seguidos"] >= limite:
            ativos[f"fonte:{nome}"] = (
                f"Fonte '{nome}' falhou em {estado['erros_seguidos']} execucoes "
                f"seguidas (ultimo erro: {info.get('erro')}). Pode estar com problema."
            )
        elif (
            estado["zeros_seguidos"] >= limite
            and not nome.startswith(config.FONTES_SEM_ALERTA_DE_ZERO)
        ):
            ativos[f"fonte:{nome}"] = (
                f"Fonte '{nome}' retornou 0 vagas em {estado['zeros_seguidos']} "
                f"execucoes seguidas. Pode estar com problema."
            )

    # --- IA -------------------------------------------------------------
    if resultados_ia:  # sem chamadas nesta execucao: nao mexe no contador
        ia = saude["ia"]
        no_final = _falhas_no_final(resultados_ia)
        if no_final == len(resultados_ia):
            ia["falhas_seguidas"] += no_final  # falhou o tempo todo: acumula
        else:
            ia["falhas_seguidas"] = no_final
        if ia["falhas_seguidas"] >= config.LIMITE_FALHAS_IA:
            detalhe = execucao["ia"].get("ultimo_erro") or "erro desconhecido"
            ativos["ia"] = (
                f"IA falhou {ia['falhas_seguidas']} vezes seguidas (ultimo erro: "
                f"{detalhe}). Vagas podem estar chegando sem avaliacao."
            )

    # --- anti-spam: repete um alerta persistente so apos REALERTA_HORAS ---
    alertas = saude["alertas"]
    for chave in [c for c in alertas if c not in ativos]:
        del alertas[chave]  # problema resolvido: proximo alerta sai na hora

    devidos = []
    espera = timedelta(hours=config.REALERTA_HORAS)
    for chave, texto in ativos.items():
        ultimo = alertas.get(chave)
        if ultimo is None or agora - datetime.fromisoformat(ultimo) >= espera:
            devidos.append((chave, texto))
    return devidos


def marcar_alertas_enviados(dados, chaves):
    """Registra que estes alertas chegaram ao Telegram (para o anti-spam)."""
    agora = _agora().isoformat()
    for chave in chaves:
        dados["saude"]["alertas"][chave] = agora


def formatar_aviso(alertas):
    """Bloco de texto para o topo da mensagem do Telegram, ou None."""
    if not alertas:
        return None
    linhas = ["⚠️ ATENÇÃO — Vaga Radar"]
    linhas += [f"• {texto}" for _, texto in alertas]
    return "\n".join(linhas)


def registrar(dados, execucao, inicio_monotonico=None):
    """Acrescenta a execucao ao log e grava o arquivo."""
    if inicio_monotonico is not None:
        execucao["duracao_s"] = round(time.monotonic() - inicio_monotonico, 1)
    dados["execucoes"].append(execucao)
    salvar(dados)
