# Multi-Marcenarias

Plataforma de gestão para marcenarias com API em FastAPI, PostgreSQL, autenticação segura, painel web e automações de CI/CD.

## Arquitetura

- Backend: Python 3.12, FastAPI, SQLAlchemy e Pydantic
- Banco: PostgreSQL com Alembic
- Cache/limites: Redis
- Autenticação: JWT, refresh token, rotação/revogação e CSRF para fluxos por cookie
- Frontend: HTML, CSS e JavaScript
- Contêineres: Docker e Docker Compose
- Deploy: Render e publicação de imagem no GHCR

## Qualidade e segurança

O GitHub Actions valida automaticamente Ruff, imports, PostgreSQL, Redis, Alembic, testes com cobertura, auditoria de dependências, frontend, Docker, secret scanning e CodeQL.

Workflows principais:

- `postgres.yml` — CI principal, backend, banco, Redis, migrações, testes e frontend
- `docker.yml` — build, smoke tests e publicação da imagem da API
- `security.yml` — Gitleaks e auditoria das dependências Python
- `codeql.yml` — análise estática de segurança do Python

## Estrutura do projeto

```text
backend/                 API FastAPI, modelos, serviços, migrações e testes
frontend/                site e painel web
.github/workflows/       CI/CD e segurança
docs/                    documentação complementar
render.yaml              infraestrutura declarativa do Render
docker-compose*.yml      ambientes local, teste e produção
```

## Desenvolvimento local

Crie suas variáveis de ambiente a partir de `.env.production.example` ou das configurações adequadas ao ambiente. Nunca versione segredos reais.

Para validar a stack de testes com Docker:

```bash
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from app
```

Para o backend, use o diretório `backend/` e execute as validações do projeto com as mesmas ferramentas usadas no CI.

## Fluxo recomendado no GitHub

Mudanças devem ser feitas em uma branch, abertas em Pull Request e mescladas na `main` somente após os checks obrigatórios passarem. A branch `main` deve permanecer protegida contra exclusão e force-push.

## Deploy no Render

O arquivo `render.yaml` descreve a API, o PostgreSQL e o Key Value (Redis) para produção no Render. O frontend permanece no serviço existente, gerenciado separadamente para evitar recursos duplicados. As conexões com banco e Redis são injetadas por referências entre recursos, sem versionar credenciais. As migrações Alembic fazem parte da inicialização da API; por isso, se o banco estiver inacessível, a API pode encerrar a inicialização.

A configuração do frontend, incluindo fallback de navegação para rotas como `/dashboard/`, está documentada em [`docs/frontend-hosting.md`](docs/frontend-hosting.md).

## Recuperação segura de conexão PostgreSQL

Use esta sequência se o deploy da API falhar com erros como `failed to resolve host`, `could not translate host name` ou erro de conexão do Psycopg:

1. No painel do Render, abra o workspace correto e confira se o serviço PostgreSQL esperado realmente existe e está disponível.
2. Confira a variável `DATABASE_URL` configurada no serviço da API. Não publique o valor completo em issues, prints ou mensagens, pois ele pode conter usuário e senha.
3. Compare o hostname configurado com o hostname atual do banco. Se o banco tiver sido recriado, a URL antiga pode apontar para um endereço inexistente.
4. Antes de criar, excluir ou substituir qualquer banco, verifique backups, snapshots e opções de recuperação disponíveis. Um banco novo não recupera automaticamente os dados do banco anterior.
5. Só depois de confirmar o banco correto, atualize a variável de ambiente da API com a URL de conexão interna fornecida pelo Render e faça um deploy controlado.
6. Verifique os logs da migração e confirme que `/ready` indica que o banco está acessível. Em seguida, teste login e operações de leitura/escrita com uma conta de teste.
7. Se não houver banco existente nem backup recuperável, interrompa o processo e decida explicitamente se deve criar um banco novo. Essa decisão pode envolver custos e perda dos dados anteriores.

Não contorne a falha removendo a migração de inicialização ou declarando a API saudável sem conexão com o banco. Isso pode ocultar a indisponibilidade sem restaurar as funções que dependem dos dados.
