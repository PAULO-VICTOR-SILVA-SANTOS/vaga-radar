"""
Vaga Radar - ponto de entrada.

Fluxo:
  1. busca vagas nos feeds publicos
  2. remove as que ja foram notificadas antes
  3. camada 1: filtro por palavra-chave (barato)
  4. camada 2: filtro por IA (opcional, so no que sobrou)
  5. envia as aprovadas no Telegram
  6. grava o historico

Toda execucao (com vaga enviada ou nao) termina em _encerrar(): confere a
saude do sistema, manda o alerta no Telegram se algo fugiu do normal e grava
uma entrada no log_auditoria.json. Ver auditoria.py.

Rodar local:  python src/main.py
"""
import sys
import time

import auditoria
import config
import filtro_data
import filtro_ia
import filtro_keyword
import fontes
import historico
import telegram


def _encerrar(dados, execucao, inicio, vagas=None):
    """
    Fecha a execucao: avalia a saude, envia (vagas e/ou alerta) e grava o log.
    Retorna quantas vagas foram enviadas.

    A parte de auditoria nunca pode derrubar a execucao: se falhar, so avisa
    no log e segue (o envio das vagas e o que importa).
    """
    ia = filtro_ia.ESTATISTICAS
    avaliacoes = ia.get("avaliacoes", [])
    execucao["ia"].update(
        chamadas=ia.get("chamadas", 0),
        falhas=ia.get("falhas", 0),
        erros_429=ia.get("erros_429", 0),
        ultimo_erro=ia.get("ultimo_erro"),
        avaliacoes=avaliacoes,
    )
    execucao["camadas"]["camada2_ia_avaliadas"] = len(avaliacoes)
    execucao["camadas"]["camada2_ia_aprovadas"] = sum(a["aprovada"] for a in avaliacoes)

    alertas = []
    try:
        alertas = auditoria.avaliar_saude(dados, execucao, ia.get("resultados", []))
    except Exception as erro:
        print(f"  [auditoria] falha ao avaliar saude ({type(erro).__name__})")
    aviso = auditoria.formatar_aviso(alertas)
    if aviso:
        print("\n" + aviso)

    enviadas = 0
    aviso_entregue = False
    if vagas:
        print(f"\n[6/6] Enviando {len(vagas)} vaga(s) no Telegram...")
        enviadas = telegram.enviar_lote(vagas, aviso)
        print(f"  enviadas: {enviadas}")
        aviso_entregue = enviadas > 0
    if aviso and not aviso_entregue:
        # Nada foi enviado (ou o envio falhou): o alerta sai sozinho.
        aviso_entregue = telegram.enviar_aviso(aviso)

    execucao["camadas"]["enviadas"] = enviadas
    execucao["avisos"] = [texto for _, texto in alertas]
    try:
        if aviso_entregue:
            auditoria.marcar_alertas_enviados(dados, [chave for chave, _ in alertas])
        auditoria.registrar(dados, execucao, inicio)
    except Exception as erro:
        print(f"  [auditoria] falha ao gravar o log ({type(erro).__name__})")
    return enviadas


def _executar(dados, execucao, inicio):
    print("=" * 60)
    print("VAGA RADAR")
    print(f"Camada de IA: {'LIGADA' if config.USE_AI else 'desligada'}")
    print("=" * 60)

    print("\n[1/6] Buscando nas fontes...")
    vagas = fontes.buscar_todas()
    print(f"  total bruto: {len(vagas)}")
    execucao["fontes"] = {nome: dict(info) for nome, info in fontes.RELATORIO.items()}
    execucao["camadas"]["brutas"] = len(vagas)

    if not vagas:
        print("\nNenhuma vaga retornada. Encerrando sem erro.")
        _encerrar(dados, execucao, inicio)
        return 0

    print(f"\n[2/6] Camada 0 - filtro por data (max {config.DIAS_MAX_VAGA} dias)...")
    vagas = filtro_data.filtrar(vagas)
    execucao["camadas"]["camada0_data"] = len(vagas)

    if not vagas:
        print("\nNenhuma vaga recente o suficiente.")
        _encerrar(dados, execucao, inicio)
        return 0

    print("\n[3/6] Removendo vagas ja vistas...")
    visto = historico.carregar()
    vagas = historico.separar_novas(vagas, visto)
    print(f"  novas: {len(vagas)}")
    execucao["camadas"]["novas"] = len(vagas)

    if not vagas:
        print("\nNada novo desde a ultima execucao.")
        _encerrar(dados, execucao, inicio)
        return 0

    print("\n[4/6] Camada 1 - filtro por palavra-chave...")
    vagas = filtro_keyword.filtrar(vagas)
    execucao["camadas"]["camada1_keyword"] = len(vagas)

    if not vagas:
        print("\nNenhuma vaga passou no filtro de palavra-chave.")
        visto = historico.marcar(vagas, visto)
        historico.salvar(visto)
        _encerrar(dados, execucao, inicio)
        return 0

    if config.USE_AI:
        print("\n[5/6] Camada 2 - filtro por IA...")
        vagas = filtro_ia.filtrar(vagas)
    else:
        print("\n[5/6] Camada 2 pulada (USE_AI=false)")

    if not vagas:
        print("\nNenhuma vaga passou no filtro de IA.")
        _encerrar(dados, execucao, inicio)
        return 0

    # Corta o excesso para nao inundar o Telegram numa execucao.
    total_aprovadas = len(vagas)
    vagas = vagas[: config.MAX_POR_EXECUCAO]
    if total_aprovadas > len(vagas):
        print(f"  limitando a {len(vagas)} de {total_aprovadas} aprovadas")

    enviadas = _encerrar(dados, execucao, inicio, vagas)

    # So marca como vista o que realmente foi enviado com sucesso.
    if enviadas > 0:
        visto = historico.marcar(vagas[:enviadas], visto)
        historico.salvar(visto)
        print(f"  historico atualizado: {len(visto)} vagas registradas")

    print("\nConcluido.")
    return 0


def main():
    inicio = time.monotonic()
    execucao = auditoria.nova_execucao()
    dados = auditoria.carregar()

    try:
        return _executar(dados, execucao, inicio)
    except Exception as erro:
        # Deixa registrado no log e devolve o erro para o handler abaixo,
        # que avisa no Telegram e encerra com codigo 1.
        execucao["erro_fatal"] = type(erro).__name__
        try:
            auditoria.registrar(dados, execucao, inicio)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:
        print(f"\nERRO FATAL: {type(erro).__name__}: {erro}")
        telegram.enviar_aviso(f"Vaga Radar falhou: {type(erro).__name__}: {erro}")
        sys.exit(1)
