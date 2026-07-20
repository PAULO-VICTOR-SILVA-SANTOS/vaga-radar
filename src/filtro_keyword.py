"""
Camada 1: filtro por palavra-chave.

Barato, deterministico, roda em todas as vagas.
Objetivo: cortar o ruido obvio antes de gastar chamada de IA.

Sao DUAS listas de bloqueio, e a diferenca importa:

  TITULO     - define o cargo. "Desenvolvedor Java" nao e sua vaga,
               nao importa o que a descricao diga.

  DESCRICAO  - so o que e realmente eliminatorio (ingles fluente,
               8 anos de experiencia). Bloquear tecnologia na descricao
               derruba vaga boa: quase toda vaga React cita Angular
               em algum lugar como "diferencial" ou "conhecimento em".
"""
import unicodedata

import config


def _normalizar(texto):
    """Minusculas e sem acento, para 'senior' casar com 'senior' acentuado."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _preparar(lista):
    return [_normalizar(p) for p in lista]


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

    # 3. E presencial em outra cidade?
    # So corta se for presencial E numa cidade bloqueada. Vaga remota
    # sediada em Sao Paulo continua valendo.
    local = _normalizar(vaga.get("local", ""))
    contexto = f"{titulo} {local} {descricao[:800]}"

    tem_remoto = any(
        _normalizar(p) in contexto for p in config.INDICADORES_REMOTO
    )
    if not tem_remoto:
        tem_presencial = any(
            _normalizar(p) in contexto for p in config.INDICADORES_PRESENCIAL
        )
        if tem_presencial:
            for cidade in _preparar(config.CIDADES_BLOQUEADAS):
                if cidade in contexto:
                    return False, f"presencial em {cidade}"

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
