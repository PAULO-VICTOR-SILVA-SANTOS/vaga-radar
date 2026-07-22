"""
Camada 2: filtro semantico via API do Google Gemini (camada gratuita).

So roda no que sobrou da camada 1. Usa Gemini Flash-Lite, que tem cota
gratuita generosa no Google AI Studio (sem cartao de credito) e e rapido
o bastante para uma tarefa de classificacao com criterio claro.

Se a chamada falhar, a vaga passa (fail-open). E melhor voce receber uma
vaga duvidosa do que perder uma boa por causa de instabilidade de rede ou
limite de cota gratuita.
"""
import json
import re
import time

import requests

import config

URL_API = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{modelo}:generateContent"
)
MODELO = "gemini-3.5-flash-lite"

# Camada gratuita do Gemini limita requisicoes por minuto. Uma pequena
# pausa entre chamadas evita estourar o limite (HTTP 429) no meio de uma
# execucao com varias vagas para avaliar.
PAUSA_ENTRE_CHAMADAS_SEGUNDOS = 4.1

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
    if not config.GEMINI_API_KEY:
        return 10, "IA sem chave configurada, vaga liberada"

    prompt = INSTRUCAO.format(
        perfil=config.PERFIL.strip(),
        titulo=vaga["titulo"],
        empresa=vaga["empresa"],
        local=vaga["local"],
        descricao=vaga["descricao"][:2500],
    )

    corpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 200,
            "responseMimeType": "application/json",
        },
    }
    url = URL_API.format(modelo=MODELO)

    try:
        resposta = requests.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json=corpo,
            timeout=45,
        )
        resposta.raise_for_status()
        dados = resposta.json()

        candidatos = dados.get("candidates") or []
        texto = ""
        if candidatos:
            partes = candidatos[0].get("content", {}).get("parts", [])
            texto = "".join(parte.get("text", "") for parte in partes)

        analise = _extrair_json(texto)
        if not analise:
            return 10, "resposta da IA ilegivel, vaga liberada"

        nota = int(analise.get("nota", 10))
        motivo = str(analise.get("motivo", "")).strip() or "sem motivo informado"
        return max(0, min(10, nota)), motivo

    except requests.HTTPError as erro:
        # Fail-open: erro de rede ou de cota nao pode custar uma vaga boa.
        # Loga o corpo da resposta pra dar pra saber o motivo real (chave
        # invalida, cota gratuita esgotada, modelo indisponivel etc.).
        print(f"    [IA] {erro} - corpo: {erro.response.text[:300]}")
        return 10, f"IA indisponivel ({type(erro).__name__}), vaga liberada"
    except Exception as erro:
        return 10, f"IA indisponivel ({type(erro).__name__}), vaga liberada"


def filtrar(vagas):
    """Avalia cada vaga e devolve apenas as que batem a nota minima."""
    aprovadas = []

    for indice, vaga in enumerate(vagas):
        if indice > 0:
            # Respeita o limite de requisicoes por minuto da cota gratuita.
            time.sleep(PAUSA_ENTRE_CHAMADAS_SEGUNDOS)

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
