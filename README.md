# Sistema de Juntas de Evaluación

Sistema web para generar automáticamente los calendarios de juntas de evaluación para centros educativos (FP y Bachillerato). Desarrollado para el **CIFP Felipe VI**.

Sube un Excel con los datos de grupos y profesores, configura las sesiones de evaluación, y obtén un documento Word con el calendario completo asignando grupos, salas y horarios sin solapamientos.

## Funcionalidades

- **Parseo inteligente de Excel**: Admite múltiples formatos de entrada y los adapta automáticamente a la plantilla del sistema
- **Motor de asignación sin conflictos**: Resuelve automáticamente las restricciones de profesores compartidos, salas disponibles y franjas horarias
- **Exportación a Word**: Genera documentos `.docx` formateados listos para imprimir
- **Autenticación de usuarios**: Registro, login y panel de administración para gestionar accesos
- **Despliegue flexible**: Docker, Vercel o ejecución local con un solo comando

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Frontend | HTML, TailwindCSS, JavaScript |
| Procesamiento Excel | Pandas, OpenPyXL |
| Generación Word | python-docx |
| Base de datos | PostgreSQL (psycopg2) |
| Autenticación | JWT, bcrypt |
| Despliegue | Docker / Vercel |

## Instalación rápida

### Requisitos

- Python 3.11+
- PostgreSQL (opcional para auth, el sistema funciona sin él en modo local)

### Ejecución local

```bash
git clone https://github.com/Victor-ems21/sistema-juntas-evaluacion.git
cd sistema-juntas-evaluacion
pip install -r requirements.txt
python main.py
```

Se abre automáticamente el navegador en `http://127.0.0.1:8000`.

### Con Docker

```bash
docker compose up --build
```

Accede a `http://localhost:8000`.

### Variables de entorno

Copia `.env.example` a `.env` y configura:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
JWT_SECRET=your-secret-key-here
ADMIN_EMAIL=admin@example.com
```

## Estructura del proyecto

```
├── api/                    # Endpoints de la API (FastAPI)
│   ├── index.py            # Rutas principales y auth
│   ├── auth.py             # Lógica de autenticación (JWT, bcrypt)
│   └── init_db.sql         # Esquema de la base de datos
├── tools/                  # Scripts de procesamiento deterministas
│   ├── parse_excel.py      # Parseo y normalización de archivos Excel
│   ├── get_groups.py       # Extracción de grupos desde datos
│   ├── adapt_excel.py      # Adaptación automática de formatos
│   ├── generate_schedule.py # Motor de asignación de horarios
│   ├── generate_word.py    # Exportación a documento Word
│   └── ...
├── public/                 # Frontend estático
│   ├── index.html          # Interfaz principal
│   ├── login.html          # Autenticación
│   ├── admin.html          # Panel de administración
│   ├── tutorial.html       # Guía paso a paso
│   └── Plantilla_*.xlsx    # Plantillas de Excel
├── workflows/              # SOPs en Markdown (framework WAT)
├── server.py               # Servidor FastAPI (modo local sin auth)
├── main.py                 # Punto de entrada con navegador automático
├── Dockerfile
├── docker-compose.yml
└── vercel.json             # Configuración para deploy en Vercel
```

## Cómo funciona

1. **Descarga la plantilla** Excel desde la aplicación
2. **Rellena los datos** de grupos (ID, familia, turno) y profesores con sus grupos asignados
3. **Sube el archivo** y configura las sesiones de evaluación (fechas, salas, duración)
4. **El sistema asigna** automáticamente grupos a franjas horarias respetando todas las restricciones
5. **Descarga el calendario** en formato Word, listo para distribuir

## Licencia

Este proyecto está licenciado bajo **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**.

Eres libre de usar, modificar y distribuir este software, incluso con fines comerciales, siempre que des crédito apropiado y distribuyas las obras derivadas bajo la misma licencia.

Consulta el archivo [LICENSE](LICENSE) para más detalles o visita [creativecommons.org/licenses/by-sa/4.0](https://creativecommons.org/licenses/by-sa/4.0/).
