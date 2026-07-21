"""
Camada 2: filtro semantico via API da Anthropic.

So roda no que sobrou da camada 1. Usa Haiku, que e barato e suficiente
para uma tarefa de classificacao com criterio claro.

Se a chamada falhar, a vaga passa (fail-open). E melhor voce receber uma
vaga duvidosa do que perder uma boa por causa de instabilidade de rede.
"""
import json
import re

import requests

import config

URL_API = "https://api.anthropic.com/v1/messages"
MODELO = "claude-haiku-4-5-20251001"

INSTRUCAO = """Voce avalia vagas de emprego para um candidato especifico.

PERFIL DO CANDIDATO:
{perfil}

VAGA:
Titulo: {titulo}
Empresa: {empresa}
Local: {local}
Descricao: {descricao}

Responda APENAS com um objeto JSON, sem markdown, sem cercas de codigo,
sem texto antes ou depois, exatamente neste formato:

{{"nota": <inteiro de 0 a 10>, "motivo": "<uma frase curta em portugues>"}}

Criterio da nota:
0-3  = incompativel (senioridade errada, stack errada, exige ingles fluente,
       presencial fora da Paraiba, ou e apenas banco de talentos)
4-6  = parcialmente compativel (vale olhar, mas tem ressalva relevante)
7-10 = boa aderencia (stack bate, senioridade bate, formato de trabalho bate)

Seja rigoroso com senioridade. "Pleno" que exige 4+ anos nao serve.
Seja rigoroso com ingles: exigencia de ingles conversacional derruba a nota.
"""


def _extrair_json(texto):
    """A resposta deveria ser JSON puro, mas as vezes vem embrulhada."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?", "", texto)
    texto = re.sub(r"```$", "", texto).strip()

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Ultima tentativa: achar o primeiro objeto JSON dentro do texto.
    match = re.search(r"\{.*?\}", texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def avaliar(vaga):
    """Retorna (nota: int, motivo: str)."""
    if not config.ANTHROPIC_API_KEY:
        return 10, "IA sem chave configurada, vaga liberada"

    prompt = INSTRUCAO.format(
        perfil=config.PERFIL.strip(),
        titulo=vaga["titulo"],
        empresa=vaga["empresa"],
        local=vaga["local"],
        descricao=vaga["descricao"][:2500],
    )

    corpo = {
        "model": MODELO,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}],
    }
    cabecalhos = {
        "content-type": "application/json",
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    try:
        resposta = requests.post(
            URL_API, headers=cabecalhos, json=corpo, timeout=45
        )
        resposta.raise_for_status()
        dados = resposta.json()

        texto = "".join(
            bloco.get("text", "")
            for bloco in dados.get("content", [])
            if bloco.get("type") == "text"
        )

        analise = _extrair_json(texto)
        if not analise:
            return 10, "resposta da IA ilegivel, vaga liberada"

        nota = int(analise.get("nota", 10))
        motivo = str(analise.get("motivo", "")).strip() or "sem motivo informado"
        return max(0, min(10, nota)), motivo

    except requests.HTTPError as erro:
        # Fail-open: erro de rede nao pode custar uma vaga boa. Loga o
        # corpo da resposta pra dar pra saber o motivo real (chave
        # invalida, sem credito, modelo indisponivel etc.).
        print(f"    [IA] {erro} - corpo: {erro.response.text[:300]}")
        return 10, f"IA indisponivel ({type(erro).__name__}), vaga liberada"
    except Exception as erro:
        return 10, f"IA indisponivel ({type(erro).__name__}), vaga liberada"


def filtrar(vagas):
    """Avalia cada vaga e devolve apenas as que batem a nota minima."""
    aprovadas = []

    for vaga in vagas:
        nota, motivo = avaliar(vaga)
        vaga["nota"] = nota
        vaga["motivo"] = motivo

        if nota >= config.NOTA_MINIMA:
            aprovadas.append(vaga)
            print(f"    [{nota}/10] OK   {vaga['titulo'][:60]} - {motivo}")
        else:
            print(f"    [{nota}/10] nao  {vaga['titulo'][:60]} - {motivo}")

    # Melhores primeiro.
    aprovadas.sort(key=lambda v: v.get("nota", 0), reverse=True)
    print(f"  aprovadas pela IA: {len(aprovadas)} de {len(vagas)}")
    return aprovadas
