import pandas as pd
import json
import os
import io

SHIFT_MAP = {
    'mañana': 'morning',
    'manana': 'morning',
    'morning': 'morning',
    'm': 'morning',
    'tarde': 'afternoon',
    'afternoon': 'afternoon',
    't': 'afternoon',
    'vespertino': 'afternoon',
    'matutino': 'morning',
}


def _normalize_shift(raw):
    if not raw or pd.isna(raw):
        return 'morning'
    key = str(raw).strip().lower()
    return SHIFT_MAP.get(key, 'morning')


def parse_excel_bytes(file_bytes, config=None):
    df_grupos = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Grupos')
    try:
        df_profesores = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Profesores')
    except Exception:
        df_profesores = pd.DataFrame()

    duration_minutes = 20
    if config:
        duration_minutes = int(config.get('duration_minutes', 20))

    groups_data = []
    teachers_data = {}

    for _, row in df_grupos.iterrows():
        if pd.isna(row.get('ID_Grupo')):
            continue
        group_id = str(row['ID_Grupo']).strip()
        family = str(row.get('Nivel_o_Familia', '')).strip()
        if family.lower() == 'nan':
            family = ''
        shift = _normalize_shift(row.get('Turno'))

        groups_data.append({
            "id": group_id,
            "name": group_id,
            "family": family,
            "shift": shift,
            "duration_minutes": duration_minutes
        })
        teachers_data[group_id] = []

    if not df_profesores.empty and 'Nombre_Profesor' in df_profesores.columns and 'Grupos_Asignados' in df_profesores.columns:
        for _, row in df_profesores.iterrows():
            profesor = str(row.get('Nombre_Profesor')).strip()
            if not profesor or pd.isna(row.get('Nombre_Profesor')):
                continue
            grupos_str = str(row.get('Grupos_Asignados', ''))
            if pd.isna(row.get('Grupos_Asignados')) or not grupos_str:
                continue
            grupos = [g.strip() for g in grupos_str.split(',') if g.strip()]
            for g in grupos:
                if g not in teachers_data:
                    teachers_data[g] = []
                teachers_data[g].append(profesor)

    return groups_data, teachers_data


def parse_excel():
    file_path = ".tmp/uploaded_data.xlsx"
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: Could not find {file_path}")

    config = None
    config_path = ".tmp/config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    groups_data, teachers_data = parse_excel_bytes(file_bytes, config)

    os.makedirs(".tmp", exist_ok=True)
    with open(".tmp/groups_data.json", "w", encoding="utf-8") as f:
        json.dump(groups_data, f, indent=2, ensure_ascii=False)
    with open(".tmp/teachers_data.json", "w", encoding="utf-8") as f:
        json.dump(teachers_data, f, indent=2, ensure_ascii=False)

    print("Successfully parsed uploaded Excel file into JSONs.")


if __name__ == "__main__":
    parse_excel()
