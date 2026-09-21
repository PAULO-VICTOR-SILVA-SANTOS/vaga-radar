"""
Testes da auditoria e da checagem de saude (auditoria.py + main.py).

    python src/testar_saude.py

Tudo simulado: fontes falsas, Telegram e IA substituidos, arquivos numa pasta
temporaria. Nao usa rede e nao mexe em vagas_vistas.json nem em
log_auditoria.json de verdade.
"""
import contextlib
import io
import os
import sys
import tempfile
from datetime import timedelta
from unittest import mock

import auditoria
import config
import filtro_ia
import fontes
import main
import telegram

falhas = []


def confere(condicao, descricao):
    print(f"  [{'ok  ' if condicao else 'ERRO'}] {descricao}")
    if not condicao:
        falhas.append(descricao)


def _execucao(fontes_=None):
    e = auditoria.nova_execucao()
    e["fontes"] = {n: {"vagas": v, "erro": None} for n, v in (fontes_ or {}).items()}
    return e


def _rodar(dados, fontes_=None, ia=None):
    """Uma execucao so da parte de saude. ia = lista de bool das chamadas."""
    e = _execucao(fontes_)
    if ia:
        e["ia"]["ultimo_erro"] = "HTTP 429 (limite de cota)"
    return auditoria.avaliar_saude(dados, e, ia or [])


# --------------------------------------------------------------------------
def testar_fontes():
    print("\nFontes")
    d = auditoria._vazio()
    confere(_rodar(d, {"Fonte": 0}) == [], "1 execucao com 0 vagas: sem alerta")
    confere(_rodar(d, {"Fonte": 0}) == [], "2 execucoes com 0 vagas: sem alerta")
    alertas = _rodar(d, {"Fonte": 0})
    confere(len(alertas) == 1 and "Fonte" in alertas[0][1], "3 execucoes com 0 vagas: alerta")
    confere("0 vagas em 3" in alertas[0][1], "texto cita a fonte e as 3 execucoes")

    # anti-spam
    auditoria.marcar_alertas_enviados(d, [alertas[0][0]])
    confere(_rodar(d, {"Fonte": 0}) == [], "problema persistente: nao repete na hora")
    d["saude"]["alertas"]["fonte:Fonte"] = (
        auditoria._agora() - timedelta(hours=config.REALERTA_HORAS + 1)
    ).isoformat()
    confere(len(_rodar(d, {"Fonte": 0})) == 1, f"repete depois de {config.REALERTA_HORAS}h")

    # recuperacao
    confere(_rodar(d, {"Fonte": 5}) == [], "voltou a trazer vagas: sem alerta")
    confere("fonte:Fonte" not in d["saude"]["alertas"], "recuperada: alerta limpo do estado")
    _rodar(d, {"Fonte": 0}); _rodar(d, {"Fonte": 0})
    confere(len(_rodar(d, {"Fonte": 0})) == 1, "recaiu: novo alerta sai na hora (3 seguidas de novo)")

    # uma fonte ruim nao mascara as boas
    d = auditoria._vazio()
    for _ in range(3):
        alertas = _rodar(d, {"Boa": 10, "Ruim": 0})
    confere([c for c, _ in alertas] == ["fonte:Ruim"], "so a fonte com problema e citada")

    # erro (excecao) tambem conta
    d = auditoria._vazio()
    for _ in range(3):
        e = _execucao(); e["fontes"] = {"Fonte": {"vagas": 0, "erro": "ConnectionError"}}
        alertas = auditoria.avaliar_saude(d, e, [])
    confere(len(alertas) == 1 and "ConnectionError" in alertas[0][1], "3 falhas seguidas: alerta com o tipo do erro")

    # e-mail: 0 vagas e normal, falha nao
    d = auditoria._vazio()
    for _ in range(5):
        alertas = _rodar(d, {"E-mail": 0})
    confere(alertas == [], "e-mail com 0 vagas por muitas execucoes: sem alerta")
    for _ in range(3):
        e = _execucao(); e["fontes"] = {"E-mail": {"vagas": 0, "erro": "IMAP4_SSL"}}
        alertas = auditoria.avaliar_saude(d, e, [])
    confere(len(alertas) == 1, "e-mail falhando 3 vezes: alerta")

    # limite proprio por fonte
    d = auditoria._vazio()
    with mock.patch.dict(config.LIMITE_ZEROS_POR_FONTE, {"Nicho": 6}):
        for _ in range(5):
            alertas = _rodar(d, {"Nicho": 0})
        confere(alertas == [], "limite proprio (6): 5 zeros nao alertam")
        confere(len(_rodar(d, {"Nicho": 0})) == 1, "limite proprio (6): 6o zero alerta")

    # fonte ausente numa execucao (ex: e-mail desligado) nao altera o contador
    d = auditoria._vazio()
    _rodar(d, {"A": 0}); _rodar(d, {"A": 0}); _rodar(d, {"B": 3})
    confere(len(_rodar(d, {"A": 0})) == 1, "execucao sem a fonte A nao zera o contador dela")


def testar_ia():
    print("\nIA")
    limite = config.LIMITE_FALHAS_IA
    d = auditoria._vazio()
    confere(_rodar(d, ia=[True, True, False]) == [], "1 falha isolada: sem alerta")
    d = auditoria._vazio()
    alertas = _rodar(d, ia=[True] + [False] * limite)
    confere(len(alertas) == 1 and alertas[0][0] == "ia", f"{limite} falhas seguidas no fim: alerta")
    confere("429" in alertas[0][1], "texto traz o ultimo erro (429)")

    d = auditoria._vazio()
    _rodar(d, ia=[False, False]);
    confere(d["saude"]["ia"]["falhas_seguidas"] == 2, "falhas acumulam entre execucoes")
    alertas = _rodar(d, ia=[False])
    confere(len(alertas) == 1, "2 + 1 falhas em execucoes diferentes: alerta")
    _rodar(d, ia=[False, True])
    confere(d["saude"]["ia"]["falhas_seguidas"] == 0, "sucesso ao final zera o contador")
    _rodar(d, ia=[True, False, False])
    confere(d["saude"]["ia"]["falhas_seguidas"] == 2, "conta so as falhas do final da execucao")
    _rodar(d)
    confere(d["saude"]["ia"]["falhas_seguidas"] == 2, "execucao sem chamadas de IA nao mexe no contador")


def testar_arquivo():
    print("\nArquivo de log")
    with tempfile.TemporaryDirectory() as pasta, mock.patch.object(
        config, "ARQUIVO_AUDITORIA", os.path.join(pasta, "log.json")
    ):
        confere(auditoria.carregar()["execucoes"] == [], "sem arquivo: comeca vazio")
        d = auditoria.carregar()
        for i in range(config.AUDITORIA_MAX_EXECUCOES + 5):
            e = _execucao({"F": 1})
            e["ia"]["avaliacoes"] = [{"titulo": f"vaga {i}", "nota": 5}]
            d["execucoes"].append(e)
        auditoria.salvar(d)
        d2 = auditoria.carregar()
        n = len(d2["execucoes"])
        confere(n == config.AUDITORIA_MAX_EXECUCOES, f"poda no maximo de {n} execucoes")
        com_detalhe = sum(bool(e["ia"]["avaliacoes"]) for e in d2["execucoes"])
        confere(com_detalhe == config.AUDITORIA_DETALHE_ULTIMAS, "so as ultimas guardam nota vaga a vaga")
        confere(not os.path.exists(config.ARQUIVO_AUDITORIA + ".tmp"), "sem arquivo temporario sobrando")

        with open(config.ARQUIVO_AUDITORIA, "w") as f:
            f.write("{ corrompido")
        with contextlib.redirect_stdout(io.StringIO()):
            confere(auditoria.carregar()["execucoes"] == [], "arquivo corrompido: recomeca sem quebrar")


def testar_mensagem_telegram():
    print("\nMensagem do Telegram")
    vaga = {"titulo": "Dev <React>", "empresa": "X", "local": "Remoto", "fonte": "F",
            "url": "http://x", "nota": 8, "motivo": "ok"}
    aviso = auditoria.formatar_aviso([("k", "Fonte 'RemoteOK' retornou 0 vagas")])
    msg = telegram._montar_mensagem(vaga, aviso)
    confere(msg.startswith("<b>⚠️ ATENÇÃO"), "aviso destacado no INICIO da mensagem")
    confere(msg.index("ATENÇÃO") < msg.index("Dev &lt;React&gt;"), "aviso vem antes da vaga")
    confere("Fonte 'RemoteOK'" in msg, "aviso traz o texto do problema")
    confere(telegram._montar_mensagem_simples(vaga, aviso).startswith("⚠️ ATENÇÃO"), "versao sem HTML tambem")
    confere(telegram._montar_mensagem(vaga).startswith("<b>Dev"), "sem aviso: mensagem igual a de antes")
    confere(auditoria.formatar_aviso([]) is None, "sem alertas: nenhum aviso")


# --------------------------------------------------------------------------
def _vagas_falsas():
    base = {"empresa": "Acme", "local": "Remoto - Brasil", "url": "", "fonte": "Programathor",
            "data_publicacao": None, "descricao": "React e Node.js, vaga em Brasil."}
    return [dict(base, id=f"id{i}", titulo=t, url=f"http://x/{i}")
            for i, t in enumerate(["Dev React Junior", "Dev Full Stack Junior", "Backend Node Junior"])]


def _rodar_main(pasta, fontes_relatorio, resultados_ia, vagas=None):
    """Executa main.main() completo com tudo externo simulado."""
    enviados = {"lotes": [], "avisos": []}

    def buscar():
        fontes.RELATORIO.clear()
        fontes.RELATORIO.update(fontes_relatorio)
        return vagas if vagas is not None else _vagas_falsas()

    def ia_falsa(vaga):
        status = resultados_ia.pop(0)
        if status == "ok":
            return 8, "boa aderencia", "ok"
        return 10, "IA indisponivel (HTTPError), vaga liberada", status

    def lote(v, aviso=None):
        enviados["lotes"].append((list(v), aviso))
        return len(v)

    def aviso(texto):
        enviados["avisos"].append(texto)
        return True

    antigo = os.getcwd()
    os.chdir(pasta)
    try:
        with mock.patch.object(fontes, "buscar_todas", buscar), \
             mock.patch.object(filtro_ia, "_avaliar_detalhado", ia_falsa), \
             mock.patch.object(filtro_ia, "PAUSA_ENTRE_CHAMADAS_SEGUNDOS", 0), \
             mock.patch.object(config, "USE_AI", True), \
             mock.patch.object(telegram, "enviar_lote", lote), \
             mock.patch.object(telegram, "enviar_aviso", aviso), \
             contextlib.redirect_stdout(io.StringIO()):
            main.main()
    finally:
        os.chdir(antigo)
    return enviados


def testar_main_completo():
    print("\nExecucao completa (main) simulada")
    import json
    with tempfile.TemporaryDirectory() as pasta:
        # 1) execucao normal: registra o log, sem alerta
        env = _rodar_main(pasta, {"Programathor": {"vagas": 3, "erro": None}}, ["ok"] * 3)
        log = json.load(open(os.path.join(pasta, "log_auditoria.json"), encoding="utf-8"))
        e = log["execucoes"][-1]
        confere(len(log["execucoes"]) == 1, "grava 1 entrada no log")
        c = e["camadas"]
        confere((c["brutas"], c["camada0_data"], c["novas"], c["camada1_keyword"]) == (3, 3, 3, 3), "contagens das camadas 0 e 1")
        confere((c["camada2_ia_avaliadas"], c["camada2_ia_aprovadas"], c["enviadas"]) == (3, 3, 3), "contagens da IA e enviadas")
        confere(e["ia"]["avaliacoes"][0]["nota"] == 8 and e["ia"]["avaliacoes"][0]["motivo"] == "boa aderencia", "guarda nota e motivo por vaga")
        confere(env["lotes"][0][1] is None and env["avisos"] == [], "execucao normal: nenhum aviso no Telegram")

        # 2) fonte zerada por 3 execucoes: alerta standalone (nada a enviar)
        pasta2 = tempfile.mkdtemp()
        for i in range(3):
            env = _rodar_main(pasta2, {"RemoteOK": {"vagas": 0, "erro": None}}, [], vagas=[])
        confere(len(env["avisos"]) == 1 and "RemoteOK" in env["avisos"][0], "3a execucao com fonte zerada: aviso proprio no Telegram")
        confere(env["avisos"][0].startswith("⚠️ ATENÇÃO"), "aviso destacado")
        env = _rodar_main(pasta2, {"RemoteOK": {"vagas": 0, "erro": None}}, [], vagas=[])
        confere(env["avisos"] == [], "4a execucao (mesmo problema): nao repete o aviso")
        log = json.load(open(os.path.join(pasta2, "log_auditoria.json"), encoding="utf-8"))
        confere(len(log["execucoes"]) == 4, "todas as 4 execucoes ficaram no log")

        # 3) IA com 429 seguidos: alerta vai NO TOPO da mensagem da vaga
        pasta3 = tempfile.mkdtemp()
        env = _rodar_main(pasta3, {"Programathor": {"vagas": 3, "erro": None}}, ["http_429"] * 3)
        aviso_topo = env["lotes"][0][1]
        confere(aviso_topo is not None and "IA falhou 3 vezes" in aviso_topo and "429" in aviso_topo, "3 falhas 429: aviso vai junto da 1a vaga")
        confere(env["avisos"] == [], "aviso nao e enviado duas vezes")
        log = json.load(open(os.path.join(pasta3, "log_auditoria.json"), encoding="utf-8"))
        confere(log["execucoes"][-1]["ia"]["erros_429"] == 3, "log conta os erros 429")
        confere(all(not a["ia_ok"] for a in log["execucoes"][-1]["ia"]["avaliacoes"]), "log marca as avaliacoes que falharam")

        # 4) erro fatal: fica no log e sobe para o handler
        pasta4 = tempfile.mkdtemp()
        with mock.patch.object(fontes, "buscar_todas", side_effect=RuntimeError("x")):
            antigo = os.getcwd(); os.chdir(pasta4)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        main.main()
                        levantou = False
                    except RuntimeError:
                        levantou = True
            finally:
                os.chdir(antigo)
        log = json.load(open(os.path.join(pasta4, "log_auditoria.json"), encoding="utf-8"))
        confere(levantou and log["execucoes"][-1]["erro_fatal"] == "RuntimeError", "erro fatal registrado e propagado")


def testar_programathor():
    print("\nProgramathor: erro real x 'sem vaga junior hoje'")
    import fontes_programathor as fp

    class Resp:
        def __init__(self, texto, ok=True):
            self.text, self._ok = texto, ok
        def raise_for_status(self):
            if not self._ok:
                raise fp.requests.HTTPError("500")

    def buscar_com(resposta):
        with mock.patch.object(fp.requests, "get", resposta),              mock.patch.object(fp.time, "sleep"),              contextlib.redirect_stdout(io.StringIO()):
            return fp.buscar()

    vencida = '<div class="cell-list opacity-60p"><a href="/jobs/1-x"><h3>Vencida x</h3></a></div>'
    confere(buscar_com(lambda *a, **k: Resp(vencida)) == [], "so vagas vencidas: retorna 0 sem erro (normal)")

    try:
        buscar_com(lambda *a, **k: Resp("", ok=False))
        levantou = None
    except Exception as erro:
        levantou = type(erro).__name__
    confere(levantou == "HTTPError", "site com erro 500: levanta HTTPError (vira falha no monitoramento)")

    try:
        buscar_com(lambda *a, **k: Resp("<html>pagina sem cards</html>"))
        levantou = None
    except Exception as erro:
        levantou = type(erro).__name__
    confere(levantou == "ValueError", "pagina sem nenhum card: levanta ValueError (layout mudou)")

    confere(config.LIMITE_ZEROS_POR_FONTE.get("Programathor", 3) > 3, "Programathor tem limite proprio de zeros")


if __name__ == "__main__":
    testar_fontes()
    testar_ia()
    testar_arquivo()
    testar_mensagem_telegram()
    testar_programathor()
    testar_main_completo()
    print(f"\n{'TUDO OK' if not falhas else str(len(falhas)) + ' FALHA(S)'}")
    sys.exit(1 if falhas else 0)
