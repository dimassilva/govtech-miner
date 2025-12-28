from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
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

# ==========================================
# MÓDULO 1: DADOS PÚBLICOS (Oportunidades)
# ==========================================

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
    data_sessao = Column(String(100))       # QUANDO VAI SER?
    status = Column(String(50))             # "Aberto" ou "Contratado"
    
    # Detalhes
    prazo = Column(String(100))
    localizacao = Column(String(255))
    insight_venda = Column(Text)
    
    diario = relationship("Diario", back_populates="oportunidades")
    
    # --- NOVO: RELACIONAMENTO COM SAAS ---
    # Permite saber quais usuários favoritaram esta oportunidade
    favoritado_por = relationship("Favorito", back_populates="oportunidade")

# ==========================================
# MÓDULO 2: DADOS DE USUÁRIOS (SaaS)
# ==========================================

class Usuario(Base):
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False) # Login único
    senha_hash = Column(String(255), nullable=False)         # Senha criptografada
    empresa_cnpj = Column(String(20))                        # Para B2B (Opcional)
    tema = Column(String(10), default='light')               # 'light' ou 'dark'
    criado_em = Column(DateTime, default=datetime.now)
    
    # Relacionamentos (Se apagar o usuário, apaga os alertas e favoritos dele)
    alertas = relationship("Alerta", back_populates="usuario", cascade="all, delete-orphan")
    favoritos = relationship("Favorito", back_populates="usuario", cascade="all, delete-orphan")

class Alerta(Base):
    __tablename__ = 'alertas'
    
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    termo = Column(String(100), nullable=False) # Ex: "Limpeza", "Notebook"
    criado_em = Column(DateTime, default=datetime.now)
    
    usuario = relationship("Usuario", back_populates="alertas")

class Favorito(Base):
    __tablename__ = 'favoritos'
    
    # Chave Primária Composta (Um usuário só pode favoritar a mesma oportunidade 1 vez)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), primary_key=True)
    oportunidade_id = Column(Integer, ForeignKey('oportunidades.id'), primary_key=True)
    
    notas_comerciais = Column(Text) # CRM: "Ligar dia 10", "Já enviei proposta"
    data_salvo = Column(DateTime, default=datetime.now)
    
    usuario = relationship("Usuario", back_populates="favoritos")
    oportunidade = relationship("Oportunidade", back_populates="favoritado_por")

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("--- BANCO DE DADOS ATUALIZADO (SAAS COMPLETO) ---")
    except Exception as e:
        print(f"ERRO CRÍTICO DB: {e}")
