# Hospedagem do frontend

O frontend oficial continua no serviço existente `multi-marcenarias`. Ele não é declarado no
`render.yaml`, evitando que uma sincronização do Blueprint crie um serviço duplicado.

## Configuração proposta no serviço existente

- Runtime: Python
- Build command: `pip install -r requirements-frontend.txt`
- Start command: `uvicorn frontend_server:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Auto-deploy: manter a política já usada pelo serviço

O processo escuta em `0.0.0.0` e usa a variável `PORT` fornecida pelo Render. A aplicação ASGI
entrega arquivos existentes normalmente, devolve `404` para arquivos ausentes e direciona rotas
internas da SPA, como `/dashboard/`, para `frontend/index.html`.

`scripts/serve_frontend.py` oferece o mesmo contrato HTTP apenas para desenvolvimento e testes. Ele
não deve ser usado como servidor de produção.

Antes desta mudança, a consulta pública confirmou:

- `https://multi-marcenarias.onrender.com/` → `200`.
- `https://multi-marcenarias.onrender.com/dashboard/` → `404`.

Nenhum deploy ou alteração remota do Render é executado por esta mudança.
