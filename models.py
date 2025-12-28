from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Diario(Base):
    __tablename__ = 'diarios'
    id = Column(Integer, primary_key=True)
    municipio = Column(String(100), nullable=False) # Ex: Lençóis Paulista
    data_publicacao = Column(Date)
    nome_arquivo = Column(String(255))
    processado = Column(Boolean, default=False)
    
    # Relacionamento
    oportunidades = relationship("Oportunidade", back_populates="diario")

class Oportunidade(Base):
    __tablename__ = 'oportunidades'
    id = Column(Integer, primary_key=True)
    diario_id = Column(Integer, ForeignKey('diarios.id'))
    
    # DADOS VITAIS PARA O NEGÓCIO
    tipo = Column(String(50))           # Dispensa, Inexigibilidade, Aditivo
    numero_processo = Column(String(50)) # Ex: "Dispensa 014/2025"
    objeto_resumido = Column(Text)      # O que é?
    valor = Column(Float)               # R$ 553.677,78
    favorecido = Column(String(200))    # Quem ganhou (CNPJ ou Nome)
    prazo_vigencia = Column(String(100)) # "3 meses", "12 meses"
    
    # Inteligência (O valor agregado do seu SaaS)
    insight_venda = Column(Text)        # Ex: "Contrato curto, vence em Março/26"
    
    diario = relationship("Diario", back_populates="oportunidades")
