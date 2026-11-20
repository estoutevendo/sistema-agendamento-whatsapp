# Rotinas automáticas (APScheduler). Trecho resumido: os resumos por
# e-mail (diário e mensal) ficaram de fora.

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Agendamento

TZ = ZoneInfo("America/Sao_Paulo")
BOT_URL = os.getenv("BOT_URL", "http://127.0.0.1:3001")


def _amanha():
    inicio = (datetime.now(TZ) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio.replace(tzinfo=None), (inicio + timedelta(days=1)).replace(tzinfo=None)


def enviar_whatsapp(telefone: str, mensagem: str, agendamento_id: int = None):
    """O bot expõe um endpoint HTTP local; a API só pede pra ele mandar a mensagem."""
    try:
        requests.post(BOT_URL, json={
            "telefone": telefone,
            "mensagem": mensagem,
            "agendamento_id": agendamento_id,
        }, timeout=10)
    except requests.RequestException as e:
        print(f"[bot] falha ao enviar para {telefone}: {e}")


def lembrete_vespera():
    """Pede confirmação de quem tem horário amanhã."""
    db = SessionLocal()
    try:
        inicio, fim = _amanha()
        pendentes = db.query(Agendamento).filter(
            Agendamento.status == "agendado",
            Agendamento.data_hora >= inicio,
            Agendamento.data_hora < fim,
        ).all()

        for ag in pendentes:
            enviar_whatsapp(
                ag.cliente.telefone,
                f"Olá {ag.cliente.nome}! 💅\n"
                f"Você tem horário amanhã:\n"
                f"✂️ {ag.servico.nome}\n"
                f"🕐 {ag.data_hora.strftime('%d/%m às %H:%M')}\n\n"
                f"Responda *sim* para confirmar ou *não* para cancelar.",
                agendamento_id=ag.id,  # o bot coloca a cliente na etapa de confirmação
            )
    finally:
        db.close()


def cancelar_nao_confirmados():
    """18h: quem não confirmou o horário de amanhã perde a vaga."""
    db = SessionLocal()
    try:
        inicio, fim = _amanha()
        sem_resposta = db.query(Agendamento).filter(
            Agendamento.status == "agendado",
            Agendamento.data_hora >= inicio,
            Agendamento.data_hora < fim,
        ).all()

        for ag in sem_resposta:
            ag.status = "cancelado"
            enviar_whatsapp(
                ag.cliente.telefone,
                f"Olá {ag.cliente.nome}, seu horário de "
                f"{ag.data_hora.strftime('%d/%m às %H:%M')} foi liberado porque não "
                f"recebemos a confirmação até as 18h. Se quiser remarcar, é só chamar!",
            )
        db.commit()
    finally:
        db.close()


def concluir_passados():
    db = SessionLocal()
    try:
        agora = datetime.now(TZ).replace(tzinfo=None)
        db.query(Agendamento).filter(
            Agendamento.status.in_(["agendado", "confirmado"]),
            Agendamento.data_hora < agora - timedelta(hours=3),
        ).update({"status": "concluido"}, synchronize_session=False)
        db.commit()
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone=TZ)
scheduler.add_job(lembrete_vespera,         "cron", hour=13, minute=30)
scheduler.add_job(cancelar_nao_confirmados, "cron", hour=18, minute=0)
scheduler.add_job(concluir_passados,        "interval", minutes=30)
