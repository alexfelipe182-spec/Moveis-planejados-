# Auditoria de prontidão para produção — 31/08/2026

## Resumo executivo

A base técnica está madura para evolução, mas ainda não deve operar como SaaS multiempresa com mais de uma marcenaria real até que o isolamento de tenant seja implementado e testado.

## Achados críticos

### P0 — Ausência de isolamento multi-tenant
- `User` não possui vínculo com empresa/tenant.
- `Customer` não possui `tenant_id`.
- `Quote` não possui `tenant_id` e referencia `Customer` globalmente.
- O CRUD genérico lista e busca registros sem filtro de empresa.
- Rotas de escrita usam `require_admin`, mas o conceito de admin ainda é global.

Risco: quando houver duas marcenarias, dados podem ser acessados fora do escopo da empresa se o isolamento não for implementado de forma centralizada.

Critério de aceite:
- entidade `Tenant`/`Marcenaria`;
- `tenant_id` em todos os dados de negócio;
- usuário vinculado ao tenant;
- consultas sempre filtradas pelo tenant autenticado;
- FK/constraints coerentes;
- testes com Tenant A e Tenant B provando isolamento de list/read/create/update/delete.

### P0 — Proteção da main não está efetiva
O ruleset existe, mas a auditoria anterior registrou que ele não possui branch-alvo efetivo. A branch deve exigir PR, checks obrigatórios e bloquear force-push/deleção.

### P1 — Fluxo comercial de orçamento precisa de validação ponta a ponta
O backend possui modelos e módulos de orçamento, itens, custos, margem, decisões e fluxo de projeto, porém o critério comercial deve ser validado via frontend → API → PostgreSQL:
1. login;
2. cadastrar cliente;
3. criar orçamento;
4. adicionar itens;
5. calcular custos/margem;
6. aprovar/rejeitar;
7. converter em projeto;
8. acompanhar status.

### P1 — IA deve ser assistiva e auditável
A inteligência de orçamento deve interpretar a descrição e produzir proposta estruturada, mas o cálculo final de preços deve permanecer determinístico. Nenhuma proposta deve ser enviada ou persistida como aprovada sem ação humana.

### P1 — Onboarding comercial ainda precisa ser fechado
Criar fluxo de primeira empresa, administrador, identidade, dados básicos, configuração inicial e ambiente de demonstração.

## Arquitetura recomendada para multi-tenant

- `tenants`: id, nome, slug, status, created_at, configurações comerciais.
- `users.tenant_id` obrigatório para usuários operacionais.
- `customers.tenant_id`, `products.tenant_id`, `categories.tenant_id`, `quotes.tenant_id`, `projects.tenant_id` e demais entidades de negócio.
- Índices compostos por `tenant_id` nos campos de consulta frequente.
- Resolução central do tenant a partir do usuário autenticado.
- Nunca aceitar `tenant_id` arbitrário do frontend para autorização.
- Serviços/CRUD devem receber o tenant atual explicitamente ou aplicar query scope obrigatório.

## Ordem de execução

1. Fundação multi-tenant e testes de isolamento.
2. Orçamento ponta a ponta.
3. IA real de orçamento com aprovação humana.
4. Hardening de produção/CI/deploy.
5. Onboarding e pacote comercial.

## Definition of Done

Uma etapa só termina quando:
- Ruff passa;
- Pytest passa;
- Alembic upgrade funciona em banco limpo e banco existente;
- PostgreSQL e Redis passam no CI;
- Security Gates e CodeQL passam;
- frontend valida;
- não há quebra de autenticação/CSRF;
- critérios de isolamento e autorização têm testes automatizados.
