from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

# SEUS DADOS DE CONEXÃO
DB_USER = "licitacao"
DB_PASS = "26432412"
DB_HOST = "104.168.4.3"
DB_NAME = "gov_miner"

# String de Conexão MySQL (Driver PyMySQL)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# Configuração do Engine
# pool_recycle é importante para MySQL para evitar queda de conexão por inatividade
engine = create_engine(DATABASE_URL, echo=False, pool_recycle=3600)

session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)

Base = declarative_base()

def init_db():
    # Cria as tabelas no seu MySQL se elas não existirem
    import models
    try:
        Base.metadata.create_all(bind=engine)
        print(f"--- Conectado com sucesso ao MySQL em {DB_HOST} ---")
    except Exception as e:
        print(f"Erro ao conectar no Banco de Dados: {e}")
