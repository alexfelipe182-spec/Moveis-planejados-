# Multi-Marcenarias

Plataforma para gestão de marcenaria com API em FastAPI, PostgreSQL, autenticação segura, painel web e automações de CI/CD.

## Apresentação para cliente

O [roteiro de demonstração local](docs/apresentacao-cliente.md) reúne acesso de
teste, seis passos de apresentação, um orçamento detalhado e custos ilustrativos.
A prévia usa dados descartáveis, não envia mensagens e não substitui o ambiente
definitivo. O roteiro também explica como reabrir e preparar o exemplo sem duplicações.

## Arquitetura

- Backend: Python 3.12, FastAPI, SQLAlchemy e Pydantic
- Banco: PostgreSQL com Alembic
- Cache/limites: Redis
- Autenticação: JWT, refresh token, rotação/revogação e CSRF para fluxos por cookie
- Multi-tenancy: uma organização por marcenaria, ownership obrigatório, referências
  compostas no banco e painel de plataforma separado
- Monetização: catálogo de planos, trial inicial, checkout em sandbox e webhooks
  idempotentes; Stripe só é habilitado depois da configuração de produção
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
- `recovery.yml` — backup e restauração isolada em PostgreSQL 18, com dados sintéticos

## Operação e conclusão da primeira versão

O [roteiro de operação e aceite](docs/operations.md) separa as correções de código
das pendências que dependem do responsável: banco definitivo, armazenamento e rotina
de backup, remetente de e-mail e número comercial. O ensaio de recuperação do CI não
é um backup dos dados de produção.

- [Configuração de e-mail](docs/email-setup.md)
- [Configuração do atendimento público](docs/public-contact.md)
- [Arquitetura SaaS e plano de lançamento](docs/saas-architecture.md)

Os dados internos são restritos a administradores. O cadastro público cria uma nova
marcenaria isolada, concede a essa primeira conta a propriedade administrativa do
próprio espaço e inicia 14 dias de teste no plano comercial escolhido. O catálogo
oferece Essencial (R$ 49/mês), Profissional (R$ 99/mês) e Empresarial
(R$ 249/mês). A cobrança permanece desativada por padrão e só deve ser ligada
depois da configuração e homologação do provedor de pagamento.
Listagens possuem paginação e busca no servidor; decisões e edições de orçamento usam
bloqueio de linha para preservar valores aprovados.

**Atenção ao Docker existente:** a stack usa PostgreSQL 18 e um volume novo.
Instalações com PostgreSQL 16 precisam seguir o plano de migração do manual antes
de aplicar o Compose atualizado. Nenhum volume antigo é convertido automaticamente.

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

## Deploy

O arquivo `render.yaml` define a API, o frontend estático, o PostgreSQL e o Key Value (Redis) para produção no Render. As conexões com banco e Redis são injetadas por referências entre recursos, sem versionar credenciais. As migrações Alembic fazem parte do processo de inicialização/validação da aplicação.
