# Trecho da API (FastAPI) com as regras de agenda.
# Arquivo resumido para o portfólio: rotas de admin, e-mails e outras partes
# do main.py original ficaram de fora.

from datetime import datetime, date, timedelta
from typing import List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import schemas
from auth import exigir_admin_ou_bot
from database import get_db
from models import Agendamento, Cliente, Servico, Feriado, DiaFechado

router = APIRouter()
TZ = ZoneInfo("America/Sao_Paulo")

HORARIOS_SEMANA = ["07:00", "08:30", "10:00", "13:00", "14:30", "16:00"]
HORARIOS_SABADO = ["07:00", "08:30", "10:00"]

ANTECEDENCIA_MIN_H = 4

# Rotas com dados de clientes: só o painel logado ou o bot (LGPD)
PROTEGIDO = [Depends(exigir_admin_ou_bot)]


def horarios_base(d: date) -> List[str]:
    if d.weekday() == 6:  # domingo
        return []
    return HORARIOS_SABADO if d.weekday() == 5 else HORARIOS_SEMANA


def feriado_do_dia(db: Session, d: date):
    return db.query(Feriado).filter(
        Feriado.dia == d.day,
        Feriado.mes == d.month,
        (Feriado.ano == None) | (Feriado.ano == d.year),  # noqa: E711
    ).first()


def situacao_do_dia(db: Session, d: date) -> dict:
    """Junta domingo, feriado e fechamentos manuais numa resposta só.
    Bot, vitrine e painel usam essa mesma função, então a regra fica num lugar."""
    base = horarios_base(d)
    if not base:
        return {"fechado": True, "tipo": "domingo", "motivo": "Domingo", "horarios": []}

    fer = feriado_do_dia(db, d)
    if fer:
        return {"fechado": True, "tipo": "feriado", "motivo": fer.nome, "horarios": []}

    fechados = set()
    for f in db.query(DiaFechado).filter(DiaFechado.data == d).all():
        if not f.horarios:
            return {"fechado": True, "tipo": "fechado", "motivo": f.motivo, "horarios": []}
        fechados.update(h.strip() for h in f.horarios.split(",") if h.strip())

    abertos = [h for h in base if h not in fechados]
    return {
        "fechado": not abertos,
        "tipo": "fechado" if not abertos else None,
        "motivo": None,
        "horarios": abertos,
    }


@router.get("/agenda-publica")
def agenda_publica(dias: int = 90, db: Session = Depends(get_db)):
    """Próximos dias sem atendimento, usados na vitrine.
    O motivo de um fechamento manual nunca sai daqui."""
    dias = max(1, min(dias, 180))
    hoje = datetime.now(TZ).date()
    fechados = []
    for i in range(dias):
        d = hoje + timedelta(days=i)
        if d.weekday() == 6:
            continue
        sit = situacao_do_dia(db, d)
        if sit["fechado"]:
            fechados.append({
                "data": d.isoformat(),
                "tipo": sit["tipo"],
                "nome": sit["motivo"] if sit["tipo"] == "feriado" else None,
            })
    return {"horarios": {"semana": HORARIOS_SEMANA, "sabado": HORARIOS_SABADO}, "fechados": fechados}


@router.get("/horarios-disponiveis")
def horarios_disponiveis(data: str, db: Session = Depends(get_db)):
    dia = datetime.strptime(data, "%d/%m/%Y").date()
    sit = situacao_do_dia(db, dia)
    if sit["fechado"]:
        raise HTTPException(400, "Não há atendimento nesta data.")

    inicio = datetime.combine(dia, datetime.min.time())
    ocupados = {
        a.data_hora.strftime("%H:%M")
        for a in db.query(Agendamento).filter(
            Agendamento.status.in_(["agendado", "confirmado"]),
            Agendamento.data_hora >= inicio,
            Agendamento.data_hora < inicio + timedelta(days=1),
        )
    }
    return {"data": data, "horarios": [h for h in sit["horarios"] if h not in ocupados]}


@router.post("/agendamentos", response_model=schemas.AgendamentoOut, dependencies=PROTEGIDO)
def criar_agendamento(dados: schemas.AgendamentoCreate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.telefone == dados.telefone).first()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado.")

    # Uma cliente só pode ter um horário futuro por vez
    pendente = db.query(Agendamento).filter(
        Agendamento.cliente_id == cliente.id,
        Agendamento.status.in_(["agendado", "confirmado"]),
        Agendamento.data_hora >= datetime.now(TZ).replace(tzinfo=None),
    ).first()
    if pendente:
        quando = pendente.data_hora.strftime("%d/%m/%Y às %H:%M")
        raise HTTPException(400, f"Você já tem um horário marcado para {quando}.")

    servico = db.get(Servico, dados.servico_id)
    if not servico:
        raise HTTPException(404, "Serviço não encontrado.")

    data_hora = dados.data_hora.replace(tzinfo=TZ)
    sit = situacao_do_dia(db, data_hora.date())
    if sit["fechado"] or data_hora.strftime("%H:%M") not in sit["horarios"]:
        raise HTTPException(400, "Horário indisponível nesta data.")

    falta = data_hora - datetime.now(TZ)
    if falta.total_seconds() < ANTECEDENCIA_MIN_H * 3600:
        raise HTTPException(400, f"Agende com no mínimo {ANTECEDENCIA_MIN_H}h de antecedência.")

    conflito = db.query(Agendamento).filter(
        Agendamento.status.in_(["agendado", "confirmado"]),
        Agendamento.data_hora == data_hora.replace(tzinfo=None),
    ).first()
    if conflito:
        raise HTTPException(400, "Esse horário acabou de ser preenchido. Escolha outro.")

    # Marcou pra daqui a menos de 24h: não faz sentido pedir confirmação na véspera
    status = "confirmado" if falta.total_seconds() <= 24 * 3600 else "agendado"

    novo = Agendamento(
        cliente_id=cliente.id,
        servico_id=servico.id,
        data_hora=data_hora.replace(tzinfo=None),
        status=status,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo
