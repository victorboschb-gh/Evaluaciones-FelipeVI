import os
import sys
import json
import io
import logging
import traceback

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    filename='SistemaJuntas.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from tools.parse_excel import parse_excel_bytes
from tools.get_groups import get_groups_from_bytes
from tools.adapt_excel import try_adapt_bytes, is_raw_export
from tools.generate_schedule import generate_schedule_from_data
from tools.generate_word import generate_word_bytes

app = FastAPI()


def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


base_path = get_base_path()
public_path = os.path.join(base_path, "public")
os.makedirs(public_path, exist_ok=True)
TEMPLATE_PATH = os.path.join(public_path, "Plantilla_Evaluacion.xlsx")


def _load_template_bytes():
    with open(TEMPLATE_PATH, 'rb') as f:
        return f.read()


@app.post("/api/parse-groups")
async def parse_groups(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()

        template_bytes = _load_template_bytes()
        adapted_bytes, was_adapted = try_adapt_bytes(file_bytes, template_bytes)
        if adapted_bytes:
            file_bytes = adapted_bytes.read()

        groups = get_groups_from_bytes(file_bytes)
        return JSONResponse(content={"groups": groups, "adapted": was_adapted})
    except Exception as e:
        logging.error(f"Error in /api/parse-groups: {e}\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/generate")
async def generate_schedule(
    file: UploadFile = File(None),
    duration_minutes: int = Form(20),
    evaluation_sessions: str = Form("[]"),
    selected_groups: str = Form("[]"),
    excluded_hours: str = Form("{}"),
):
    try:
        config = {
            "duration_minutes": duration_minutes,
            "evaluation_sessions": json.loads(evaluation_sessions),
            "selected_groups": json.loads(selected_groups),
            "excluded_hours": json.loads(excluded_hours),
        }

        file_bytes = await file.read() if file and file.filename else None

        if file_bytes:
            template_bytes = _load_template_bytes()
            adapted_bytes, _ = try_adapt_bytes(file_bytes, template_bytes)
            if adapted_bytes:
                file_bytes = adapted_bytes.read()
        else:
            xlsx_path = ".tmp/uploaded_data.xlsx"
            if os.path.exists(xlsx_path):
                with open(xlsx_path, "rb") as f:
                    file_bytes = f.read()
            else:
                raise ValueError("No se proporcionó archivo ni hay datos previos.")

        groups_data, teachers_data = parse_excel_bytes(file_bytes, config)

        schedule, stats = generate_schedule_from_data(groups_data, teachers_data, config)

        if not schedule:
            msg = "No se pudo generar ningún horario. Revisa los datos de entrada."
            logging.error(msg)
            return JSONResponse(status_code=500, content={"error": msg})

        doc_bytes = generate_word_bytes(schedule)

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

    except Exception as e:
        logging.error(f"Error in /api/generate: {e}\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/heartbeat")
async def heartbeat():
    return {"ok": True}


app.mount("/", StaticFiles(directory=public_path, html=True), name="public")
