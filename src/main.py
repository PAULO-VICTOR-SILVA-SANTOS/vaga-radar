"""
Vaga Radar - ponto de entrada.

Fluxo:
  1. busca vagas nos feeds publicos
  2. remove as que ja foram notificadas antes
  3. camada 1: filtro por palavra-chave (barato)
  4. camada 2: filtro por IA (opcional, so no que sobrou)
  5. envia as aprovadas no Telegram
  6. grava o historico

Rodar local:  python src/main.py
"""
import sys

import config
import filtro_data
import filtro_ia
import filtro_keyword
import fontes
import historico
import telegram


def main():
    print("=" * 60)
    print("VAGA RADAR")
    print(f"Camada de IA: {'LIGADA' if config.USE_AI else 'desligada'}")
    print("=" * 60)

    print("\n[1/6] Buscando nas fontes...")
    vagas = fontes.buscar_todas()
    print(f"  total bruto: {len(vagas)}")

    if not vagas:
        print("\nNenhuma vaga retornada. Encerrando sem erro.")
        return 0

    print(f"\n[2/6] Camada 0 - filtro por data (max {config.DIAS_MAX_VAGA} dias)...")
    vagas = filtro_data.filtrar(vagas)

    if not vagas:
        print("\nNenhuma vaga recente o suficiente.")
        return 0

    print("\n[3/6] Removendo vagas ja vistas...")
    visto = historico.carregar()
    vagas = historico.separar_novas(vagas, visto)
    print(f"  novas: {len(vagas)}")

    if not vagas:
        print("\nNada novo desde a ultima execucao.")
        return 0

    print("\n[4/6] Camada 1 - filtro por palavra-chave...")
    vagas = filtro_keyword.filtrar(vagas)

    if not vagas:
        print("\nNenhuma vaga passou no filtro de palavra-chave.")
        visto = historico.marcar(vagas, visto)
        historico.salvar(visto)
        return 0

    if config.USE_AI:
        print("\n[5/6] Camada 2 - filtro por IA...")
        vagas = filtro_ia.filtrar(vagas)
    else:
        print("\n[5/6] Camada 2 pulada (USE_AI=false)")

    if not vagas:
        print("\nNenhuma vaga passou no filtro de IA.")
        return 0

    # Corta o excesso para nao inundar o Telegram numa execucao.
    total_aprovadas = len(vagas)
    vagas = vagas[: config.MAX_POR_EXECUCAO]
    if total_aprovadas > len(vagas):
        print(f"  limitando a {len(vagas)} de {total_aprovadas} aprovadas")

    print(f"\n[6/6] Enviando {len(vagas)} vaga(s) no Telegram...")
    enviadas = telegram.enviar_lote(vagas)
    print(f"  enviadas: {enviadas}")

    # So marca como vista o que realmente foi enviado com sucesso.
    if enviadas > 0:
        visto = historico.marcar(vagas[:enviadas], visto)
        historico.salvar(visto)
        print(f"  historico atualizado: {len(visto)} vagas registradas")

    print("\nConcluido.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:
        print(f"\nERRO FATAL: {type(erro).__name__}: {erro}")
        telegram.enviar_aviso(f"Vaga Radar falhou: {type(erro).__name__}: {erro}")
        sys.exit(1)
