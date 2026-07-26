# Estado y limitaciones conocidas

## 1. Alcance de la revisión

La revisión cubre todos los archivos fuente Python, la GUI, la CLI heredada, el esquema y las dos bases locales presentes, los recursos, `.gitignore`, el script de release, el workflow de GitHub Actions, el changelog y el empaquetado local.

Comprobaciones realizadas el 26 de julio de 2026:

- sintaxis correcta en los ocho archivos Python de fuente y automatización;
- esquema leído en modo solo lectura;
- flujo aislado sobre una base temporal: crear, añadir, sobrescribir, clasificar, rellenar abandonos, penalizar y validar entradas límite;
- funciones de cálculo SemVer probadas directamente y cubiertas por pruebas unitarias;
- revisión de tags, historial y archivos versionados;
- no se abrió ni modificó la base de trabajo real.

Existe una suite de 51 pruebas para versionado y publicación, reglas de entrada, persistencia, clasificación completa, abandonos, penalizaciones y lógica de tabla sin interfaz gráfica. La ventana no se sometió a una prueba gráfica automatizada y el ejecutable local no se reconstruyó durante esta revisión.

## 2. Funciones confirmadas

| Área | Estado observado |
| --- | --- |
| Creación de competición válida | Funciona |
| Rechazo de nombre vacío o repetido | Funciona desde el servicio |
| Alta y sustitución de tiempo | Funciona |
| Validación de tiempo `m:ss.xxx` | Cubierta por pruebas unitarias |
| Rango de etapas y pertenencia de participantes | Validado en servicio y persistencia |
| Rechazo de participantes duplicados | Validado sin distinguir mayúsculas/minúsculas |
| Cálculo de total con filas existentes | Cubierto para clasificaciones completas |
| Relleno con peor tiempo + 10 s | Cubierto, incluidos repetición y overflow |
| Penalización positiva y acumulativa | Cubierta por participante y etapa |
| Borrado de datos asociados y limpieza de la vista | Cubierto mediante borrado manual y prueba de regresión de la GUI |
| Persistencia entre sesiones | Cubierta sobre SQLite temporal |
| Selección de primera etapa incompleta | Cubierta por conteo de filas |
| SemVer, changelog y Conventional Commits | Cubiertos por pruebas unitarias |
| CI antes del merge | Configurada para ramas y pull requests |
| Build automatizado de Windows | Configurado, no reconstruido en esta revisión |

## 3. Problemas de prioridad alta

### Clasificación incorrecta mientras faltan tiempos

El total solo suma filas existentes. Un participante sin registros obtiene total `0` y ocupa la primera posición. Esto también hace incorrectas las diferencias con el líder.

Impacto: una clasificación parcial puede comunicar un orden falso durante una carrera.

### Desplazamiento de tiempos entre columnas

`get_times` devuelve únicamente valores ordenados, sin el número de etapa. Si un piloto tiene tiempo en la etapa 2 pero no en la 1, la capa de servicio coloca ese único valor en la columna del tramo 1.

Impacto: la tabla puede atribuir un tiempo al tramo equivocado.

## 4. Problemas de prioridad media

### Integridad débil del esquema

La clave foránea de `participants` apunta a `competiciones`, no se activan claves foráneas y faltan restricciones únicas. Servicio y persistencia impiden crear nuevos participantes duplicados, pero el esquema por sí solo aún los permite si se modifica SQLite externamente.

### Sin historial ni reversión

Corregir un tiempo sustituye el original y penalizar modifica el valor acumulado. No queda auditoría de tiempos, abandonos o sanciones.

### Ruta de desarrollo dependiente del directorio actual

La base no se resuelve respecto a los archivos fuente. Dos lanzamientos desde carpetas diferentes pueden abrir bases distintas sin que sea evidente.

### Ausencia de manejo global de errores

Errores de permisos, base bloqueada o corrupta, y excepciones SQLite no se convierten en mensajes de interfaz. Pueden cerrar la aplicación.

### Rendimiento por consultas repetidas

Construir el ranking consulta los tiempos dos veces por participante y abre una conexión nueva para cada operación. Es suficiente para listas pequeñas, pero escala mal.

## 5. Problemas de prioridad baja o mantenimiento

- La ordenación de cabeceras solo es ascendente y no muestra el criterio activo.
- La preferencia de tema no persiste.
- La penalización de abandono está fija en 10 segundos.
- CLI y GUI conservan presentación duplicada, aunque comparten validación mediante `RallyService`.
- La CLI valida los datos de dominio, pero una opción de menú no numérica aún puede cerrarla y usa `cls`, específico de Windows.
- `varchar2` funciona por afinidad flexible de SQLite, pero no es un tipo idiomático de SQLite.
- La suite no levanta una ventana ni prueba diálogos o el EXE; tampoco hay linter, formateador, type checking ni informe porcentual de cobertura.
- No hay metadatos de paquete, versión visible en la aplicación ni archivo de licencia.
- Hay bytecode histórico versionado a pesar de estar ignorado actualmente.
- El `.spec` local no coincide con el comando de build del workflow.

## 6. Precauciones de uso

Hasta corregir los problemas de clasificación:

1. completa todos los tramos de todos los participantes antes de tomar la tabla como resultado oficial;
2. introduce etapas en orden o revisa los datos fuera de la tabla si hay huecos;
3. usa siempre `m:ss.xxx`, con segundos entre `00` y `59`;
4. mantén una copia de `datos.db` antes de correcciones o borrados masivos;
5. no ejecutes dos instancias sobre la misma base;
6. ejecuta la suite completa y revisa el tag esperado antes de publicar desde `main`.

## 7. Criterio sugerido de estabilización

Una siguiente versión puede considerarse apta para operación fiable cuando:

- el modelo identifica tiempos por participante y número real de etapa;
- la clasificación distingue participantes incompletos;
- todas las entradas se validan en el servicio y se respaldan con restricciones SQLite;
- existe una migración compatible con bases actuales;
- los casos de uso aún no cubiertos tienen pruebas temporales automatizadas;
- el release sigue superando sus pruebas de tags y Conventional Commits;
- se ha probado el ejecutable contra una copia de una base real.
