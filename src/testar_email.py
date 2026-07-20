"""
Diagnostico da leitura de e-mail.

Rode isto ANTES de ligar a fonte de e-mail no radar:

    python src/testar_email.py

Ele testa em etapas e diz exatamente onde parou:
  1. credenciais preenchidas
  2. login IMAP
  3. quantas mensagens tem no periodo
  4. quais remetentes aparecem na sua caixa (isso e o mais util)
  5. o que foi extraido
"""
import email
import imaplib
from collections import Counter

import config
import fontes_email


def etapa(numero, texto):
    print(f"\n[{numero}] {texto}")
    print("-" * 55)


def main():
    print("=" * 55)
    print("DIAGNOSTICO DE E-MAIL")
    print("=" * 55)

    etapa(1, "Credenciais")
    if not config.EMAIL_USUARIO:
        print("EMAIL_USUARIO vazio.")
        print("Rode:  export EMAIL_USUARIO='seuemail@gmail.com'")
        return
    if not config.EMAIL_SENHA_APP:
        print("EMAIL_SENHA_APP vazio.")
        print("Gere em: myaccount.google.com/apppasswords")
        print("Rode:  export EMAIL_SENHA_APP='abcd efgh ijkl mnop'")
        return

    usuario = config.EMAIL_USUARIO
    mascarado = usuario[:3] + "***" + usuario[usuario.find("@"):]
    print(f"Usuario: {mascarado}")
    print(f"Senha de app: {len(config.EMAIL_SENHA_APP)} caracteres")
    print(f"Pasta: {config.EMAIL_PASTA}")
    print(f"Periodo: ultimos {config.EMAIL_DIAS_ATRAS} dias")

    etapa(2, "Login IMAP")
    try:
        conexao = imaplib.IMAP4_SSL(
            fontes_email.SERVIDOR_IMAP, fontes_email.PORTA_IMAP
        )
        conexao.login(usuario, config.EMAIL_SENHA_APP)
        print("Login OK")
    except imaplib.IMAP4.error as erro:
        print(f"FALHOU: {erro}")
        print("\nCausas mais comuns:")
        print("  - verificacao em duas etapas nao esta ativa na conta")
        print("  - voce usou a senha normal em vez da senha de app")
        print("  - a senha de app foi revogada")
        return

    etapa(3, "Pastas disponiveis")
    try:
        estado, pastas = conexao.list()
        if estado == "OK":
            for linha in pastas[:20]:
                print("  " + linha.decode("utf-8", errors="replace"))
    except Exception as erro:
        print(f"nao consegui listar: {erro}")

    etapa(4, "Mensagens no periodo")
    try:
        conexao.select(config.EMAIL_PASTA, readonly=True)
        estado, resultado = conexao.search(None, fontes_email._montar_busca_imap())
        ids = resultado[0].split() if estado == "OK" else []
        print(f"Total de mensagens: {len(ids)}")
    except Exception as erro:
        print(f"FALHOU: {erro}")
        conexao.logout()
        return

    if not ids:
        print("Nenhuma mensagem. Aumente EMAIL_DIAS_ATRAS e tente de novo.")
        conexao.logout()
        return

    etapa(5, "Remetentes encontrados (ESTA E A PARTE IMPORTANTE)")
    print("Compare com a lista EMAIL_REMETENTES do config.py.\n")

    amostra = ids[::-1][:80]
    contagem = Counter()
    reconhecidos = 0
    conhecidos = [r.lower() for r in config.EMAIL_REMETENTES]

    for id_msg in amostra:
        try:
            estado, dados = conexao.fetch(id_msg, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            if estado != "OK" or not dados or not dados[0]:
                continue
            cabecalho = email.message_from_bytes(dados[0][1])
            remetente = str(cabecalho.get("From", "")).lower()

            dominio = remetente
            if "@" in remetente:
                dominio = remetente.split("@")[-1].strip(" >\"'")

            marca = ""
            if any(r in remetente for r in conhecidos):
                marca = "  <-- reconhecido"
                reconhecidos += 1
            contagem[dominio + marca] += 1
        except Exception:
            continue

    for dominio, quantidade in contagem.most_common(25):
        print(f"  {quantidade:3}x  {dominio}")

    print(f"\nMensagens de remetentes reconhecidos: {reconhecidos}")
    if reconhecidos == 0:
        print("\nNenhum remetente bateu com a lista.")
        print("Copie os dominios acima que sao de vaga e adicione")
        print("em EMAIL_REMETENTES no config.py.")

    conexao.logout()

    etapa(6, "Extracao completa")
    if not config.EMAIL_ATIVO:
        print("EMAIL_ATIVO esta false. Ligando temporariamente para o teste...")
        config.EMAIL_ATIVO = True

    vagas = fontes_email.buscar()
    print(f"\nVagas extraidas: {len(vagas)}")

    for vaga in vagas[:5]:
        print(f"\n  fonte:  {vaga['fonte']}")
        print(f"  titulo: {vaga['titulo'][:70]}")
        print(f"  url:    {vaga['url'][:90]}")

    print("\n" + "=" * 55)
    print("Fim do diagnostico.")


if __name__ == "__main__":
    main()
