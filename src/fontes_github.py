"""
Busca vagas nas issues de repositorios publicos do GitHub
(ex: frontendbr/vagas, react-brasil/vagas, etc.).
"""
import requests

import config

TIMEOUT = 20
HEADERS = {"User-Agent": "vaga-radar/1.0 (projeto pessoal de estudo)"}

# Se o token estiver configurado nos segredos, usamos para evitar rate limit (60 -> 5000 req/h)
if getattr(config, "GITHUB_TOKEN", None):
    HEADERS["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"

# Lista de repositorios oficiais da comunidade dev brasileira
REPOSITORIOS = [
    "frontendbr/vagas",
    "react-brasil/vagas",
    "backend-br/vagas",
    "vuejs-br/vagas",
    "androiddevbr/vagas",
]


def _fazer_id(url, titulo):
    import hashlib
    base = f"{url}|{titulo}".lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def buscar():
    """Busca issues abertas de vagas nos repositorios configurados."""
    vagas = []

    for repo in REPOSITORIOS:
        url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=30"
        try:
            resposta = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resposta.raise_for_status()
            issues = resposta.json()

            if not isinstance(issues, list):
                continue

            for issue in issues:
                # Pula pull requests se vierem na listagem de issues
                if "pull_request" in issue:
                    continue

                titulo = issue.get("title", "").strip()
                corpo = issue.get("body", "") or ""
                link = issue.get("html_url", "")
                
                if not titulo or not link:
                    continue

                # Tenta extrair informacoes basicas do autor ou rotulos
                labels = [l.get("name", "") for l in issue.get("labels", [])]
                tags_str = f" | labels: {', '.join(labels)}" if labels else ""

                vagas.append({
                    "id": _fazer_id(link, titulo),
                    "titulo": titulo,
                    "empresa": f"GitHub ({repo})",
                    "local": "remoto / nacional",
                    "descricao": (corpo[:3500] + tags_str),
                    "url": link,
                    "fonte": f"GitHub ({repo})",
                    "data_publicacao": issue.get("created_at"),
                })
        except Exception as erro:
            print(f"  Erro ao buscar no repo {repo}: {erro}")
            continue

    return vagas