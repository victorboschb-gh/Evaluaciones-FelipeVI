# SOP: Generación del Calendario de Juntas de Evaluación 25/26

## Objetivo
Tu objetivo principal es coordinar de principio a fin la creación del calendario de juntas de evaluación para el curso 25/26. Tienes que asegurarte de que el calendario cumpla con todas las restricciones del centro (disponibilidad de profesores, límite de salas, efecto espejo de turnos y las duraciones específicas por grupo).

## Entradas Requeridas
Antes de empezar, asegúrate de tener acceso a los siguientes archivos de datos (normalmente ubicados en `.tmp/` o proporcionados por el usuario):
- `groups.json`: Datos de los grupos, turno y duración requerida (20 o 30 min).
- `teachers.json`: Listado de profesores.
- `schedule_constraints.json`: Fechas disponibles, salas (máx. 2 simultáneas) y reglas generales.

## Herramientas a Usar
Debes ejecutar estas herramientas estrictamente en el siguiente orden. No intentes procesar los datos tú mismo, delega la ejecución en los scripts Python:
1. `tools/parse_academic_data.py`: Parsea y estandariza los datos de entrada.
2. `tools/generate_schedule.py`: El motor que genera la primera propuesta de calendario.
3. `tools/check_conflicts.py`: Valida que no haya profesores solapados, que se respete el efecto espejo y el límite de salas.
4. `tools/analyze_time_capacity.py`: Analiza si las jornadas planificadas tienen tiempo suficiente o si hay huecos libres.
5. `tools/export_schedule.py`: Exporta el calendario final validado.

## Pasos de Ejecución

**Paso 1: Preparar y Validar los Datos de Entrada**
Ejecuta `tools/parse_academic_data.py` apuntando a los archivos JSON (`groups.json`, `teachers.json` y `schedule_constraints.json`). Revisa la salida del script para confirmar que los datos se han leído correctamente y están listos para usarse.

**Paso 2: Generar el Calendario**
Usa `tools/generate_schedule.py` pasando los datos procesados en el paso anterior. Este script te devolverá una propuesta inicial de calendario.

**Paso 3: Validar Conflictos y Tiempos**
- Primero, ejecuta `tools/check_conflicts.py` sobre la propuesta generada. Es crucial que no haya ningún conflicto de solapamiento de profesores ni incumplimiento del aforo de salas (máximo 2 sesiones simultáneas).
- Si la validación pasa limpiamente sin errores, ejecuta `tools/analyze_time_capacity.py` para verificar que la distribución del tiempo es lógica (que no falte tiempo para los grupos asignados ese día, ni que sobren demasiadas horas muertas).

**Paso 4: Generar la Salida Final (Entregable)**
Una vez que el calendario ha pasado todas las validaciones sin errores, ejecuta `tools/export_schedule.py`. Esto generará el archivo final (por ejemplo, `.tmp/final_schedule_25_26.csv`). Informa al usuario que el proceso ha finalizado y entrégale la ruta del archivo o un resumen de los resultados.

## Manejo de Casos Límite (Edge Cases)
- **Faltan datos o el formato es incorrecto:** Si `parse_academic_data.py` falla, detente. Pide al usuario que proporcione o corrija los archivos requeridos antes de continuar.
- **Conflictos detectados en el calendario:** Si `check_conflicts.py` encuentra errores (solapamientos, violación de aforos, etc.), NO pases al siguiente paso. Lee y sigue las instrucciones de `workflows/resolve_schedule_conflicts.md` para ajustar los parámetros e intentar generar el calendario de nuevo.
- **Avisos de capacidad de tiempo:** Si `analyze_time_capacity.py` arroja *warnings* (ej. "sobran 2 horas en la jornada del 18 de febrero"), notifica al usuario. Pregúntale si prefiere que intentes ajustar las restricciones y regenerar, o si procedemos a exportar el calendario tal cual.

## Salidas Esperadas
- Un archivo exportado (ej. CSV) en la carpeta `.tmp/` con el calendario final sin conflictos.
- Un reporte limpio de las validaciones y análisis de capacidad de tiempo, listo para la revisión final del usuario.