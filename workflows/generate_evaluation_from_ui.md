# Workflow: Generación de Horario de Evaluaciones desde UI (Streamlit)

**Objetivo:** Permitir al usuario subir sus archivos de datos en formato Excel mediante una interfaz gráfica (Streamlit), procesar esos datos para generar el calendario de evaluaciones, y devolver finalmente un documento de Word (.docx) descargable, basado en el formato de "SEGUNDA EVALUACIÓN 25-26.docx".

## 1. Entradas Esperadas (vía UI)
- **Excels de Datos:** Archivos Excel que contienen la información de los grupos, profesores y restricciones (ej. `grupos.xlsx`, `profesores.xlsx`).
- **Parámetros:** Configuraciones adicionales como fechas disponibles, duración predeterminada de las juntas, etc. (se pueden introducir en la UI o mediante un archivo Excel adicional).

## 2. Herramientas a Utilizar
- `app.py`: La interfaz web de Streamlit que orquesta la interacción con el usuario.
- `tools/parse_excel.py`: Convierte los Excels subidos a formato estandarizado JSON en la carpeta `.tmp/`.
- `workflows/generate_evaluation_schedule.md`: El workflow central que genera el horario basado en los datos parseados.
- `tools/generate_word.py`: Exporta el calendario generado a un archivo final `.docx` listo para la descarga.

## 3. Pasos del Flujo de Trabajo

### Paso 1: Recepción de Datos en la UI
1. El usuario accede a la aplicación web (Streamlit).
2. Sube los archivos Excel requeridos.
3. La UI guarda temporalmente estos archivos en `.tmp/` y lanza el proceso.

### Paso 2: Procesamiento y Parseo (`parse_excel.py`)
1. El sistema ejecuta `tools/parse_excel.py`.
2. Lee los Excels desde `.tmp/`.
3. Valida que las columnas obligatorias estén presentes.
4. Exporta los datos a `groups_data.json` y `teachers_data.json` en `.tmp/`.

### Paso 3: Generación del Horario (Llamada al motor base)
1. El sistema invoca el motor de generación (o sigue las instrucciones de `workflows/generate_evaluation_schedule.md`).
2. Se procesan los datos con `tools/generate_schedule.py`.
3. Se verifica si hay conflictos (usando `check_conflicts.py`). Si los hay, se resuelven o se reportan al usuario en la UI.
4. Se produce un documento de datos estructurado del horario final (ej. `schedule_output.json`).

### Paso 4: Generación del Documento Final (`generate_word.py`)
1. Una vez el horario está generado sin conflictos, el sistema ejecuta `tools/generate_word.py`.
2. Lee `schedule_output.json`.
3. Utilizando el estilo de `SEGUNDA EVALUACIÓN 25-26.docx` como referencia, construye un archivo `.docx`.
4. El archivo generado se guarda en `.tmp/horario_evaluaciones_generado.docx`.

### Paso 5: Descarga en la UI
1. La aplicación web detecta que el archivo `.docx` se ha generado correctamente.
2. Muestra un botón de descarga al usuario.
3. El usuario obtiene su archivo de Word y finaliza el proceso.

## 4. Manejo de Errores y Edge Cases
- **Formato de Excel incorrecto:** Si `parse_excel.py` detecta un formato no válido o faltan columnas, emitirá un error legible que la UI debe mostrar (ej. "Falta la columna 'Profesor' en el archivo de grupos").
- **Imposibilidad de generar horario:** Si el motor no logra asignar las reuniones por falta de tiempo en los días elegidos, la UI notificará al usuario para que modifique las restricciones y vuelva a subir los datos.