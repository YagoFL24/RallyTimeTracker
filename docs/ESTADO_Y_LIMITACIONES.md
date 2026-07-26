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

Existe una suite automatizada para el versionado. La funcionalidad de la aplicación aún no tiene tests automatizados, la ventana no se sometió a una prueba gráfica automatizada y el ejecutable local no se reconstruyó durante esta revisión.

## 2. Funciones confirmadas

| Área | Estado observado |
| --- | --- |
| Creación de competición válida | Funciona |
| Rechazo de nombre vacío o repetido | Funciona desde el servicio |
| Alta y sustitución de tiempo | Funciona |
| Cálculo de total con filas existentes | Funciona |
| Relleno con peor tiempo + 10 s | Funciona con al menos un tiempo base |
| Penalización positiva y acumulativa | Funciona sobre un tiempo existente |
| Borrado de datos asociados | Funciona mediante borrado manual |
| Persistencia entre sesiones | Soportada por SQLite local |
| Selección de primera etapa incompleta | Funciona por conteo de filas |
| SemVer y Conventional Commits | Cubierto por pruebas unitarias |
| Build automatizado de Windows | Configurado, no reconstruido en esta revisión |

## 3. Problemas de prioridad alta

### Clasificación incorrecta mientras faltan tiempos

El total solo suma filas existentes. Un participante sin registros obtiene total `0` y ocupa la primera posición. Esto también hace incorrectas las diferencias con el líder.

Impacto: una clasificación parcial puede comunicar un orden falso durante una carrera.

### Desplazamiento de tiempos entre columnas

`get_times` devuelve únicamente valores ordenados, sin el número de etapa. Si un piloto tiene tiempo en la etapa 2 pero no en la 1, la capa de servicio coloca ese único valor en la columna del tramo 1.

Impacto: la tabla puede atribuir un tiempo al tramo equivocado.

### Validación insuficiente de tiempos y referencias

La API acepta etapas fuera del rango de la competición y el parser admite valores como `1:75.000`. Persistencia tampoco verifica que el texto del participante pertenezca a la competición.

Impacto: datos válidos para SQLite pero inválidos para el dominio, con posibles resultados o errores de renderizado incoherentes.

## 4. Problemas de prioridad media

### Integridad débil del esquema

La clave foránea de `participants` apunta a `competiciones`, no se activan claves foráneas y faltan restricciones únicas. Los participantes duplicados son aceptados.

### Borrado visualmente obsoleto

Después de borrar la competición seleccionada, `refresh_competitions` intenta reseleccionar el nombre ya inexistente y puede conservar la tabla y `current_competition` en memoria. Un segundo refresco limpia la vista.

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
- CLI y GUI duplican flujos, pero no comparten toda la validación.
- La CLI no captura entradas inválidas y usa `cls`, específico de Windows.
- La creación de competición no es una única transacción atómica.
- `varchar2` funciona por afinidad flexible de SQLite, pero no es un tipo idiomático de SQLite.
- Solo el versionado tiene tests; no hay tests de aplicación, linter, formateador, type checking ni cobertura configurados.
- No hay metadatos de paquete, versión visible en la aplicación ni archivo de licencia.
- Hay bytecode histórico versionado a pesar de estar ignorado actualmente.
- El `.spec` local no coincide con el comando de build del workflow.

## 6. Precauciones de uso

Hasta corregir los problemas de clasificación:

1. completa todos los tramos de todos los participantes antes de tomar la tabla como resultado oficial;
2. introduce etapas en orden o revisa los datos fuera de la tabla si hay huecos;
3. usa siempre `m:ss.xxx`, con segundos entre `00` y `59`;
4. evita participantes duplicados;
5. mantén una copia de `datos.db` antes de correcciones o borrados masivos;
6. no ejecutes dos instancias sobre la misma base;
7. ejecuta las pruebas de release y revisa el tag esperado antes de publicar desde `main`.

## 7. Criterio sugerido de estabilización

Una siguiente versión puede considerarse apta para operación fiable cuando:

- el modelo identifica tiempos por participante y número real de etapa;
- la clasificación distingue participantes incompletos;
- todas las entradas se validan en el servicio y se respaldan con restricciones SQLite;
- existe una migración compatible con bases actuales;
- los casos de uso principales tienen pruebas temporales automatizadas;
- el release sigue superando sus pruebas de tags y Conventional Commits;
- el borrado limpia inmediatamente el estado de la GUI;
- se ha probado el ejecutable contra una copia de una base real.
