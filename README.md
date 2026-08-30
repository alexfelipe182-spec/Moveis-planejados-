# MM — Multi-Marcenarias

Plataforma SaaS para gestão de marcenarias, com API FastAPI, PostgreSQL, isolamento multi-tenant, orçamento inteligente, produção, custos, painel web e automações de CI/CD.

## Arquitetura

- Backend: Python 3.12, FastAPI, SQLAlchemy e Pydantic
- Banco: PostgreSQL 16 com Alembic
- Cache/limites: Redis
- SaaS: tenants isolados por `tenant_id`, admin por empresa e superadmin da plataforma
- Autenticação: JWT, refresh token, rotação/revogação e CSRF para fluxos por cookie
- Orçamento: precificação determinística, análise inteligente, recomendação histórica de preço/risco e persistência da decisão
- Produção: projetos, etapas, fornecedores, insumos, custos e rentabilidade
- Frontend: HTML, CSS e JavaScript responsivo
- Contêineres: Docker e Docker Compose
- Deploy: Render e publicação de imagem no GHCR

## SaaS

O onboarding de uma nova marcenaria está disponível em `frontend/onboarding.html` e cria um tenant próprio com owner administrador e trial. O painel de operação da plataforma está em `frontend/superadmin.html` e exige `is_superadmin`.

Planos iniciais: Starter, Professional e Business. O backend aplica limite de usuários conforme o plano. O modelo de Tenant possui status de assinatura, provedor e identificadores externos preparados para integração com cobrança.

**Importante:** nenhum provedor de pagamento é tratado como ativo sem credenciais e validação de webhook. Até essa integração ser configurada, cobrança permanece desabilitada e o superadmin controla apenas o estado comercial da conta.

## Qualidade e segurança

O GitHub Actions valida Ruff, imports, PostgreSQL, Redis, Alembic, testes com cobertura, auditoria de dependências, frontend, Docker, secret scanning e CodeQL. A branch SaaS também adiciona um Recovery Drill que cria backup, restaura em outro banco e valida a revisão Alembic.

Workflows principais:

- `postgres.yml` — CI principal, backend, banco, Redis, migrações, testes e frontend
- `docker.yml` — build, smoke tests e publicação da imagem da API
- `security.yml` — Gitleaks e auditoria das dependências Python
- `codeql.yml` — análise estática de segurança do Python
- `recovery.yml` — ensaio sintético de backup e restore PostgreSQL

## Estrutura

```text
backend/                 API FastAPI, tenant isolation, modelos, serviços, migrações e testes
frontend/                site, painel, onboarding SaaS e superadmin
.github/workflows/       CI/CD, segurança e recovery drill
docs/                    arquitetura SaaS e homologação
render.yaml              infraestrutura declarativa do Render
docker-compose*.yml      ambientes local, teste e produção
```

## Segurança multi-tenant

As rotas operacionais derivam a empresa do usuário autenticado; o cliente nunca escolhe `tenant_id` na requisição. IDs e referências de outro tenant retornam como não encontrados. O superadmin possui endpoints separados em `/api/v1/superadmin/*` e não ganha acesso cruzado implícito através do CRUD normal.

Leia `docs/SAAS_ARCHITECTURE.md` e `docs/PRODUCTION_ACCEPTANCE.md` antes de qualquer rollout.

## Fluxo de publicação

Mudanças entram por Pull Request. A `main` deve exigir CI summary, Security summary, resolução de threads e pelo menos uma aprovação humana. Antes do rollout multi-tenant, faça backup real do PostgreSQL e conclua a homologação cliente → orçamento → aceite → projeto → produção.
