"""
Busca vagas no Programathor (programathor.com.br), site brasileiro de vagas
de tecnologia.

Nao ha API nem RSS oficial (/jobs.rss responde 500), entao le o HTML da
listagem publica. Verificado antes de implementar:
  - robots.txt libera /jobs (so bloqueia /admin, /user, /users, /company);
  - os Termos de Servico (/terms) nao tem clausula sobre acesso automatizado.

Para ser um bom vizinho: poucas requisicoes por execucao (so os filtros de
nivel/contrato que interessam, no maximo MAX_PAGINAS cada), pausa entre elas
e User-Agent que identifica o projeto. Se o site pedir para parar, remova
esta fonte.

A listagem traz nivel, contrato, local e tags, mas nao a descricao completa
nem a data de publicacao. Montamos a "descricao" com o que existe; a vaga
sem data passa pela camada 0 (comportamento ja previsto em filtro_data.py).
"""
import hashlib
import html
import re
import time

import requests

TIMEOUT = 20
HEADERS = {"User-Agent": "vaga-radar/1.0 (projeto pessoal de estudo)"}
BASE = "https://programathor.com.br"

# O que pedimos ao site: so os niveis/contratos que o perfil aceita.
CONSULTAS = [
    "expertise=J%C3%BAnior",
    "contract_type=Est%C3%A1gio",
]
MAX_PAGINAS = 3
PAUSA_SEGUNDOS = 1.5

# Card ativo = classe exata "cell-list ". Vaga vencida vem como
# "cell-list opacity-60p" (com selo "Vencida" no titulo) e fica de fora de
# proposito: o site mistura vencidas no fim da mesma listagem.
_RE_CARD = re.compile(r'<div class="cell-list ">(.*?)</a>\s*</div>', re.DOTALL)
_RE_LINK = re.compile(r'href="(/jobs/[^"]+)"')
_RE_TITULO = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
_RE_SPAN_ICONE = re.compile(r"<span><i class='([^']*)'></i>(.*?)</span>", re.DOTALL)
_RE_TAG = re.compile(r"<span class='tag-list[^']*'>(.*?)</span>", re.DOTALL)


def _texto(fragmento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


def _fazer_id(url, titulo):
    base = f"{url}|{titulo}".lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _parsear_card(bloco):
    """Converte o HTML de um card no dicionario padrao de vaga, ou None."""
    link = _RE_LINK.search(bloco)
    titulo = _RE_TITULO.search(bloco)
    if not link or not titulo:
        return None

    url = BASE + link.group(1)
    titulo = _texto(titulo.group(1))

    campos = {}
    for icone, valor in _RE_SPAN_ICONE.findall(bloco):
        for chave, marca in (
            ("empresa", "fa-briefcase"),
            ("local", "fa-map-marker-alt"),
            ("porte", "fa-building"),
            ("nivel", "fa-chart-bar"),
            ("contrato", "fa-file-alt"),
            ("obs", "fa-plane"),
        ):
            if marca in icone:
                campos[chave] = _texto(valor)

    tags = [_texto(t) for t in _RE_TAG.findall(bloco)]

    partes = []
    if campos.get("nivel"):
        partes.append(f"Nivel: {campos['nivel']}.")
    if campos.get("contrato"):
        partes.append(f"Contrato: {campos['contrato']}.")
    if campos.get("local"):
        partes.append(f"Local: {campos['local']}.")
    if campos.get("porte"):
        partes.append(f"Empresa: {campos.get('empresa', '')} ({campos['porte']}).")
    if campos.get("obs"):
        partes.append(campos["obs"] + ".")
    descricao = " ".join(partes)
    if tags:
        descricao += " | tags: " + ", ".join(tags)

    return {
        "id": _fazer_id(url, titulo),
        "titulo": titulo,
        "empresa": campos.get("empresa") or "nao informada",
        "local": campos.get("local") or "nao informado",
        "descricao": descricao[:4000],
        "url": url,
        "fonte": "Programathor",
        "data_publicacao": None,
    }


def _pagina(consulta, numero):
    """Retorna (vagas ativas, quantos cards a pagina tem, ativos ou vencidos)."""
    caminho = "/jobs" if numero == 1 else f"/jobs/page/{numero}"
    resposta = requests.get(
        f"{BASE}{caminho}?{consulta}", headers=HEADERS, timeout=TIMEOUT
    )
    resposta.raise_for_status()
    vagas = [
        v for v in (_parsear_card(b) for b in _RE_CARD.findall(resposta.text)) if v
    ]
    return vagas, resposta.text.count('<div class="cell-list ')


def buscar():
    """
    Busca as vagas de junior e de estagio, deduplicadas por URL.

    Levanta excecao quando ha problema de verdade (site fora do ar, ou pagina
    sem nenhum card, sinal de que o layout mudou), para o monitoramento nao
    confundir com "hoje nao ha vaga junior", que e normal: o site tem poucas.
    """
    vagas = []
    vistos = set()
    primeira = True
    paginas_ok = 0
    cards_total = 0
    ultimo_erro = None

    for consulta in CONSULTAS:
        for numero in range(1, MAX_PAGINAS + 1):
            if not primeira:
                time.sleep(PAUSA_SEGUNDOS)
            primeira = False

            try:
                da_pagina, cards = _pagina(consulta, numero)
            except Exception as erro:
                ultimo_erro = erro
                print(f"  Programathor ({consulta}, pag {numero}): {type(erro).__name__}")
                break
            paginas_ok += 1
            cards_total += cards

            if not da_pagina:
                break
            for vaga in da_pagina:
                if vaga["url"] not in vistos:
                    vistos.add(vaga["url"])
                    vagas.append(vaga)

    if paginas_ok == 0 and ultimo_erro is not None:
        raise ultimo_erro
    if paginas_ok > 0 and cards_total == 0:
        raise ValueError("layout do Programathor mudou (nenhum card encontrado)")
    return vagas
