# Backend — Móveis Planejados

API em FastAPI com SQLAlchemy e PostgreSQL.

## Executar localmente

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API inicial possui `GET /health` para verificar se o serviço está funcionando.

## Indisponibilidade das dependências

- `REDIS_TIMEOUT_SECONDS` (padrão: `1`, positivo e finito) limita o tempo total da
  operação do limitador de requisições e da sondagem Redis de `/ready`. Ao vencer
  o prazo, o limitador mantém a proteção local por processo; `/ready` retorna
  `503`, sem esconder a indisponibilidade. Não há repetição automática de `INCR`.
- `DATABASE_CONNECT_TIMEOUT_SECONDS` (padrão: `5`, mínimo: `2`) limita a abertura
  de cada conexão PostgreSQL por host/endereço. Não é um prazo para consultas ou
  para a requisição inteira; o pool continua com espera máxima de 10 segundos.
- A sondagem PostgreSQL de `/ready` roda em uma thread de trabalho. Assim, uma
  conexão ou consulta lenta não bloqueia a fila assíncrona das outras requisições.

Os valores podem ser configurados no ambiente do backend. Não alteram dados,
migrações ou credenciais. Uma falha de dependência não torna `/health` indisponível.

Referências: [timeouts do asyncio](https://docs.python.org/3.12/library/asyncio-task.html#timeouts),
[conexões PostgreSQL](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS)
e [thread pool do Starlette](https://www.starlette.io/threadpool/).
