# Estado y limitaciones conocidas

## 1. Estado verificado

Comprobaciones realizadas durante el desarrollo de la v1.3.0:

- suite de 110 pruebas unitarias y funcionales;
- bases SQLite temporales para todos los flujos de escritura;
- migración v1 a v2 con backup y conservación de tiempos;
- migración v2 a v3 con backup y conservación de las competiciones;
- estados explícitos por participante y tramo;
- retirada y reactivación de participantes;
- clasificación completa, incompleta y con retirados;
- campeonatos con calendario, plantel, alias, invitados, bajas y puntuación configurable;
- exportación de campeonatos a CSV, Excel y PDF;
- validación de tiempos, etapas, participantes y penalizaciones;
- SemVer, changelog y publicación automatizada.

La ventana no se ha sometido a automatización gráfica real y el ejecutable todavía no se ha reconstruido para este bloque.

## 2. Funciones confirmadas

| Área | Estado observado |
| --- | --- |
| Alta y borrado de competiciones | Cubiertos con transacciones y cascadas |
| Entrada de tiempo | Formato `m:ss.xxx` o compacto, punto obligatorio y milisegundos autocompletados |
| Estados de tramo | Pendiente, finalizado, no finalizado, no presentado y descalificado |
| No finalizado | Aplica peor tiempo + 10 s y mantiene al piloto activo |
| Retirada del rally | Conserva resultados, bloquea tramos posteriores y permite reactivar |
| Descalificación | Sin posición ni diferencia; visible al final, conserva tiempos y puede revertirse |
| Clasificación | Mantiene la columna real del tramo y separa categorías |
| Victorias de tramo | Recuento visible por participante, con empates, retiradas y DSQ cubiertos |
| Intercambio | Exportación e importación CSV/Excel versionada, validada y transaccional |
| PDF | Clasificación A4 horizontal paginada por bloques de tramos |
| Panel de tramo | Seguimiento automático, contadores, pendientes y resultados modificados |
| Copias de seguridad | Arranque, preimportación, prerrestauración, copia manual y restauración validada |
| Atajos de teclado | Ayuda integrada, guardado, navegación circular y avance automático entre pendientes |
| Campeonatos | Plantel oficial, alias, invitados, calendario ordenado y competiciones compartidas |
| Puntuación de campeonato | Posiciones configurables, empates, bonus de tramos, bajas y desempate general |
| Exportación de campeonato | Clasificación CSV, libro Excel de tres hojas y PDF imprimible |
| Modificación de resultado | Conserva valor anterior, revisión y fecha de actualización |
| Migración | Convierte v1 a estados y amplía v2 con el modelo de campeonatos |
| Integridad SQLite | Claves foráneas, unicidad, checks, índices y triggers activos |
| CI | Suite y sintaxis ejecutadas en ramas y pull requests |

## 3. Problemas de prioridad media

### Sin historial completo

Solo se conserva el valor inmediatamente anterior y un contador. Todavía no existe un registro independiente de cada corrección, sanción, usuario o motivo.

### Ruta de desarrollo dependiente del directorio actual

Dos lanzamientos desde carpetas diferentes pueden abrir bases distintas porque la ruta de desarrollo depende de `os.getcwd()`.

### Ausencia de manejo global de errores

Algunos errores de permisos, bloqueo o corrupción SQLite todavía pueden cerrar la aplicación en lugar de mostrarse de forma controlada.

## 4. Problemas de prioridad baja o mantenimiento

- La ordenación de cabeceras solo es ascendente y no muestra el criterio activo.
- La preferencia de tema no persiste.
- La penalización de tramo no finalizado está fija en 10 segundos.
- La CLI heredada no expone todavía los nuevos controles de estados y retirada.
- La CLI heredada tampoco permite gestionar campeonatos.
- Los campeonatos se pueden exportar, pero no importar como una unidad completa.
- La CLI puede cerrarse con una opción de menú no numérica y usa `cls`, específico de Windows.
- La suite no levanta una ventana ni prueba diálogos o el EXE.
- No hay linter, formateador, type checking ni informe porcentual de cobertura.
- No hay metadatos de paquete, versión visible en la aplicación ni archivo de licencia.
- Hay bytecode histórico versionado a pesar de estar ignorado actualmente.

## 5. Precauciones de uso

1. Usa `m:ss.xxx` o el formato compacto sin dos puntos; incluye el punto y mantén los segundos entre `00` y `59`.
2. Conserva el backup v1 o v2 hasta validar manualmente la migración.
3. No ejecutes dos instancias sobre la misma base.
4. Ejecuta la suite completa antes de integrar `feat/campeonatos` en `main`.

## 6. Criterio para completar la v1.3.0

- validar conjuntamente calendario, asignación de pilotos, puntuación, bajas y exportación;
- comprobar una migración v2 real conservando su copia preventiva;
- probar la GUI y el ejecutable sobre una copia de una base real;
- fusionar `feat/campeonatos` directamente en `main` con un commit `feat:` para publicar `v1.3.0`.
