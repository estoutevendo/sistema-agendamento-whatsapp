from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, TIMESTAMP, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Servico(Base):
    __tablename__ = "servicos"

    id          = Column(Integer, primary_key=True)
    categoria   = Column(String(50),   nullable=False)
    nome        = Column(String(100),  nullable=False)
    preco       = Column(Numeric(8, 2), nullable=False)
    duracao_min = Column(Integer,      nullable=False)


class Cliente(Base):
    __tablename__ = "clientes"

    id        = Column(Integer, primary_key=True)
    nome      = Column(String(100), nullable=False)
    telefone  = Column(String(20),  nullable=False, unique=True)
    criado_em = Column(TIMESTAMP,   server_default=func.now())


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id         = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    data_hora  = Column(TIMESTAMP, nullable=False)
    # agendado -> confirmado -> concluido  |  cancelado
    status     = Column(String(20), nullable=False, default="agendado")
    criado_em  = Column(TIMESTAMP, server_default=func.now())

    cliente = relationship("Cliente")
    servico = relationship("Servico")


class Sessao(Base):
    """Estado da conversa de cada cliente no bot (em que etapa ela está).
    Fica no banco para o bot poder reiniciar sem perder conversas no meio."""
    __tablename__ = "sessoes"

    telefone   = Column(String(20), primary_key=True)
    dados      = Column(String, nullable=False)  # JSON
    atualizado = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Feriado(Base):
    """ano = None -> repete todo ano | ano = 2027 -> feriado móvel, só naquele ano"""
    __tablename__ = "feriados"

    id   = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False)
    dia  = Column(Integer, nullable=False)
    mes  = Column(Integer, nullable=False)
    ano  = Column(Integer, nullable=True)


class DiaFechado(Base):
    """Folga, viagem, curso...
    horarios = None          -> dia inteiro fechado
    horarios = "07:00,08:30" -> só esses horários
    motivo é anotação interna, nunca aparece pra cliente."""
    __tablename__ = "dias_fechados"

    id        = Column(Integer, primary_key=True)
    data      = Column(Date, nullable=False, index=True)
    horarios  = Column(String(120), nullable=True)
    motivo    = Column(String(120), nullable=True)
    criado_em = Column(TIMESTAMP, server_default=func.now())


class NumeroBloqueado(Base):
    """Números que o bot ignora (fornecedores, contatos pessoais etc.)."""
    __tablename__ = "numeros_bloqueados"

    id        = Column(Integer, primary_key=True)
    telefone  = Column(String(20), nullable=False, unique=True)
    nome      = Column(String(80), nullable=True)
    criado_em = Column(TIMESTAMP, server_default=func.now())
