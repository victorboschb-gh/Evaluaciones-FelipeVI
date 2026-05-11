import pandas as pd
import os


def generate_template(output_path=None):
    if output_path is None:
        os.makedirs('public', exist_ok=True)
        output_path = os.path.join('public', 'Plantilla_Evaluacion.xlsx')

    instructivo_data = {
        'Instrucciones para rellenar la plantilla': [
            '1. Rellena la hoja "Grupos" con los datos de cada grupo.',
            '   Columnas obligatorias: ID_Grupo, Nivel_o_Familia, Turno.',
            '   En "Turno" escribe "Mañana" o "Tarde" (sin las comillas).',
            '2. Rellena la hoja "Profesores" indicando el nombre completo del profesor.',
            '3. En la hoja "Profesores", rellena la columna "Grupos_Asignados" escribiendo todos los grupos en los que da clase ese profesor, separados por comas.',
            'Ejemplo de Grupos_Asignados: "S1A, S1B, S2A"'
        ]
    }
    df_instructivo = pd.DataFrame(instructivo_data)

    profesores_data = {
        'Nombre_Profesor': ['Miguel Angel Pérez', 'Ana Gómez', 'Carlos Ruiz', 'Laura Martínez'],
        'Grupos_Asignados': ['B2J, B2C', 'B2C, 1A', '1A, 2B', 'B2J, 2B']
    }
    df_profesores = pd.DataFrame(profesores_data)

    grupos_data = {
        'ID_Grupo': ['B2J', 'B2C', '1A', '2B', 'S1A'],
        'Nivel_o_Familia': ['Bachillerato', 'Bachillerato', 'ESO', 'ESO', 'FP'],
        'Turno': ['Mañana', 'Mañana', 'Mañana', 'Mañana', 'Tarde']
    }
    df_grupos = pd.DataFrame(grupos_data)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_instructivo.to_excel(writer, sheet_name='Instructivo', index=False)
        df_profesores.to_excel(writer, sheet_name='Profesores', index=False)
        df_grupos.to_excel(writer, sheet_name='Grupos', index=False)

        ws_i = writer.sheets['Instructivo']
        ws_i.column_dimensions['A'].width = 120

        ws_p = writer.sheets['Profesores']
        ws_p.column_dimensions['A'].width = 40
        ws_p.column_dimensions['B'].width = 60

        ws_g = writer.sheets['Grupos']
        ws_g.column_dimensions['A'].width = 15
        ws_g.column_dimensions['B'].width = 35
        ws_g.column_dimensions['C'].width = 15

    print(f"Template successfully generated at {output_path}")


if __name__ == "__main__":
    generate_template()
