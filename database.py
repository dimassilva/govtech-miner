from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

# SEUS DADOS (CUIDADO: Em produção, use variáveis de ambiente)
DB_USER = "licitacao"
DB_PASS = "26432412"
DB_HOST = "104.168.4.3"
DB_NAME = "gov_miner"

# String de conexão MySQL + PyMySQL
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# Configuração do Engine com pool_recycle para manter a conexão viva
engine = create_engine(DATABASE_URL, echo=False, pool_recycle=3600)

session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)

Base = declarative_base()

def init_db():
    import models  # Importa os modelos para registrá-los
    try:
        Base.metadata.create_all(bind=engine)
        print(f"--- Conectado ao MySQL ({DB_HOST}) e tabelas verificadas ---")
    except Exception as e:
        print(f"ERRO CRÍTICO DE BANCO DE DADOS: {e}")
