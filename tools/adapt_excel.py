import pandas as pd
import io
from tools.parse_excel import _normalize_shift


def is_raw_export(file_bytes):
    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        if 'Grupos' in xls.sheet_names:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Grupos', nrows=1)
            if 'ID_Grupo' in df.columns:
                return False
        df_first = pd.read_excel(io.BytesIO(file_bytes), nrows=1)
        if 'Nombre_Completo' in df_first.columns and 'Grupos' in df_first.columns:
            return True
        return False
    except Exception:
        return False


def adapt_excel_bytes(input_bytes, template_bytes):
    df_in = pd.read_excel(io.BytesIO(input_bytes))

    group_mapping = {}
    teacher_mapping = {}

    for _, row in df_in.iterrows():
        prof = str(row['Nombre_Completo']).strip()
        grupos_str = str(row['Grupos'])
        turno = str(row['Turno']) if pd.notna(row.get('Turno')) else ''

        if pd.isna(prof) or not prof or prof.lower() == 'nan':
            continue
        if pd.isna(grupos_str) or grupos_str.lower() == 'nan':
            continue

        grupos_str = grupos_str.replace('[', '').replace(']', '').replace('"', '').replace("'", '')
        grupos = [g.strip() for g in grupos_str.replace('\n', ',').split(',')]

        if prof not in teacher_mapping:
            teacher_mapping[prof] = set()

        for g in grupos:
            if not g:
                continue
            teacher_mapping[prof].add(g)
            if g not in group_mapping:
                group_mapping[g] = {
                    'ID_Grupo': g,
                    'Nivel_o_Familia': '',
                    'Turno': turno
                }

    profesores_list = []
    for t, gs in teacher_mapping.items():
        profesores_list.append({
            'Nombre_Profesor': t,
            'Grupos_Asignados': ', '.join(sorted(list(gs)))
        })
    df_profesores = pd.DataFrame(profesores_list)

    grupos_list = list(group_mapping.values())
    df_grupos = pd.DataFrame(grupos_list)

    df_instructivo = pd.read_excel(io.BytesIO(template_bytes), sheet_name='Instructivo')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_instructivo.to_excel(writer, sheet_name='Instructivo', index=False)
        df_profesores.to_excel(writer, sheet_name='Profesores', index=False)
        df_grupos.to_excel(writer, sheet_name='Grupos', index=False)
    output.seek(0)
    return output


def try_adapt_bytes(input_bytes, template_bytes):
    if is_raw_export(input_bytes):
        return adapt_excel_bytes(input_bytes, template_bytes), True
    return None, False


def is_raw_export_file(file_path):
    with open(file_path, 'rb') as f:
        return is_raw_export(f.read())


def try_adapt(input_path, template_path, output_path):
    with open(input_path, 'rb') as f:
        input_bytes = f.read()
    with open(template_path, 'rb') as f:
        template_bytes = f.read()

    result, adapted = try_adapt_bytes(input_bytes, template_bytes)
    if adapted and result:
        with open(output_path, 'wb') as f:
            f.write(result.read())
        return True
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        adapted = try_adapt(sys.argv[1], sys.argv[2], sys.argv[3])
        sys.exit(0 if adapted else 2)
    else:
        input_xlsx = "public/Horario Profesores (sin formato).xlsx"
        template_xlsx = "public/Plantilla_Evaluacion.xlsx"
        output_xlsx = "public/Horario_Formatado.xlsx"
        if int(os.environ.get("RUN_ADAPT", 1)):
            import os
            adapt_excel_bytes(open(input_xlsx, 'rb').read(), open(template_xlsx, 'rb').read())
