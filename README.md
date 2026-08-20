# Moveis-planejados-
Ideal Marcenaria 
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# URL do banco de dados
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://usuario:senha@localhost:5432/marcenaria_db"
)

# Compatibilidade com URLs antigas do Render/Heroku
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

# Configuração do engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Fábrica de sessões
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Classe base dos Models
Base = declarative_base()


# Dependência do FastAPI
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
