"""
Configuracao central do Vaga Radar.
Edite este arquivo para ajustar seu perfil e filtros.
"""
import json
import os

# ---------------------------------------------------------------------------
# LIGA / DESLIGA A CAMADA DE IA
# Comece com "false". Quando entender o fluxo, mude para "true".
# ---------------------------------------------------------------------------
USE_AI = os.getenv("USE_AI", "true").lower() == "true"

# Nota minima (0-10) dada pela IA para a vaga ser notificada.
NOTA_MINIMA = int(os.getenv("NOTA_MINIMA", "6"))

# ---------------------------------------------------------------------------
# CAMADA 0 - FILTRO POR DATA (vaga fresca, sem vaga expirada)
# Corta vaga publicada ha mais dias que isso. Se a fonte nao informar a
# data de publicacao, a vaga passa (nao penaliza fonte sem essa info).
# ---------------------------------------------------------------------------
DIAS_MAX_VAGA = int(os.getenv("DIAS_MAX_VAGA", "30"))

# ---------------------------------------------------------------------------
# SEU PERFIL - usado apenas pela camada de IA
# Os dados (stack, gaps, regras) ficam em perfil.json, na raiz do repo.
# Para atualizar o curriculo, edite aquele arquivo; aqui so montamos o texto
# que vai no prompt.
# ---------------------------------------------------------------------------
ARQUIVO_PERFIL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "perfil.json"
)


def _montar_perfil(p):
    stack = p["stack"]
    sen = p["senioridade"]
    gaps = p["gaps"]
    return f"""
{p['cargo_alvo']}, baseado em {p['localizacao']}.

LINGUAGENS: {', '.join(stack['linguagens'])}.
FRONT: {', '.join(stack['front'])}.
BACK: {', '.join(stack['back'])}.
DADOS: {', '.join(stack['bancos'])}.
INTEGRACOES: {', '.join(stack['integracoes'])}.
AUTOMACAO: {', '.join(stack['automacao'])}.
FERRAMENTAS: {', '.join(stack['ferramentas'])}.

MATCH FORTE (stack que a vaga precisa girar em torno): {', '.join(p['match_forte'])}.

DIFERENCIAIS: {'; '.join(p['diferenciais'])}.

SENIORIDADE: procura SOMENTE {', '.join(sen['aceita'][:-1])} ou {sen['aceita'][-1]}. NAO serve
{', '.join(sen['nao_aceita'])}, nem vaga que exija mais de
{sen['anos_experiencia_max']} anos de experiencia como desenvolvedor. "Pleno"
no titulo ou como nivel da vaga e incompativel, mesmo sem anos explicitos.
Ele ainda nao tem a primeira vaga formal como desenvolvedor.

GEOGRAFIA: {p['geografia']['regra']}. Vaga fora do Brasil, ou que exija fuso
horario ou idioma nao-BR como requisito central, NAO serve.

INGLES: {p['ingles']}. Vaga que exija ingles intermediario, avancado, fluente
ou conversacional e incompativel.

GAPS (nao penalize sozinhos; so nao trate como match forte se forem requisito
CENTRAL da vaga): {'; '.join(gaps['sem_experiencia_profissional'])}. Ainda sem
confirmacao: {'; '.join(gaps['nao_confirmado'])}. Citados de passagem ou como
"diferencial desejavel", nao mudam nada.

NAO SERVE: banco de talentos sem posicao aberta.
"""


with open(ARQUIVO_PERFIL, "r", encoding="utf-8") as _arquivo:
    PERFIL_DADOS = json.load(_arquivo)
PERFIL = _montar_perfil(PERFIL_DADOS)

# ---------------------------------------------------------------------------
# CAMADA 1 - FILTRO POR PALAVRA-CHAVE (barato, roda primeiro)
# ---------------------------------------------------------------------------

# A vaga precisa conter PELO MENOS UMA destas palavras.
#
# DECISOES (perfil atualizado com o curriculo ATS v2):
#  - Alvo: SOMENTE junior, trainee, estagio ou vaga sem senioridade. Pleno,
#    senior e afins sao cortados (titulo, marcador de nivel na descricao e
#    anos de experiencia acima de ANOS_EXPERIENCIA_MAX).
#  - Alvo: SOMENTE Brasil (remoto BR, ou presencial/hibrido em qualquer
#    cidade do pais). Fora do Brasil e cortado.
#  - Python/FastAPI agora conta como stack sua.
#  - Java/Spring, .NET, PHP, Angular, Ruby, Delphi como CARGO no titulo sao
#    cortados: seu Java e academico e os demais nao fazem parte da stack.
#    Citados de passagem na descricao nao derrubam a vaga.
#  - React Native / mobile PASSA: a base de React transfere.
#  - "junior"/"trainee"/"estagio" sozinhos NAO entram aqui de proposito:
#    sem isso, "Estagio de Enfermagem" passaria so pelo nivel, sem nenhuma
#    palavra de dev. O nivel e avaliado nos bloqueios abaixo e pela IA.
PALAVRAS_OBRIGATORIAS = [
    # Linguagens
    "javascript", "typescript", "js developer", "python",
    # Front
    "react", "reactjs", "react.js", "next.js", "nextjs",
    "redux", "styled components", "tailwind",
    # Back
    "node", "node.js", "nodejs", "express", "fastapi",
    "api rest", "apis rest", "rest api", "restful",
    # Dados
    "postgresql", "postgres", "supabase", "mongodb", "firebase",
    # Cargos
    "full stack", "fullstack", "full-stack",
    "front-end", "frontend", "front end",
    "back-end", "backend", "back end",
    "web developer", "desenvolvedor web", "desenvolvedor full",
    "desenvolvedor front", "desenvolvedor back",
    "programador web", "engenheiro de software",
]

# BLOQUEIO NO TITULO
# O titulo define o cargo. Se aparece aqui, a vaga nao e para voce,
# nao importa o que a descricao diga.
PALAVRAS_BLOQUEADAS_TITULO = [
    # Senioridade acima do seu nivel (so junior/trainee/estagio/sem nivel)
    "pleno", "senior", "sr.", "sr ", "specialist", "especialista",
    "mid-level", "mid level", "midlevel", "middle", "intermediate",
    "staff engineer", "principal", "tech lead", "team lead",
    "engineering manager", "head of", "architect", "arquiteto",
    "coordenador", "gerente de", "diretor",
    # Stacks que nao sao a sua, como CARGO
    "desenvolvedor java", "programador java", "java developer",
    "desenvolvedor php", "php developer", "programador php",
    "desenvolvedor .net", ".net developer", "desenvolvedor c#",
    "desenvolvedor angular", "angular developer",
    "desenvolvedor ruby", "ruby developer",
    "desenvolvedor delphi", "cobol",
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

# Senioridade no titulo que precisa de fronteira de palavra: como substring
# ("pl", "lead", "ii") casaria com "sql", "misleading", "iiot" etc.
# Roda sobre o titulo ja normalizado (minusculo, sem acento).
REGEX_SENIORIDADE_TITULO = [
    r"\bsr\b", r"\bpl\b", r"\b(?:ii|iii|iv)\b", r"\bmid\b",
    r"\blead\b", r"\blider\b", r"\bstaff\b",
]

# Nivel da propria vaga declarado na DESCRICAO (titulo generico, nivel no
# corpo). Deliberadamente restrito a "nivel: pleno" / "desenvolvedor senior":
# "pleno" solto e comum em portugues ("pleno dominio") e "senior engineers"
# aparece em vaga junior ("voce vai trabalhar com senior engineers").
REGEX_SENIORIDADE_DESCRICAO = [
    r"\b(?:nivel|senioridade|seniority|level|perfil|cargo|vaga)\s*(?:de\s+)?[:\-]?\s*"
    r"(?:desenvolvedor\w*\s+)?(?:pleno|senior|sr|mid|middle|especialista)\b",
    # "Desenvolvedor(a) Cobol Senior", "Developer Full Stack Pleno": aceita
    # "(a)" e no maximo uma palavra entre o cargo e o nivel.
    r"\b(?:desenvolvedor\w*|developer|engineer|engenheir\w+|programador\w*|dev)"
    r"(?:\(a\))?(?:\s+(?:full[\s-]?stack|front[\s-]?end|back[\s-]?end|[\w#+.-]+))?"
    r"\s+(?:pleno|senior|sr|mid-level|especialista)\b",
    r"\b(?:pleno|senior)\s*[/(]\s*(?:pleno|senior)\b",
    r"\(\s*(?:pleno|senior|sr)\s*\)",
]

# Rotulos/tags que as fontes anexam ao fim da descricao ("| labels: PJ,
# Pleno, Senior" nos repos do GitHub; "| tags: ..." no RemoteOK). Como o
# nivel e declarado ali de forma explicita, qualquer um destes derruba a vaga.
ROTULOS_SENIORIDADE = [
    "pleno", "senior", "sr", "especialista", "specialist", "lead", "staff",
    "principal", "mid", "middle", "mid-level",
]

# Anos de experiencia como desenvolvedor: acima disto a vaga cai. Vem do
# perfil.json ("mais de ~2 anos" = 3 ou mais). Em faixas ("2 a 4 anos") vale
# o minimo. Quem calcula e o filtro_keyword.
ANOS_EXPERIENCIA_MAX = PERFIL_DADOS["senioridade"]["anos_experiencia_max"]

# BLOQUEIO NA DESCRICAO
# Aqui so o que e realmente eliminatorio, esteja onde estiver.
# Cuidado ao aumentar esta lista: e facil derrubar vaga boa que apenas
# menciona uma tecnologia de passagem.
#
# Anos de experiencia NAO ficam aqui: sao tratados por regex (ver acima).
PALAVRAS_BLOQUEADAS_DESCRICAO = [
    # Ingles eliminatorio (voce tem so ingles basico)
    "fluent english", "native english", "english fluency",
    "fluent in english", "ingles fluente", "ingles avancado",
    "ingles intermediario", "intermediate english",
    "advanced english", "must speak english", "espanhol fluente",
    "spoken english", "excellent english", "strong english",
    "english proficiency", "proficiency in english",
    "written and spoken", "verbal and written english",
    "business english", "conversational english", "ingles conversacional",
    "ingles obrigatorio", "english is required", "english is mandatory",
    "fluency in english", "proficient in english",
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
# "Fullstack Java" cai, porque "fullstack" e cargo e nao entra nesta lista.
TECNOLOGIAS_SUAS = [
    "javascript", "typescript", "react", "reactjs", "react.js",
    "next.js", "nextjs", "next js", "node", "node.js", "nodejs",
    "express", "redux", "tailwind", "styled components",
    "postgresql", "postgres", "supabase", "mongodb", "firebase",
    "python", "fastapi",
    "html", "css", "sass", "scss", "vite",
]

# STACK CONFLITANTE NO TITULO
# Se o titulo tiver uma destas E NAO tiver nenhuma da sua stack, corta.
# Isso pega "Frontend Angular", "Fullstack Java", "Dev .NET" — formatos
# que a lista de cargo nao alcanca porque nao comecam com "Desenvolvedor".
#
# A regra e condicional de proposito: "Full Stack React/Angular" passa,
# porque React aparece junto. "Frontend Angular" cai, porque so tem Angular.
# Python saiu daqui: agora e stack sua (Django/Flask continuam fora).
STACKS_CONFLITANTES = [
    "angular", "django", "flask", ".net", "c#", "dotnet",
    "php", "laravel", "ruby", "rails", "spring", "java ",
    "sql server", "golang", " go ", "rust", "scala", "kotlin", "elixir",
    "vue", "svelte", "ember",
]

# FILTRO GEOGRAFICO: SOMENTE BRASIL
# Remoto BR e presencial/hibrido em qualquer cidade do Brasil servem, entao
# nao ha mais bloqueio por cidade. O que corta e vaga sem ligacao com o
# Brasil. "Worldwide"/"Anywhere"/"LATAM" NAO contam como Brasil: sao vagas
# internacionais que costumam exigir ingles e fuso estrangeiro.

# Sinais de que a vaga e brasileira (procurados no titulo, local e no inicio
# da descricao, ja normalizados).
SINAIS_BRASIL = [
    "brasil", "brazil", "brasileir", "pt-br", "clt",
    "joao pessoa", "sao paulo", "rio de janeiro", "belo horizonte",
    "curitiba", "porto alegre", "florianopolis", "brasilia", "salvador",
    "recife", "fortaleza", "campinas", "goiania", "manaus", "belem",
    "natal", "maceio", "aracaju", "teresina", "sao luis", "vitoria",
    "cuiaba", "campo grande", "londrina", "joinville", "campina grande",
]

# Palavras de portugues que raramente aparecem em vaga em ingles. Tres ou
# mais na descricao contam como sinal de Brasil (vaga escrita em pt-br).
PALAVRAS_PORTUGUES = [
    "voce", "requisitos", "responsabilidades", "beneficios", "atividades",
    "vaga", "conhecimentos", "diferencial", "empresa",
]

# Indicios explicitos de vaga fora do Brasil (ou aberta a toda a America
# Latina). Valem para qualquer fonte, mesmo com texto em portugues: um repo
# brasileiro tambem publica "Remoto - Portugal" e "Oportunidade internacional".
# Um sinal explicito de Brasil (SINAIS_BRASIL) tem prioridade sobre estes.
INDICADORES_FORA_DO_BRASIL = [
    "usa only", "us only", "u.s. only", "united states", "north america",
    "europe", "emea", "apac", "uk only", "united kingdom", "canada",
    "germany", "india", "australia", "portugal", "espanha", "spain",
    "argentina", "mexico", "colombia", "chile",
    "latam", "america latina", "latin america", "oportunidade internacional",
    "international opportunity",
]

# Fontes que ja sao brasileiras: nao exigem sinal de Brasil, so caem se
# houver indicio de fora. Qualquer outra fonte (RemoteOK, Remotive, WWR,
# Himalayas e o que for adicionado a FONTES) precisa trazer sinal de Brasil.
FONTES_BRASILEIRAS_PREFIXOS = ("GitHub", "E-mail", "Programathor")

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
    "indeed.com",          # Alertas diretos de vagas do Indeed (muito uteis)
    "linkedin.com",        # Alertas de vaga do LinkedIn ("jobalerts-noreply@linkedin.com")
    "gupy.com.br",         # Alertas de vaga do Gupy (ATS mais usado no Brasil; remetente real "no-reply@gupy.com.br")
    "remotar.com.br",      # Focado em vagas remotas no Brasil
    "programathor.com.br", # Vagas de tecnologia/desenvolvimento
    "micro1.ai",           # Plataforma de vagas globais/IA
]

# ---------------------------------------------------------------------------
# ARQUIVOS
# ---------------------------------------------------------------------------
ARQUIVO_VISTAS = "vagas_vistas.json"

# ---------------------------------------------------------------------------
# AUDITORIA E SAUDE (ver auditoria.py)
# ---------------------------------------------------------------------------
# Log persistente: uma entrada por execucao. O Actions commita este arquivo.
ARQUIVO_AUDITORIA = "log_auditoria.json"
AUDITORIA_MAX_EXECUCOES = 200       # ~25 dias a 8 execucoes por dia
AUDITORIA_DETALHE_ULTIMAS = 30      # so estas guardam a nota de cada vaga

# Alerta: fonte com 0 vagas (ou falhando) por tantas execucoes seguidas.
LIMITE_ZEROS_FONTE = 3
# Fontes de nicho podem ficar em 0 legitimamente por dias: limite proprio.
LIMITE_ZEROS_POR_FONTE = {
    # Programathor: so pedimos junior/estagio e ha poucas vagas ativas, entao
    # 0 por um dia e meio (12 execucoes) ainda e normal. Site fora do ar ou
    # layout alterado nao dependem disto: viram falha e alertam em 3.
    "Programathor": 12,
}
# Fontes que naturalmente ficam dias sem trazer nada (alerta por e-mail so
# chega quando ha vaga nova). Ficam de fora do alerta de "0 vagas", mas o
# alerta de FALHA (login IMAP, por exemplo) continua valendo.
FONTES_SEM_ALERTA_DE_ZERO = ("E-mail",)

# Alerta: chamadas da IA que falham (erro, cota 429, chave ausente) seguidas.
LIMITE_FALHAS_IA = int(os.getenv("LIMITE_FALHAS_IA", "3"))

# Um alerta que continua valendo so e repetido depois deste intervalo.
REALERTA_HORAS = 24

# Quantos dias manter uma vaga no historico antes de esquecer.
DIAS_HISTORICO = 45

# Limite de vagas notificadas por execucao, para nao inundar o Telegram.
MAX_POR_EXECUCAO = 10

# ---------------------------------------------------------------------------
# SEGREDOS - nunca escreva valores aqui, use variaveis de ambiente
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Chave gratuita do Google AI Studio (aistudio.google.com/apikey).
# Sem cartao de credito, cota gratuita generosa no modelo Flash-Lite.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Opcional: aumenta o limite de chamadas a API do GitHub (60 -> 5000 req/h).
# No GitHub Actions, o secret automatico GITHUB_TOKEN ja serve para isso.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
