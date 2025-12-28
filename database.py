from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
import os

# --- CONEXÃO ---
DB_USER = os.getenv("DB_USER", "licitacao")
DB_PASS = os.getenv("DB_PASS", "26432412")
DB_HOST = os.getenv("DB_HOST", "104.168.4.3")
DB_NAME = "gov_miner"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False, pool_recycle=3600)
session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)

Base = declarative_base()

# --- TABELA 1: O DOCUMENTO ---
class Diario(Base):
    __tablename__ = 'diarios'
    
    id = Column(Integer, primary_key=True)
    municipio = Column(String(100))
    data_publicacao = Column(Date)
    
    nome_arquivo = Column(String(255))
    codigo_origem = Column(Integer, unique=True) # ID usado para gerar o Link
    numero_edicao = Column(Integer)
    hash_origem = Column(String(100))
    processado = Column(Boolean, default=False)
    
    oportunidades = relationship("Oportunidade", back_populates="diario")

# --- TABELA 2: A OPORTUNIDADE (GOLD) ---
class Oportunidade(Base):
    __tablename__ = 'oportunidades'
    
    id = Column(Integer, primary_key=True)
    diario_id = Column(Integer, ForeignKey('diarios.id'))
    
    # Identificação
    id_processo = Column(String(100))       # "Pregão 90/2025"
    categoria = Column(String(100))         # "Limpeza", "TI"
    objeto = Column(Text)                   # O que é?
    
    # Financeiro
    valor = Column(Float)                   # Quanto vale?
    
    # Resultado (Passado)
    vencedor = Column(String(200))          # Quem ganhou?
    cnpj_vencedor = Column(String(30))      # CNPJ
    
    # Futuro (Avisos)
    data_sessao = Column(String(100))       # QUANDO VAI SER? (Vital para vendas)
    status = Column(String(50))             # "Aberto" ou "Contratado"
    
    # Detalhes
    prazo = Column(String(100))
    localizacao = Column(String(255))
    insight_venda = Column(Text)
    
    diario = relationship("Diario", back_populates="oportunidades")

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("--- BANCO DE DADOS ATUALIZADO (VERSÃO GOLD) ---")
    except Exception as e:
        print(f"ERRO CRÍTICO DB: {e}")
