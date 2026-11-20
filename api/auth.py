import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Header, HTTPException, Request
from jose import jwt

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

# Usada quando o bot roda numa máquina diferente da API
BOT_API_KEY = os.getenv("BOT_API_KEY")


def criar_token(dados: dict) -> str:
    payload = {**dados, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def _token_do_header(authorization: Optional[str]):
    if authorization and authorization.lower().startswith("bearer "):
        return verificar_token(authorization[7:].strip())
    return None


def _eh_bot(request: Request, x_bot_key: Optional[str]) -> bool:
    # Bot e API rodando juntos: a chamada vem de 127.0.0.1 sem passar por proxy.
    # Qualquer coisa que veio da internet chega com X-Forwarded-For.
    host = request.client.host if request.client else ""
    via_proxy = "x-forwarded-for" in request.headers or "forwarded" in request.headers
    if host in ("127.0.0.1", "::1") and not via_proxy:
        return True
    return bool(BOT_API_KEY and x_bot_key and hmac.compare_digest(x_bot_key, BOT_API_KEY))


def exigir_admin(authorization: Optional[str] = Header(default=None)):
    if not _token_do_header(authorization):
        raise HTTPException(401, "Faça login no painel.")
    return True


def exigir_admin_ou_bot(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_bot_key: Optional[str] = Header(default=None),
):
    if _token_do_header(authorization) or _eh_bot(request, x_bot_key):
        return True
    raise HTTPException(401, "Acesso não autorizado.")
