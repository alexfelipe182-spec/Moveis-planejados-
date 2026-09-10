# Auditoria IA e automação — 09/09/2026

Branch: `feat/ia-automacao-completa`. Inventário inicial: 166 arquivos versionados,
sem alterações locais. Nenhuma operação de publicação foi autorizada.

## Levantamento antes da implementação

- FastAPI síncrono, SQLAlchemy 2, PostgreSQL, 15 migrations com uma HEAD;
  Redis usado para rate limiting com fallback limitado em memória.
- Autenticação JWT/cookies, rotação de refresh e CSRF existentes. Permissões
  administrativas e acesso comercial são aplicados nas dependências HTTP.
- Frontend HTML/CSS/JS sem framework, testes Node e contratos Pytest.
- Orçamento: interpretação, catálogo, cálculo Decimal, análise, revisão,
  decisão interna, envio registrado, decisão comercial, projeto e custos.
- Custos reais e rentabilidade são agregados do PostgreSQL a cada leitura;
  não existe cache financeiro a invalidar.
- Cadastro cria tenant, administrador, onboarding inicial e trial de 30 dias.
  Stripe já possui checkout, portal e verificação HMAC de webhooks.
- CI exige Ruff, imports, migrations sem drift, PostgreSQL, Redis, cobertura
  de 80%, pip-audit, frontend, Gitleaks, CodeQL e Docker.

## Problemas identificados

1. Dois clientes OpenAI independentes, timeouts/retries fixos e análise financeira
   aceitando texto externo sem validar sua estrutura. Catálogo não confiável
   interpolado nas instruções internas. Ausência de `OPENAI_ENABLED`.
2. `quote.created` dispara uma segunda análise fora da transação, não contabilizada;
   o motor guarda resultados em memória, sem retry, persistência ou isolamento.
3. Contadores fazem read-modify-write sem bloqueio. Criação de orçamento e estimate
   dependem da cota IA mesmo quando só executam cálculo local.
4. Filtro de tenant cobre SELECT, mas não bulk UPDATE/DELETE; objetos já carregados
   e alterações de tenant não têm proteção equivalente. Subscription e usage não
   participam do mixin de isolamento.
5. Decisões e mudanças de etapa não bloqueiam a linha. A unicidade de quote_id no
   projeto existe, porém a corrida pode terminar em erro de integridade.
6. Webhook não possui recibo idempotente nem ordenação de eventos. Expiração do
   trial só é derivada em leitura; não há scheduler persistente.
7. UI protege botões individualmente, mas permite requisições concorrentes entre
   interpretar/calcular/salvar e aplicar respostas obsoletas após edição. Existe
   um formulário legado paralelo. Dados faltantes e riscos não têm contrato rico.
8. Logger de exceções HTTP pode incluir detalhes de exceções do banco/provider.

## Estratégia

Evoluir os serviços existentes, sem mudar stack, autenticação ou mecanismo
financeiro. Uma migration nova adiciona outbox, metadados de IA e controles de
idempotência. Transações curtas para automações internas, `FOR UPDATE SKIP LOCKED`
no worker e testes de concorrência reais em PostgreSQL. Dados de clientes e
catálogo nunca recebem privilégios de instruções, ferramentas ou acesso ao banco.

Os resultados de execução e limites da validação são registrados no relatório
final desta rodada e em `ia-automacao.md`.
