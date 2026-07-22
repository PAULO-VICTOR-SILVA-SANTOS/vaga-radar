"""
Camada 0: filtro por data de publicacao.

Roda antes de tudo, na lista bruta vinda das fontes. Objetivo: nunca
notificar vaga que provavelmente ja expirou.

Se a fonte nao informar a data (campo "data_publicacao" ausente), a vaga
passa sem penalidade - e melhor arriscar uma vaga sem data conhecida do
que descartar fontes inteiras por falta de metadado.
"""
from datetime import datetime, timezone

import config


def idade_em_dias(vaga):
    """Retorna quantos dias desde a publicacao, ou None se a data e desconhecida/invalida."""
    bruta = vaga.get("data_publicacao")
    if not bruta:
        return None

    try:
        texto = str(bruta).replace("Z", "+00:00")
        data = datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None

    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)

    agora = datetime.now(timezone.utc)
    return (agora - data).days


def filtrar(vagas):
    """Mantem so vagas com no maximo config.DIAS_MAX_VAGA dias de publicadas."""
    aprovadas = []
    descartadas_por_idade = 0
    sem_data = 0

    for vaga in vagas:
        idade = idade_em_dias(vaga)
        if idade is None:
            sem_data += 1
            aprovadas.append(vaga)
        elif idade <= config.DIAS_MAX_VAGA:
            aprovadas.append(vaga)
        else:
            descartadas_por_idade += 1

    print(
        f"  aprovadas por data: {len(aprovadas)} de {len(vagas)} "
        f"(expiradas/antigas: {descartadas_por_idade}, sem data informada: {sem_data})"
    )
    return aprovadas
