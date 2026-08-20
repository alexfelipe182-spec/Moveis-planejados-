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
