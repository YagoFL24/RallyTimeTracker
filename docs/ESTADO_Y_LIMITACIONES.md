# Estado y limitaciones conocidas

## 1. Estado verificado

Comprobaciones realizadas durante el desarrollo de la v1.2.0:

- suite de 82 pruebas unitarias y funcionales;
- bases SQLite temporales para todos los flujos de escritura;
- migración v1 a v2 con backup y conservación de tiempos;
- estados explícitos por participante y tramo;
- retirada y reactivación de participantes;
- clasificación completa, incompleta y con retirados;
- validación de tiempos, etapas, participantes y penalizaciones;
- SemVer, changelog y publicación automatizada.

La ventana no se ha sometido a automatización gráfica real y el ejecutable todavía no se ha reconstruido para este bloque.

## 2. Funciones confirmadas

| Área | Estado observado |
| --- | --- |
| Alta y borrado de competiciones | Cubiertos con transacciones y cascadas |
| Tiempo `m:ss.xxx` | Validado en servicio y persistencia |
| Estados de tramo | Pendiente, finalizado, no finalizado, no presentado y descalificado |
| No finalizado | Aplica peor tiempo + 10 s y mantiene al piloto activo |
| Retirada del rally | Conserva resultados, bloquea tramos posteriores y permite reactivar |
| Descalificación | Sin posición ni diferencia; visible al final, conserva tiempos y puede revertirse |
| Clasificación | Mantiene la columna real del tramo y separa categorías |
| Intercambio | Exportación e importación CSV/Excel versionada, validada y transaccional |
| PDF | Clasificación A4 horizontal paginada por bloques de tramos |
| Panel de tramo | Seguimiento automático, contadores, pendientes y resultados modificados |
| Copias de seguridad | Arranque, preimportación, prerrestauración, copia manual y restauración validada |
| Modificación de resultado | Conserva valor anterior, revisión y fecha de actualización |
| Migración | Convierte tiempos a finalizados y huecos a pendientes |
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
- La CLI puede cerrarse con una opción de menú no numérica y usa `cls`, específico de Windows.
- La suite no levanta una ventana ni prueba diálogos o el EXE.
- No hay linter, formateador, type checking ni informe porcentual de cobertura.
- No hay metadatos de paquete, versión visible en la aplicación ni archivo de licencia.
- Hay bytecode histórico versionado a pesar de estar ignorado actualmente.

## 5. Precauciones de uso

1. Usa siempre `m:ss.xxx`, con segundos entre `00` y `59`.
2. Conserva el backup v1 hasta validar manualmente la migración.
3. No ejecutes dos instancias sobre la misma base.
4. Ejecuta la suite completa antes de integrar una funcionalidad en `feat/v1.2.0`.

## 6. Criterio para completar la v1.2.0

- validar cada rama funcional antes de fusionarla en `feat/v1.2.0`;
- completar los atajos de teclado;
- probar la GUI y el ejecutable sobre una copia de una base real;
- fusionar en `main` una sola vez para publicar `v1.2.0`.
