import pandas as pd
import io
from tools.parse_excel import _normalize_shift


def get_groups_from_bytes(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Grupos')
    groups = []
    for _, row in df.iterrows():
        if pd.isna(row.get('ID_Grupo')):
            continue
        group_id = str(row['ID_Grupo']).strip()
        family = str(row.get('Nivel_o_Familia', '')).strip()
        if family.lower() == 'nan':
            family = ''
        shift = _normalize_shift(row.get('Turno'))
        groups.append({
            "id": group_id,
            "family": family,
            "shift": shift
        })
    return groups


def get_groups(file_path):
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    return get_groups_from_bytes(file_bytes)


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        result = get_groups(sys.argv[1])
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({"error": "No file path provided"}))
        sys.exit(1)
