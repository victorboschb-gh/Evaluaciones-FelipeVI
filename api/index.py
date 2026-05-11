import os
import sys
import json
import io
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from tools.parse_excel import parse_excel_bytes
from tools.get_groups import get_groups_from_bytes
from tools.adapt_excel import try_adapt_bytes
from tools.generate_schedule import generate_schedule_from_data
from tools.generate_word import generate_word_bytes
from api.auth import (
    init_tables, hash_password, verify_password, create_token,
    get_user_by_email, get_user_by_id, is_admin, log_usage,
    require_auth, require_admin,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")


@app.on_event("startup")
def startup():
    try:
        init_tables()
    except Exception as e:
        print(f"Warning: Could not init tables: {e}")


def _build_template_bytes():
    buf = io.BytesIO()
    instructivo = pd.DataFrame({
        'Instrucciones para rellenar la plantilla': [
            '1. Rellena la hoja "Grupos" con los datos de cada grupo.',
            '   Columnas obligatorias: ID_Grupo, Nivel_o_Familia, Turno.',
            '   En "Turno" escribe "Mañana" o "Tarde".',
            '2. Rellena la hoja "Profesores" indicando el nombre completo del profesor.',
            '3. En la hoja "Profesores", rellena "Grupos_Asignados" con los grupos separados por comas.',
        ]
    })
    profesores = pd.DataFrame({'Nombre_Profesor': [], 'Grupos_Asignados': []})
    grupos = pd.DataFrame({'ID_Grupo': [], 'Nivel_o_Familia': [], 'Turno': []})

    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        instructivo.to_excel(writer, sheet_name='Instructivo', index=False)
        profesores.to_excel(writer, sheet_name='Profesores', index=False)
        grupos.to_excel(writer, sheet_name='Grupos', index=False)
    buf.seek(0)
    return buf


_template_cache = None


def _load_template_bytes():
    global _template_cache
    if _template_cache is None:
        _template_cache = _build_template_bytes()
    _template_cache.seek(0)
    return _template_cache.read()


# ── Auth endpoints ──────────────────────────────────────────

@app.post("/api/auth/register")
async def register(request: Request):
    try:
        body = await request.json()
        full_name = body.get("full_name", "").strip()
        phone = body.get("phone", "").strip()
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")

        if not all([full_name, phone, email, password]):
            return JSONResponse(status_code=400, content={"error": "Todos los campos son obligatorios"})

        if len(password) < 6:
            return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos 6 caracteres"})

        existing = get_user_by_email(email)
        if existing:
            return JSONResponse(status_code=400, content={"error": "Ya existe una cuenta con este email"})

        pw_hash = hash_password(password)
        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (full_name, phone, email, password_hash) VALUES (%s, %s, %s, %s) RETURNING id",
                    (full_name, phone, email, pw_hash),
                )
                user_id = str(cur.fetchone()[0])
        finally:
            conn.close()

        return {"message": "Cuenta creada. Pendiente de aprobación por el administrador.", "user_id": user_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")

        if not email or not password:
            return JSONResponse(status_code=400, content={"error": "Email y contraseña son obligatorios"})

        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash, status FROM users WHERE email = %s",
                    (email,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

        user_id, user_email, pw_hash, status = row

        if not verify_password(password, pw_hash):
            return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

        if status != "approved" and not is_admin(user_email):
            if status == "pending":
                return JSONResponse(status_code=403, content={"error": "Tu cuenta está pendiente de aprobación"})
            if status == "rejected":
                return JSONResponse(status_code=403, content={"error": "Tu cuenta ha sido rechazada"})

        token = create_token(user_id, user_email)

        try:
            log_usage(str(user_id), "login")
        except Exception:
            pass

        response = JSONResponse(content={
            "message": "Login correcto",
            "user": {"id": str(user_id), "email": user_email, "is_admin": is_admin(user_email)},
        })
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=86400,
            path="/",
        )
        return response
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse(content={"message": "Sesión cerrada"})
    response.delete_cookie(key="session_token", path="/")
    return response


@app.post("/api/auth/forgot-password")
async def forgot_password(request: Request):
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()
        phone = body.get("phone", "").strip()

        if not email or not phone:
            return JSONResponse(status_code=400, content={"error": "Email y teléfono son obligatorios"})

        if is_admin(email):
            return JSONResponse(status_code=403, content={"error": "La cuenta de administrador no puede ser restablecida por este medio"})

        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, full_name FROM users WHERE email = %s AND phone = %s",
                    (email, phone),
                )
                row = cur.fetchone()
                if not row:
                    return JSONResponse(status_code=404, content={"error": "No se encontró una cuenta con ese email y teléfono"})
                user_id = str(row[0])
                cur.execute("DELETE FROM usage_log WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM users WHERE id = %s AND email != %s", (user_id, os.environ.get("ADMIN_EMAIL", "")))
        finally:
            conn.close()

        return {"message": "Cuenta eliminada. Puedes registrarte de nuevo con el mismo email."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/auth/me")
async def me(request: Request):
    try:
        user = require_auth(request)
        return {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "is_admin": is_admin(user["email"]),
            "status": user["status"],
        }
    except HTTPException:
        return JSONResponse(status_code=401, content={"error": "No autenticado"})


# ── Admin endpoints ─────────────────────────────────────────

@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    try:
        admin = require_admin(request)
        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.id, u.full_name, u.phone, u.email, u.status, u.created_at,
                           COALESCE(g.cnt, 0) as generate_count,
                           COALESCE(l.last_login, NULL) as last_login
                    FROM users u
                    LEFT JOIN (
                        SELECT user_id, COUNT(*) as cnt FROM usage_log WHERE action = 'generate' GROUP BY user_id
                    ) g ON g.user_id = u.id
                    LEFT JOIN (
                        SELECT user_id, MAX(created_at) as last_login FROM usage_log WHERE action = 'login' GROUP BY user_id
                    ) l ON l.user_id = u.id
                    ORDER BY u.created_at DESC
                """)
                rows = cur.fetchall()
        finally:
            conn.close()

        users = []
        for row in rows:
            users.append({
                "id": str(row[0]),
                "full_name": row[1],
                "phone": row[2],
                "email": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "generate_count": row[6],
                "last_login": row[7].isoformat() if row[7] else None,
            })
        return {"users": users}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/admin/users/{user_id}/approve")
async def admin_approve_user(user_id: str, request: Request):
    try:
        require_admin(request)
        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET status = 'approved' WHERE id = %s", (user_id,))
                if cur.rowcount == 0:
                    return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        finally:
            conn.close()
        return {"message": "Usuario aprobado"}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@app.post("/api/admin/users/{user_id}/reject")
async def admin_reject_user(user_id: str, request: Request):
    try:
        require_admin(request)
        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET status = 'rejected' WHERE id = %s", (user_id,))
                if cur.rowcount == 0:
                    return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        finally:
            conn.close()
        return {"message": "Usuario rechazado"}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    try:
        require_admin(request)
        from api.auth import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                if cur.rowcount == 0:
                    return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
        finally:
            conn.close()
        return {"message": "Usuario eliminado"}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


# ── Protected app endpoints ─────────────────────────────────

@app.post("/api/parse-groups")
async def parse_groups(file: UploadFile = File(...), request: Request = None):
    try:
        if request:
            try:
                user = require_auth(request)
            except HTTPException:
                return JSONResponse(status_code=401, content={"error": "No autenticado"})

        file_bytes = await file.read()

        template_bytes = _load_template_bytes()
        adapted_bytes, was_adapted = try_adapt_bytes(file_bytes, template_bytes)
        if adapted_bytes:
            file_bytes = adapted_bytes.read()

        groups = get_groups_from_bytes(file_bytes)
        return JSONResponse(content={"groups": groups, "adapted": was_adapted})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@app.post("/api/generate")
async def generate_schedule(
    request: Request,
    file: UploadFile = File(None),
    duration_minutes: int = Form(20),
    evaluation_sessions: str = Form("[]"),
    selected_groups: str = Form("[]"),
    excluded_hours: str = Form("{}"),
):
    try:
        user = require_auth(request)
    except HTTPException:
        return JSONResponse(status_code=401, content={"error": "No autenticado"})

    try:
        config = {
            "duration_minutes": duration_minutes,
            "evaluation_sessions": json.loads(evaluation_sessions),
            "selected_groups": json.loads(selected_groups),
            "excluded_hours": json.loads(excluded_hours),
        }

        file_bytes = await file.read() if file and file.filename else None
        if not file_bytes:
            raise HTTPException(status_code=400, detail="No se proporcionó archivo.")

        template_bytes = _load_template_bytes()
        adapted_bytes, _ = try_adapt_bytes(file_bytes, template_bytes)
        if adapted_bytes:
            file_bytes = adapted_bytes.read()

        groups_data, teachers_data = parse_excel_bytes(file_bytes, config)

        schedule, stats = generate_schedule_from_data(groups_data, teachers_data, config)

        if not schedule:
            raise HTTPException(status_code=500, detail="No se pudo generar ningún horario. Revisa los datos de entrada.")

        doc_bytes = generate_word_bytes(schedule)

        try:
            log_usage(user["id"], "generate")
        except Exception:
            pass

        target_count = len(json.loads(selected_groups)) if json.loads(selected_groups) else len(groups_data)
        warning_header = len(schedule) < target_count
        missing_minutes = stats.get("unassigned_duration_minutes", 0)

        headers = {}
        if warning_header:
            headers["X-Schedule-Warning"] = "1"
            headers["X-Schedule-Missing-Minutes"] = str(missing_minutes)
            headers["Access-Control-Expose-Headers"] = "X-Schedule-Warning, X-Schedule-Missing-Minutes"

        return StreamingResponse(
            doc_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@app.post("/api/heartbeat")
async def heartbeat():
    return {"ok": True}


if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
