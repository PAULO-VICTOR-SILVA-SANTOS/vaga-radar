"""
Camada 1: filtro por palavra-chave.

Barato, deterministico, roda em todas as vagas.
Objetivo: cortar o ruido obvio antes de gastar chamada de IA.

Sao DUAS listas de bloqueio, e a diferenca importa:

  TITULO     - define o cargo. "Desenvolvedor Java" nao e sua vaga,
               nao importa o que a descricao diga.

  DESCRICAO  - so o que e realmente eliminatorio (ingles fluente,
               nivel pleno/senior declarado, mais de 2 anos de experiencia).
               Bloquear tecnologia na descricao derruba vaga boa: quase
               toda vaga React cita Angular em algum lugar como
               "diferencial" ou "conhecimento em".

Alem disso: so entra vaga junior/trainee/estagio/sem senioridade, e so
vaga do Brasil.
"""
import re
import unicodedata

import config


def _normalizar(texto):
    """Minusculas e sem acento, para 'senior' casar com 'senior' acentuado."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _preparar(lista):
    return [_normalizar(p) for p in lista]


def _contem_termo(termos, texto):
    """True se algum termo aparece como palavra inteira (evita 'natal' em 'natalie')."""
    return next(
        (t for t in termos if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", texto)),
        None,
    )


# "3+ anos", "mais de 2 anos", "2 a 4 years", "5 yrs". Em faixa, vale o minimo.
_RE_ANOS = re.compile(
    r"(?:(mais de|more than|over|acima de)\s+)?"
    r"(\d{1,2})\s*(?:\+|ou mais)?\s*(?:(?:a|to|-|–|ate)\s*\d{1,2}\s*)?"
    r"(?:anos?|years?|yrs?)(?!\w)"
)


def _anos_exigidos(descricao):
    """
    Maior exigencia de anos de EXPERIENCIA na descricao, ou None.
    So conta numero perto de 'experi': "empresa com 10 anos de mercado"
    nao e requisito.
    """
    maior = None
    for m in _RE_ANOS.finditer(descricao):
        contexto = descricao[max(0, m.start() - 50):m.end() + 60]
        if "experi" not in contexto:
            continue
        anos = int(m.group(2)) + (1 if m.group(1) else 0)  # "mais de 2" = 3+
        maior = anos if maior is None else max(maior, anos)
    return maior


def _fora_do_brasil(vaga, titulo, descricao):
    """
    Retorna o motivo se a vaga nao e do Brasil, ou None se pode seguir.

    Sinal explicito de Brasil libera. Sem ele, indicio de fora (pais, LATAM,
    "oportunidade internacional") corta em qualquer fonte. Restando duvida,
    fontes brasileiras (GitHub, e-mail) passam e as internacionais
    (RemoteOK, Remotive, WWR, Himalayas) so passam se escritas em portugues.
    """
    local = _normalizar(vaga.get("local", ""))
    topo = f"{titulo} {local} {descricao[:1500]}"

    if _contem_termo(_preparar(config.SINAIS_BRASIL), topo):
        return None

    fora = _contem_termo(_preparar(config.INDICADORES_FORA_DO_BRASIL), topo)
    if fora:
        return f"fora do Brasil: '{fora}'"

    if vaga.get("fonte", "").startswith(config.FONTES_BRASILEIRAS_PREFIXOS):
        return None

    # Fonte internacional sem nenhum sinal de Brasil: so passa se a vaga for
    # escrita em portugues (tres ou mais palavras tipicas).
    palavras_pt = [
        p for p in _preparar(config.PALAVRAS_PORTUGUES)
        if re.search(rf"(?<!\w){p}(?!\w)", descricao)
    ]
    if len(palavras_pt) >= 3:
        return None
    return "sem indicacao de Brasil (vaga internacional)"


def avaliar(vaga):
    """
    Retorna (passou: bool, motivo: str).
    O motivo serve para voce entender por que algo foi cortado.
    """
    obrigatorias = _preparar(config.PALAVRAS_OBRIGATORIAS)
    bloq_titulo = _preparar(config.PALAVRAS_BLOQUEADAS_TITULO)
    bloq_descricao = _preparar(config.PALAVRAS_BLOQUEADAS_DESCRICAO)

    titulo = _normalizar(vaga["titulo"])
    descricao = _normalizar(vaga.get("descricao", ""))
    corpo = f"{titulo} {descricao}"

    # Vagas vindas de e-mail sao um caso a parte.
    # O "titulo" e o assunto do alerta ("15 novas vagas para voce") e a
    # "descricao" e o e-mail inteiro, com VARIAS vagas misturadas. Aplicar
    # a regra normal aqui derrubaria tudo: basta uma vaga senior no mesmo
    # e-mail para bloquear as outras onze.
    # Entao aqui exigimos so a palavra-chave positiva e deixamos a
    # camada de IA (ou voce, no clique) fazer o julgamento fino.
    if vaga.get("fonte", "").startswith("E-mail"):
        for palavra in obrigatorias:
            if palavra in corpo:
                return True, f"e-mail, casou com '{palavra}'"
        return False, "e-mail sem palavra-chave da sua stack"

    # 1. O cargo desqualifica?
    for palavra in bloq_titulo:
        if palavra in titulo:
            return False, f"cargo incompativel: '{palavra}'"
    for padrao in config.REGEX_SENIORIDADE_TITULO:
        if re.search(padrao, titulo):
            return False, f"senioridade no titulo: '{padrao}'"

    # 1b. O titulo cita uma stack conflitante SEM citar a sua?
    # "Frontend Angular" cai. "Full Stack React/Angular" passa, porque
    # React aparece junto. Sem isso, formatos que nao comecam com
    # "Desenvolvedor" escapam da lista de cargo acima.
    #
    # Cuidado: comparamos so contra TECNOLOGIAS, nao contra cargos.
    # "frontend" e "fullstack" sao cargos e aparecem em qualquer vaga —
    # se contassem aqui, "Fullstack Python" seria liberado pelo proprio
    # "fullstack" e o bloqueio nunca dispararia.
    tecnologias = _preparar(config.TECNOLOGIAS_SUAS)
    tem_stack_sua = any(p in titulo for p in tecnologias)
    if not tem_stack_sua:
        for conflito in _preparar(config.STACKS_CONFLITANTES):
            if conflito in titulo:
                return False, f"stack conflitante no titulo: '{conflito.strip()}'"

    # 2. Tem algum requisito eliminatorio?
    for palavra in bloq_descricao:
        if palavra in descricao:
            return False, f"requisito eliminatorio: '{palavra}'"

    # 2a. Os rotulos/tags da fonte declaram nivel pleno/senior?
    rotulos = re.search(r"\|\s*(?:labels|tags):\s*([^\n]*)\s*$", descricao)
    if rotulos:
        nivel = _contem_termo(_preparar(config.ROTULOS_SENIORIDADE), rotulos.group(1))
        if nivel:
            return False, f"senioridade nos rotulos: '{nivel}'"

    # 2b. A propria vaga declara nivel pleno/senior no corpo do texto?
    for padrao in config.REGEX_SENIORIDADE_DESCRICAO:
        achado = re.search(padrao, descricao)
        if achado:
            return False, f"senioridade na descricao: '{' '.join(achado.group(0).split())}'"

    # 2c. Pede mais anos de experiencia do que voce tem?
    anos = _anos_exigidos(descricao)
    if anos is not None and anos > config.ANOS_EXPERIENCIA_MAX:
        return False, f"experiencia acima do limite: {anos} anos"

    # 3. E do Brasil? (remoto BR ou presencial em qualquer cidade do pais)
    motivo_geo = _fora_do_brasil(vaga, titulo, descricao)
    if motivo_geo:
        return False, motivo_geo

    # 4. Bate com a sua stack?
    for palavra in obrigatorias:
        if palavra in corpo:
            return True, f"casou com '{palavra}'"

    return False, "nenhuma palavra-chave da sua stack"


def filtrar(vagas):
    """Aplica o filtro na lista inteira e imprime um resumo."""
    aprovadas = []
    contagem_motivos = {}

    for vaga in vagas:
        passou, motivo = avaliar(vaga)
        if passou:
            aprovadas.append(vaga)
        else:
            chave = motivo.split(":")[0]
            contagem_motivos[chave] = contagem_motivos.get(chave, 0) + 1

    print(f"  aprovadas: {len(aprovadas)} de {len(vagas)}")
    for motivo, quantidade in sorted(
        contagem_motivos.items(), key=lambda x: -x[1]
    ):
        print(f"    descartadas por {motivo}: {quantidade}")

    return aprovadas
