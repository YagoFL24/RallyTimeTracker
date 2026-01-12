# Rally Time Tracker

Aplicacion de escritorio para gestionar tiempos de rally de forma sencilla y visual. Permite crear competiciones,
registrar tiempos por tramo, calcular clasificacion general y aplicar penalizaciones. La informacion se guarda en
una base de datos SQLite local (`datos.db`), por lo que no necesitas servidor ni conexion a internet. La interfaz
esta hecha con Tkinter y esta pensada para usarse rapidamente durante una carrera: seleccionas la competicion,
agregas tiempos, rellenas abandonos y ves la tabla general en tiempo real.

## Estructura
- `src/`: codigo fuente de la aplicacion
- `data/`: base de datos SQLite local (ignorada en Git)
- `assets/images/`: iconos de la app

## Funcionalidades principales
- Crear, borrar y listar competiciones.
- Definir participantes y numero de etapas.
- Agregar tiempos por tramo a cada piloto.
- Rellenar abandonos con penalizacion automatica.
- Penalizar tiempos por tramo.
- Ver clasificacion general y diferencias con el lider.
- Ordenar la tabla por piloto, tramo o total.

## Ejecutar en desarrollo
```bash
python src/main.py
```

## Ejecutable
Si ya tienes PyInstaller instalado, puedes generar el ejecutable asi:
```bash
python -m PyInstaller --noconfirm --onefile --windowed --name RallyTimeTracker --icon assets/images/rally.ico --add-data "assets/images/rally.ico;assets/images" --add-data "assets/images/rally.png;assets/images" src/main.py
```

El ejecutable queda en `dist/RallyTimeTracker.exe`.

Al ejecutar el `.exe`, la base de datos se crea vacia en `%LOCALAPPDATA%\\RallyTimeTracker`.
