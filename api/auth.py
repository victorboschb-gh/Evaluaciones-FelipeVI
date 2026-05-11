import os
import psycopg2
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


def init_tables():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
    finally:
        conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_by_email(email: str) -> dict:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, full_name, phone, email, status, created_at FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "full_name": row[1],
                "phone": row[2],
                "email": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict:
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, full_name, phone, email, status, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "full_name": row[1],
                "phone": row[2],
                "email": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }
    finally:
        conn.close()


def is_admin(email: str) -> bool:
    return email.lower() == ADMIN_EMAIL.lower()


def log_usage(user_id: str, action: str):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usage_log (user_id, action) VALUES (%s, %s)",
                (user_id, action),
            )
    finally:
        conn.close()


def get_token_from_request(request: Request) -> str:
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def require_auth(request: Request) -> dict:
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sesión expirada o inválida")
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if user["status"] != "approved" and not is_admin(user["email"]):
        raise HTTPException(status_code=403, detail="Cuenta pendiente de aprobación")
    return user


def require_admin(request: Request) -> dict:
    user = require_auth(request)
    if not is_admin(user["email"]):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user
