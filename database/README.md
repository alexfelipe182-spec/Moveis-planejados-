# Recuperação do banco — Multi-Marcenarias

Este projeto usa **PostgreSQL + SQLAlchemy + Alembic**. Não usa Prisma e não foi
convertido nem validado para MySQL. O SQL é derivado das migrações do código,
incluindo índices, chaves estrangeiras, restrições e a revisão do Alembic.

## Escolha apenas um caminho

### Banco existente com dados: migrações

Confirme o banco de destino e faça um backup antes de alterar sua estrutura.
Não execute o SQL de criação sobre um banco existente. Não use `alembic stamp`
para esconder migrações pendentes.

Na pasta `backend`, com as dependências instaladas e `DATABASE_URL` configurada
privadamente no ambiente (ou no arquivo `backend/.env`, nunca no GitHub):

```powershell
python -m alembic current
python -m alembic upgrade head
python -m alembic check
```

O comando `upgrade head` consulta a revisão atual e aplica somente as migrações
pendentes. Já estar na revisão `016_ai_automation` não reaplica as revisões antigas.
As correções nesta entrega habilitam a exportação SQL e não mudam o esquema final.
Se houver tabelas sem histórico Alembic, pare e compare a estrutura antes de agir.

### Banco novo e vazio: SQL completo

Arquivo: `multi_marcenarias_postgresql.sql`.

1. Crie um banco PostgreSQL vazio no destino escolhido. Isso pode gerar custos
   de hospedagem; o arquivo não cria uma conta ou serviço.
2. Use a conexão desse banco no seu cliente PostgreSQL. Configure `PGHOST`,
   `PGPORT`, `PGDATABASE` e `PGUSER` no ambiente. Use senha pelo prompt ou `.pgpass`.
3. Execute, a partir da raiz deste projeto:

```powershell
psql -X --set=ON_ERROR_STOP=1 --file=database/multi_marcenarias_postgresql.sql
```

O script recusa um schema que já tenha tabelas, sequências ou views. Toda a criação
fica em uma transação; uma falha impede a confirmação parcial. Não retire essa
proteção para forçar uma importação. Ele registra a revisão `016_ai_automation`.
Não execute migrações desde `base` novamente após importar esse arquivo.

O script cria a estrutura e os registros técnicos previstos nas migrações, não
recupera clientes ou usuários de um banco perdido. Recuperar registros exige um
backup. A primeira conta pode ser criada pelo cadastro de uma nova marcenaria,
que já cria seu responsável administrador e o período grátis de 30 dias. Não há
senha padrão, conta universal nem credencial real incluída na entrega.

## Tabelas e funções

| Área | Tabelas |
| --- | --- |
| Empresas e acesso | `tenants`, `users`, `refresh_tokens`, `password_reset_tokens` |
| Clientes e catálogo | `customers`, `categories`, `products` |
| Orçamentos | `quotes`, `quote_items` |
| Produção e custos | `projects`, `suppliers`, `materials`, `project_costs` |
| Assinaturas e consumo | `subscriptions`, `usage_counters` |
| Histórico, IA e automações | `activities`, `ai_usage`, `automation_jobs` |
| Controle de versão | `alembic_version` |

São 18 tabelas da aplicação e 1 tabela de controle. As rotas estão em
`backend/app/api`, as operações compartilhadas em `crud.py`/`api/crud_router.py`
e as regras de negócio em `services`. A separação entre marcenarias também
depende dos filtros e validações da aplicação; não existe RLS criada por este SQL.

## Exportar novamente

Na raiz, usando o Python que tem as dependências de `backend/requirements.txt`:

```powershell
python scripts/export_database_sql.py
```

Não é necessária conexão com banco para exportar. O arquivo só é substituído
depois de gerar a cadeia inteira com sucesso. A exportação não inclui a
promoção opcional de administrador por `BOOTSTRAP_ADMIN_EMAIL`; essa promoção
exige migração online e um usuário ativo existente. Para um banco novo, deixe
essa variável ausente também no deploy inicial e utilize o cadastro empresarial.

## Retomar o Render

1. Confirme qual é o PostgreSQL correto e faça backup se houver dados.
2. Em `ideal-marcenaria-api` → Environment, ajuste somente `DATABASE_URL` para
   a **Internal Database URL** desse banco. Não publique a URL nem a senha.
3. Preserve as demais variáveis; confira Redis, CORS e a URL do frontend.
4. Confira se há `BOOTSTRAP_ADMIN_EMAIL` antes de iniciar um banco vazio.
5. Faça o deploy. O Dockerfile executa `alembic upgrade head` antes da API.
6. Aguarde o estado `Live`, confira os logs e `GET /ready` (HTTP 200 com os
   componentes saudáveis). Um deploy solicitado não equivale a deploy concluído.
7. Teste cadastro → login → painel → 30 dias grátis → cliente → categoria →
   produto → orçamento → sair → entrar e consultar os mesmos registros.

Não apague nem substitua um PostgreSQL existente para corrigir apenas uma URL.
O prazo do plano grátis do banco é independente dos 30 dias grátis oferecidos
aos clientes pelo software. Recriar tabelas não renova o prazo da hospedagem.

## Limites da validação

Os testes automatizados usam PostgreSQL e Redis descartáveis. Eles não devem
apontar para o banco do Render. Consulte `docs/recuperacao-2026-11-08.md` para
os resultados desta entrega e o que ainda depende de acesso à produção.
