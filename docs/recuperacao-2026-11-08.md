# Diagnóstico e validação — Multi-Marcenarias

Em 08/11/2026, o serviço Render `ideal-marcenaria-api` estava com o último
deploy falho e os logs registravam `failed to resolve host` para um PostgreSQL
antigo. O banco disponível `Ideal` no espaço `My Workspace` é PostgreSQL 18,
nome `ideal_nisd`, hospedado em Oregon. Sua expiração de plano grátis aparece
como **15/11/2026** no painel Render e no aviso por e-mail. O Redis existente
também foi listado como disponível.

O banco Render não foi apagado, substituído nem aberto à internet. Sua lista de
IPs externos permitidos está vazia, e a consulta SQL pelo conector não pôde
confirmar quais tabelas e registros ele contém. Por isso, a estrutura dele
precisa ser conferida antes de qualquer importação manual.

O projeto tem 16 migrações, da revisão `001_initial` até `016_ai_automation`.
As migrações 011 e 015 passaram a gerar SQL PostgreSQL sem conexão com banco,
preservando o mesmo esquema final. A 010 rejeita explicitamente exportação
offline quando uma promoção administrativa dependente de dados é solicitada.
O exportador gera `database/multi_marcenarias_postgresql.sql` com 18 tabelas da
aplicação, mais `alembic_version`, e protege contra execução em esquema não
vazio.

## Validação em ambiente descartável

| Verificação | Resultado |
| --- | --- |
| Importação do SQL em PostgreSQL 17 | Concluída, com revisão `016_ai_automation` |
| Comparação Alembic x modelos | Sem operações pendentes |
| Atualização de banco antigo com registros | Preservou usuários, clientes, categorias, produtos e orçamentos, online e por SQL |
| Reaplicação do SQL no mesmo esquema | Recusada pela proteção |
| Plano pago e testes grátis já datados | Preservados pela migração de 30 dias |
| Fluxo novo cadastro → sessão → trial → cliente → categoria → produto → orçamento → logout → login | Aprovado em teste HTTP isolado |
| Testes Python | 244 passaram; cobertura 91,22% |
| Testes frontend Node | 50 passaram |
| Ruff / Alembic check | Aprovados |

Os testes não substituem o teste visual de todos os botões na produção. Também
não comprovam que `ideal_nisd` tenha dados históricos nem que a API esteja
saudável no Render. O último deploy bem-sucedido da API era anterior ao último
deploy falho quando o diagnóstico foi feito.

## Próximo passo de produção

O SQL e as migrações estão prontos para revisão. A conexão atual deve ser
ajustada no serviço `ideal-marcenaria-api` para a *Internal Database URL* do
banco `Ideal`, mantendo as outras variáveis. Antes do deploy, confira a variável
`BOOTSTRAP_ADMIN_EMAIL`: se o banco novo estiver vazio e o endereço configurado
não corresponder a usuário ativo, a migração 010 falhará. Uma nova marcenaria
criada pelo cadastro já recebe um administrador próprio.

Somente após um deploy `Live`, `GET /ready` com HTTP 200 e o fluxo completo
feito no site real se pode afirmar que o projeto está pronto para o cliente.
O PostgreSQL Free tem prazo próprio; recriar o esquema não impede a expiração.
