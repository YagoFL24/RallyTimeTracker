# Desarrollo, empaquetado y releases

## 1. Entorno

El proyecto usa `openpyxl` para Excel y `reportlab` para PDF. La publicación oficial configura Python 3.12 en Windows y obtiene las versiones fijadas en `requirements.txt`.

Comprueba el entorno:

```bash
python --version
python -m pip install -r requirements.txt
python -c "import tkinter, sqlite3; print('Tk', tkinter.TkVersion, 'SQLite', sqlite3.sqlite_version)"
```

PyInstaller solo es necesario para construir el ejecutable.

## 2. Ejecutar desde código

Desde la raíz del repositorio:

```bash
python src/main.py
```

La ruta de desarrollo depende de `os.getcwd()`. Ejecutar el archivo desde otro directorio crea o utiliza un `data/datos.db` distinto bajo ese directorio. Para trabajar siempre con la misma base, inicia el programa desde la raíz.

CLI heredada:

```bash
python src/cli_main.py
```

Los módulos usan imports planos (`from gui_tk import ...`, `from persistencia import ...`), por lo que importar el proyecto como paquete requiere antes una reorganización.

## 3. Datos de desarrollo

`data/` y `*.db` están ignorados por Git. En una copia local pueden existir:

- `data/datos.db`: base de trabajo;
- `data/datos_template.db`: plantilla histórica vacía, no utilizada por el código;
- notas locales de commits.

No uses una base real para pruebas destructivas. Crea un directorio temporal, cambia a él antes de llamar a persistencia y vuelve al directorio anterior antes de eliminarlo, porque `_get_db_path()` depende del directorio actual.

## 4. Pruebas y controles

El repositorio contiene 104 pruebas unitarias y funcionales. Las operaciones de datos se ejecutan sobre bases SQLite temporales, nunca sobre `data/datos.db`.

Cobertura automatizada actual:

- parsing y formato de tiempos;
- validación de competiciones, etapas, participantes y penalizaciones;
- ciclo completo de alta, consulta, persistencia y borrado;
- clasificación completa e incompleta, estados explícitos, retiradas y selección de etapa pendiente;
- exportación e importación real de CSV/Excel y generación PDF;
- resumen operativo del tramo, pendientes activos, revisiones y carga rápida en formularios;
- presentación y ordenación de descalificados conservando resultados previos;
- recuento de victorias de tramo, incluidos empates y reasignación tras una descalificación;
- creación, rotación, validación y restauración atómica de backups SQLite;
- abandonos, acumulación de penalizaciones y protección frente a overflow;
- ordenación de tabla y carga de combos sin levantar una ventana real;
- recorrido del siguiente piloto pendiente, cambio circular de piloto/tramo y guardado por teclado;
- migración v2 a v3, planteles, alias, invitados, calendario y protección de competiciones vinculadas;
- puntuación de campeonatos, empates, bonus de tramos, DSQ, retiradas, bajas y recálculo;
- exportación de campeonatos a CSV, Excel y PDF;
- SemVer, lectura de commits, changelog, notas y salidas de GitHub Actions.

Todavía no hay automatización de la renderización gráfica real, interacción con diálogos o empaquetado ejecutable. Tampoco hay linter, formateador, comprobación de tipos o informe porcentual de cobertura.

Ejecutar las pruebas disponibles:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Control de sintaxis sin iniciar la GUI:

```bash
python -m compileall src .github/scripts
```

`.github/workflows/tests.yml` ejecuta ambos controles con Python 3.12 en Windows para cada pull request, cada push a una rama distinta de `main` y cuando se inicia manualmente. El workflow de release vuelve a ejecutar la suite completa al llegar a `main`.

Comprobación manual mínima recomendada:

1. arrancar con una base vacía;
2. crear una competición con al menos tres participantes y tres etapas;
3. guardar y corregir un tiempo;
4. registrar tiempos fuera de orden para comprobar columnas;
5. rellenar abandonos con y sin tiempo base;
6. aplicar una penalización decimal;
7. ordenar cada columna;
8. cambiar el tema;
9. cerrar, reabrir y comprobar persistencia;
10. crear un campeonato, añadir la competición y comprobar la asignación de pilotos e invitados;
11. completar la prueba y verificar posiciones, puntos, bonus y diferencias;
12. retirar y reincorporar un piloto desde otra prueba;
13. reordenar y desvincular una prueba, comprobando que la competición se conserva;
14. exportar el campeonato a CSV, Excel y PDF;
15. borrar la competición y comprobar que desaparecen todos sus datos.

Antes de automatizar casos de integración, conviene permitir inyectar la ruta de SQLite en vez de depender de `os.getcwd()`.

## 5. Construir el ejecutable

Instala PyInstaller:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
```

Ejecuta el mismo comando que usa GitHub Actions:

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name RallyTimeTracker --icon assets/images/rally.ico --add-data "assets/images/rally.ico;assets/images" --add-data "assets/images/rally.png;assets/images" src/main.py
```

Resultado:

```text
dist/RallyTimeTracker.exe
```

Durante el build, los recursos quedan bajo `assets/images` dentro de `_MEIPASS`. `RallyApp._resource_path()` resuelve esa ubicación al ejecutar el binario.

El archivo `RallyTimeTracker.spec` que puede existir localmente está ignorado por `.gitignore`, usa rutas de recursos diferentes y menciona una plantilla de base. No es la fuente de verdad del build automatizado; se debe regenerar o corregir antes de adoptarlo.

## 6. Flujo automatizado de release

`.github/workflows/release.yml` se ejecuta en cada push a `main`, salvo si el actor es `github-actions[bot]`:

```text
checkout completo
  -> Python 3.12
  -> instalar dependencias de requirements.txt
  -> release.py
  -> instalar PyInstaller (si hay release)
  -> compilar EXE
  -> commit de CHANGELOG + tag + push
  -> GitHub Release con el EXE
```

El script pretende aplicar SemVer según Conventional Commits:

| Prioridad | Commit | Incremento pretendido |
| --- | --- | --- |
| 1 | `BREAKING CHANGE` o `tipo!:` | major |
| 2 | `feat:` o `feat(ámbito):` | minor |
| 3 | cualquier otro commit | patch |

Después antepone una sección a `CHANGELOG.md`, genera `release_notes.md` y escribe `version`, `release_notes` y `release` en `GITHUB_OUTPUT`.

### Validación del versionado

Antes de preparar una release, el workflow ejecuta los tres módulos de pruebas. La publicación se detiene si falla la funcionalidad o cualquiera de estos comportamientos de release:

- lectura estricta de tags `vX.Y.Z`;
- descarte de tags que empiezan por `v` pero no son SemVer válido;
- `feat:` y `feat(ámbito):` como incremento minor;
- `tipo!:` y `tipo(ámbito)!:` como incremento major;
- footers `BREAKING CHANGE:` y `BREAKING-CHANGE:` como incremento major;
- prioridad de major sobre minor y patch;
- incremento correcto de cada componente SemVer.

Un tipo de incremento desconocido provoca un error explícito en lugar de convertirse silenciosamente en patch.

## 7. CHANGELOG y commits

El `CHANGELOG.md` conserva secciones repetidas generadas por versiones anteriores del script. Aunque el cálculo actual está cubierto por pruebas, conviene limpiar este histórico en un cambio separado. Para cada publicación:

- revisa la versión esperada antes de hacer merge a `main`;
- usa asuntos Conventional Commits coherentes;
- evita editar o etiquetar automáticamente desde una prueba local;
- limpia el changelog en un cambio separado y revisable.

Ejemplos:

```text
feat: añadir exportación CSV
fix: conservar huecos en los tramos
docs: ampliar manual de usuario
feat!: cambiar el formato de almacenamiento
```

## 8. Guía para modificar cada área

### Nuevo caso de uso

1. Añade o ajusta las operaciones atómicas en `persistencia.py`.
2. Expón validación y mensajes desde `RallyService`.
3. Conecta la acción en `RallyApp`.
4. Si la CLI sigue soportada, decide explícitamente si debe incorporar el cambio.
5. Añade pruebas de servicio con una base temporal.

### Cambio de esquema

El esquema se administra en `database_schema.py` mediante `PRAGMA user_version`. Cualquier cambio futuro debe incrementar la versión, crear una copia previa, migrar dentro de una transacción y añadir una prueba desde cada versión soportada.

### Cambio visual

Los estilos ttk se centralizan en `apply_theme`. Los widgets `tk.Text` se registran aparte porque no heredan estilos ttk. Conserva funcionamiento en ambos temas y revisa tamaños a 900 × 600.

## 9. Archivos generados y control de versiones

`.gitignore` excluye:

- `build/` y `dist/`;
- `*.spec` y `*.exe`;
- `__pycache__/` y bytecode;
- `data/` y cualquier `*.db`.

Hay archivos `__pycache__` históricos ya versionados; ignorarlos no los elimina del índice. Conviene retirarlos del repositorio en un cambio de mantenimiento sin borrar los archivos fuente.

## 10. Lista de comprobación antes de publicar

- Confirmar que el workflow `Tests` está en verde y ejecutar localmente la suite completa.
- Completar el smoke test de la GUI sobre una base descartable.
- Confirmar ruta e iconos del ejecutable.
- Verificar la lectura/escritura en `%LOCALAPPDATA%`.
- Validar el tag esperado contra los tags existentes.
- Revisar la nueva sección de `CHANGELOG.md`.
- Probar el EXE en una máquina Windows limpia.
- Hacer una copia de una base real y comprobar compatibilidad.
- Validar manualmente la migración v2 a v3 y la clasificación de un campeonato representativo.
- Verificar que no se incluyan bases, participantes ni artefactos locales en Git.
