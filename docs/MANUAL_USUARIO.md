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
3. escribe el tiempo como `m:ss.xxx` o con el formato rápido sin dos puntos;
4. pulsa **Guardar**.

Ejemplos habituales:

| Entrada | Significado |
| --- | --- |
| `0:42.315` | 42 segundos y 315 milisegundos |
| `1:05.000` | 1 minuto y 5 segundos |
| `12:34.987` | 12 minutos, 34 segundos y 987 milisegundos |
| `234.345` | Se normaliza como `2:34.345` |
| `234.3` | Se normaliza como `2:34.300` |
| `34.5` | Se normaliza como `0:34.500` |

Si ya existe un registro para ese participante y etapa, el nuevo valor sustituye al anterior. No hay historial ni botón para deshacer la corrección.

Después de guardar, la tabla se vuelve a cargar y el campo conserva el tiempo normalizado, seleccionado por completo para sustituirlo directamente al empezar a escribir. La aplicación selecciona el siguiente piloto activo pendiente del mismo tramo. Si ya no queda ninguno, avanza al primer pendiente del tramo actual siguiente. Los retirados y descalificados no forman parte de este recorrido.

La etapa sugerida al seleccionar una competición es la primera que tiene menos registros que participantes. Si todas están completas, se propone la última.

### Validación del formato y las referencias

Se aceptan dos formas de introducir el tiempo:

- formato tradicional `m:ss.xxx`, por ejemplo `2:34.345`;
- formato rápido sin dos puntos, por ejemplo `234.345`, donde los dos últimos dígitos antes del punto son los segundos y los anteriores son los minutos.

En ambos formatos:

- el punto es obligatorio;
- los segundos deben estar entre `00` y `59`;
- se admiten entre cero y tres dígitos después del punto;
- los decimales omitidos se completan con ceros por la derecha: `.3` pasa a `.300`, `.34` a `.340` y `.` a `.000`;
- más de tres decimales y la coma se rechazan;
- duración total mayor que cero.

Por ejemplo, `1:05.25` y `105.25` son válidos y ambos se muestran como `1:05.250`. En cambio, `1:5.250`, `260.5`, `234`, `234.3456` y `0:00.000` se rechazan. La aplicación también comprueba que la etapa sea un entero dentro del rango de la competición y que el participante pertenezca a ella.

El campo se normaliza automáticamente medio segundo después de la última tecla. Los ceros añadidos quedan seleccionados: si escribes `234.3`, verás `2:34.300` con los dos últimos ceros seleccionados, por lo que puedes continuar con `4` o `45` para obtener `.340` o `.345`. Al escribir solo `234.`, se seleccionan los tres ceros añadidos.

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
- **Descalificado**: queda fuera de las posiciones, pero permanece visible al final y sus datos se conservan.

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
- **Tramos ganados**: cantidad de etapas en las que el piloto registró el mejor tiempo válido;
- **General**: suma de los registros recuperados para el participante;
- **Dif.**: diferencia respecto al primer clasificado.

Los tiempos se almacenan en milisegundos y se muestran como `m:ss.xxx`. Un tramo sin ningún tiempo todavía se muestra como `-`; cuando el tramo ya ha comenzado, los pilotos activos sin resultado muestran `Pendiente`. La tabla usa además `NF`, `NP` y `DSQ` para los estados explícitos.

Solo cuentan como victorias los resultados **Finalizado**. Si varios pilotos empatan con el mejor tiempo, todos suman una victoria. Los retirados conservan las logradas antes de abandonar y los descalificados muestran cero; al descalificar al ganador, la victoria pasa automáticamente al siguiente mejor tiempo válido.

Puedes pulsar cualquier cabecera para ordenar la vista en sentido ascendente. La ordenación no alterna entre ascendente y descendente. Ordenar la vista tampoco recalcula el número de posición: **Pos** sigue representando el ranking general original.

La clasificación coloca primero a todos los pilotos que continúan activos, después a los retirados y finalmente a los descalificados. Dentro de cada grupo se prioriza el mayor número de tramos con tiempo —incluidos los `NF`— y después el menor tiempo acumulado. Así, un retirado nunca ocupa el primer puesto mientras quede algún piloto activo.

Los descalificados muestran `DSQ` en **Pos** y `-` en **Dif.**. Conservan en su columna todos los tiempos que habían registrado; los demás tramos muestran `DSQ`. Entre ellos se aplica también la ordenación por cantidad de tramos con tiempo y total acumulado.

Las diferencias provisionales se calculan entre pilotos no descalificados del mismo grupo y con el mismo número de tramos con tiempo; quien todavía no tiene ningún tiempo muestra `-`. Cada resultado permanece en la columna de su tramo aunque existan huecos anteriores.

## 10. Panel de control del tramo

Selecciona una competición y pulsa **Panel del tramo**, situado junto al encabezado de la clasificación. Se abre una ventana que puedes mantener visible mientras introduces resultados.

El panel sigue automáticamente el tramo actual, entendido como el primero que todavía tiene resultados pendientes para pilotos activos. Cuando completas ese tramo, avanza al siguiente después de refrescar los datos. Para revisar otro tramo, desmarca **Seguir tramo actual** y selecciónalo en el desplegable; **Ir al actual** recupera el seguimiento automático.

Los contadores muestran total de pilotos, pendientes activos, finalizados, NF, NP, DSQ y resultados modificados. La tabla sitúa primero los pendientes y utiliza estos avisos visuales:

- pendiente: requiere introducir un resultado;
- resultado modificado: tiene al menos una revisión y muestra su valor anterior;
- resuelto: dispone de un estado definitivo para el tramo;
- inactivo: está retirado o descalificado.

Un participante descalificado nunca aparece como pendiente en el panel. Si no había registrado tiempo en el tramo seleccionado, su resultado se muestra como **Descalificado** y aumenta el contador DSQ.

Un resultado se considera anómalo únicamente cuando ha sido modificado después de su registro inicial. Haz doble clic sobre un piloto —o usa **Cargar participante seleccionado**— para copiar piloto y tramo a los formularios principales. Un pendiente prepara el estado **Finalizado** y deja el cursor en el campo de tiempo.

El panel se actualiza después de guardar tiempos, aplicar estados, rellenar abandonos, penalizar, retirar o reactivar participantes.

## 11. Exportar, importar y guardar PDF

Los tres botones están debajo de la lista de competiciones.

### Exportar CSV o Excel

1. Selecciona una competición.
2. Pulsa **Exportar**.
3. Elige `Excel (*.xlsx)` o `CSV (*.csv)` y guarda el archivo.

La exportación incluye todos los participantes y tramos, incluso pendientes, no presentados, retirados y descalificados. También conserva tiempos anteriores y el contador de revisiones. El CSV utiliza UTF-8 y separador `;`. El Excel contiene una hoja **Datos**, que permite volver a importarlo, y una hoja **Clasificación** preparada para consulta.

### Importar

Pulsa **Importar** y selecciona un CSV o Excel creado por RallyTimeTracker. El archivo se valida por completo antes de escribir en SQLite y la importación se realiza en una sola transacción.

La importación siempre crea una competición nueva y nunca modifica la existente. Si el nombre ya está ocupado, se añade `_importada`; si también existe, se utilizan `_importada_2`, `_importada_3`, etc.

No elimines ni renombres columnas de la hoja **Datos**. Los tiempos editados manualmente deben conservar el formato `m:ss.xxx` y los estados deben usar los valores ofrecidos por la exportación.

### Clasificación PDF

Selecciona una competición y pulsa **Guardar PDF**. La aplicación solo guarda el documento; después puedes abrirlo e imprimirlo con tu lector habitual. Para mantener la legibilidad, las competiciones con muchos tramos se dividen en bloques de hasta ocho tramos por página.

## 12. Cambiar de tema

El botón situado bajo la lista de competiciones alterna los colores claro y oscuro. La preferencia vive solo durante la sesión: al reiniciar, la aplicación vuelve a iniciar en modo oscuro.

## 13. Eliminar una competición

1. Selecciona una competición.
2. Pulsa **Borrar**.
3. Confirma el diálogo.

Se eliminan permanentemente la competición, sus participantes y sus tiempos. No hay papelera ni deshacer. Haz una copia de seguridad antes de borrar información relevante.

Tras borrar, la selección, la tabla y los formularios se limpian inmediatamente.

## 14. Base de datos y copias de seguridad

Ubicaciones:

| Forma de ejecución | Archivo |
| --- | --- |
| `python src/main.py` | `<directorio desde el que se ejecuta>/data/datos.db` |
| `.exe` de PyInstaller | `%LOCALAPPDATA%\RallyTimeTracker\datos.db` |

La base y sus tablas se crean automáticamente al abrir la aplicación por primera vez. Una base v1 se migra al esquema de estados y crea antes `datos.v1.backup.db`; los tiempos existentes pasan a **Finalizado** y los huecos a **Pendiente**. Al abrir una base v2 se añaden las tablas de campeonatos y se crea previamente `datos.v2.backup.db`.

### Copias automáticas

La aplicación crea una copia consistente de SQLite:

- en cada arranque, después de abrir y validar la base;
- antes de importar una competición válida;
- antes de restaurar otra copia.
- antes de eliminar un campeonato o retirar una competición de su calendario.

Se conservan las 10 copias de arranque más recientes. Las copias manuales y preventivas no se eliminan automáticamente. Sus carpetas son:

| Forma de ejecución | Carpeta de copias |
| --- | --- |
| `python src/main.py` | `<directorio de ejecución>/data/backups` |
| `.exe` de PyInstaller | `%LOCALAPPDATA%\RallyTimeTracker\backups` |

### Crear una copia manual

1. Pulsa **Copias de seguridad** en el panel izquierdo.
2. Selecciona **Crear copia ahora**.
3. La nueva entrada aparece con el motivo **Manual**.

El listado muestra fecha, motivo, tamaño y nombre de archivo. Las copias usan la API de backup de SQLite, por lo que no es necesario cerrar la aplicación.

### Restaurar

Puedes seleccionar una copia gestionada y pulsar **Restaurar seleccionada**, hacer doble clic sobre ella o usar **Restaurar otro archivo** para elegir un `.db` externo.

Antes de sustituir los datos, la aplicación:

1. valida la integridad SQLite, la versión del esquema, las tablas y las claves foráneas;
2. solicita confirmación;
3. crea una copia **Antes de restaurar** del estado actual;
4. copia la base seleccionada a un archivo temporal validado;
5. reemplaza `datos.db` de forma atómica y refresca la interfaz.

Si el archivo está dañado o no es compatible, la base actual no se modifica. No reemplaces manualmente `datos.db` mientras la aplicación está abierta.

## 15. Atajos de teclado

Pulsa **Atajos**, junto a **Panel del tramo**, o `F1` para abrir la referencia dentro de la aplicación.

| Tecla | Acción |
| --- | --- |
| `F1` | Mostrar la ayuda de atajos |
| `F2` | Llevar el cursor al campo de tiempo y seleccionar su contenido |
| `Enter` | Guardar cuando el cursor está en el campo de tiempo |
| `Ctrl+Enter` | Guardar el resultado desde cualquier control de la ventana principal |
| `Ctrl+↑` / `Ctrl+↓` | Seleccionar el piloto anterior o siguiente |
| `Ctrl+←` / `Ctrl+→` | Seleccionar el tramo anterior o siguiente |
| `Ctrl+P` | Abrir o traer al frente el panel del tramo |

La selección de pilotos y tramos es circular: al superar el último vuelve al primero, y viceversa. Después de cambiar con `Ctrl` y las flechas, el foco vuelve al campo de tiempo para continuar escribiendo sin usar el ratón.

## 16. Campeonatos

Pulsa **Campeonatos** en el panel izquierdo para abrir el gestor. Un campeonato tiene un nombre, un plantel oficial, un calendario ordenado, una tabla de puntos por posición y un bonus opcional para quien consiga más victorias de tramo en cada prueba.

### Crear y configurar

1. Pulsa **Nuevo campeonato**.
2. Escribe un nombre y añade un piloto oficial por línea. Los nombres no pueden repetirse.
3. Revisa los puntos por posición. El valor inicial es `25,18,15,12,10,8,6,4,2,1`.
4. Define el bonus por victorias de tramo. Usa `0` para desactivarlo.

Desde **Configuración** puedes cambiar posteriormente la puntuación, el bonus o marcar manualmente el campeonato como finalizado. Los cambios recalculan la clasificación sin modificar los resultados originales.

### Calendario y participantes

En la pestaña **Calendario** puedes:

- añadir una competición existente, incluso si ya pertenece a otro campeonato;
- crear una competición específica, que recibe automáticamente todos los pilotos activos del campeonato;
- indicar o corregir su fecha;
- mover una prueba hacia arriba o abajo en cualquier momento;
- retirarla del calendario sin borrar la competición.

Al vincular una competición existente debes asociar cada piloto oficial activo con uno de sus participantes. Los participantes no asociados se consideran invitados: aparecen en la competición, pero no reciben posición ni puntos del campeonato. Una asociación nueva queda guardada como alias para facilitar pruebas posteriores.

Una competición vinculada a algún campeonato no se puede borrar. Primero debes retirarla de todos sus calendarios. Borrar un campeonato no borra sus competiciones y ambas operaciones crean antes una copia preventiva de la base.

### Estados y puntuación

El calendario muestra automáticamente cada prueba como **Planificada**, **En curso** o **Finalizada** según sus resultados. Solo una prueba finalizada aporta puntos oficiales; mientras está en curso se muestra en el calendario pero aporta cero puntos.

Las reglas del campeonato son:

- los invitados se excluyen antes de calcular posiciones;
- un piloto retirado conserva su posición, sus puntos y el posible bonus;
- un no presentado o descalificado recibe cero puntos;
- un `NF` de tramo no impide puntuar en la clasificación del rally;
- si varios pilotos empatan en el rally, comparten puntos y se salta la posición siguiente;
- cada victoria de tramo cuenta también en caso de empate exacto de tiempo;
- el mayor número de victorias de tramo concede el bonus completo a todos los empatados;
- un descalificado no puede recibir el bonus; se concede al siguiente máximo válido.

La clasificación general desempata por número de victorias de rally, segundos puestos, terceros puestos y, finalmente, el mejor resultado en la prueba más reciente. Se muestran también podios, victorias de tramo, retiradas, puntos por prueba y diferencia con el líder.

### Bajas y reincorporaciones

En **Pilotos** puedes retirar un piloto desde una prueba concreta. Conserva todos sus puntos anteriores y recibe cero en las pruebas que no dispute. Puede reincorporarse desde otra prueba si figura —por nombre o alias— entre los participantes de esa competición. No se modifican ni eliminan sus resultados previos.

### Exportar

El gestor permite guardar la clasificación del campeonato en CSV, Excel o PDF. El Excel incluye hojas separadas para clasificación, calendario y tabla de puntuación. El PDF está preparado para imprimir. La aplicación no importa campeonatos completos; la importación disponible continúa siendo la de una competición individual.

## 17. CLI heredada

La interfaz de consola usa la misma base y las mismas funciones de persistencia:

```bash
python src/cli_main.py
```

Permite listar, crear y borrar competiciones, ver datos, añadir tiempos, rellenar abandonos y penalizar. Comparte con la GUI las validaciones de competiciones, etapas, participantes, tiempos y penalizaciones. Está orientada a Windows porque limpia la pantalla con `cls`; una opción de menú no numérica todavía puede cerrar el programa con un error. Para operación normal se recomienda la interfaz gráfica.

## 18. Mensajes frecuentes

| Mensaje | Acción recomendada |
| --- | --- |
| `Seleccione una competicion.` | Elige una entrada en el panel izquierdo. |
| `Formato de tiempo invalido` | Usa `1:05.240` o el formato rápido `105.24`; incluye siempre el punto. |
| `No hay tiempos base para esa etapa.` | Registra al menos un tiempo antes de rellenar abandonos. |
| `No existe tiempo para ese participante/etapa.` | Guarda primero el tiempo del participante en ese tramo. |
| `Ya existe una competicion con ese nombre.` | Usa un nombre distinto o elimina la competición anterior. |

