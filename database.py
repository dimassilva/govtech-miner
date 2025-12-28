from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
import os

# --- CONFIGURAÇÃO DE CONEXÃO ---
DB_USER = os.getenv("DB_USER", "licitacao")
DB_PASS = os.getenv("DB_PASS", "26432412")
DB_HOST = os.getenv("DB_HOST", "104.168.4.3")
DB_NAME = "gov_miner"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# Configuração do Engine
engine = create_engine(DATABASE_URL, echo=False, pool_recycle=3600)
session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)

Base = declarative_base()

# --- DEFINIÇÃO DAS TABELAS (MODELOS) ---
# Agora ficam aqui dentro para evitar erros de importação

class Diario(Base):
    __tablename__ = 'diarios'
    
    id = Column(Integer, primary_key=True)
    municipio = Column(String(100))
    data_publicacao = Column(Date)
    
    # Metadados do Arquivo
    nome_arquivo = Column(String(255))
    codigo_origem = Column(Integer, unique=True)
    numero_edicao = Column(Integer)
    hash_origem = Column(String(100))
    tipo_documento_geral = Column(String(100)) 
    
    processado = Column(Boolean, default=False)
    
    oportunidades = relationship("Oportunidade", back_populates="diario")

class Oportunidade(Base):
    __tablename__ = 'oportunidades'
    
    id = Column(Integer, primary_key=True)
    diario_id = Column(Integer, ForeignKey('diarios.id'))
    
    # NOVAS COLUNAS PARA O JSON RICO
    id_processo = Column(String(100))       # Ex: "Dispensa 014/2025"
    categoria = Column(String(100))         # Ex: "Limpeza"
    objeto = Column(Text)                   # Descrição
    valor = Column(Float)                   # Valor monetário
    vencedor = Column(String(200))          # Nome da empresa
    cnpj_vencedor = Column(String(30))      # CNPJ da empresa
    prazo = Column(String(100))             # Vigência
    status = Column(String(50))             # Status
    localizacao = Column(String(255))       # Local
    insight_venda = Column(Text)            # Dica da IA
    
    diario = relationship("Diario", back_populates="oportunidades")

def init_db():
    try:
        # Cria as tabelas com as NOVAS COLUNAS
        Base.metadata.create_all(bind=engine)
        print(f"--- Conectado ao MySQL ({DB_HOST}) e Tabelas Atualizadas ---")
    except Exception as e:
        print(f"ERRO CRÍTICO DE BANCO DE DADOS: {e}")
