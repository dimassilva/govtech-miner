from sqlalchemy import Column, Integer, String, Float, Text, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base  # Importa o Base configurado acima

class Diario(Base):
    __tablename__ = 'diarios'
    
    id = Column(Integer, primary_key=True)
    municipio = Column(String(100))
    data_publicacao = Column(Date)
    nome_arquivo = Column(String(255))
    
    # METADADOS DE CONTROLE (Vindos da API da Prefeitura)
    codigo_origem = Column(Integer, unique=True, index=True) # Ex: 1782
    numero_edicao = Column(Integer)                          # Ex: 234
    tipo_edicao = Column(String(10))                         # Ex: "R"
    hash_origem = Column(String(100))                        # Hash que vem no JSON da lista
    
    # Hash do arquivo binário (segurança nossa)
    hash_arquivo_binario = Column(String(64)) 
    
    processado = Column(Boolean, default=False)
    
    # Relacionamento
    oportunidades = relationship("Oportunidade", back_populates="diario")

class Oportunidade(Base):
    __tablename__ = 'oportunidades'
    
    id = Column(Integer, primary_key=True)
    diario_id = Column(Integer, ForeignKey('diarios.id'))
    
    # DADOS COMERCIAIS
    tipo = Column(String(50))            # Dispensa, Licitação...
    numero_processo = Column(String(50))
    objeto_resumido = Column(Text)
    valor = Column(Float)
    favorecido = Column(String(200))
    prazo_vigencia = Column(String(100))
    insight_venda = Column(Text)         # O "pulo do gato" da IA
    
    diario = relationship("Diario", back_populates="oportunidades")
