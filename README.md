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

## Passo a passo de instalação

### 1. Criar o bot do Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome e um username terminado em `bot`
4. Ele devolve um **token** parecido com `7891234567:AAF...` — guarde

### 2. Descobrir seu chat ID

1. Mande qualquer mensagem para o bot que você acabou de criar
2. Abra no navegador (trocando `SEU_TOKEN`):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
3. Procure por `"chat":{"id":123456789` — esse número é seu **chat ID**

Se vier vazio, mande outra mensagem para o bot e recarregue.

### 3. Rodar na sua máquina primeiro

```bash
git clone https://github.com/SEU_USUARIO/vaga-radar.git
cd vaga-radar
pip install -r requirements.txt
```

**Teste as fontes antes de qualquer coisa:**

```bash
python src/testar_fontes.py
```

Isso mostra, fonte por fonte, se o feed respondeu e quantas vagas saíram.
Se alguma falhar, comente ela na lista `FONTES` do `src/config.py` — feeds
públicos mudam de endereço e de formato sem aviso.

**Depois rode o radar completo:**

```bash
export TELEGRAM_TOKEN="seu_token"
export TELEGRAM_CHAT_ID="seu_chat_id"
python src/main.py
```

No Windows (PowerShell), troque `export` por `$env:TELEGRAM_TOKEN="..."`.

### 4. Ajustar os filtros

Abra `src/config.py` e edite:

- `PALAVRAS_OBRIGATORIAS` — a vaga precisa ter pelo menos uma
- `PALAVRAS_BLOQUEADAS` — qualquer uma derruba a vaga
- `PERFIL` — o texto que a IA usa para julgar

Rode algumas vezes e veja o que passa. É normal ajustar por uma semana.

### 5. Subir para o GitHub Actions

No repositório, vá em **Settings → Secrets and variables → Actions**.

Em **Secrets**, adicione:

| Nome | Valor |
|---|---|
| `TELEGRAM_TOKEN` | o token do BotFather |
| `TELEGRAM_CHAT_ID` | seu chat ID |
| `GEMINI_API_KEY` | sua chave gratuita do Google AI Studio (só se for usar IA) |

Em **Variables**, adicione:

| Nome | Valor |
|---|---|
| `USE_AI` | `false` no começo |
| `NOTA_MINIMA` | `6` |
| `DIAS_MAX_VAGA` | `30` (não notifica vaga publicada há mais tempo que isso) |

Faça push. Vá na aba **Actions**, escolha "Vaga Radar" e clique em
**Run workflow** para testar manualmente. Depois disso ele roda sozinho
de 2 em 2 horas, das 8h às 22h (horário de João Pessoa).

### 6. Ligar a camada de IA

1. Crie uma chave gratuita em [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   (conta Google, sem cartão de crédito)
2. Adicione a chave como secret `GEMINI_API_KEY` no repositório
3. Mude a variável `USE_AI` para `true`

Custo: zero. O modelo usado é o `gemini-3.5-flash-lite`, que está na
cota gratuita do Google AI Studio. Se a cota gratuita for excedida em
algum dia de pico, a camada falha "aberta" (a vaga é liberada em vez de
descartada) — veja o comentário no topo de `filtro_ia.py`.

---

## Como ler os logs

A aba **Actions** mostra a saída de cada execução:

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

Se "aprovadas" der sempre 0, seus filtros estão apertados demais.
Se der 50, estão frouxos demais.

---

## Fonte extra: alertas por e-mail

LinkedIn e Gupy não têm feed público, mas mandam alertas por e-mail.
Ler a própria caixa é legítimo e costuma ser a fonte mais rica de todas.

### Configurar o Gmail

1. Ative a **verificação em duas etapas** na sua conta Google
2. Vá em `myaccount.google.com/apppasswords`
3. Gere uma senha de app (16 caracteres) e guarde

**Senha de app é revogável** a qualquer momento sem trocar sua senha
principal. Nunca use a senha normal da conta aqui.

### Testar

```bash
export EMAIL_USUARIO="seuemail@gmail.com"
export EMAIL_SENHA_APP="abcd efgh ijkl mnop"
python src/testar_email.py
```

A etapa 5 do diagnóstico é a mais importante: ela lista os domínios que
realmente aparecem na sua caixa. Compare com `EMAIL_REMETENTES` no
`config.py` e adicione os que faltarem.

### Ligar

```bash
export EMAIL_ATIVO="true"
python src/main.py
```

### Dica: filtrar por label

Crie no Gmail um filtro que marca os alertas de vaga com a label `Vagas`.
Depois, no `config.py`, troque `EMAIL_PASTA` para `"Vagas"`. Fica muito
mais rápido e preciso do que varrer a caixa inteira.

### Hotmail / Outlook

A Microsoft desativou IMAP com senha em contas pessoais — só funciona via
OAuth2, que é bem mais trabalhoso. **Solução prática:** configure no
Outlook um encaminhamento automático dos e-mails de vaga para o Gmail e
leia tudo por um canal só.

### Sobre rodar isso no GitHub Actions

Por padrão, colocar credencial de e-mail pessoal em secrets de
repositório é um risco maior que um token de bot: quem tiver acesso de
escrita ao repositório pode extrair o segredo, e em repositório
**público** um fork malicioso com workflow alterado é vetor real.

Neste projeto o repositório é **privado**, então esse risco principal
(fork malicioso de estranho) não se aplica - só quem já tem acesso ao
repositório (você) consegue explorar o secret. Por isso `EMAIL_ATIVO`,
`EMAIL_USUARIO` e `EMAIL_SENHA_APP` estão configurados como secrets
e o workflow os encaminha para a execução na nuvem.

Se um dia o repositório virar público, revise essa decisão antes -
nesse cenário, as opções mais seguras passam a ser:

1. Rodar a parte de e-mail só na sua máquina, quando quiser
2. Criar um Gmail dedicado que só recebe encaminhamento dos alertas

## Ideias para a v2

- Botões de "interessado" / "ignorar" direto na mensagem do Telegram
- Rascunho automático de mensagem para o recrutador
- Painel web com histórico e estatísticas de conversão
- Fontes brasileiras (Programathor, Trampos.co) se tiverem feed público

## Licença

MIT.
