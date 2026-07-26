
## Cambios prioritarios que propondría

| Prioridad | Cambio                                                  | Motivo                                                                                                        | Esfuerzo |
| --------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------- |
| Crítica  | Corregir clasificación y columnas de tramos            | Ahora un piloto sin tiempos puede aparecer primero y un tiempo de la etapa 2 puede mostrarse como etapa 1     | Medio    |
| Crítica  | Validación estricta de tiempos, etapas y participantes | Actualmente se aceptan etapas fuera de rango y tiempos como`1:75.000`                                       | Bajo     |
| Crítica  | Corregir el versionado automático                      | El script interpreta mal tags,`feat(scope):`y`feat!:`; puede generar versiones o tags incorrectos         | Bajo     |
| Alta      | Migrar y reforzar SQLite                                | Faltan restricciones únicas, claves fiables y existe una FK que apunta a`competiciones`, tabla inexistente | Medio    |
| Alta      | Añadir pruebas automatizadas                           | Protegería clasificación, abandonos, penalizaciones, migraciones y releases                                 | Medio    |
| Alta      | Historial de modificaciones y deshacer                  | Hoy una corrección o penalización destruye el valor anterior                                                | Medio    |
| Media     | Corregir el estado después de borrar                   | La competición eliminada puede seguir visible hasta refrescar otra vez                                       | Bajo     |
| Media     | Centralizar la ruta de datos                            | Ejecutar desde carpetas diferentes puede abrir bases distintas                                                | Bajo     |

## Funcionalidades nuevas recomendadas

1. Exportación e importación CSV/Excel, además de una clasificación imprimible o PDF. Es probablemente la mejora con mejor relación utilidad/esfuerzo.
2. Estados explícitos por participante y tramo: pendiente, finalizado, abandono, no presentado o descalificado. Evitaría representar todos esos casos mediante un tiempo artificial.
3. Penalizaciones como registros independientes, con motivo, fecha, cantidad y posibilidad de anularlas.
4. Dorsal, vehículo, copiloto y categoría. Permitiría clasificación general y por clase.
5. Panel de control del tramo actual, resaltando pilotos pendientes y entradas anómalas. Sería especialmente útil durante una carrera.
6. Copias de seguridad automáticas y restauración desde la aplicación.
7. Importación rápida desde cronómetros o archivos de otros sistemas, además de atajos de teclado para introducir resultados.
8. Vista pública de resultados en navegador, inicialmente de solo lectura y en la red local.
9. Empates y reglas configurables: penalización de abandono, criterios de desempate y cierre de etapas.
10. Versión visible, actualización automática y sistema de migraciones para conservar bases creadas con versiones anteriores.

Para convertir esto en un roadmap preciso necesito saber tres cosas:

1. ¿La aplicación se utilizará para resultados oficiales en directo o principalmente para competiciones pequeñas/uso personal?
2. ¿El objetivo seguirá siendo exclusivamente Windows?
3. ¿Trabajará una sola persona con un ordenador o necesitas varios operadores y una clasificación pública en tiempo real?
