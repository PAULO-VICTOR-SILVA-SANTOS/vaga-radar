"""
Busca vagas nos feeds publicos configurados.
Cada fonte tem formato diferente; aqui normalizamos tudo para o mesmo dicionario:

    {"id": str, "titulo": str, "empresa": str, "local": str,
     "descricao": str, "url": str, "fonte": str}
"""
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

import config

TIMEOUT = 20
HEADERS = {"User-Agent": "vaga-radar/1.0 (projeto pessoal de estudo)"}


def _extrair_data_publicacao_json(item):
    """
    Normaliza a data de publicacao para ISO 8601 (UTC).

    Cada fonte usa um campo diferente:
      RemoteOK   -> "date" (ISO 8601 com timezone)
      Remotive   -> "publication_date" (ISO 8601 sem timezone, UTC implicito)
      Himalayas  -> "pubDate" (epoch em segundos)

    Retorna None se a fonte nao informar data - nesse caso a vaga nao e
    penalizada pelo filtro de frescor (ver filtro_data.py).
    """
    bruta = item.get("date") or item.get("publication_date")
    if bruta:
        try:
            texto = str(bruta).replace("Z", "+00:00")
            data = datetime.fromisoformat(texto)
            if data.tzinfo is None:
                data = data.replace(tzinfo=timezone.utc)
            return data.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass

    epoch = item.get("epoch") or item.get("pubDate")
    if isinstance(epoch, (int, float)):
        try:
            return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            pass

    return None


def _extrair_data_publicacao_rss(item):
    """RSS usa <pubDate> no formato RFC 822 (ex: 'Tue, 30 Jun 2026 20:32:52 +0000')."""
    bruta = item.findtext("pubDate")
    if not bruta:
        return None
    try:
        data = parsedate_to_datetime(bruta)
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return data.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _limpar_html(texto):
    """Remove tags HTML e normaliza espacos."""
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", str(texto))
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def _fazer_id(url, titulo):
    """ID estavel para deduplicacao, mesmo que a fonte nao forneca um."""
    base = f"{url}|{titulo}".lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _buscar_json(fonte):
    resposta = requests.get(fonte["url"], headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    dados = resposta.json()

    # Cada API embrulha a lista de um jeito. Normalizamos aqui.
    if isinstance(dados, dict):
        for chave in ("jobs", "data", "results"):
            if isinstance(dados.get(chave), list):
                dados = dados[chave]
                break
        else:
            return []

    if not isinstance(dados, list):
        return []

    vagas = []
    for item in dados:
        if not isinstance(item, dict):
            continue

        # RemoteOK manda um item de metadados como primeiro elemento.
        if "legal" in item:
            continue

        titulo = item.get("position") or item.get("title") or ""
        empresa = (
            item.get("company")
            or item.get("company_name")
            or item.get("companyName")
            or ""
        )
        url = item.get("url") or item.get("applicationLink") or item.get("link") or ""
        descricao = _limpar_html(
            item.get("description") or item.get("excerpt") or ""
        )
        local = (
            item.get("location")
            or item.get("candidate_required_location")
            or ""
        )
        if isinstance(local, list):
            local = ", ".join(str(x) for x in local)

        # Tags entram na descricao para o filtro de keyword enxergar a stack.
        tags = item.get("tags") or []
        if isinstance(tags, list) and tags:
            descricao = descricao + " | tags: " + ", ".join(str(t) for t in tags)

        if not titulo or not url:
            continue

        vagas.append({
            "id": _fazer_id(url, titulo),
            "titulo": str(titulo).strip(),
            "empresa": str(empresa).strip() or "nao informada",
            "local": str(local).strip() or "nao informado",
            "descricao": descricao[:4000],
            "url": str(url).strip(),
            "fonte": fonte["nome"],
            "data_publicacao": _extrair_data_publicacao_json(item),
        })
    return vagas


def _buscar_rss(fonte):
    resposta = requests.get(fonte["url"], headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    raiz = ET.fromstring(resposta.content)

    vagas = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        descricao = _limpar_html(item.findtext("description") or "")

        if not titulo or not url:
            continue

        # WeWorkRemotely usa o formato "Empresa: Cargo" no titulo.
        empresa = "nao informada"
        if ":" in titulo:
            possivel_empresa, _, resto = titulo.partition(":")
            if len(possivel_empresa) < 60:
                empresa = possivel_empresa.strip()
                titulo = resto.strip() or titulo

        vagas.append({
            "id": _fazer_id(url, titulo),
            "titulo": titulo,
            "empresa": empresa,
            "local": "remoto",
            "descricao": descricao[:4000],
            "url": url,
            "fonte": fonte["nome"],
            "data_publicacao": _extrair_data_publicacao_rss(item),
        })
    return vagas


def buscar_todas():
    """Busca em todas as fontes. Uma fonte que falha nao derruba as outras."""
    todas = []
    vistos = set()

    for fonte in config.FONTES:
        try:
            if fonte["tipo"] == "json":
                vagas = _buscar_json(fonte)
            else:
                vagas = _buscar_rss(fonte)
            print(f"  {fonte['nome']}: {len(vagas)} vagas")
        except Exception as erro:
            print(f"  {fonte['nome']}: FALHOU ({type(erro).__name__}: {erro})")
            continue

        # Deduplica dentro desta execucao (a mesma vaga aparece em varios feeds).
        for vaga in vagas:
            if vaga["id"] in vistos:
                continue
            vistos.add(vaga["id"])
            todas.append(vaga)

    # Fonte nacional via GitHub Issues (comunidade dev brasileira)
    try:
        import fontes_github
        for vaga in fontes_github.buscar():
            if vaga["id"] in vistos:
                continue
            vistos.add(vaga["id"])
            todas.append(vaga)
    except Exception as erro:
        print(f"  GitHub Vagas: FALHOU ({type(erro).__name__}: {erro})")

    # Fonte extra: alertas por e-mail. Importado aqui dentro para que um
    # problema neste modulo nao impeca o resto do programa de rodar.
    if config.EMAIL_ATIVO:
        try:
            import fontes_email
            for vaga in fontes_email.buscar():
                if vaga["id"] in vistos:
                    continue
                vistos.add(vaga["id"])
                todas.append(vaga)
        except Exception as erro:
            print(f"  E-mail: FALHOU ({type(erro).__name__}: {erro})")

    return todas