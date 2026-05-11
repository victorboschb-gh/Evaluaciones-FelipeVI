# Diseño de Arquitectura: Calendario de Juntas de Evaluación 25/26

## 1. Resumen del Flujo de Trabajo General
El sistema automatizará la generación del calendario de evaluaciones para el curso 25/26 respetando restricciones complejas (disponibilidad de profesores, salas y horarios cruzados). Basado en el framework WAT (Workflows, Agents, Tools), el agente inteligente orquestará la ejecución leyendo los flujos de trabajo en texto plano y delegando el procesamiento pesado, validaciones y cálculos de tiempo a scripts deterministas en Python.
Para posibilitar un despliegue profesional en un VPS, la arquitectura utiliza un modelo Cliente-Servidor: un backend robusto basado en FastAPI (o Flask) que orquesta las herramientas, y un frontend estático (HTML/JS/CSS) limpio para la interacción del usuario. Todo el sistema estará contenerizado usando Docker para asegurar consistencia e independencia del entorno.

## 2. Workflows (SOPs en `workflows/`)
*   **`workflows/generate_evaluation_from_ui.md`**: Flujo principal interactivo. Define el proceso donde el usuario sube Excels desde el frontend al backend, los datos se procesan, se genera el horario y el backend devuelve el documento de Word (.docx) para su descarga.
*   **`workflows/generate_evaluation_schedule.md`**: Flujo core de generación del calendario (backend lógico).
*   **`workflows/resolve_schedule_conflicts.md`**: Flujo secundario para manejo de errores. Define qué hacer si las herramientas detectan solapamientos o si falta/sobra tiempo en las jornadas.

## 3. Componentes del Sistema (Backend & Frontend)
*   **`server.py`**: Backend API (FastAPI o Flask). Expone un endpoint para recibir los archivos Excel subidos, invoca los flujos/scripts internos, y retorna el archivo `.docx` generado.
*   **`public/` (o `static/`)**: Carpeta que contiene el frontend web profesional. Incluye un `index.html`, estilos CSS y scripts JavaScript (manejo de drag & drop, peticiones HTTP al backend).
*   **`Dockerfile`**: Archivo de configuración de Docker para empaquetar el backend, frontend y todas las dependencias de Python, permitiendo un despliegue directo en cualquier VPS.

## 4. Tools (Scripts en `tools/`)
*   **`tools/parse_excel.py`**: Parsea los archivos Excel subidos por el usuario y los convierte a formato JSON en la carpeta `.tmp/`.
*   **`tools/parse_academic_data.py`**: Lee los datos de entrada en JSON y los estandariza para el motor de asignación.
*   **`tools/generate_schedule.py`**: Motor principal de programación (posiblemente usando un solver de restricciones como `ortools`). Asigna grupos a fechas y salas específicas considerando las duraciones.
*   **`tools/check_conflicts.py`**: Script de validación estricta de reglas de negocio. Verifica efecto espejo, límite de espacios, etc.
*   **`tools/analyze_time_capacity.py`**: Compara el tiempo programado contra la duración basada en el número de grupos por día.
*   **`tools/export_schedule.py`**: Genera el documento temporal en formatos utilizables (ej. CSV, Markdown).
*   **`tools/generate_word.py`**: Exporta el horario generado a un archivo `.docx` formateado usando como plantilla o base `SEGUNDA EVALUACIÓN 25-26.docx`.

## 4. Estructuras de Datos Propuestas (JSON)

### `groups.json`
Define los grupos, sus familias profesionales, turno y duración requerida de la junta.
```json
[
  {
    "id": "B2I",
    "name": "2 Bachillerato I",
    "family": "Bachillerato",
    "shift": "morning",
    "duration_minutes": 30,
    "teachers": ["T001", "T005", "T012"]
  },
  {
    "id": "S2A",
    "name": "S2A",
    "family": "Formacion Profesional",
    "shift": "afternoon",
    "duration_minutes": 20,
    "teachers": ["T002", "T008"]
  }
]
```

### `teachers.json`
Define los profesores para gestionar las restricciones de simultaneidad y evitar solapamientos.
```json
[
  {
    "id": "T001",
    "name": "Profesor 1"
  },
  {
    "id": "T002",
    "name": "Profesor 2"
  }
]
```

### `schedule_constraints.json`
Reglas de negocio y disponibilidad de fechas/salas según los datos del curso 25/26.
```json
{
  "max_simultaneous_sessions": 2,
  "mirror_effect_enabled": true,
  "sessions": [
    { 
      "date": "2026-02-18", 
      "rooms": ["Sala Profesores"],
      "allowed_groups": ["B2I", "B2C", "B2H"],
      "default_duration": 30
    },
    { 
      "date": "2026-02-19", 
      "rooms": ["Sala Profesores", "Salon Actos"],
      "allowed_groups": ["S2A", "S2B", "S2C", "S2D", "S2E", "M2A", "M2R"],
      "default_duration": 20
    }
  ]
}
```

## 6. Diagrama de Arquitectura (Mermaid)

```mermaid
graph TD
    U[Usuario] -->|Arrastra Excels| F[Frontend - public/index.html]
    F -->|POST /upload| B[Backend API - server.py FastAPI/Flask]
    B -->|Inicia proceso| A[Agente Orquestador]
    A -->|Lee Instrucciones| W[workflows/generate_evaluation_from_ui.md]
    W --> PE[tools/parse_excel.py]
    PE -->|Crea JSON en .tmp/| PA[tools/parse_academic_data.py]
    PA --> GS[tools/generate_schedule.py]
    GS --> CC[tools/check_conflicts.py]
    CC -->|Si hay conflictos| RC[workflows/resolve_schedule_conflicts.md]
    RC -->|Ajusta parametros| GS
    CC -->|Sin conflictos| GW[tools/generate_word.py]
    GW -->|Retorna .docx| B
    B -->|Descarga Archivo| F
    F -->|Muestra al Usuario| U
    
    subgraph Docker Container
    B
    F
    A
    W
    PE
    PA
    GS
    CC
    RC
    GW
    end
