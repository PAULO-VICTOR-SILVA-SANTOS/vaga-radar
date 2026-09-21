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
0-3  = incompativel (pleno, senior, especialista, lead ou acima; pede mais
       de 2 anos de experiencia; vaga fora do Brasil ou que exige fuso ou
       idioma nao-BR; exige ingles intermediario pra cima; stack central
       que o candidato nao domina; ou e apenas banco de talentos)
4-6  = parcialmente compativel (vale olhar, mas tem ressalva relevante)
7-10 = boa aderencia (stack bate, senioridade bate, formato de trabalho bate)

Senioridade: so junior, trainee, estagio ou vaga sem senioridade
especificada servem. "Pleno" no titulo ou como nivel da vaga e incompativel
(nota 0-3), mesmo sem anos explicitos. Se a vaga pedir anos de experiencia,
ate 2 anos ainda e boa aderencia; 3 anos ou mais derruba a nota.

Localizacao: so Brasil (remoto BR, ou presencial/hibrido em qualquer cidade
do Brasil). Vaga aberta ao "mundo todo" mas de empresa estrangeira, com
fuso ou reunioes em horario estrangeiro, so serve se o texto deixar claro
que contrata no Brasil.

Ingles: o candidato tem so nivel basico, entao exigencia de ingles
intermediario pra cima (intermediario, avancado, fluente ou conversacional)
derruba a nota.

Gaps do candidato (Java/Spring Boot, SQL Server, Angular, .NET, PHP): se
forem o requisito CENTRAL da vaga, a nota NAO passa de 5. Docker e testes
automatizados (Jest, Pytest, Cypress) sao gaps mais leves: como requisito
central, nota no maximo 6. Citados de passagem ou como diferencial desejavel,
ignore. Stack central React, Next.js, Node.js, Python/FastAPI, TypeScript,
APIs REST, PostgreSQL ou MongoDB sustenta nota 7 ou mais, desde que
senioridade e localizacao batam.
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


# Estatisticas da ultima execucao de filtrar(). O main le isto para o log de
# auditoria e para o alerta de saude da IA. Nao muda o que e aprovado.
ESTATISTICAS = {}

_ROTULO_FALHA = {
    "sem_chave": "GEMINI_API_KEY ausente",
    "ilegivel": "resposta ilegivel",
    "http_429": "HTTP 429 (limite de cota)",
}


def _zerar_estatisticas():
    ESTATISTICAS.clear()
    ESTATISTICAS.update(
        chamadas=0, falhas=0, erros_429=0, ultimo_erro=None,
        resultados=[], avaliacoes=[],
    )


def _avaliar_detalhado(vaga):
    """Retorna (nota, motivo, status). status e 'ok' ou o tipo da falha."""
    if not config.GEMINI_API_KEY:
        return 10, "IA sem chave configurada, vaga liberada", "sem_chave"

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
            return 10, "resposta da IA ilegivel, vaga liberada", "ilegivel"

        nota = int(analise.get("nota", 10))
        motivo = str(analise.get("motivo", "")).strip() or "sem motivo informado"
        return max(0, min(10, nota)), motivo, "ok"

    except requests.HTTPError as erro:
        # Fail-open: erro de rede ou de cota nao pode custar uma vaga boa.
        # Loga o corpo da resposta pra dar pra saber o motivo real (chave
        # invalida, cota gratuita esgotada, modelo indisponivel etc.).
        # Nao loga str(erro): o requests inclui a URL completa na mensagem,
        # e a URL desta API carrega a chave como query param.
        codigo = erro.response.status_code
        print(f"    [IA] HTTP {codigo} - corpo: {erro.response.text[:300]}")
        return 10, f"IA indisponivel ({type(erro).__name__}), vaga liberada", f"http_{codigo}"
    except Exception as erro:
        return (
            10,
            f"IA indisponivel ({type(erro).__name__}), vaga liberada",
            f"erro_{type(erro).__name__}",
        )


def avaliar(vaga):
    """Retorna (nota: int, motivo: str)."""
    nota, motivo, _ = _avaliar_detalhado(vaga)
    return nota, motivo


def _resumir(vaga, nota, motivo, aprovada, status):
    return {
        "titulo": vaga["titulo"][:90],
        "empresa": vaga["empresa"][:40],
        "fonte": vaga["fonte"],
        "url": vaga["url"],
        "nota": nota,
        "aprovada": aprovada,
        "motivo": motivo[:160],
        "ia_ok": status == "ok",
    }


def filtrar(vagas):
    """Avalia cada vaga e devolve apenas as que batem a nota minima."""
    _zerar_estatisticas()
    aprovadas = []

    for indice, vaga in enumerate(vagas):
        if indice > 0:
            # Respeita o limite de requisicoes por minuto da cota gratuita.
            time.sleep(PAUSA_ENTRE_CHAMADAS_SEGUNDOS)

        nota, motivo, status = _avaliar_detalhado(vaga)
        vaga["nota"] = nota
        vaga["motivo"] = motivo

        ESTATISTICAS["chamadas"] += 1
        ESTATISTICAS["resultados"].append(status == "ok")
        if status != "ok":
            ESTATISTICAS["falhas"] += 1
            ESTATISTICAS["ultimo_erro"] = _ROTULO_FALHA.get(status, status)
            if status == "http_429":
                ESTATISTICAS["erros_429"] += 1

        aprovada = nota >= config.NOTA_MINIMA
        ESTATISTICAS["avaliacoes"].append(_resumir(vaga, nota, motivo, aprovada, status))

        if aprovada:
            aprovadas.append(vaga)
            print(f"    [{nota}/10] OK   {vaga['titulo'][:60]} - {motivo}")
        else:
            print(f"    [{nota}/10] nao  {vaga['titulo'][:60]} - {motivo}")

    # Melhores primeiro.
    aprovadas.sort(key=lambda v: v.get("nota", 0), reverse=True)
    print(f"  aprovadas pela IA: {len(aprovadas)} de {len(vagas)}")
    return aprovadas
