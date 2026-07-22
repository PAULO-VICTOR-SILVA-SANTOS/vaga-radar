"""
Fonte extra: alertas de vaga que chegam por e-mail.

Le a caixa do Gmail via IMAP, filtra os remetentes conhecidos de alerta de
vaga (LinkedIn, Gupy, Indeed, etc) e extrai os links das vagas.

POR QUE ISSO VALE A PENA
LinkedIn e Gupy nao tem feed publico, mas mandam alerta por e-mail. Ler o
proprio e-mail e legitimo e nao burla termo de uso de ninguem.

SEGURANCA
Este modulo usa SENHA DE APP, nao a senha da sua conta. Senha de app e
revogavel a qualquer momento sem trocar sua senha principal.
Por padrao ele NAO roda no GitHub Actions (veja EMAIL_ATIVO no config).

HOTMAIL / OUTLOOK
A Microsoft desativou IMAP com senha em contas pessoais. Configure no
Outlook um encaminhamento automatico dos e-mails de vaga para o Gmail e
leia tudo por um canal so.
"""
import email
import email.utils
import hashlib
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

import config


def _extrair_data_publicacao(mensagem):
    """Usa o cabecalho Date do proprio e-mail como data de publicacao."""
    bruta = mensagem.get("Date")
    if not bruta:
        return None
    try:
        data = email.utils.parsedate_to_datetime(bruta)
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return data.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None

SERVIDOR_IMAP = "imap.gmail.com"
PORTA_IMAP = 993


def _decodificar_assunto(bruto):
    """Assunto de e-mail vem codificado em MIME. Isso normaliza."""
    if not bruto:
        return ""
    try:
        return str(make_header(decode_header(bruto)))
    except Exception:
        return str(bruto)


def _extrair_texto(mensagem):
    """Pega o corpo do e-mail, preferindo texto puro sobre HTML."""
    texto_puro = ""
    texto_html = ""

    if mensagem.is_multipart():
        for parte in mensagem.walk():
            tipo = parte.get_content_type()
            disposicao = str(parte.get("Content-Disposition") or "")

            if "attachment" in disposicao:
                continue

            try:
                carga = parte.get_payload(decode=True)
                if not carga:
                    continue
                charset = parte.get_content_charset() or "utf-8"
                conteudo = carga.decode(charset, errors="replace")
            except Exception:
                continue

            if tipo == "text/plain":
                texto_puro += conteudo
            elif tipo == "text/html":
                texto_html += conteudo
    else:
        try:
            carga = mensagem.get_payload(decode=True)
            charset = mensagem.get_content_charset() or "utf-8"
            conteudo = carga.decode(charset, errors="replace") if carga else ""
        except Exception:
            conteudo = ""

        if mensagem.get_content_type() == "text/html":
            texto_html = conteudo
        else:
            texto_puro = conteudo

    return texto_puro, texto_html


def _limpar_html(html_bruto):
    """Remove script, style e tags, deixando o texto legivel."""
    if not html_bruto:
        return ""
    texto = re.sub(r"<script.*?</script>", " ", html_bruto, flags=re.DOTALL | re.I)
    texto = re.sub(r"<style.*?</style>", " ", texto, flags=re.DOTALL | re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = texto.replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
    return re.sub(r"\s+", " ", texto).strip()


def _extrair_links(html_bruto, texto_puro):
    """
    Pega os links de vaga do e-mail.

    Alertas costumam usar link de rastreio que redireciona para a vaga real.
    Guardamos o link como veio: abrir no navegador leva ao destino certo.
    """
    links = []

    for match in re.finditer(
        r'href=["\'](https?://[^"\']+)["\']', html_bruto or "", re.I
    ):
        links.append(match.group(1))

    for match in re.finditer(r'https?://[^\s<>"\']+', texto_puro or ""):
        links.append(match.group(0))

    # Descarta link de rodape que nao e vaga.
    ruido = (
        "unsubscribe", "descadastr", "optout", "opt-out", "preferences",
        "preferencias", "privacy", "privacidade", "termos", "terms",
        "help.", "ajuda.", "settings", "configurac", "facebook.com",
        "twitter.com", "instagram.com", "youtube.com", "apps.apple.com",
        "play.google.com", "mailto:",
    )

    limpos = []
    vistos = set()
    for link in links:
        minusculo = link.lower()
        if any(r in minusculo for r in ruido):
            continue
        link = link.rstrip(").,;'\"")
        if link in vistos:
            continue
        vistos.add(link)
        limpos.append(link)

    return limpos


def _fazer_id(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def _identificar_plataforma(remetente, links):
    """Descobre de qual plataforma veio, para mostrar na notificacao."""
    tudo = (remetente + " " + " ".join(links)).lower()
    mapa = {
        "linkedin": "LinkedIn",
        "gupy": "Gupy",
        "indeed": "Indeed",
        "glassdoor": "Glassdoor",
        "vagas.com": "Vagas.com",
        "catho": "Catho",
        "infojobs": "InfoJobs",
        "programathor": "Programathor",
        "trampos": "Trampos.co",
        "remotar": "Remotar",
        "inhire": "InHire",
        "solides": "Solides",
    }
    for chave, nome in mapa.items():
        if chave in tudo:
            return nome
    return "E-mail"


def _montar_busca_imap():
    """
    Monta o criterio de busca IMAP.

    IMAP nao aceita OR com muitos termos de forma legivel, entao fazemos
    uma busca por data e filtramos os remetentes no Python. E mais simples
    de manter e a diferenca de performance e irrelevante nesse volume.
    """
    desde = datetime.now() - timedelta(days=config.EMAIL_DIAS_ATRAS)
    return f'(SINCE "{desde.strftime("%d-%b-%Y")}")'


def buscar():
    """
    Le a caixa e devolve vagas no mesmo formato das outras fontes.
    Uma falha aqui nao pode derrubar o resto do pipeline.
    """
    if not config.EMAIL_ATIVO:
        return []

    if not config.EMAIL_USUARIO or not config.EMAIL_SENHA_APP:
        print("  E-mail: credenciais nao configuradas, pulando")
        return []

    conexao = None
    try:
        conexao = imaplib.IMAP4_SSL(SERVIDOR_IMAP, PORTA_IMAP)
        conexao.login(config.EMAIL_USUARIO, config.EMAIL_SENHA_APP)
        conexao.select(config.EMAIL_PASTA, readonly=True)

        estado, resultado = conexao.search(None, _montar_busca_imap())
        if estado != "OK":
            print("  E-mail: busca IMAP falhou")
            return []

        ids = resultado[0].split()
        if not ids:
            print("  E-mail: nenhuma mensagem no periodo")
            return []

        # Mais recentes primeiro, com teto para nao demorar demais.
        ids = ids[::-1][: config.EMAIL_MAX_MENSAGENS]

        vagas = []
        remetentes_conhecidos = [r.lower() for r in config.EMAIL_REMETENTES]
        lidas = 0

        for id_msg in ids:
            estado, dados = conexao.fetch(id_msg, "(RFC822)")
            if estado != "OK" or not dados or not dados[0]:
                continue

            mensagem = email.message_from_bytes(dados[0][1])
            remetente = str(mensagem.get("From", "")).lower()

            # So processa remetentes da lista.
            if not any(r in remetente for r in remetentes_conhecidos):
                continue

            lidas += 1
            assunto = _decodificar_assunto(mensagem.get("Subject", ""))
            texto_puro, texto_html = _extrair_texto(mensagem)
            corpo = _limpar_html(texto_html) or texto_puro
            links = _extrair_links(texto_html, texto_puro)

            if not links:
                continue

            plataforma = _identificar_plataforma(remetente, links)
            data_publicacao = _extrair_data_publicacao(mensagem)

            # Um alerta traz varias vagas. Cada link vira um candidato,
            # e as camadas de filtro decidem o que presta.
            for link in links[: config.EMAIL_MAX_LINKS_POR_EMAIL]:
                vagas.append({
                    "id": _fazer_id(link),
                    "titulo": assunto[:200] or "Vaga por e-mail",
                    "empresa": plataforma,
                    "local": "ver na vaga",
                    "descricao": corpo[:4000],
                    "url": link,
                    "fonte": f"E-mail ({plataforma})",
                    "data_publicacao": data_publicacao,
                })

        print(f"  E-mail: {lidas} alertas lidos, {len(vagas)} links extraidos")
        return vagas

    except imaplib.IMAP4.error as erro:
        print(f"  E-mail: FALHOU no login ou na busca ({erro})")
        print("    Verifique: verificacao em duas etapas ativa e senha de app valida")
        return []
    except Exception as erro:
        print(f"  E-mail: FALHOU ({type(erro).__name__}: {erro})")
        return []
    finally:
        if conexao is not None:
            try:
                conexao.close()
            except Exception:
                pass
            try:
                conexao.logout()
            except Exception:
                pass
