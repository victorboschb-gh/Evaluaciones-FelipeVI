import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import bisect


def _parse_time(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def _session_shift(start_time, end_time):
    midday = start_time.replace(hour=14, minute=0)
    if end_time <= midday:
        return 'morning'
    if start_time >= midday:
        return 'afternoon'
    return 'both'


def _infer_session_shifts(sessions):
    result = []
    for sess in sessions:
        start_dt = _parse_time(sess['date'], sess['start'])
        end_dt = _parse_time(sess['date'], sess['end'])
        result.append({
            'start': start_dt,
            'end': end_dt,
            'rooms': sess.get('rooms', ["Sala de Profesores", "Salón de Actos"]),
            'shift': _session_shift(start_dt, end_dt),
            'date': sess['date'],
        })
    return result


class TeacherSchedule:
    def __init__(self):
        self._busy = defaultdict(list)

    def add(self, teacher, start, end):
        intervals = self._busy[teacher]
        bisect.insort(intervals, (start, end))

    def is_busy(self, teacher, start, end):
        intervals = self._busy.get(teacher, [])
        lo = bisect.bisect_right(intervals, (start, datetime.max))
        if lo > 0:
            prev_start, prev_end = intervals[lo - 1]
            if prev_end > start:
                return True, prev_end
        if lo < len(intervals):
            next_start, next_end = intervals[lo]
            if next_start < end:
                return True, next_end
        return False, None

    def next_free_after(self, teachers, start, end):
        jump_to = None
        for t in teachers:
            busy, free_at = self.is_busy(t, start, end)
            if busy and free_at and (jump_to is None or free_at > jump_to):
                jump_to = free_at
        return jump_to


def _is_excluded(start, end, group_shift, excluded_hours):
    if group_shift not in excluded_hours:
        return False
    ex = excluded_hours[group_shift]
    ex_start_str = ex.get('start', '')
    ex_end_str = ex.get('end', '')
    if not ex_start_str or not ex_end_str:
        return False
    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M")
    if start_str < ex_end_str and end_str > ex_start_str:
        ex_end_dt = start.replace(
            hour=int(ex_end_str.split(':')[0]),
            minute=int(ex_end_str.split(':')[1])
        )
        return True, ex_end_dt
    return False



def _sort_groups(groups, teachers_map):
    def constraint_score(g):
        num_teachers = len(teachers_map.get(g['id'], []))
        shared = 0
        for other in groups:
            if other['id'] == g['id']:
                continue
            t1 = set(teachers_map.get(g['id'], []))
            t2 = set(teachers_map.get(other['id'], []))
            shared += len(t1 & t2)
        return (g.get('shift', 'morning'), g.get('family', ''), -shared, -num_teachers, g['id'])

    groups.sort(key=constraint_score)
    return groups


def generate_schedule_from_data(groups, teachers_map, config=None):
    if not groups or not teachers_map:
        raise ValueError("Los datos de grupos o profesores están vacíos.")

    config = config or {}
    evaluation_sessions = config.get('evaluation_sessions', [])
    selected_groups = config.get('selected_groups', [])
    excluded_hours = config.get('excluded_hours', {})

    teacher_shifts = {}
    for g in groups:
        shift = g.get('shift', 'morning')
        for t in teachers_map.get(g['id'], []):
            if t not in teacher_shifts:
                teacher_shifts[t] = set()
            teacher_shifts[t].add(shift)

    if selected_groups:
        groups = [g for g in groups if g['id'] in selected_groups]

    groups = _sort_groups(list(groups), teachers_map)

    if not evaluation_sessions:
        evaluation_sessions = [
            {"date": "2026-02-18", "start": "15:30", "end": "21:30"},
            {"date": "2026-02-19", "start": "08:30", "end": "14:30"}
        ]

    sessions = _infer_session_shifts(evaluation_sessions)

    teacher_sched = TeacherSchedule()
    room_avail = {}
    for sess in sessions:
        for room in sess['rooms']:
            room_avail[(sess['date'], room)] = sess['start']

    last_room_by_family = {}
    family_room_rotation = defaultdict(list)
    all_rooms = list(set(r for sess in sessions for r in sess['rooms']))

    schedule = []
    unassigned_duration = 0

    remaining = list(enumerate(groups))
    scheduled_indices = set()

    while remaining:
        best_overall_time = None
        best_overall_room = None
        best_overall_group_idx = None
        best_overall_sess = None
        best_overall_room_avail = None

        for idx, group in remaining:
            duration = timedelta(minutes=group.get('duration_minutes', 20))
            group_id = group['id']
            group_shift = group.get('shift', 'morning')
            group_teachers = teachers_map.get(group_id, [])

            preferred_sessions = []
            other_sessions = []
            for sess in sessions:
                if sess['shift'] == 'both' or sess['shift'] == group_shift:
                    preferred_sessions.append(sess)
                else:
                    other_sessions.append(sess)
            ordered_sessions = preferred_sessions + other_sessions

            best_time = None
            best_room = None
            best_room_avail = None

            for sess in ordered_sessions:
                sess_start = sess['start']
                sess_end = sess['end']
                sess_rooms = sess['rooms']
                date_key = sess['date']

                for cand_room in sess_rooms:
                    room_search = room_avail.get((date_key, cand_room), sess_end)
                    if room_search >= sess_end:
                        continue
                    if room_search < sess_start:
                        room_search = sess_start

                    found_time = None

                    for _ in range(200):
                        cand_end = room_search + duration

                        if cand_end > sess_end:
                            break

                        excl = _is_excluded(room_search, cand_end, group_shift, excluded_hours)
                        if excl:
                            _, ex_start_dt = excl
                            ex_end_str = excluded_hours[group_shift].get('end', '')
                            ex_end_dt = room_search.replace(
                                hour=int(ex_end_str.split(':')[0]),
                                minute=int(ex_end_str.split(':')[1])
                            )
                            if ex_end_dt >= sess_end:
                                break
                            room_search = ex_end_dt
                            continue

                        if group_teachers:
                            busy_until = teacher_sched.next_free_after(group_teachers, room_search, cand_end)
                            if busy_until is not None:
                                if busy_until >= sess_end:
                                    break
                                room_search = busy_until
                                continue

                        found_time = room_search
                        break

                    if found_time is not None:
                        cand_room_avail = room_avail.get((date_key, cand_room), sess_start)
                        if best_time is None or found_time < best_time:
                            best_time = found_time
                            best_room = cand_room
                            best_room_avail = cand_room_avail
                        elif found_time == best_time and cand_room_avail < best_room_avail:
                            best_room = cand_room
                            best_room_avail = cand_room_avail

                if best_time is not None:
                    if best_overall_time is None or best_time < best_overall_time:
                        best_overall_time = best_time
                        best_overall_room = best_room
                        best_overall_group_idx = idx
                        best_overall_sess = sess
                    elif best_time == best_overall_time:
                        cur_room_avail = best_room_avail
                        if cur_room_avail is not None and (best_overall_room_avail is None or cur_room_avail < best_overall_room_avail):
                            pass
                    break

        if best_overall_group_idx is None:
            break

        group = groups[best_overall_group_idx]
        duration = timedelta(minutes=group.get('duration_minutes', 20))
        group_id = group['id']
        family = group.get('family', '')
        group_teachers = teachers_map.get(group_id, [])

        best_time = best_overall_time
        best_room = best_overall_room
        end_time = best_time + duration
        date_str = best_time.strftime("%Y-%m-%d")

        schedule.append({
            "group_id": group_id,
            "group_name": group.get('name', group_id),
            "family": family,
            "date": date_str,
            "start_time": best_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "room": best_room,
            "duration_minutes": group.get('duration_minutes', 20),
            "teachers": group_teachers
        })

        room_avail[(date_str, best_room)] = end_time
        last_room_by_family[family] = best_room
        for prof in group_teachers:
            teacher_sched.add(prof, best_time, end_time)

        remaining = [(idx, g) for idx, g in remaining if idx != best_overall_group_idx]
        scheduled_indices.add(best_overall_group_idx)

    for idx, group in enumerate(groups):
        if idx not in scheduled_indices:
            print(f"Advertencia: No se pudo programar el grupo {group['id']}.")
            unassigned_duration += group.get('duration_minutes', 20)

    return schedule, {"unassigned_duration_minutes": unassigned_duration}


def generate_schedule():
    try:
        with open('.tmp/groups_data.json', 'r', encoding='utf-8') as f:
            groups = json.load(f)
        with open('.tmp/teachers_data.json', 'r', encoding='utf-8') as f:
            teachers_data = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Error cargando datos: {e}")

    config = {}
    try:
        if os.path.exists('.tmp/config.json'):
            with open('.tmp/config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
    except Exception as e:
        print(f"No se pudo cargar config.json, usando defaults: {e}")

    schedule, stats = generate_schedule_from_data(groups, teachers_data, config)

    os.makedirs('.tmp', exist_ok=True)
    with open('.tmp/proposed_schedule.json', 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)
    with open('.tmp/unassigned_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f)

    print(f"Calendario generado con éxito con {len(schedule)} grupos asignados.")


if __name__ == "__main__":
    generate_schedule()
