"""
Historico de vagas ja notificadas.

Persistencia simples em JSON. O GitHub Actions faz commit desse arquivo
de volta no repositorio, entao ele sobrevive entre execucoes.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import config


def carregar():
    """Le o historico e ja descarta o que passou de DIAS_HISTORICO."""
    if not os.path.exists(config.ARQUIVO_VISTAS):
        return {}

    try:
        with open(config.ARQUIVO_VISTAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        print("  historico corrompido ou ilegivel, comecando do zero")
        return {}

    if not isinstance(dados, dict):
        return {}

    limite = datetime.now(timezone.utc) - timedelta(days=config.DIAS_HISTORICO)
    limpo = {}

    for id_vaga, visto_em in dados.items():
        try:
            data = datetime.fromisoformat(visto_em)
            if data.tzinfo is None:
                data = data.replace(tzinfo=timezone.utc)
            if data >= limite:
                limpo[id_vaga] = visto_em
        except (ValueError, TypeError):
            continue

    return limpo


def salvar(historico):
    with open(config.ARQUIVO_VISTAS, "w", encoding="utf-8") as arquivo:
        json.dump(historico, arquivo, indent=2, ensure_ascii=False)


def separar_novas(vagas, historico):
    """Devolve so as vagas que ainda nao foram notificadas."""
    return [vaga for vaga in vagas if vaga["id"] not in historico]


def marcar(vagas, historico):
    """Registra as vagas como ja vistas."""
    agora = datetime.now(timezone.utc).isoformat()
    for vaga in vagas:
        historico[vaga["id"]] = agora
    return historico
