"""
Configuracao central do Vaga Radar.
Edite este arquivo para ajustar seu perfil e filtros.
"""
import os

# ---------------------------------------------------------------------------
# LIGA / DESLIGA A CAMADA DE IA
# Comece com "false". Quando entender o fluxo, mude para "true".
# ---------------------------------------------------------------------------
USE_AI = os.getenv("USE_AI", "true").lower() == "true"

# Nota minima (0-10) dada pela IA para a vaga ser notificada.
NOTA_MINIMA = int(os.getenv("NOTA_MINIMA", "6"))

# ---------------------------------------------------------------------------
# SEU PERFIL - usado apenas pela camada de IA
# ---------------------------------------------------------------------------
PERFIL = """
Desenvolvedor Full Stack junior, baseado em Joao Pessoa/PB, Brasil.

LINGUAGENS: JavaScript ES6+, TypeScript, Java (POO).
FRONT: React 19 (Hooks, Context API), Next.js, Redux Toolkit, Styled
Components, Tailwind, Bootstrap, HTML5, CSS3/SCSS.
BACK: Node.js, Express, APIs REST (consumo e criacao), autenticacao JWT.
DADOS: PostgreSQL via Supabase (em producao), MongoDB, Firebase.
FERRAMENTAS: Git/GitHub, Vite, ESLint, Vercel, Render, Cloudinary,
Mercado Pago (pagamentos PIX), N8N (automacao).

DIFERENCIAIS: tem projetos reais em producao para clientes pagantes,
incluindo um SaaS por assinatura com banco relacional. Tem 19 anos de
gestao administrativa e operacional, o que da leitura de negocio.
Cursa ADS (conclusao 12/2026) e formacao Full Stack EBAC (04/2026).

TEMPO DE EXPERIENCIA: cerca de 1 ano de pratica intensiva com React e
o ecossistema JavaScript, com entregas reais em producao. Isso importa
para julgar senioridade: uma vaga que peca 2 anos ainda pode valer a
tentativa; 4 anos ou mais nao.

INGLES: basico. Le documentacao tecnica sem dificuldade, mas NAO conduz
reuniao nem entrevista em ingles.

PROCURA: vaga remota, hibrida ou PRESENCIAL em Joao Pessoa/PB e regiao
metropolitana (Cabedelo, Bayeux, Santa Rita). Presencial em Joao Pessoa
serve normalmente, nao penalize a nota por isso.
Preferencia por CLT, mas aceita PJ. Nivel junior, trainee ou estagio
remunerado. Aceita pleno se o requisito de experiencia for baixo.

React Native e mobile com React SERVEM: ele nao tem projeto mobile no
portfolio, mas a base de React transfere. Nota media, nao nota baixa.

NAO SERVE: vagas presenciais FORA da Paraiba, vagas senior ou que pecam
4+ anos de experiencia, vagas que exigem ingles conversacional ou fluente,
banco de talentos sem posicao aberta, e stacks principais que ele nao
domina (Angular, Python/Django, .NET/C#, Spring Boot, PHP, Ruby).

OBSERVACAO SOBRE JAVA: ele tem Java (POO) em nivel academico, com um
projeto de jogo. Isso NAO o qualifica para vaga de Desenvolvedor Java
com Spring Boot — trate essas como incompativeis. Java como
"diferencial desejavel" numa vaga JavaScript e irrelevante, nao muda nada.
"""

# ---------------------------------------------------------------------------
# CAMADA 1 - FILTRO POR PALAVRA-CHAVE (barato, roda primeiro)
# ---------------------------------------------------------------------------

# A vaga precisa conter PELO MENOS UMA destas palavras.
#
# DECISOES JA TOMADAS (nao mexa sem querer mudar de ideia):
#  - React Native / mobile PASSA. Voce nao tem projeto mobile, mas a base
#    de React transfere e voce prefere ver e decidir.
#  - Presencial em Joao Pessoa PASSA. Nao ha bloqueio por localidade aqui;
#    quem julga isso e a camada de IA, pelo PERFIL acima.
#  - Java com Spring Boot e CORTADO no titulo. Seu Java e academico (POO,
#    um jogo), nao serve para vaga de backend Java.
#  - Vagas de stack que voce nao domina (Delphi, Java, .NET) sao CORTADAS
#    mesmo quando a empresa oferece treinamento. Voce ja se candidatou a
#    uma assim (TecnoSpeed/Delphi) e decidiu que nao vale o volume: o
#    radar existe para achar o que ja bate, nao para gerar excecoes.
#    Se quiser tentar uma dessas, faca manualmente.
#  - Estagio/trainee NAO tem tratamento especial. Passa se a stack bater,
#    como qualquer outra. Ubots e It4us passariam por citarem JavaScript.
PALAVRAS_OBRIGATORIAS = [
    # Linguagens
    "javascript", "typescript", "js developer",
    # Front
    "react", "reactjs", "react.js", "next.js", "nextjs",
    "redux", "styled components", "tailwind",
    # Back
    "node", "node.js", "nodejs", "express",
    # Dados
    "postgresql", "postgres", "supabase", "mongodb", "firebase",
    # Cargos
    "full stack", "fullstack", "full-stack",
    "front-end", "frontend", "front end",
    "back-end", "backend", "back end",
    "web developer", "desenvolvedor web", "desenvolvedor full",
    "desenvolvedor front", "desenvolvedor back",
    "programador web", "engenheiro de software",
    # Nivel (pega vaga generica de entrada)
    "junior", "trainee", "estagio", "estagiario", "entry level",
]

# BLOQUEIO NO TITULO
# O titulo define o cargo. Se aparece aqui, a vaga nao e para voce,
# nao importa o que a descricao diga.
PALAVRAS_BLOQUEADAS_TITULO = [
    # Senioridade acima do seu nivel
    "senior", "sr.", "sr ", " iii", "specialist", "especialista",
    "staff engineer", "principal", "tech lead", "team lead",
    "engineering manager", "head of", "architect", "arquiteto",
    "coordenador", "gerente de", "diretor",
    # Stacks que nao sao a sua, como CARGO
    "desenvolvedor java", "programador java", "java developer",
    "desenvolvedor php", "php developer", "programador php",
    "desenvolvedor python", "python developer",
    "desenvolvedor .net", ".net developer", "desenvolvedor c#",
    "desenvolvedor angular", "angular developer",
    "desenvolvedor ruby", "ruby developer",
    "desenvolvedor delphi", "desenvolvedor cobol",
    "wordpress", "drupal", "salesforce", "sap ", "abap",
    # Areas que nao sao desenvolvimento
    "designer", "ux/ui", "product owner", "scrum master",
    "analista de dados", "cientista de dados", "data scientist",
    "devops", "sre ", "seguranca da informacao", "qa ",
    "analista de suporte", "help desk", "comercial", "vendas",
    "recrutador", "recruiter", "marketing",
    # Ruido puro que ja apareceu no seu historico
    "pcb", "altium", "eletronica", "eletrico", "mecanico",
    "enfermeiro", "enfermagem", "medico", "farmaceutico",
    "motorista", "vendedor", "atendente", "operador de caixa",
    "auxiliar administrativo", "estoquista", "seguranca patrimonial",
]

# BLOQUEIO NA DESCRICAO
# Aqui so o que e realmente eliminatorio, esteja onde estiver.
# Cuidado ao aumentar esta lista: e facil derrubar vaga boa que apenas
# menciona uma tecnologia de passagem.
#
# Esta lista foi montada a partir de vagas REAIS que voce ja rejeitou.
PALAVRAS_BLOQUEADAS_DESCRICAO = [
    # Experiencia que voce nao tem
    "10+ years", "8+ years", "7+ years", "6+ years", "5+ years",
    "10+ anos", "8+ anos", "7+ anos", "6+ anos", "5+ anos",
    "minimo de 5 anos", "minimo de 6 anos", "minimo de 7 anos",
    "pelo menos 5 anos", "pelo menos 6 anos",
    # Ingles eliminatorio
    "fluent english", "native english", "english fluency",
    "fluent in english", "ingles fluente", "ingles avancado",
    "advanced english", "must speak english", "espanhol fluente",
    "spoken english", "excellent english", "strong english",
    "english proficiency", "proficiency in english",
    "written and spoken", "verbal and written english",
    # Nao e vaga de verdade
    "banco de talentos", "talent pool", "cadastro reserva",
    # Stacks proprietarias que voce ja rejeitou por nome
    # (Tely/Sitecnet: Protheus+AdvPL. Cadastra: VTEX IO.)
    "advpl", "protheus", "totvs", "vtex io", "faststore",
    "sap abap", "salesforce", "sharepoint", "power apps",
    # CMS que nao e sua area (Jobgether: WordPress+SEO)
    "wordpress", "woocommerce", "drupal", "joomla",
]

# TECNOLOGIAS SUAS (so nomes de tecnologia, NENHUM cargo)
# Usada para decidir se um titulo com stack conflitante deve ser salvo.
# "Full Stack React/Angular" passa porque React esta aqui.
# "Fullstack Python" cai, porque "fullstack" e cargo e nao entra nesta lista.
TECNOLOGIAS_SUAS = [
    "javascript", "typescript", "react", "reactjs", "react.js",
    "next.js", "nextjs", "next js", "node", "node.js", "nodejs",
    "express", "redux", "tailwind", "styled components",
    "postgresql", "postgres", "supabase", "mongodb", "firebase",
    "html", "css", "sass", "scss", "vite",
]

# STACK CONFLITANTE NO TITULO
# Se o titulo tiver uma destas E NAO tiver nenhuma da sua stack, corta.
# Isso pega "Frontend Angular", "Fullstack Python", "Dev .NET" — formatos
# que a lista de cargo nao alcanca porque nao comecam com "Desenvolvedor".
#
# A regra e condicional de proposito: "Full Stack React/Angular" passa,
# porque React aparece junto. "Frontend Angular" cai, porque so tem Angular.
STACKS_CONFLITANTES = [
    "angular", "python", "django", "flask", ".net", "c#", "dotnet",
    "php", "laravel", "ruby", "rails", "spring", "java ",
    "golang", " go ", "rust", "scala", "kotlin", "elixir",
    "vue", "svelte", "ember",
]

# BLOQUEIO POR LOCALIDADE
# Voce aceita presencial em Joao Pessoa e regiao. Fora da Paraiba, nao.
# So bloqueia se a vaga for explicitamente presencial NAQUELA cidade.
CIDADES_BLOQUEADAS = [
    "sao paulo", "rio de janeiro", "belo horizonte", "curitiba",
    "porto alegre", "florianopolis", "brasilia", "salvador",
    "recife", "fortaleza", "maracanau", "campinas",
    "sao jose dos campos", "goiania", "manaus", "belem",
    "natal", "maceio", "aracaju", "teresina", "sao luis",
    "vitoria", "cuiaba", "campo grande", "londrina", "joinville",
]

# Palavras que indicam que a vaga e presencial de verdade.
# Se aparecer uma destas JUNTO com uma cidade bloqueada, a vaga cai.
INDICADORES_PRESENCIAL = [
    "presencial", "on-site", "onsite", "no escritorio",
    "hibrido", "hybrid", "comparecer",
]

# Se a vaga disser que e remota, a cidade nao importa.
INDICADORES_REMOTO = [
    "remoto", "remote", "home office", "100% remoto",
    "trabalho remoto", "anywhere", "totalmente remoto",
]

# Compatibilidade: alguns scripts antigos usam este nome.
PALAVRAS_BLOQUEADAS = PALAVRAS_BLOQUEADAS_TITULO + PALAVRAS_BLOQUEADAS_DESCRICAO

# ---------------------------------------------------------------------------
# FONTES - feeds publicos, sem scraping de plataforma fechada
# ---------------------------------------------------------------------------
FONTES = [
    {
        "nome": "RemoteOK",
        "tipo": "json",
        "url": "https://remoteok.com/api",
    },
    {
        "nome": "Remotive",
        "tipo": "json",
        "url": "https://remotive.com/api/remote-jobs?category=software-dev",
    },
    {
        "nome": "WeWorkRemotely",
        "tipo": "rss",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    },
    {
        "nome": "Himalayas",
        "tipo": "json",
        "url": "https://himalayas.app/jobs/api",
    },
]

# ---------------------------------------------------------------------------
# FONTE EXTRA - ALERTAS DE VAGA POR E-MAIL (Gmail via IMAP)
#
# Le os alertas que LinkedIn, Gupy e afins mandam por e-mail. Essas
# plataformas nao tem feed publico, entao o e-mail e a unica via legitima.
#
# ATENCAO: exige senha de app do Gmail. Por padrao vem DESLIGADO e a
# recomendacao e rodar so na sua maquina, nao no GitHub Actions.
# ---------------------------------------------------------------------------
EMAIL_ATIVO = os.getenv("EMAIL_ATIVO", "false").lower() == "true"

EMAIL_USUARIO = os.getenv("EMAIL_USUARIO", "")
EMAIL_SENHA_APP = os.getenv("EMAIL_SENHA_APP", "")

# Pasta a ser lida. "INBOX" e a caixa de entrada.
# Se voce criar um filtro no Gmail que joga os alertas numa label
# chamada "Vagas", troque aqui por "Vagas" - fica bem mais rapido.
EMAIL_PASTA = os.getenv("EMAIL_PASTA", "INBOX")

# Quantos dias para tras buscar.
EMAIL_DIAS_ATRAS = int(os.getenv("EMAIL_DIAS_ATRAS", "2"))

# Teto de mensagens lidas por execucao.
EMAIL_MAX_MENSAGENS = 60

# Um alerta traz varias vagas; teto de links por e-mail.
EMAIL_MAX_LINKS_POR_EMAIL = 12

# So e-mails destes remetentes sao processados.
# Confira os enderecos reais na sua caixa e ajuste.
EMAIL_REMETENTES = [
    "indeed.com",         # Alertas diretos de vagas do Indeed (muito úteis)
    "remotar.com.br",     # Focado em vagas remotas no Brasil
    "programathor.com.br",# Vagas de tecnologia/desenvolvimento
    "micro1.ai"           # Plataforma de vagas globais/IA
]

# ---------------------------------------------------------------------------
# ARQUIVOS
# ---------------------------------------------------------------------------
ARQUIVO_VISTAS = "vagas_vistas.json"

# Quantos dias manter uma vaga no historico antes de esquecer.
DIAS_HISTORICO = 45

# Limite de vagas notificadas por execucao, para nao inundar o Telegram.
MAX_POR_EXECUCAO = 10

# ---------------------------------------------------------------------------
# SEGREDOS - nunca escreva valores aqui, use variaveis de ambiente
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Opcional: aumenta o limite de chamadas a API do GitHub (60 -> 5000 req/h).
# No GitHub Actions, o secret automatico GITHUB_TOKEN ja serve para isso.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
