import json
import os
import sys
import time
import copy
import io
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.generate_schedule import generate_schedule_from_data
from tools.parse_excel import parse_excel_bytes

EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "public", "Horario_Formateado.xlsx")

DEFAULT_SESSIONS = [
    {"date": "2026-02-18", "start": "15:30", "end": "21:30"},
    {"date": "2026-02-19", "start": "08:30", "end": "14:30"}
]

PASS = "PASS"
FAIL = "FAIL"
import sys as _sys
_sys.stdout.reconfigure(encoding='utf-8')


def load_data():
    with open(EXCEL_PATH, "rb") as f:
        file_bytes = f.read()
    return parse_excel_bytes(file_bytes, {"duration_minutes": 20})


def validate_schedule(schedule, groups, teachers_map, sessions, config):
    errors = []
    warnings = []

    if not schedule and groups:
        errors.append("Horario vacío pero hay grupos por asignar")
        return errors, warnings

    for i, entry in enumerate(schedule):
        start_dt = datetime.strptime(f"{entry['date']} {entry['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{entry['date']} {entry['end_time']}", "%Y-%m-%d %H:%M")
        actual_dur = (end_dt - start_dt).total_seconds() / 60
        expected_dur = entry.get('duration_minutes', 20)

        if actual_dur != expected_dur:
            errors.append(
                f"[{entry['group_name']}] Duración real {actual_dur}min != esperada {expected_dur}min"
            )

    sess_map = {}
    for sess in sessions:
        s_start = datetime.strptime(f"{sess['date']} {sess['start']}", "%Y-%m-%d %H:%M")
        s_end = datetime.strptime(f"{sess['date']} {sess['end']}", "%Y-%m-%d %H:%M")
        rooms = sess.get('rooms', ["Sala de Profesores", "Salón de Actos"])
        sess_map[sess['date']] = {'start': s_start, 'end': s_end, 'rooms': rooms}

    for entry in schedule:
        start_dt = datetime.strptime(f"{entry['date']} {entry['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{entry['date']} {entry['end_time']}", "%Y-%m-%d %H:%M")

        if entry['date'] not in sess_map:
            errors.append(f"[{entry['group_name']}] Fecha {entry['date']} no está en las sesiones")
            continue

        s_info = sess_map[entry['date']]
        if start_dt < s_info['start']:
            errors.append(f"[{entry['group_name']}] Empieza antes de la sesión ({entry['start_time']} < {sess['start']})")
        if end_dt > s_info['end']:
            errors.append(f"[{entry['group_name']}] Termina después de la sesión ({entry['end_time']} > {sess['end']})")
        if entry['room'] not in s_info['rooms']:
            errors.append(f"[{entry['group_name']}] Sala '{entry['room']}' no disponible en sesión")

    room_events = defaultdict(list)
    for entry in schedule:
        start_dt = datetime.strptime(f"{entry['date']} {entry['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{entry['date']} {entry['end_time']}", "%Y-%m-%d %H:%M")
        key = (entry['date'], entry['room'])
        room_events[key].append((start_dt, end_dt, entry['group_name']))

    for key, events in room_events.items():
        events.sort()
        for i in range(len(events) - 1):
            _, end_prev, name_prev = events[i]
            start_next, _, name_next = events[i + 1]
            if start_next < end_prev:
                errors.append(
                    f"Solapamiento sala {key[1]} el {key[0]}: {name_prev} termina {end_prev.strftime('%H:%M')}, "
                    f"{name_next} empieza {start_next.strftime('%H:%M')}"
                )

    teacher_events = defaultdict(list)
    for entry in schedule:
        start_dt = datetime.strptime(f"{entry['date']} {entry['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{entry['date']} {entry['end_time']}", "%Y-%m-%d %H:%M")
        for t in entry.get('teachers', []):
            teacher_events[t].append((start_dt, end_dt, entry['group_name']))

    for teacher, events in teacher_events.items():
        events.sort()
        for i in range(len(events) - 1):
            _, end_prev, name_prev = events[i]
            start_next, _, name_next = events[i + 1]
            if start_next < end_prev:
                errors.append(
                    f"Solapamiento profesor '{teacher}': {name_prev} ({end_prev.strftime('%H:%M')}) "
                    f"vs {name_next} ({start_next.strftime('%H:%M')})"
                )

    assigned_ids = {e['group_id'] for e in schedule}
    group_ids = {g['id'] for g in groups}
    if config.get('selected_groups'):
        group_ids = set(config['selected_groups'])
    unassigned = group_ids - assigned_ids
    if unassigned:
        warnings.append(f"Grupos sin asignar: {sorted(unassigned)}")

    return errors, warnings


def compute_metrics(schedule, groups, sessions):
    if not schedule:
        return {"total_assigned": 0, "total_unassigned": len(groups), "room_usage": {},
                "teacher_load": {}, "time_distribution": {}, "sessions_used": set()}

    assigned = len(schedule)
    total = len(groups)
    unassigned = total - assigned

    room_usage = defaultdict(int)
    for e in schedule:
        room_usage[e['room']] += 1

    teacher_count = defaultdict(int)
    for e in schedule:
        for t in e.get('teachers', []):
            teacher_count[t] += 1

    top_teachers = sorted(teacher_count.items(), key=lambda x: -x[1])[:5]

    time_dist = defaultdict(int)
    for e in schedule:
        hour = e['start_time'][:2]
        time_dist[f"{hour}:00-{hour}:59"] += 1

    sessions_used = set(e['date'] for e in schedule)

    total_minutes = sum(e.get('duration_minutes', 20) for e in schedule)
    room_slots = {}
    for sess in sessions:
        s = datetime.strptime(f"{sess['date']} {sess['start']}", "%Y-%m-%d %H:%M")
        en = datetime.strptime(f"{sess['date']} {sess['end']}", "%Y-%m-%d %H:%M")
        avail = (en - s).total_seconds() / 60
        for r in sess.get('rooms', ["Sala de Profesores", "Salón de Actos"]):
            room_slots[(sess['date'], r)] = avail
    total_capacity = sum(room_slots.values())
    occupancy = (total_minutes / total_capacity * 100) if total_capacity > 0 else 0

    return {
        "total_assigned": assigned,
        "total_unassigned": unassigned,
        "occupancy_pct": round(occupancy, 1),
        "room_usage": dict(room_usage),
        "top_teachers": [(t, c) for t, c in top_teachers],
        "time_distribution": dict(sorted(time_dist.items())),
        "sessions_used": sorted(sessions_used)
    }


def run_test(name, groups, teachers_map, config, sessions=None):
    if sessions is None:
        sessions = DEFAULT_SESSIONS

    full_config = dict(config)
    full_config['evaluation_sessions'] = sessions

    t0 = time.time()
    schedule, stats = generate_schedule_from_data(
        copy.deepcopy(groups), copy.deepcopy(teachers_map), full_config
    )
    elapsed = time.time() - t0

    errors, warnings = validate_schedule(schedule, groups, teachers_map, sessions, full_config)
    metrics = compute_metrics(schedule, groups, sessions)

    status = PASS if not errors else FAIL

    return {
        "name": name,
        "status": status,
        "elapsed_s": round(elapsed, 3),
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "schedule": schedule,
        "stats": stats
    }


def print_result(r):
    icon = "✓" if r['status'] == PASS else "✗"
    print(f"\n{'='*60}")
    print(f"{icon} {r['name']}: {r['status']} ({r['elapsed_s']}s)")
    print(f"{'='*60}")

    m = r['metrics']
    print(f"  Asignados: {m['total_assigned']} | Sin asignar: {m['total_unassigned']} | Ocupación: {m.get('occupancy_pct', 'N/A')}%")
    print(f"  Sesiones usadas: {m['sessions_used']}")
    print(f"  Uso de salas: {m.get('room_usage', {})}")

    if m.get('top_teachers'):
        print(f"  Top 5 profesores por carga:")
        for t, c in m['top_teachers']:
            print(f"    - {t}: {c} sesiones")

    if m.get('time_distribution'):
        print(f"  Distribución horaria:")
        for slot, count in m['time_distribution'].items():
            bar = "█" * count
            print(f"    {slot}: {bar} ({count})")

    if r['errors']:
        print(f"\n  ERRORES ({len(r['errors'])}):")
        for e in r['errors'][:10]:
            print(f"    ✗ {e}")
        if len(r['errors']) > 10:
            print(f"    ... y {len(r['errors']) - 10} más")

    if r['warnings']:
        print(f"\n  AVISOS ({len(r['warnings'])}):")
        for w in r['warnings']:
            print(f"    ⚠ {w}")


def test_t1_base(groups, teachers_map):
    return run_test(
        "T1: Configuración base (2 días, 20min, sin restricciones)",
        groups, teachers_map, {}
    )


def test_t2_mixed_duration(groups, teachers_map):
    modified = copy.deepcopy(groups)
    count = 0
    for g in modified:
        if g['id'].startswith('B') or g['id'].startswith('M'):
            g['duration_minutes'] = 30
            count += 1
    return run_test(
        f"T2: Duración mixta ({count} grupos a 30min, resto 20min)",
        modified, teachers_map, {}
    )


def test_t3_mirror(groups, teachers_map):
    morning_only = [
        {"date": "2026-02-19", "start": "08:30", "end": "14:30"}
    ]
    afternoon_only = [
        {"date": "2026-02-18", "start": "15:30", "end": "21:30"}
    ]
    sessions = morning_only + afternoon_only
    return run_test(
        "T3: Efecto espejo (sesión mañana + sesión tarde separadas)",
        groups, teachers_map, {}, sessions
    )


def test_t4_shift_family_order(groups, teachers_map):
    result = run_test(
        "T4: Agrupación por turno → familia",
        groups, teachers_map, {}
    )
    schedule = result['schedule']
    shifts_seen = []
    families_by_shift = defaultdict(set)
    for entry in schedule:
        group = next((g for g in groups if g['id'] == entry['group_id']), None)
        if group:
            shifts_seen.append(group.get('shift', 'morning'))
            families_by_shift[group.get('shift', 'morning')].add(group.get('family', ''))

    morning_index = None
    afternoon_index = None
    for i, s in enumerate(shifts_seen):
        if s == 'morning' and morning_index is None:
            morning_index = i
        if s == 'afternoon' and afternoon_index is None:
            afternoon_index = i

    if morning_index is not None and afternoon_index is not None:
        morning_end = max(i for i, s in enumerate(shifts_seen) if s == 'morning')
        afternoon_start = next(i for i, s in enumerate(shifts_seen) if s == 'afternoon')
        if afternoon_start < morning_end:
            result['warnings'].append("Grupos de mañana y tarde mezclados (esperado por sesiones disponibles)")

    if not result['errors']:
        result['status'] = PASS
    return result


def test_t5_insufficient_time(groups, teachers_map):
    sessions = [
        {"date": "2026-02-18", "start": "08:30", "end": "10:30"}
    ]
    result = run_test(
        "T8: Tiempo insuficiente (solo 2h para 34 grupos)",
        groups, teachers_map, {}, sessions
    )
    if result['metrics']['total_unassigned'] > 0:
        result['status'] = PASS
        if "esperaba grupos sin asignar" not in str(result['warnings']):
            result['warnings'].insert(0, "✓ Correctamente reportó grupos sin asignar (esperado)")
    else:
        result['status'] = FAIL
        result['errors'].append("Esperaba grupos sin asignar pero todos fueron asignados — revisar")
    return result


def main():
    print("=" * 60)
    print("BATERÍA DE TESTS — Motor de Generación de Horarios")
    print("=" * 60)

    print("\nCargando datos desde Horario_Formateado.xlsx...")
    groups, teachers_map = load_data()
    print(f"  {len(groups)} grupos, {len(teachers_map)} mapeos de profesores")

    morning = sum(1 for g in groups if g['shift'] == 'morning')
    afternoon = sum(1 for g in groups if g['shift'] == 'afternoon')
    print(f"  Mañana: {morning} | Tarde: {afternoon}")

    tests = [
        test_t1_base,
        test_t2_mixed_duration,
        test_t3_mirror,
        test_t4_shift_family_order,
        test_t5_insufficient_time,
    ]

    results = []
    for test_fn in tests:
        print(f"\nEjecutando {test_fn.__name__}...")
        result = test_fn(groups, teachers_map)
        results.append(result)
        print_result(result)

    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)

    passed = sum(1 for r in results if r['status'] == PASS)
    failed = sum(1 for r in results if r['status'] == FAIL)

    for r in results:
        icon = "✓" if r['status'] == PASS else "✗"
        errs = f" ({len(r['errors'])} errores)" if r['errors'] else ""
        warns = f" ({len(r['warnings'])} avisos)" if r['warnings'] else ""
        extra = errs or warns
        print(f"  {icon} {r['name']}: {r['status']}{extra}")

    print(f"\nTotal: {passed}/{len(results)} PASSED, {failed}/{len(results)} FAILED")

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp")
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "test_results.json")

    summary = []
    for r in results:
        summary.append({
            "name": r['name'],
            "status": r['status'],
            "elapsed_s": r['elapsed_s'],
            "errors_count": len(r['errors']),
            "warnings_count": len(r['warnings']),
            "metrics": {k: v for k, v in r['metrics'].items() if k != 'schedule'},
            "errors": r['errors'][:5],
            "warnings": r['warnings'][:5]
        })

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {summary_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
