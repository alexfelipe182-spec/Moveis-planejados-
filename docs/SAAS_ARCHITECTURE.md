# Multi-Marcenarias — arquitetura SaaS

## Regra central

Todo dado operacional pertence a exatamente uma marcenaria (`tenant`). Usuários comuns e administradores de empresa jamais selecionam o tenant por parâmetro de requisição: o tenant é derivado da identidade autenticada.

## Isolamento

As tabelas `users`, `categories`, `customers`, `products`, `quotes`, `projects`, `activities`, `suppliers`, `materials`, `project_costs` e `quote_items` possuem `tenant_id` obrigatório.

As rotas normais sempre filtram `tenant_id == current_user.tenant_id`. Referências entre recursos também são validadas no mesmo tenant, impedindo que IDs de outra marcenaria sejam usados em produtos, materiais, orçamentos ou projetos.

O superadministrador não recebe acesso implícito aos dados operacionais através das rotas normais. A visão global existe apenas em endpoints `/api/v1/superadmin/*`, reduzindo o risco de acesso cruzado acidental.

## Conversão da instalação existente

A migração `011_multi_tenancy` cria um tenant legado ativo no plano Business e associa a ele os dados já existentes. A migração `012_quote_intelligence` reaproveita com segurança a persistência planejada no PR #77, agora sem colidir com a revisão `010_bootstrap_admin`. A migração `013_bootstrap_superadmin` promove o administrador legado definido por variável de ambiente para operador da plataforma.

## Papéis

- usuário: trabalha dentro de uma marcenaria;
- administrador: gerencia equipe e dados da própria marcenaria;
- superadministrador: gerencia empresas, planos e estado de acesso da plataforma.

## Planos

O catálogo inicial possui Starter, Professional e Business. Limites de usuários são aplicados no backend. Preços são configuração comercial inicial e devem ser revisados antes do lançamento público.

## Cobrança

O modelo de tenant já possui estado de assinatura, plano, provedor e IDs externos. O provedor de pagamento permanece desabilitado por padrão até haver escolha comercial, credenciais e validação de webhook. Nenhum pagamento é simulado ou considerado aprovado sem confirmação externa.

## Segurança para merge

A evolução deve entrar na `main` somente após:

1. migrations `upgrade head` em PostgreSQL 16;
2. testes de isolamento entre dois tenants;
3. CI, Security Gates, Docker, CodeQL e Recovery Drill verdes;
4. revisão humana obrigatória;
5. backup real da produção e plano de rollback;
6. homologação do fluxo cliente → orçamento → aceite → projeto → produção.
