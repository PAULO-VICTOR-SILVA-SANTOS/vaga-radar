# Vaga Radar

Bot que monitora feeds públicos de vagas remotas, filtra pelo meu perfil e
notifica no Telegram. Roda sozinho no GitHub Actions, de graça.

Nasceu de uma dor real: eu perdia vagas boas porque não tinha tempo de
garimpar todo dia, e as que achava eram majoritariamente incompatíveis.

## O que ele faz e o que ele não faz

**Faz:**
- Consulta feeds e APIs **públicas** de agregadores de vagas remotas
- Filtra em duas camadas: palavras-chave (barata) e IA (semântica)
- Notifica no Telegram com título, empresa, local, nota e link
- Guarda histórico para nunca notificar a mesma vaga duas vezes

**Não faz, por decisão de projeto:**
- Não faz scraping de LinkedIn, Gupy, Catho ou qualquer plataforma fechada
- Não se candidata automaticamente a nada
- Não cria conta, não preenche formulário, não burla captcha

A candidatura continua sendo manual e humana. A automação serve para eu
gastar meu tempo escolhendo entre 5 vagas boas em vez de filtrar 200 ruins.

## Arquitetura

```
feeds públicos
      |
      v
[ fontes.py ]          busca e normaliza formatos diferentes
      |
      v
[ historico.py ]       descarta o que já foi notificado
      |
      v
[ filtro_keyword.py ]  CAMADA 1 - corta ~90% do ruído, custo zero
      |
      v
[ filtro_ia.py ]       CAMADA 2 - opcional, avalia contexto e senioridade
      |
      v
[ telegram.py ]        notifica
```

As duas camadas existem porque chamar IA para classificar vaga de enfermagem
é desperdício. A camada 1 é um pré-filtro barato; a IA só vê o que sobrou.

## Stack

Python 3.11, `requests`, GitHub Actions (cron), API do Telegram Bot,
API do Google Gemini (Flash-Lite, camada gratuita) para a classificação
semântica.

Sem banco de dados: o histórico é um JSON que o próprio workflow commita
de volta no repositório.

---

## Como funciona por dentro

Este README documenta a arquitetura para quem quiser entender as decisões
técnicas (recrutadores, portfólio) — não é um tutorial de "clone e use":
o código é de um projeto pessoal, com direitos reservados (veja a Licença
no fim).

- **Telegram**: bot próprio via @BotFather; token e chat ID ficam como
  secrets do GitHub Actions, nunca no código.
- **Filtros**: duas camadas configuráveis em `src/config.py` — palavras-
  chave (barata, roda primeiro) e um perfil em texto livre que a camada
  de IA usa para julgar contexto e senioridade.
- **IA**: Google Gemini (Flash-Lite, camada gratuita), chamado só no que
  sobra da camada 1 — não compensa gastar chamada de IA pra descartar
  vaga fora da área.
- **Execução**: GitHub Actions com cron, sem servidor e sem banco de
  dados — o histórico é um JSON que o próprio workflow commita de volta.
- **Fonte extra por e-mail**: lê alertas do Indeed/LinkedIn/Gupy via
  IMAP (essas plataformas não têm feed público), autenticando com senha
  de app do Gmail — revogável a qualquer momento, nunca a senha principal
  da conta.

## Como ler os logs

A aba **Actions** mostra a saída de cada execução, contando quantas
vagas entraram e saíram de cada camada de filtro:

```
[1/6] Buscando nas fontes...
  RemoteOK: 87 vagas
  Remotive: 142 vagas
  total bruto: 229

[2/6] Camada 0 - filtro por data (max 30 dias)...
  aprovadas por data: 210 de 229 (expiradas/antigas: 12, sem data informada: 7)

[4/6] Camada 1 - filtro por palavra-chave...
  aprovadas: 14 de 210
    descartadas por cargo incompativel: 96
    descartadas por nenhuma palavra-chave da sua stack: 100
```

## Segurança do workflow

Repositório público, mas o `radar.yml` só dispara em `schedule` e
`workflow_dispatch` — nenhum dos dois é acionável por um fork de
terceiro, então secrets (Telegram, Gemini, senha de app do e-mail) não
ficam expostos a um fork malicioso via `pull_request`. Esse gatilho
nunca deve ser adicionado ao workflow sem revisar esse risco de novo.

## Ideias para a v2

- Botões de "interessado" / "ignorar" direto na mensagem do Telegram
- Rascunho automático de mensagem para o recrutador
- Painel web com histórico e estatísticas de conversão
- Fontes brasileiras (Programathor, Trampos.co) se tiverem feed público

## Licença

Todos os direitos reservados. O código está público para leitura e avaliação
(recrutadores, portfólio), mas não há licença de uso concedida — isso
significa que copiar, redistribuir ou reutilizar qualquer parte deste
código exige autorização explícita do autor.
