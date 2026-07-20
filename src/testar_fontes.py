"""
Diagnostico das fontes.

Rode isto PRIMEIRO, na sua maquina:  python src/testar_fontes.py

Ele testa cada feed isoladamente e mostra o que voltou. Se uma fonte
falhar, comente ela na lista FONTES do config.py e siga com as outras.
"""
import json

import requests

import config
import fontes


def testar(fonte):
    print(f"\n{'=' * 55}")
    print(f"FONTE: {fonte['nome']}  ({fonte['tipo']})")
    print(f"URL: {fonte['url']}")
    print("=" * 55)

    try:
        resposta = requests.get(
            fonte["url"], headers=fontes.HEADERS, timeout=fontes.TIMEOUT
        )
        print(f"Status HTTP: {resposta.status_code}")
        print(f"Tamanho: {len(resposta.content)} bytes")
        print(f"Content-Type: {resposta.headers.get('content-type', '?')}")

        if resposta.status_code != 200:
            print("FALHOU: status diferente de 200")
            print(f"Inicio da resposta: {resposta.text[:200]}")
            return

        if fonte["tipo"] == "json":
            vagas = fontes._buscar_json(fonte)
        else:
            vagas = fontes._buscar_rss(fonte)

        print(f"Vagas parseadas: {len(vagas)}")

        if vagas:
            print("\nExemplo do que foi extraido:")
            exemplo = dict(vagas[0])
            exemplo["descricao"] = exemplo["descricao"][:200] + "..."
            print(json.dumps(exemplo, ensure_ascii=False, indent=2))
        else:
            print("ATENCAO: conectou mas nao extraiu nenhuma vaga.")
            print("O formato do feed provavelmente mudou.")
            print(f"Inicio da resposta bruta: {resposta.text[:300]}")

    except Exception as erro:
        print(f"FALHOU: {type(erro).__name__}: {erro}")


def main():
    print("Testando cada fonte isoladamente...")
    for fonte in config.FONTES:
        testar(fonte)
    print(f"\n{'=' * 55}")
    print("Fim do diagnostico.")


if __name__ == "__main__":
    main()
