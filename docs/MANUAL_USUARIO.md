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

Las líneas vacías y los espacios al principio o al final se eliminan. La versión actual no impide repetir un participante dentro de la misma competición; conviene revisar la lista antes de crearla.

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

### Validación actual del formato

La interfaz exige que haya texto y que pueda separarse por `:` en dos valores numéricos. El mensaje orientativo es `m:ss.xxx`, pero actualmente no se comprueba que los segundos estén entre 0 y 59, que el tiempo sea positivo o que tenga exactamente tres decimales. Para evitar datos incoherentes, usa siempre el formato de los ejemplos.

## 6. Rellenar abandonos

Esta operación asigna un tiempo a todos los participantes que aún no tienen registro en una etapa.

1. Debe existir al menos un tiempo en el tramo elegido.
2. Selecciona la etapa en **Rellenar abandonos**.
3. Pulsa **Rellenar**.

Regla aplicada:

```text
tiempo de abandono = peor tiempo ya registrado en el tramo + 10 segundos
```

Todos los participantes ausentes reciben el mismo valor. Si la etapa no tiene ningún tiempo base, no se modifica nada y aparece el aviso «No hay tiempos base para esa etapa».

La penalización fija de 10 segundos no es configurable en la versión actual. Los valores rellenados son tiempos ordinarios en la base de datos: no conservan una marca que indique que proceden de un abandono.

## 7. Aplicar una penalización

En **Penalizar**:

1. selecciona participante y etapa;
2. escribe una cantidad positiva de segundos; admite decimales;
3. pulsa **Aplicar**.

La aplicación convierte los segundos a milisegundos y los suma al tiempo existente. La operación es acumulativa: si se aplica dos veces, se suman las dos sanciones.

No es posible penalizar una combinación participante/etapa que aún no tenga tiempo. Tampoco existe una operación específica para retirar una sanción; habría que volver a guardar manualmente el tiempo correcto.

## 8. Clasificación

La tabla contiene:

- **Pos**: posición calculada por el tiempo total;
- **Piloto**: nombre del participante;
- **Tramo N**: tiempo mostrado para cada etapa;
- **General**: suma de los registros recuperados para el participante;
- **Dif.**: diferencia respecto al primer clasificado.

Los tiempos se almacenan en milisegundos y se muestran como `m:ss.xxx`. Un tramo sin dato se representa como `--:--.---`.

Puedes pulsar cualquier cabecera para ordenar la vista en sentido ascendente. La ordenación no alterna entre ascendente y descendente. Ordenar la vista tampoco recalcula el número de posición: **Pos** sigue representando el ranking general original.

### Importante sobre resultados incompletos

En el estado actual, el total suma únicamente los tiempos existentes. Por ello, un piloto sin tiempos tiene total cero y puede aparecer delante de quienes sí han participado. Además, si falta un tramo anterior pero existe uno posterior, el dato posterior puede aparecer desplazado a la primera columna disponible. No se debe considerar definitiva la clasificación hasta completar todas las etapas. Consulta [Estado y limitaciones](ESTADO_Y_LIMITACIONES.md).

## 9. Cambiar de tema

El botón situado bajo la lista de competiciones alterna los colores claro y oscuro. La preferencia vive solo durante la sesión: al reiniciar, la aplicación vuelve a iniciar en modo oscuro.

## 10. Eliminar una competición

1. Selecciona una competición.
2. Pulsa **Borrar**.
3. Confirma el diálogo.

Se eliminan permanentemente la competición, sus participantes y sus tiempos. No hay papelera ni deshacer. Haz una copia de seguridad antes de borrar información relevante.

Existe una limitación visual: tras borrar, la tabla anterior puede permanecer visible hasta pulsar **Refrescar** o elegir otra competición. Los datos sí se han eliminado de la base cuando aparece el mensaje de éxito.

## 11. Base de datos y copias de seguridad

Ubicaciones:

| Forma de ejecución | Archivo |
| --- | --- |
| `python src/main.py` | `<directorio desde el que se ejecuta>/data/datos.db` |
| `.exe` de PyInstaller | `%LOCALAPPDATA%\RallyTimeTracker\datos.db` |

La base y sus tablas se crean automáticamente al abrir la aplicación por primera vez.

Para copiar o restaurar:

1. cierra todas las ventanas de Rally Time Tracker;
2. copia `datos.db` a una ubicación segura o sustituye el archivo por una copia anterior;
3. vuelve a abrir la aplicación y comprueba una competición.

No sustituyas la base mientras la aplicación realiza una operación.

## 12. CLI heredada

La interfaz de consola usa la misma base y las mismas funciones de persistencia:

```bash
python src/cli_main.py
```

Permite listar, crear y borrar competiciones, ver datos, añadir tiempos, rellenar abandonos y penalizar. Está orientada a Windows porque limpia la pantalla con `cls`. Tiene menos validaciones que la GUI: una entrada no numérica puede cerrar el programa con un error. Para operación normal se recomienda la interfaz gráfica.

## 13. Mensajes frecuentes

| Mensaje | Acción recomendada |
| --- | --- |
| `Seleccione una competicion.` | Elige una entrada en el panel izquierdo. |
| `Formato de tiempo invalido. Use m:ss.xxx` | Usa dos partes separadas por `:`, por ejemplo `1:05.240`. |
| `No hay tiempos base para esa etapa.` | Registra al menos un tiempo antes de rellenar abandonos. |
| `No existe tiempo para ese participante/etapa.` | Guarda primero el tiempo del participante en ese tramo. |
| `Ya existe una competicion con ese nombre.` | Usa un nombre distinto o elimina la competición anterior. |

