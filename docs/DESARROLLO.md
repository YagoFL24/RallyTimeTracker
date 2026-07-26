# Desarrollo, empaquetado y releases

## 1. Entorno

El proyecto no tiene dependencias de ejecución fuera de la biblioteca estándar de Python. La publicación oficial configura Python 3.12 en Windows.

Comprueba el entorno:

```bash
python --version
python -c "import tkinter, sqlite3; print('Tk', tkinter.TkVersion, 'SQLite', sqlite3.sqlite_version)"
```

No hay `requirements.txt` ni `pyproject.toml`. PyInstaller solo es necesario para construir el ejecutable.

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

El repositorio no contiene actualmente archivos de test ni configuración de lint, formato, tipos o cobertura.

Control de sintaxis sin iniciar la GUI:

```bash
python -m compileall src .github/scripts
```

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
10. borrar la competición y comprobar que desaparecen todos sus datos.

Antes de automatizar casos de integración, conviene permitir inyectar la ruta de SQLite en vez de depender de `os.getcwd()`.

## 5. Construir el ejecutable

Instala PyInstaller:

```bash
python -m pip install --upgrade pip pyinstaller
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

### Limitación actual del versionado

Las expresiones regulares del script tienen barras invertidas duplicadas. Las comprobaciones realizadas sobre el código actual muestran:

- `parse_version("v1.2.3")` devuelve `(0, 0, 0)`;
- `feat: ...` sí se reconoce como minor;
- `feat(ui): ...` cae en patch;
- `feat!: ...` cae en patch;
- un cuerpo con `BREAKING CHANGE` sí se reconoce como major.

Esto puede producir versiones incorrectas, etiquetas repetidas y changelogs duplicados. Debe corregirse y probarse antes de confiar en una nueva publicación.

## 7. CHANGELOG y commits

El `CHANGELOG.md` actual contiene secciones repetidas y texto histórico generado más de una vez. Hasta estabilizar el script:

- revisa la versión calculada antes de hacer merge a `main`;
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

`CREATE TABLE IF NOT EXISTS` no migra tablas existentes. Cualquier cambio de columnas, restricciones o claves necesita una estrategia de migración versionada y copia previa. No basta con editar `_initialize_schema`.

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

- Ejecutar pruebas automatizadas cuando existan.
- Completar el smoke test de la GUI sobre una base descartable.
- Confirmar ruta e iconos del ejecutable.
- Verificar la lectura/escritura en `%LOCALAPPDATA%`.
- Validar versión SemVer y tag contra los tags existentes.
- Revisar la nueva sección de `CHANGELOG.md`.
- Probar el EXE en una máquina Windows limpia.
- Hacer una copia de una base real y comprobar compatibilidad.
- Verificar que no se incluyan bases, participantes ni artefactos locales en Git.

