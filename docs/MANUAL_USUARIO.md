# Manual de usuario

## 1. Propósito

Rally Time Tracker permite llevar el control local de varias competiciones, sus participantes y los tiempos obtenidos en cada tramo. Está orientado a una persona que introduce resultados durante o después de una prueba.

La aplicación no necesita cuentas, servidor ni Internet. Todos los cambios se guardan inmediatamente en SQLite.

## 2. Abrir la aplicación

En desarrollo, desde la raíz del proyecto:

```bash
python src/main.py
```

En una distribución de Windows, abre `RallyTimeTracker.exe`.

La ventana arranca a 1100 × 650 píxeles, admite redimensionado y tiene un tamaño mínimo de 900 × 600. La interfaz principal se divide en:

- panel izquierdo con la lista de competiciones;
- tabla central de clasificación y tiempos;
- formularios inferiores para tiempos, abandonos y penalizaciones;
- barra inferior de estado, que comunica éxito o aviso.

## 3. Crear una competición

1. Pulsa **Nueva**.
2. Escribe un nombre no vacío y que no exista ya.
3. Introduce un número entero de etapas mayor que cero.
4. Introduce al menos un participante.
5. Pulsa **Crear**.

Los participantes se pueden escribir de dos formas:

- uno por línea, que es la opción recomendada;
- todos en una única línea, separados por comas.

Las líneas vacías introducidas en el cuadro se omiten y los espacios al principio o al final se eliminan. Los nombres de participantes no pueden estar vacíos, superar 255 caracteres ni repetirse, incluso si solo cambia el uso de mayúsculas y minúsculas.

Cuando la operación termina correctamente, la competición queda seleccionada y se muestra su tabla.

## 4. Seleccionar y refrescar

Selecciona una competición en la lista izquierda para cargar:

- su nombre y número de etapas;
- los participantes;
- los tiempos registrados;
- el total y la diferencia de cada participante;
- la etapa sugerida para el siguiente tiempo.

**Refrescar** vuelve a consultar la base de datos. Resulta útil si el archivo SQLite ha cambiado fuera de la ventana actual, aunque no se recomienda editar la base manualmente mientras la aplicación está abierta.

## 5. Registrar o corregir un tiempo

En **Agregar tiempo**:

1. selecciona el participante;
2. selecciona la etapa;
3. escribe el tiempo con el formato `m:ss.xxx`;
4. pulsa **Guardar**.

Ejemplos habituales:

| Entrada | Significado |
| --- | --- |
| `0:42.315` | 42 segundos y 315 milisegundos |
| `1:05.000` | 1 minuto y 5 segundos |
| `12:34.987` | 12 minutos, 34 segundos y 987 milisegundos |

Si ya existe un registro para ese participante y etapa, el nuevo valor sustituye al anterior. No hay historial ni botón para deshacer la corrección.

Después de guardar, la tabla se vuelve a cargar, el campo de tiempo se vacía y la etapa elegida se conserva.

La etapa sugerida al seleccionar una competición es la primera que tiene menos registros que participantes. Si todas están completas, se propone la última.

### Validación del formato y las referencias

El tiempo debe cumplir exactamente `m:ss.xxx`:

- uno o más dígitos para los minutos;
- dos dígitos de segundos entre `00` y `59`;
- exactamente tres dígitos de milisegundos;
- duración total mayor que cero.

Por ejemplo, `1:05.250` es válido; `1:5.250`, `1:75.000`, `1:05.25` y `0:00.000` se rechazan. La aplicación también comprueba que la etapa sea un entero dentro del rango de la competición y que el participante pertenezca a ella.

## 6. Rellenar abandonos

Esta operación marca como **No finalizado** a todos los participantes activos que siguen pendientes en una etapa. No los retira del rally: pueden continuar en los tramos posteriores.

1. Debe existir al menos un tiempo en el tramo elegido.
2. Selecciona la etapa en **Rellenar abandonos**.
3. Pulsa **Rellenar**.

Regla aplicada:

```text
tiempo de abandono = peor tiempo ya registrado en el tramo + 10 segundos
```

Todos los participantes ausentes reciben el mismo valor. Si la etapa no tiene ningún tiempo base, no se modifica nada y aparece el aviso «No hay tiempos base para esa etapa».

La penalización fija de 10 segundos no es configurable en la versión actual. El estado queda registrado explícitamente y se muestra como `NF` junto al tiempo asignado.

## 7. Estados y abandono del rally

En **Estado del participante y tramo** puedes seleccionar participante, tramo y uno de estos estados:

- **Pendiente**: todavía no existe un resultado definitivo;
- **Finalizado**: exige un tiempo `m:ss.xxx`;
- **No finalizado**: recibe el peor tiempo del tramo más 10 segundos y continúa en el rally;
- **No presentado**: no tiene tiempo en ese tramo, pero puede participar en los siguientes;
- **Descalificado**: queda fuera de la clasificación, aunque sus datos se conservan.

**Retirar** es una operación distinta. Permite indicar que el piloto abandona definitivamente después de finalizar el tramo o durante él. En el segundo caso se registra primero el tramo como no finalizado. Sus tiempos anteriores se conservan y aparece después de todos los pilotos que continúan activos. **Reactivar** permite devolverlo al rally y editar después sus estados.

## 8. Aplicar una penalización

En **Penalizar**:

1. selecciona participante y etapa;
2. escribe una cantidad positiva de segundos; admite decimales;
3. pulsa **Aplicar**.

La aplicación convierte los segundos a milisegundos y los suma al tiempo existente. La operación es acumulativa: si se aplica dos veces, se suman las dos sanciones.

No es posible penalizar una combinación participante/etapa que aún no tenga tiempo. Tampoco existe una operación específica para retirar una sanción; habría que volver a guardar manualmente el tiempo correcto.

## 9. Clasificación

La tabla contiene:

- **Pos**: posición calculada por el tiempo total;
- **Piloto**: nombre del participante;
- **Estado**: clasificado, retirado, pendiente o no presentado;
- **Tramo N**: tiempo mostrado para cada etapa;
- **General**: suma de los registros recuperados para el participante;
- **Dif.**: diferencia respecto al primer clasificado.

Los tiempos se almacenan en milisegundos y se muestran como `m:ss.xxx`. Un tramo sin ningún tiempo todavía se muestra como `-`; cuando el tramo ya ha comenzado, los pilotos activos sin resultado muestran `Pendiente`. La tabla usa además `NF`, `NP` y `DSQ` para los estados explícitos.

Puedes pulsar cualquier cabecera para ordenar la vista en sentido ascendente. La ordenación no alterna entre ascendente y descendente. Ordenar la vista tampoco recalcula el número de posición: **Pos** sigue representando el ranking general original.

La clasificación coloca primero a todos los pilotos que continúan activos y después a los retirados; los descalificados no aparecen. Dentro de cada grupo se prioriza el mayor número de tramos completados y después el menor tiempo acumulado. Así, un retirado nunca ocupa el primer puesto mientras quede algún piloto activo. Las diferencias provisionales se calculan entre pilotos del mismo grupo y con el mismo número de tramos con tiempo; quien todavía no tiene ningún tiempo muestra `-`. Cada resultado permanece en la columna de su tramo aunque existan huecos anteriores.

## 10. Cambiar de tema

El botón situado bajo la lista de competiciones alterna los colores claro y oscuro. La preferencia vive solo durante la sesión: al reiniciar, la aplicación vuelve a iniciar en modo oscuro.

## 11. Eliminar una competición

1. Selecciona una competición.
2. Pulsa **Borrar**.
3. Confirma el diálogo.

Se eliminan permanentemente la competición, sus participantes y sus tiempos. No hay papelera ni deshacer. Haz una copia de seguridad antes de borrar información relevante.

Tras borrar, la selección, la tabla y los formularios se limpian inmediatamente.

## 12. Base de datos y copias de seguridad

Ubicaciones:

| Forma de ejecución | Archivo |
| --- | --- |
| `python src/main.py` | `<directorio desde el que se ejecuta>/data/datos.db` |
| `.exe` de PyInstaller | `%LOCALAPPDATA%\RallyTimeTracker\datos.db` |

La base y sus tablas se crean automáticamente al abrir la aplicación por primera vez. Una base anterior se migra al esquema de estados y crea antes `datos.v1.backup.db`; los tiempos existentes pasan a **Finalizado** y los huecos a **Pendiente**.

Para copiar o restaurar:

1. cierra todas las ventanas de Rally Time Tracker;
2. copia `datos.db` a una ubicación segura o sustituye el archivo por una copia anterior;
3. vuelve a abrir la aplicación y comprueba una competición.

No sustituyas la base mientras la aplicación realiza una operación.

## 13. CLI heredada

La interfaz de consola usa la misma base y las mismas funciones de persistencia:

```bash
python src/cli_main.py
```

Permite listar, crear y borrar competiciones, ver datos, añadir tiempos, rellenar abandonos y penalizar. Comparte con la GUI las validaciones de competiciones, etapas, participantes, tiempos y penalizaciones. Está orientada a Windows porque limpia la pantalla con `cls`; una opción de menú no numérica todavía puede cerrar el programa con un error. Para operación normal se recomienda la interfaz gráfica.

## 14. Mensajes frecuentes

| Mensaje | Acción recomendada |
| --- | --- |
| `Seleccione una competicion.` | Elige una entrada en el panel izquierdo. |
| `Formato de tiempo invalido. Use m:ss.xxx` | Usa dos partes separadas por `:`, por ejemplo `1:05.240`. |
| `No hay tiempos base para esa etapa.` | Registra al menos un tiempo antes de rellenar abandonos. |
| `No existe tiempo para ese participante/etapa.` | Guarda primero el tiempo del participante en ese tramo. |
| `Ya existe una competicion con ese nombre.` | Usa un nombre distinto o elimina la competición anterior. |

