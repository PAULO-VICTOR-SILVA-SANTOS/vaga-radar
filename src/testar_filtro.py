"""
Teste do filtro de palavra-chave (camada 1) contra o perfil atual.

    python src/testar_filtro.py          casos sinteticos com resultado esperado
    python src/testar_filtro.py --live   vagas reais dos feeds, uma linha por vaga

Nao envia nada no Telegram, nao chama a IA e nao grava o historico: so
busca (GET) nas fontes e mostra o que o filtro faria.
"""
import sys

import config
import filtro_keyword


def _vaga(titulo, descricao="", local="Brasil", fonte="GitHub (frontendbr/vagas)"):
    return {
        "id": titulo, "titulo": titulo, "empresa": "x", "local": local,
        "descricao": descricao, "url": "http://x", "fonte": fonte,
    }


# (esperado_passa, vaga, o_que_o_caso_prova)
CASOS = [
    # --- senioridade -------------------------------------------------------
    (True,  _vaga("Desenvolvedor Full Stack Junior", "React e Node.js"), "junior passa"),
    (True,  _vaga("Estagio em Desenvolvimento Web", "React, TypeScript"), "estagio passa"),
    (True,  _vaga("Desenvolvedor React", "Vaga em React, remoto"), "sem senioridade passa"),
    (True,  _vaga("Trainee Full Stack", "Node.js e React"), "trainee passa"),
    (False, _vaga("Desenvolvedor Full Stack Pleno", "React e Node.js"), "pleno no titulo"),
    (False, _vaga("Desenvolvedor React Pl", "React"), "'Pl' abreviado"),
    (False, _vaga("Desenvolvedor Frontend Sênior", "React"), "senior com acento"),
    (False, _vaga("Sr. Node.js Developer", "Node"), "Sr."),
    (False, _vaga("Full Stack Developer II", "React"), "nivel II"),
    (False, _vaga("Mid-Level React Developer", "React"), "mid-level"),
    (False, _vaga("Full Stack Specialist", "React"), "specialist"),
    (False, _vaga("Desenvolvedor React", "Nivel: Pleno. React e Node"), "pleno declarado na descricao"),
    (False, _vaga("Desenvolvedor Full Stack", "Buscamos desenvolvedor senior em React"), "'desenvolvedor senior' na descricao"),
    (True,  _vaga("Desenvolvedor React Junior", "Voce vai trabalhar com senior engineers na equipe. React"), "'senior engineers' de passagem nao derruba"),
    (True,  _vaga("Desenvolvedor React Junior", "Pleno dominio de HTML e CSS. React"), "'pleno dominio' nao e nivel"),
    (True,  _vaga("Desenvolvedor SQL Junior", "React e SQL"), "'sql' nao e o token 'pl'"),
    (False, _vaga("Back-end developer Cobol", "Procuramos Desenvolvedor(a) Cobol Sênior para o time"), "'Desenvolvedor(a) Cobol Senior' na descricao"),
    (False, _vaga("Desenvolvedor", "Vaga para Developer Full Stack Pleno, React"), "'Developer Full Stack Pleno' na descricao"),
    (True,  _vaga("Desenvolvedor React Junior", "Desenvolvedores juniores com mentoria de senior engineers. React"), "mentoria de senior nao derruba"),
    (False, _vaga("Desenvolvedor Full Stack", "React e Node. | labels: PJ, Pleno, Sênior, Remoto"), "rotulo Pleno/Senior do GitHub"),
    (True,  _vaga("Desenvolvedor Full Stack", "React e Node. | labels: CLT, Júnior, Remoto"), "rotulo Junior do GitHub passa"),
    # --- anos de experiencia -----------------------------------------------
    (True,  _vaga("Desenvolvedor React", "Experiencia de ate 2 anos com React"), "2 anos passa"),
    (True,  _vaga("Desenvolvedor React", "2+ anos de experiencia com React"), "2+ passa"),
    (True,  _vaga("Desenvolvedor React", "De 1 a 3 anos de experiencia com React"), "faixa vale o minimo"),
    (False, _vaga("Desenvolvedor React", "3+ anos de experiencia com React"), "3+ anos"),
    (False, _vaga("Desenvolvedor React", "Experiencia minima de 4 anos com React"), "4 anos"),
    (False, _vaga("Desenvolvedor React", "Mais de 2 anos de experiencia com React"), "'mais de 2' = 3+"),
    (False, _vaga("Desenvolvedor React", "3 a 5 anos de experiencia com React"), "faixa 3 a 5"),
    (False, _vaga("Desenvolvedor React", "5+ years of experience with React"), "5+ years"),
    (True,  _vaga("Desenvolvedor React Junior", "Empresa com 15 anos de mercado. React"), "anos da empresa nao contam"),
    # --- geografia ---------------------------------------------------------
    (True,  _vaga("Desenvolvedor React Junior", "React", local="Sao Paulo, SP - presencial"), "presencial em SP passa"),
    (True,  _vaga("Desenvolvedor React Junior", "React", local="Recife - hibrido"), "hibrido em Recife passa"),
    (True,  _vaga("Desenvolvedor React Junior", "React", local="Brazil", fonte="Remotive"), "Remotive com Brazil passa"),
    (True,  _vaga("Desenvolvedor React Junior", "Vaga remota. Requisitos: React. Responsabilidades: telas. Beneficios: VR.", local="Worldwide", fonte="RemoteOK"), "descricao em pt-br passa"),
    (False, _vaga("Junior React Developer", "React", local="Worldwide", fonte="RemoteOK"), "worldwide sem Brasil"),
    (False, _vaga("Junior React Developer", "React", local="USA Only", fonte="Remotive"), "USA only"),
    (False, _vaga("Junior React Developer", "React", local="Europe", fonte="Himalayas"), "Europa"),
    (False, _vaga("Junior React Developer", "React", local="Latin America", fonte="Remotive"), "LATAM nao conta como Brasil"),
    (False, _vaga("Desenvolvedor React Junior", "Remoto - Portugal. React", local="remoto / nacional"), "Portugal num repo BR"),
    (False, _vaga("Back-end Node.js Junior", "OPORTUNIDADE INTERNACIONAL. Localizacao: America Latina (LATAM). Voce vai atuar. Requisitos: Node. Responsabilidades: APIs.", local="remoto / nacional"), "LATAM em portugues nao vira Brasil"),
    (True,  _vaga("Back-end Node.js Junior", "Vaga aberta a toda a LATAM, com contratacao CLT no Brasil. Node", local="remoto / nacional"), "sinal explicito de Brasil vence LATAM"),
    # --- stack -------------------------------------------------------------
    (True,  _vaga("Desenvolvedor Python Junior", "FastAPI e PostgreSQL"), "Python agora e stack sua"),
    (True,  _vaga("Desenvolvedor Backend Junior", "Node.js, Express, MongoDB"), "Node + Mongo"),
    (True,  _vaga("Desenvolvedor Full Stack Junior", "Next.js, TypeScript, PostgreSQL"), "Next + TS + Postgres"),
    (True,  _vaga("Full Stack React/Angular Junior", "React"), "React junto com Angular passa"),
    (False, _vaga("Desenvolvedor Java Junior", "Spring Boot"), "Java como cargo"),
    (False, _vaga("Desenvolvedor PHP Junior", "Laravel"), "PHP como cargo"),
    (False, _vaga("Desenvolvedor .NET Junior", "C# e SQL Server"), ".NET como cargo"),
    (False, _vaga("Desenvolvedor Frontend Angular Junior", "Angular"), "Angular sem React"),
    (True,  _vaga("Desenvolvedor React Junior", "Diferencial: Angular, Java, Docker. React"), "gap citado de passagem passa"),
    (False, _vaga("Analista Financeiro Junior", "Planilhas e relatorios"), "nao e vaga de dev"),
    # --- ingles / nao-vaga -------------------------------------------------
    (False, _vaga("Desenvolvedor React Junior", "Ingles fluente. React"), "ingles fluente"),
    (False, _vaga("Desenvolvedor React Junior", "Banco de talentos. React"), "banco de talentos"),
]


def rodar_sinteticos():
    falhas = 0
    for esperado, vaga, prova in CASOS:
        passou, motivo = filtro_keyword.avaliar(vaga)
        ok = passou == esperado
        falhas += not ok
        marca = "ok  " if ok else "ERRO"
        print(f"  [{marca}] {'passa' if passou else 'corta':5} {prova} ({motivo})")
    print(f"\n{len(CASOS) - falhas}/{len(CASOS)} casos como esperado")
    return falhas


def rodar_live():
    import filtro_data
    import fontes

    print("Buscando nas fontes (somente leitura)...")
    vagas = filtro_data.filtrar(fontes.buscar_todas())
    print(f"\nVagas recentes (ate {config.DIAS_MAX_VAGA} dias): {len(vagas)}\n")

    aprovadas = []
    for vaga in vagas:
        passou, motivo = filtro_keyword.avaliar(vaga)
        if passou:
            aprovadas.append(vaga)
        print(f"{'PASSA' if passou else 'corta':5} | {vaga['fonte'][:22]:22} | "
              f"{vaga['titulo'][:55]:55} | {motivo}")

    print(f"\n{len(aprovadas)} de {len(vagas)} passariam para a camada de IA:")
    for vaga in aprovadas:
        print(f"  - {vaga['titulo']} | {vaga['empresa']} | {vaga['local']} | {vaga['url']}")


if __name__ == "__main__":
    if "--live" in sys.argv:
        rodar_live()
    else:
        sys.exit(1 if rodar_sinteticos() else 0)
