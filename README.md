# Rally Time Tracker

![Logotipo de Rally Time Tracker](assets/images/rally.png)

Aplicación de escritorio para registrar y clasificar tiempos de una competición de rally. Funciona sin servidor ni conexión a Internet: la interfaz está construida con Tkinter y los datos se guardan en una base SQLite local.

## Funcionalidad

- Crear y eliminar competiciones.
- Definir el número de tramos y la lista de participantes.
- Registrar o corregir el tiempo de un piloto en un tramo.
- Completar abandonos con el peor tiempo del tramo más 10 segundos.
- Aplicar penalizaciones acumulativas en segundos.
- Consultar la clasificación, el total y la diferencia con el líder.
- Ordenar visualmente la tabla por posición, piloto, tramo, total o diferencia.
- Alternar entre tema claro y oscuro.
- Usar una interfaz gráfica principal y una CLI heredada.

## Inicio rápido

Requisitos:

- Windows, Linux o macOS con Python 3 y Tkinter. El desarrollo y la publicación automatizada usan Python 3.12.
- No hay dependencias externas para ejecutar el código fuente.

Desde la raíz del repositorio:

```bash
python src/main.py
```

La base de datos se crea automáticamente en `data/datos.db`, tomando como referencia el directorio desde el que se lanza el comando.

La CLI heredada se puede abrir con:

```bash
python src/cli_main.py
```

## Uso básico

1. Pulsa **Nueva** e introduce el nombre, el número de etapas y los participantes.
2. Selecciona una competición en el panel izquierdo.
3. En **Agregar tiempo**, escoge participante y etapa, escribe el tiempo como `m:ss.xxx` y pulsa **Guardar**.
4. Si un piloto no termina un tramo, registra primero al menos un tiempo válido y usa **Rellenar abandonos**.
5. Para sumar una sanción, escoge piloto, etapa y segundos en **Penalizar**.
6. Haz clic en una cabecera para ordenar la vista.

Consulta la [guía de usuario](docs/MANUAL_USUARIO.md) para conocer todos los flujos y las reglas de cálculo.

## Datos

| Entorno | Ubicación |
| --- | --- |
| Código fuente | `<directorio de ejecución>/data/datos.db` |
| Ejecutable de Windows | `%LOCALAPPDATA%\RallyTimeTracker\datos.db` |

Para hacer una copia de seguridad, cierra la aplicación y copia `datos.db`. La aplicación no sincroniza ni envía información a servicios externos.

## Documentación

- [Manual de usuario](docs/MANUAL_USUARIO.md): operación diaria, formatos, reglas y copia de seguridad.
- [Arquitectura y modelo de datos](docs/ARQUITECTURA.md): módulos, flujos, esquema SQLite y decisiones técnicas.
- [Desarrollo, empaquetado y releases](docs/DESARROLLO.md): entorno, ejecución, distribución y mantenimiento.
- [Estado y limitaciones conocidas](docs/ESTADO_Y_LIMITACIONES.md): comportamiento verificado, riesgos y deuda técnica.

## Estructura

```text
RallyTimeTracker/
├── .github/
│   ├── scripts/release.py       # Cálculo de versión y changelog
│   └── workflows/release.yml    # Build y publicación en GitHub
├── assets/images/               # PNG e icono de la aplicación
├── data/                        # Bases locales; ignorado por Git
├── docs/                        # Documentación funcional y técnica
├── src/
│   ├── main.py                  # Entrada de la GUI
│   ├── gui_tk.py                # Interfaz Tkinter
│   ├── servicios.py             # Casos de uso y validación
│   ├── persistencia.py          # Acceso SQLite
│   ├── gestorTiempos.py         # Conversión y ordenación de tiempos
│   ├── cli_main.py              # Entrada de la CLI heredada
│   └── interfaz.py              # Presentación de la CLI
├── CHANGELOG.md
└── README.md
```

`build/`, `dist/`, las bases de datos, los ejecutables y los archivos `.spec` son artefactos locales ignorados por Git. El repositorio no contiene actualmente una suite automatizada de pruebas ni un archivo de licencia.

## Ejecutable de Windows

Con PyInstaller instalado:

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name RallyTimeTracker --icon assets/images/rally.ico --add-data "assets/images/rally.ico;assets/images" --add-data "assets/images/rally.png;assets/images" src/main.py
```

El resultado se genera en `dist/RallyTimeTracker.exe`. El workflow de GitHub Actions ejecuta este mismo proceso al publicar una release.

Antes de usar la aplicación en una prueba real, revisa las [limitaciones conocidas](docs/ESTADO_Y_LIMITACIONES.md), especialmente las relacionadas con clasificaciones incompletas y validación de datos.
