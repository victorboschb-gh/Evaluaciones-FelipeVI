import pandas as pd
import io
import os
import sys
import copy
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from tools.parse_excel import parse_excel_bytes
from tools.generate_schedule import generate_schedule_from_data
from tools.test_schedule import validate_schedule, compute_metrics, DEFAULT_SESSIONS, PASS, FAIL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.path.join(BASE_DIR, "public", "Horario_Formateado.xlsx")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")


def load_base_excel():
    with open(EXCEL_PATH, "rb") as f:
        return f.read()


def save_template(name, df_grupos, df_profesores, df_instructivo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_instructivo.to_excel(writer, sheet_name='Instructivo', index=False)
        df_profesores.to_excel(writer, sheet_name='Profesores', index=False)
        df_grupos.to_excel(writer, sheet_name='Grupos', index=False)
    output.seek(0)
    path = os.path.join(PUBLIC_DIR, name)
    with open(path, 'wb') as f:
        f.write(output.read())
    print(f"  Guardada: {path}")
    return output.getvalue()


def gen_plantilla_base():
    print("\n[1/5] Plantilla_base.xlsx (copia exacta)")
    raw = load_base_excel()
    path = os.path.join(PUBLIC_DIR, "Plantilla_base.xlsx")
    with open(path, 'wb') as f:
        f.write(raw)
    print(f"  Guardada: {path}")
    return raw


def gen_plantilla_30min():
    print("\n[2/5] Plantilla_30min.xlsx (B* y M* a 30min)")
    raw = load_base_excel()
    df_grupos = pd.read_excel(io.BytesIO(raw), sheet_name='Grupos')
    df_profes = pd.read_excel(io.BytesIO(raw), sheet_name='Profesores')
    df_instr = pd.read_excel(io.BytesIO(raw), sheet_name='Instructivo')
    return save_template("Plantilla_30min.xlsx", df_grupos, df_profes, df_instr)


def gen_plantilla_con_familias():
    print("\n[3/5] Plantilla_con_familias.xlsx (Nivel_o_Familia rellenado)")
    raw = load_base_excel()
    df_grupos = pd.read_excel(io.BytesIO(raw), sheet_name='Grupos')
    df_profes = pd.read_excel(io.BytesIO(raw), sheet_name='Profesores')
    df_instr = pd.read_excel(io.BytesIO(raw), sheet_name='Instructivo')

    family_map = {
        'B': 'Bachillerato',
        'M': 'ESO',
        'S': 'FP',
        'CEPB': 'CEP'
    }

    def infer_family(gid):
        if gid == 'CEPB':
            return 'CEP'
        prefix = gid[0] if gid else ''
        return family_map.get(prefix, 'Otros')

    df_grupos['Nivel_o_Familia'] = df_grupos['ID_Grupo'].apply(infer_family)
    return save_template("Plantilla_con_familias.xlsx", df_grupos, df_profes, df_instr)


def gen_plantilla_mas_grupos():
    print("\n[4/5] Plantilla_mas_grupos.xlsx (+10 grupos extra)")
    raw = load_base_excel()
    df_grupos = pd.read_excel(io.BytesIO(raw), sheet_name='Grupos')
    df_profes = pd.read_excel(io.BytesIO(raw), sheet_name='Profesores')
    df_instr = pd.read_excel(io.BytesIO(raw), sheet_name='Instructivo')

    extra_groups = []
    shifts = ['Mañana', 'Tarde']
    for i in range(10):
        gid = f"X{i+1:02d}"
        shift = shifts[i % 2]
        extra_groups.append({'ID_Grupo': gid, 'Nivel_o_Familia': 'FP', 'Turno': shift})

    df_extra = pd.DataFrame(extra_groups)
    df_grupos = pd.concat([df_grupos, df_extra], ignore_index=True)
    return save_template("Plantilla_mas_grupos.xlsx", df_grupos, df_profes, df_instr)


def gen_plantilla_pocos_profes():
    print("\n[5/5] Plantilla_pocos_profes.xlsx (menos profesores = más shared)")
    raw = load_base_excel()
    df_grupos = pd.read_excel(io.BytesIO(raw), sheet_name='Grupos')
    df_profes = pd.read_excel(io.BytesIO(raw), sheet_name='Profesores')
    df_instr = pd.read_excel(io.BytesIO(raw), sheet_name='Instructivo')

    df_profes['_count'] = df_profes['Grupos_Asignados'].str.count(',') + 1
    top_teachers = df_profes.nlargest(10, '_count', keep='first')
    df_profes = top_teachers.drop(columns=['_count']).reset_index(drop=True)
    return save_template("Plantilla_pocos_profes.xlsx", df_grupos, df_profes, df_instr)


def test_template(name, file_bytes, config=None):
    groups, teachers_map = parse_excel_bytes(file_bytes, {"duration_minutes": 20})
    full_config = config or {}
    full_config['evaluation_sessions'] = DEFAULT_SESSIONS

    schedule, stats = generate_schedule_from_data(
        copy.deepcopy(groups), copy.deepcopy(teachers_map), full_config
    )
    errors, warnings = validate_schedule(schedule, groups, teachers_map, DEFAULT_SESSIONS, full_config)
    metrics = compute_metrics(schedule, groups, DEFAULT_SESSIONS)
    status = PASS if not errors else FAIL

    return {
        "name": name,
        "status": status,
        "groups": len(groups),
        "teachers": len(set(t for ts in teachers_map.values() for t in ts)),
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics
    }


def print_template_result(r):
    icon = "✓" if r['status'] == PASS else "✗"
    m = r['metrics']
    print(f"\n  {icon} {r['name']}: {r['status']}")
    print(f"    Grupos: {r['groups']} | Profesores únicos: {r['teachers']}")
    print(f"    Asignados: {m['total_assigned']} | Sin asignar: {m['total_unassigned']} | Ocupación: {m.get('occupancy_pct', 'N/A')}%")
    print(f"    Uso salas: {m.get('room_usage', {})}")
    if r['errors']:
        print(f"    Errores ({len(r['errors'])}):")
        for e in r['errors'][:5]:
            print(f"      ✗ {e}")
    if r['warnings']:
        print(f"    Avisos ({len(r['warnings'])}):")
        for w in r['warnings']:
            print(f"      ⚠ {w}")


def main():
    print("=" * 60)
    print("GENERACIÓN DE PLANTILLAS ALTERNATIVAS")
    print("=" * 60)

    templates = {}

    templates['Plantilla_base.xlsx'] = gen_plantilla_base()
    templates['Plantilla_30min.xlsx'] = gen_plantilla_30min()
    templates['Plantilla_con_familias.xlsx'] = gen_plantilla_con_familias()
    templates['Plantilla_mas_grupos.xlsx'] = gen_plantilla_mas_grupos()
    templates['Plantilla_pocos_profes.xlsx'] = gen_plantilla_pocos_profes()

    print("\n" + "=" * 60)
    print("TESTS CON PLANTILLAS ALTERNATIVAS")
    print("=" * 60)

    results = []
    for name, data in templates.items():
        print(f"\nTesteando {name}...")
        result = test_template(name, data)
        results.append(result)
        print_template_result(result)

    print("\n" + "=" * 60)
    print("RESUMEN PLANTILLAS")
    print("=" * 60)
    passed = sum(1 for r in results if r['status'] == PASS)
    failed = sum(1 for r in results if r['status'] == FAIL)
    for r in results:
        icon = "✓" if r['status'] == PASS else "✗"
        errs = f" ({len(r['errors'])} errores)" if r['errors'] else ""
        print(f"  {icon} {r['name']}: {r['status']}{errs}")
    print(f"\nTotal: {passed}/{len(results)} PASSED, {failed}/{len(results)} FAILED")

    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               ".tmp", "template_test_results.json")
    summary = []
    for r in results:
        summary.append({
            "name": r['name'],
            "status": r['status'],
            "groups": r['groups'],
            "teachers": r['teachers'],
            "errors_count": len(r['errors']),
            "warnings_count": len(r['warnings']),
            "metrics": {k: v for k, v in r['metrics'].items() if k != 'schedule'},
            "errors": r['errors'][:5]
        })
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {output_path}")


if __name__ == "__main__":
    main()
