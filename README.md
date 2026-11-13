English version: [README.en.md](README.en.md)

# adherencia-reglas

[![ci](https://github.com/jleonceo/adherencia-reglas/actions/workflows/ci.yml/badge.svg)](https://github.com/jleonceo/adherencia-reglas/actions/workflows/ci.yml)

> Este repositorio cuenta el método y las cifras. Para instalar la herramienta como plugin de Claude Code, usa su gemelo [skill-adherencia-reglas](https://github.com/jleonceo/skill-adherencia-reglas).

**Le escribes reglas a tu agente de IA y no sabes si las cumple. Este programa lo cuenta sobre el
registro de sesiones que Claude Code ya guarda en tu disco y te devuelve un porcentaje por regla.**

## Por qué se llama así

«Adherencia» no la dice nadie hablando. Viene de la medicina, donde se llama así a la parte del
tratamiento que el paciente sigue de verdad, frente a la que el médico escribió en la receta. Aquí
pasa lo mismo con las reglas que le has escrito a tu agente: unas se siguen y otras se quedan en el
papel. Si a ti te sale antes la palabra cumplimiento, úsala. Significa eso.

## Qué es Claude Code y por qué tienes esto en el disco

Claude Code es la herramienta de Anthropic que pone un modelo de IA a trabajar dentro de tu
ordenador, con permiso para abrir ficheros, ejecutar comandos y escribir código. Mientras trabaja
va anotando lo que hace. Cada conversación deja un fichero en la carpeta `~/.claude/projects/`.
Dentro está la lista ordenada de todo lo que ocurrió: qué comando se ejecutó, qué fichero se abrió,
qué se escribió y en qué orden.

Eso no lo guarda para ti. Lo guarda para poder retomar una sesión donde la dejaste. Pero ahí queda
en tu disco y resulta ser el registro más fiel que existe de cómo se trabajó de verdad. Este
programa lo lee y no manda nada a ninguna parte.

Un aviso que conviene dar pronto: por defecto esos ficheros se borran a los 30 días, así que
cualquier medición «desde siempre» tiene ese suelo.

## El problema

Un proyecto que trabaja con agentes acumula reglas. Viven en un fichero llamado `CLAUDE.md` que el
agente lee al arrancar y también en skills y protocolos. «Pasa el corrector antes de publicar».
«Ejecuta los tests cuando toques código». «Busca antes de afirmar que algo no existe».

Todas se leen. Ninguna se cuenta.

El caso que originó esto: una regla con hook propio y skill dueña, cableada el 22/07/2026, se
cumplía **en 103 de 132 ocasiones, el 78,0 %** (medido el 27/07/2026 con esta misma versión del
código, sobre un historial privado que tú no tienes: lo que sí puedes reproducir es el ejemplo de
más abajo). La sospecha existía desde antes. El número no. Sin número no se decide nada: ni
reforzar la regla, ni retirarla, ni dejarla como está. El día que se midió por primera vez, esa
misma regla dio 24 % por la mañana y 80 % por la tarde, y ninguna de las versiones intermedias
estaba mal calculada. Cada una medía un objeto distinto: todos los ficheros o solo los que van
dirigidos a alguien, desde siempre o desde el alta de la regla, datando las sesiones por la fecha
del fichero o por la que traen dentro.

Así que **medir una regla obliga a definirla**. Definirla resultó ser el trabajo.

## Cómo decide el programa si una regla se cumplió

Esta es la primera pregunta con criterio que hace cualquiera y suena a juicio, así que va antes que
ningún número.

**No hay ningún juicio.** No hay un modelo de lenguaje leyendo tu trabajo para opinar si estuvo
bien hecho. Lo que hay es un conteo de cercanía entre dos cosas que quedaron escritas en el
registro. El procedimiento entero cabe en cuatro pasos.

El primero traduce cada llamada a herramienta en un verbo. El registro guarda llamadas crudas, del
estilo «`Bash` con este comando dentro» o «`Write` sobre esta ruta». Eso no se puede comparar con
una regla escrita en castellano, así que hay un mapa de quince verbos. Un `Bash` cuyo comando case
con `pytest`, `npm test` o `cargo test` se llama `test`. Un `Write` sobre un fichero terminado en
`.py` es `escribir-codigo`; sobre cualquier otro, `escribir-doc`. Un `Grep` es `buscar`, un `Read`
es `leer-doc` o `leer-codigo` según la extensión. Un comando que no encaja en ningún patrón cae en
`shell`, que es el cajón de sastre.

El segundo aplasta las repeticiones seguidas. Tres ficheros escritos uno detrás de otro son una
ocasión de pasar el corrector, no tres, porque la obligación es «antes de entregar» y ahí solo hubo
una entrega. Esta decisión mueve la cifra de verdad: una regla del proyecto pasa del 57,1 % al 20,0
% según se cuente la racha como una ocasión o como varias. Con `--sin-colapsar` se ve la otra
lectura.

El tercero cuenta las ocasiones. Por cada regla tú declaras un disparador y una respuesta, los dos
elegidos de esos quince verbos. Cada aparición del verbo del disparador es una ocasión en la que
tocaba cumplir. Ese es el denominador. Si además declaraste un `ambito`, solo cuentan las
ocasiones que tocaron ficheros de esas carpetas.

El cuarto mira si la respuesta llegó cerca. Se leen los N pasos siguientes, siendo N la `ventana`
que tú fijas. Si el verbo de la respuesta aparece dentro de esa ventana, la ocasión cuenta como
cumplida. Si no aparece, no cuenta. Para las reglas del tipo «haz Y antes de X» se marca
`direccion: antes` y entonces se leen los N pasos anteriores.

La tasa es cumplidas dividido entre ocasiones. Eso es todo el algoritmo.

**Un ejemplo a mano.** La regla dice «si tocas código, pasa la suite»: disparador
`escribir-codigo`, respuesta `test`, ventana 3. La sesión, ya traducida a verbos, salió así:

```
1  escribir-codigo   agent.py
2  leer-doc          README.md
3  escribir-codigo   util.py
4  test              pytest
5  buscar
6  escribir-codigo   parser.py
7  git-commit
8  leer-doc
9  buscar
```

Hay tres ocasiones, en los pasos 1, 3 y 6. La primera mira los pasos 2 a 4 y encuentra el `test`:
cumplida. La segunda mira del 4 al 6 y también lo encuentra: cumplida. La tercera mira del 7 al 9,
donde no hay ninguna suite: incumplida. Dos de tres, el 66,7 %.

Fíjate en que un solo `pytest` pagó las dos primeras. Eso infla la tasa y está declarado abajo,
entre los límites.

## Lo que este método no puede ver

De la mecánica de arriba salen sus límites. No son detalles: son de fondo. El programa no sabe si
hiciste lo correcto. Sabe que dos acciones aparecieron cerca la una de la otra.

**No hay línea base de azar, y es el límite más serio.** Un 60 % no dice nada por sí solo si la
respuesta que buscas aparece cada pocas acciones de todos modos. Si commiteas por costumbre cada
ocho pasos, la regla «commitea tras tocar código» dará un 40 % aunque nunca hayas pensado en ella.
Lo interpretable son las comparaciones: la misma regla antes y después de ponerle un hook, un día
contra otro, una regla contra otra del mismo historial. Es un termómetro comparativo.

**Una sola respuesta paga varias obligaciones**, como acaba de verse en el ejemplo. En dirección
«antes» pesa más todavía: un linter ejecutado una vez cubre todos los despliegues que quepan en la
ventana.

**Mide que ejecutaste el comando, no que saliera bien.** Un `pytest` en rojo cuenta igual que uno
en verde. Si tu regla dice «no cierro con la suite en rojo», esto mide otra cosa parecida.

**El vocabulario es tuyo y el mapa no lo adivina.** Los verbos salen de expresiones regulares sobre
el texto del comando y de la extensión del fichero. Si tu linter, tu desplegador o tu generador se
llaman de otra manera, ninguna llamada suya se reconoce y su verbo mide cero para siempre. Por eso
la primera vez se ejecuta `--acciones`, que enseña qué reconoce en tu casa.

**La respuesta vale aunque toque otro fichero.** El `ambito` filtra el disparador y no la respuesta,
así que escribir `Libro/cap3.md` y pasar el corrector sobre otro documento cualquiera cuenta como
cumplido. Es el supuesto más grande del instrumento y se deja como está a propósito, porque mover el
criterio después de ver el resultado es mover la métrica. La lectura estricta se pide con
`--respuesta-en-ambito` y la diferencia entre las dos dice cuánto pesaba el supuesto.

**La ventana no cruza sesiones.** Código al final de una y tests al principio de la siguiente cuenta
como incumplido.

**No es una tasa de incumplimiento y no juzga la regla.** Una norma puede no aplicar a todos sus
disparadores. Un 20 % puede ser una regla ignorada o una regla mal escrita. Esa lectura es tuya.
Para las reglas cuyo disparador es una intención, como «busca antes de afirmar que algo no existe»,
no hay rastro que contar hasta que ya se ha afirmado: esa familia necesita un hook.

**El formato que lee puede cambiar sin avisar.** La documentación de Claude Code dice que el de
estos ficheros es interno y cambia entre versiones, y recomienda `/export` en su lugar
([code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions)). Esta herramienta
hace lo que ahí se desaconseja. Probada contra Claude Code 2.x en julio de 2026; si el formato
cambia verás un recuento que baja sin motivo, no un error. Por eso el banco fabrica sus propias
trazas.

## Pruébalo ahora mismo

No hace falta que tengas historial propio. El paquete trae tres sesiones de juguete que se fabrican
con un script que puedes leer:

```bash
python ejemplo/fabricar_ejemplo.py
python skills/adherencia-reglas/medir_adherencia.py --sesiones ejemplo/historial --reglas ejemplo/reglas_ejemplo.json
```

El primer comando escribe las tres sesiones, con un comportamiento decidido a mano. El segundo las
mide. Esto es lo que sale por pantalla, entero y sin recortar. A ti te va a salir igual:

```
  Ampliando accion(es) de fabrica: test. Tu patron va delante, pero el de fabrica sigue
  detras: lo que no case con el tuyo se seguira contando con el suyo.
============================================================================
ADHERENCIA A LAS REGLAS PROPIAS  --  3 sesiones, 31 acciones
============================================================================
  regla                           tocaba  cumplio     tasa  umbral
  ----------------------------------------------------------------------------
  gate-tras-escribir-doc              11        8  72.7 %
      guia del equipo: todo documento pasa el gate de texto antes de darlo por bueno
  suite-tras-tocar-codigo              4        1  25.0 %*
      guia del equipo: si tocas codigo, pasa la suite antes de cerrar

(*) menos de 10 ocasiones: eso no es una tasa, es una anecdota con decimales.

La tasa es de HABITO, no de incumplimiento: una regla puede no aplicar a todos sus
disparadores. Sirve para decidir que hacer con cada una, no para repartir culpas.
```

Ese asterisco es medio paquete. Con cuatro ocasiones no hay tasa que valga, y una herramienta que
te devuelve «25 %» sin decírtelo te está dando una anécdota con decimales disfrazada de medida.

Si una regla saliera con `n/d`, eso tampoco es un cero: es que en ese historial no hubo ni una
ocasión, así que la regla no llegó a poder cumplirse, y confundir las dos cosas es el error que
esta herramienta persigue. El ejemplo se genera en vez de venir escrito por una razón emparentada
con esa. Hasta el 26/07/2026 este bloque enseñaba una tabla sacada de un historial privado que el
repositorio no traía, así que quien lo clonaba se quedaba con las afirmaciones y sin nada con lo
que contrastarlas, que es la posición más incómoda en la que puedes dejar a un lector. Ahora la
tabla de arriba es una consecuencia comprobable.

## Si no tienes nada de esto instalado

Necesitas Python 3.9 o superior y nada más. El programa usa la biblioteca estándar, no descarga
dependencias y no toca la red. Los dos comandos de arriba funcionan sobre el repositorio recién
clonado, sin instalar nada y sin tener Claude Code. Ese 3.9 está **certificado** desde el
27/07/2026: nueve trabajos en verde, con 3.9, 3.11 y 3.13 sobre Windows, Linux y Mac. Hasta esa
mañana aquí ponía «declarado, no certificado», que era cierto al escribirlo y dejó de serlo con el
primer push, pero siguió publicado unas horas porque una nota de humildad caduca igual que una
cifra y nadie vuelve a revisar las afirmaciones modestas. Esta caducó hacia el lado que hace
parecer el repositorio peor de lo que es.

Lo que sí necesitas Claude Code para tener es historial. Sin él puedes reproducir el ejemplo y leer
el código, pero no hay reglas tuyas que medir. Para medir las tuyas, apunta el programa a tu
carpeta:

```
python skills/adherencia-reglas/medir_adherencia.py --sesiones "~/.claude/projects/MI-PROYECTO"
```

Cambia `MI-PROYECTO` por el nombre de tu carpeta: mira qué hay dentro de `~/.claude/projects` y usa
la del proyecto que quieras medir. Deja las comillas, porque ese nombre lo fabrica Claude Code a
partir de tu ruta de trabajo y puede traer espacios dentro.

En macOS y en casi todo Linux el intérprete se llama `python3` y no `python`. Los comandos de esta
página se escribieron en Windows.

## Para qué te sirve el número

Para decidir qué haces con cada regla que tienes escrita. Nada más. Ya es bastante: hasta ahora esa
decisión se tomaba por corazonada.

Una tasa suelta no vale para eso. Hay que compararla con la de esa misma regla en otro momento, con
la de otra regla del mismo historial, o con lo que saldría por pura casualidad.

| La regla, comparada consigo misma | Lectura | Qué hacer con ella |
|---|---|---|
| alta y estable en el tiempo | ya es un hábito | sobra escrita, ocupa sitio |
| sube al cablearle un hook y luego cae | se recuerda a ratos | es la que más gana con mecanismo |
| baja y plana, pase lo que pase | escribirla no funciona | darle mecanismo o retirarla |
| `n/d` | no hubo ocasiones | no se pudo mirar, que no es un cero |

## Cómo se declara una regla

En `reglas.json`:

```json
{
  "id": "tests-tras-tocar-codigo",
  "disparador": "escribir-codigo",
  "respuesta": "test",
  "ventana": 6,
  "direccion": "despues",
  "desde": "2026-01-15",
  "ambito": ["src/", "lib/"]
}
```

`escribir-codigo` y `test` vienen de fábrica. Si tu regla necesita un verbo que no existe todavía,
míralo en la sección de acciones, más abajo: la herramienta rechaza una acción que no conoce en vez
de medirla a cero.

Los cuatro campos que parecen opcionales y no lo son:

**`desde`** es la fecha de alta de la regla. Sin ella se juzgan meses en los que la regla no
existía. La primera medición de este proyecto dio 8,4 % sin acotar y 24,1 % acotando: la misma
aritmética sobre el objeto equivocado.

**`ambito`** son las zonas donde la regla aplica de verdad. Sin él se mide una obligación más ancha
que la escrita. La regla del ejemplo daba 26,4 % contra cualquier fichero y 62,7 % contra los que
de verdad iban dirigidos a alguien.

**`direccion`** distingue «después de X haz Y» de «haz Y antes de X». Muchas obligaciones son del
segundo tipo y medidas al revés se hunden: una de ellas daba 7,7 % mal planteada y 36,4 % bien.

**`ventana`** es en cuántos pasos vale la respuesta. Mueve la cifra treinta y tres puntos, así que
la herramienta trae `--curva-ventana` para que puedas enseñarla junto al número.

Las reglas del `reglas.json` que viene en el paquete no declaran ámbito. Es a propósito: en un
historial de tres sesiones cualquier ámbito dejaría la tabla entera en `n/d` y no se vería nada. En
cuanto lo apuntes a tu historial de verdad, es el primer campo que hay que añadir.

## Lo primero que tienes que cambiar: las acciones

De fábrica vienen quince verbos, doce activos. Seis salen del comando que ejecutas, seis del tipo
de llamada y de la extensión del fichero, y las tres últimas dependen de que tengas carpetas de
doctrina, así que llegan con las listas vacías.

**Tu linter y tu desplegador no se llaman como los míos.** Empieza por mirar qué reconoce en tu
casa:

```
python skills/adherencia-reglas/medir_adherencia.py --acciones --sesiones "~/.claude/projects/MI-PROYECTO"
```

Después declara lo que falte en `reglas.json`. El fichero lleva dentro la referencia completa de
cada campo, con el porqué de cada uno; aquí solo va la forma:

```json
{
  "acciones_shell": [["deploy", "flyctl deploy|vercel --prod"]],
  "reglas": [
    {"id": "lint-antes-de-desplegar", "disparador": "deploy", "respuesta": "lint",
     "ventana": 8, "direccion": "antes", "desde": "2026-01-15"}
  ]
}
```

Dos detalles que cuestan una tarde si nadie los dice. Declarar un nombre que ya existe lo **amplía**
y no lo sustituye: el tuyo se prueba primero y el de fábrica sigue detrás. Y un patrón inválido
detiene la herramienta en vez de medir cero, porque una acción rota que mide cero en silencio es el
fallo exacto que esto viene a evitar.

## La vista que más enseña

```
python skills/adherencia-reglas/medir_adherencia.py --por-dia 7
```

Una tasa global promedia días muy distintos. Desglosada, la regla del ejemplo salió al **91 % el
día en que se cableó su hook**, sobre 76 ocasiones, y al **25 % al día siguiente**, sobre solo 4.
Ese 25 % no se puede leer como una caída: el instrumento le pone un asterisco justo por eso, porque
cuatro ocasiones no son una tasa. Una regla nueva se cumple mientras se recuerda, y para saber si
eso pasa aquí hacen falta más días con muestra suficiente.

## Verificación

160 casos en tres bancos, sobre trazas fabricadas y nunca sobre el historial real: un banco que
dependa de los datos de hoy cambia de resultado mañana.

```
cd skills/adherencia-reglas
python run_tests_adherencia.py     # 59 casos: la lógica
python test_portabilidad.py        # 84 casos: la herramienta fuera de su casa
python test_seguridad.py           # 17 casos: que no se lleve nada de tu historial
python mutar.py                    # 15 sabotajes: comprueba que los bancos sirven
python cobertura.py                # qué líneas del instrumento no ejecuta ningún caso
```

**El tercero es el que da derecho a fiarse.** Esta herramienta lee tu historial completo, donde hay
nombres, cuentas, documentos de identidad y claves pegadas por descuido. Se plantan canarios de
mentira dentro de un historial de juguete y se exige que no salgan por las vistas de agregados ni
por ningún camino de error, que es por donde se escapan. Más la comprobación de que no escribe nada.
La excepción es `--acciones` y conviene decirla en voz alta: esa vista existe justamente para
enseñar rutas del historial, porque sin ver una ruta de ejemplo no se puede saber si el vocabulario
que declaraste casa con tu trabajo. **Sí muestra fragmentos de tus rutas de fichero, por diseño.**
Por eso no entra en la promesa de arriba. Si vas a pegar su salida en un issue, míralo antes. Las
demás vistas devuelven conteos y porcentajes, y ahí la promesa es entera.

El segundo banco existe porque el primero no probaba nada de lo que se encuentra quien la descarga:
rutas POSIX, vocabulario de otro proyecto, configuración mal escrita y otra estructura de carpetas.
Ninguno de esos casos da error. Todos devuelven números, y los números están mal.

Verificado por **mutación**, que es lo que separa un banco de un adorno: se sabotea el código a
propósito y cada sabotaje tiene que ponerlo rojo. **Eso no hay que creérselo: `python mutar.py` lo
hace delante de ti**, quince sabotajes contra los tres bancos, y dice cuántos se cazan y cuántos
pasan callando. Un sabotaje que nadie caza no es un fallo del código: es una línea que el banco no
vigila. Hoy son quince de quince, cero huecos. Si esa cifra baja al ejecutarlo, el banco ha dejado
de cubrir algo y el número que te dé la herramienta vale menos de lo que parece. El fichero medido
se restaura al terminar, y también si el proceso muere a mitad: `mutar.py` deja una copia intacta
en disco mientras dura el sabotaje, cualquier ejecución posterior la usa para reparar, y mientras
esa copia siga ahí `test_seguridad.py` se pone rojo.

Se probó matando el proceso a la fuerza.

La mutación encontró un hueco que tres lecturas a mano no vieron: al quitar la normalización de
separadores de ruta, los casos de portabilidad de entonces seguían verdes, porque probaban el
filtro por carpeta y no la clasificación. Con rutas de Windows, `\skills\` dejaba de parecerse a
`/skills/` y tocar una skill pasaba a contarse como escribir un documento cualquiera, sin una sola
queja. Se verificó además contra el historial real que el instrumento **discrimina**, que es la
otra mitad del asunto y no se demuestra con un banco: pares que se cumplen por construcción dan
entre 62 % y 86 %; tres pares sin relación causal dan 0,0 % los tres.

## Un detalle de formato que cuesta caro

Una línea del JSONL **no es** una llamada a herramienta. El formato agrupa los trozos de streaming
por identificador de mensaje, así que la misma llamada reaparece en varias líneas. Contarlas todas
infla el recuento un 58 % sobre 12 sesiones medidas. La inflación no es uniforme entre sesiones, de
modo que no basta con dividir al final: deforma la curva entera.

El fallo no da ningún síntoma. Los números salen mal en silencio.

Esta herramienta deduplica por identificador de bloque.

## Verificado en

Windows es donde vive el historial que se ha medido. Las rutas POSIX, el vocabulario de otro
proyecto y una estructura de carpetas distinta se cubren con trazas fabricadas en
`test_portabilidad.py`, no con un historial de Mac o Linux de verdad. **Esa prueba falta y conviene
saberlo antes de fiarse de una cifra.**

## Instalación

Para leer este documento no hace falta instalar nada: el instrumento viaja dentro y los comandos de
arriba lo ejecutan tal cual. Para usarlo a diario dentro de Claude Code, el paquete y sus
instrucciones de desinstalación viven en
**[jleonceo/skill-adherencia-reglas](https://github.com/jleonceo/skill-adherencia-reglas)**.

## Piezas hermanas

[guardianes-verificados-ia](https://github.com/jleonceo/guardianes-verificados-ia) es el paso
siguiente al de aquí: esto mide, aquello obliga. El resto del ecosistema está en el perfil.
