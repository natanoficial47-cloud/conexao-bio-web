# Deploy — Conexão BIO

**Vercel (site) + Render (API) + Supabase (banco)** — sem VM, sem túnel, sem domínio próprio.

```
navegador ──HTTPS──> Vercel ──proxy /api/*──> Render (API, HTTPS) ──pooler──> Supabase
   (cookie HttpOnly, uma origem só)
```

O navegador só conhece a Vercel. A Vercel reescreve `/api/*` para o endereço
`https://SEU-APP.onrender.com` (que já vem com HTTPS). Por isso o cookie de sessão é
`SameSite=Lax`, não precisa de CORS de verdade, e a URL da Vercel entra em `CORS_ORIGINS`
só porque o `Host` que chega na API é o do Render.

> A pasta `_oracle_arquivado/` guarda os arquivos do plano antigo (Oracle + Cloudflare
> Tunnel). Eles não são usados neste deploy. Aviso: `*.cfargotunnel.com` só serve como
> destino de CNAME de um domínio seu na Cloudflare; não funciona como URL pública sozinho.

---

## Passo 1 — Supabase (o banco)

1. Crie o projeto em <https://supabase.com/dashboard>, região **South America (São Paulo)**.
2. Anote o **ref** do projeto e a **senha do banco** (a de "Reset database password").
3. Monte a `DATABASE_URL` com o **connection pooler** (o host direto é IPv6-only e o
   Render é IPv4):

```
postgresql://postgres.REF_DO_PROJETO:SENHA@aws-1-sa-east-1.pooler.supabase.com:5432/postgres
```

   O prefixo certo é `aws-0` ou `aws-1`, dependendo do projeto. O `checar_banco.py` varre
   os dois e diz qual responde:

```powershell
.\venv\Scripts\python.exe set_senha_banco.py   # grava a senha no .env (URL-encoded)
.\venv\Scripts\python.exe checar_banco.py      # testa conexão, região, tabelas e RLS
```

4. **RLS** (importante): depois da **primeira subida da API** (ela cria as tabelas), abra o
   SQL Editor do Supabase e rode o arquivo **`rls_supabase.sql`**. Sem isso a chave pública
   do projeto (`anon key`) consegue ler as tabelas, inclusive os hashes de senha. A API
   entra como `postgres`, que ignora o RLS, então nada quebra. Rode de novo se criar tabelas.

---

## Passo 2 — Render (a API)

1. <https://render.com> → **New → Web Service** → conecte o repositório.
2. Configure:

| Campo | Valor |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips "*"` |
| Health Check Path | `/api/health` |
| Região | a mais próxima do Brasil que o Render oferecer |

3. Em **Environment**, cadastre (nada disso vai para o git):

| Variável | Valor |
|---|---|
| `PYTHON_VERSION` | `3.12.8` (fixa a versão do Python) |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` — **diferente em cada ambiente** |
| `DATABASE_URL` | a do pooler (Passo 1) |
| `ADMIN_NAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | primeiro administrador (senha forte) |
| `CLASS_CODE` | código da turma — escolha um que **não** esteja escrito em nenhum arquivo |
| `CORS_ORIGINS` | `https://SEU-SITE.vercel.app` (preencha depois do Passo 3) |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `lax` |

4. **Deploy**. Teste: `https://SEU-APP.onrender.com/api/health` → `{"ok":true,...}`.
5. Depois que o admin existir, **apague `ADMIN_EMAIL` e `ADMIN_PASSWORD`** do painel.
6. Rode o `rls_supabase.sql` (Passo 1.4).

Na primeira subida a API cria as tabelas e carrega as 8 missões iniciais. Depois disso
a psicologia cria, edita, arquiva e exclui missões pelo site (aba **Missões**).

---

## Passo 3 — Vercel (o site)

1. <https://vercel.com> → **Add New → Project** → o mesmo repositório. Framework: **Other**.
   O `vercel.json` já define build e pasta de saída.
2. Edite o `vercel.json` e troque o destino do rewrite:

```json
"destination": "https://SEU-APP.onrender.com/api/:path*"
```

3. Deploy. Copie a URL do site (`https://conexao-bio.vercel.app`) e coloque em
   `CORS_ORIGINS` no Render (o Render reinicia sozinho).

---

## Passo 4 — Não deixar a API dormir (plano gratuito do Render)

O serviço gratuito dorme depois de uns 15 minutos sem requisição, e a primeira resposta
depois disso demora de 30 a 60 segundos. Duas defesas, use as duas:

1. **Ping a cada 5 minutos.** No <https://uptimerobot.com> (gratuito): *Add New Monitor* →
   tipo **HTTP(s)** → URL `https://SEU-APP.onrender.com/api/health` → intervalo **5 minutos**.
   Confira no Render a cota de horas gratuitas por mês e os termos de uso.
2. **Aviso no site.** O login já mostra "Acordando o servidor..." depois de 3 segundos de
   espera, para a demora não parecer travamento.

A Vercel pode devolver erro 504 se a API demorar demais para acordar. O ping evita isso.
Se a escola não pode depender disso, o plano pago mais barato do Render não dorme nunca.

---

## Passo 5 — Validar

Com a API no ar (local, ou apontando para a Vercel com `API_BASE`):

```powershell
$env:API_BASE = "https://SEU-SITE.vercel.app/api"   # opcional; padrão: http://127.0.0.1:8000/api
.\venv\Scripts\python.exe validar_fase1.py   # cookie HttpOnly, bloqueio no banco, logout, permissões
.\venv\Scripts\python.exe validar_fase2.py   # senha forte, troca de senha, PIN provisório, logs
.\venv\Scripts\python.exe validar_fase3.py   # missões (psicologia cria) e Meu DNA
```

Os três apagam no final tudo que criaram (contas `@teste.local`, logs, missões de teste).
Resultado esperado nos testes locais com SQLite: **38 / 62 / 30**.

Depois, no navegador: login → painel → sair → conferir que o cookie sumiu
(DevTools → Application → Cookies).

---

## Rodar localmente

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Abra o `index.html` com o Live Server (porta 5500). O site detecta a porta 5500 e fala com
a API em `http://127.0.0.1:8000/api`. Para isso o `.env` precisa de
`CORS_ORIGINS=http://127.0.0.1:5500`.

---

## Variáveis de ambiente

| Variável | Onde | Para quê |
|---|---|---|
| `SECRET_KEY` | Render | assina o JWT. 32+ caracteres, diferente em cada ambiente |
| `DATABASE_URL` | Render | Postgres do Supabase via pooler |
| `ADMIN_NAME/EMAIL/PASSWORD` | Render | cria o primeiro admin (apague depois) |
| `CLASS_CODE` | Render | habilita o cadastro de alunos |
| `CORS_ORIGINS` | Render | origem do site na Vercel |
| `COOKIE_SECURE` | Render | `true` em produção |
| `COOKIE_SAMESITE` | Render | `lax` |

---

## O que já está fechado

**Fase 1** — sessão em cookie `HttpOnly`; logout que revoga o token no servidor; bloqueio
de tentativas no banco (5 erros por e-mail em 15 min; 100 por IP); `Origin` checado em
toda requisição que muda estado (CSRF); sem dependência externa no front; cabeçalhos de
segurança e cache no `vercel.json`.

**Fase 2** — senha forte (10+ caracteres, recusa senha comum/sequência/só números);
troca de senha; PIN provisório obrigatório; `token_version` (trocar a senha derruba as
outras sessões); log de acessos (aba **Acessos**, só admin).

**Fase 3** — missões criadas e editadas pela psicologia (também pelo admin); teste
**Meu DNA da Personalidade** (30 afirmações, 5 dimensões; o resultado é só do aluno).

**Ajustes deste deploy** — limite de cadastro por IP 10 → **100** por hora e de erros de
login por IP 30 → **100** (a escola inteira sai por um único IP); e-mail inexistente no
login gasta o mesmo tempo de um e-mail real; aviso de servidor acordando.

---

## Pontos que ainda dependem de você

- **Faixas do DNA** (baixo ≤ 14, intermediário 15–21, alto ≥ 22) e os rótulos da escala
  são suposição minha: o PDF não traz pontos de corte. Confirme com a psicóloga.
- **Quem vê o resultado do DNA:** hoje só o aluno. Se a psicologia precisar ver, decidam
  junto com a escola (são menores de idade; LGPD).
- **IP do visitante:** o `_client_ip` usa o primeiro valor de `X-Forwarded-For`. A Vercel
  deve sobrescrever esse cabeçalho; confirme mandando um `X-Forwarded-For` falso pela URL da
  Vercel e olhando o IP que aparece na aba **Acessos**. Quem chamar o endereço do Render
  direto (sem a Vercel) consegue forjar o IP. O bloqueio por e-mail continua valendo.
- **Retenção do log de acessos:** guarda IP e navegador de menores sem prazo para apagar.
  Defina um prazo com a escola.
- **Esqueci a senha:** não existe recuperação por e-mail; a equipe gera um novo PIN.
- **Excluir missão** apaga também o progresso dos alunos nela. Para só esconder, use **Arquivar**.
- Revisar quem tem acesso de administrador no Render, na Vercel e no Supabase.
