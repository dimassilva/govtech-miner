from database import Base
from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship

class Diario(Base):
    __tablename__ = 'diarios'
    
    id = Column(Integer, primary_key=True)
    municipio = Column(String(100))
    data_publicacao = Column(Date)
    nome_arquivo = Column(String(255))
    
    # NOVOS CAMPOS VITAIS:
    codigo_origem = Column(Integer, unique=True) # Ex: 1782 (ID do sistema deles)
    numero_edicao = Column(Integer)              # Ex: 234
    tipo_edicao = Column(String(10))             # Ex: "R" (Regular)
    hash_origem = Column(String(100))            # Ex: "QtbVoc3hoKMACaV" (Para checagem rápida)
    
    # Hash do arquivo binário (nossa segurança extra)
    hash_arquivo_binario = Column(String(64)) 
    
    processado = Column(Boolean, default=False)
    
    oportunidades = relationship("Oportunidade", back_populates="diario")

class Oportunidade(Base):
    __tablename__ = 'oportunidades'
    
    id = Column(Integer, primary_key=True)
    diario_id = Column(Integer, ForeignKey('diarios.id'))
    
    tipo = Column(String(50))
    numero_processo = Column(String(50))
    objeto_resumido = Column(Text)
    valor = Column(Float)
    favorecido = Column(String(200))
    prazo_vigencia = Column(String(100))
    insight_venda = Column(Text)
    
    diario = relationship("Diario", back_populates="oportunidades")
