# adherencia-reglas

**Escribes reglas para tu agente de IA y no sabes si las cumple. Esta skill lo cuenta sobre el
historial que Claude Code ya guarda en tu disco, y te devuelve un porcentaje por regla.**

```
python skills/adherencia-reglas/medir_adherencia.py --sesiones "~/.claude/projects/MI-PROYECTO"
```

Cambia `MI-PROYECTO` por el nombre de tu carpeta: mira qué hay dentro de `~/.claude/projects` y
usa la del proyecto que quieras medir. Deja las comillas: el nombre lo pone Claude Code a partir
de tu ruta de trabajo y puede traer espacios dentro.

Sin instalar nada. Python 3.9, biblioteca estándar, sin red. Trae reglas de ejemplo para que la
primera ejecución devuelva algo; después edita `reglas.json` con las tuyas.

[Español](#español) · [English](#english)

---

## Español

### El problema

Un proyecto que trabaja con agentes acumula reglas. En `CLAUDE.md`, en skills, en protocolos. «Pasa el
corrector antes de publicar». «Ejecuta los tests cuando toques código». «Busca antes de afirmar que
algo no existe».

Todas se leen. Ninguna se cuenta.

El caso que originó esto: una regla con hook propio y skill dueña, cableada el 22/07/2026, se cumplía
**en 103 de 132 ocasiones, el 78,0 %** (medido el 27/07/2026 con esta misma versión del código, sobre
un historial privado que tú no tienes: lo que sí puedes reproducir es el ejemplo de más abajo). La
sospecha existía desde antes. El número no. Sin número no se decide nada: ni reforzar la regla, ni
retirarla, ni dejarla como está. El día que se midió por primera vez, esa misma regla dio 24 % por la
mañana y 80 % por la tarde, y ninguna de las versiones intermedias estaba mal calculada. Cada una
medía un objeto distinto: todos los ficheros o solo los que van dirigidos a alguien, desde siempre o
desde el alta de la regla, datando las sesiones por la fecha del fichero o por la que traen dentro.

Así que **medir una regla obliga a definirla**. Definirla resultó ser el trabajo.

### Qué hace

Lee los ficheros de sesión que Claude Code escribe en `~/.claude/projects/`, y por cada regla que le
declares cuenta dos cosas:

1. Cuántas veces apareció la situación que la activa.
2. Cuántas veces llegó la respuesta que la regla exige.

Devuelve la tasa. Nada más.

Sin modelo de lenguaje de por medio, sin red, sin dependencias.

El paquete trae un ejemplo que puedes reproducir ahora mismo, sin tocar tu historial:

```bash
python ejemplo/fabricar_ejemplo.py
python skills/adherencia-reglas/medir_adherencia.py --sesiones ejemplo/historial --reglas ejemplo/reglas_ejemplo.json
```

El primero escribe tres sesiones de juguete con un comportamiento decidido a mano. El segundo las
mide. Sale esto, y te sale igual a ti:

```
  regla                           tocaba  cumplio     tasa  umbral
  ----------------------------------------------------------------------------
  gate-tras-escribir-doc              11        8  72.7 %
  suite-tras-tocar-codigo              4        1  25.0 %*
```

`(*)` marca las que tienen menos de diez ocasiones. Eso no es una tasa, es una anécdota con
decimales, y la herramienta lo dice sola para que nadie cite un 100 % de dos casos. Alrededor verás
más cosas: cuántas sesiones y acciones se han leído, la fuente declarada de cada regla, y los avisos
que correspondan. Aquí van recortadas para que se vea lo que importa.

**Por qué el ejemplo se genera en vez de venir escrito.** Hasta el 26/07/2026 este bloque enseñaba
una tabla sacada de un historial privado. El repo no traía ninguno. Quien clonaba no podía
reproducir ni una cifra. Ahora las tres sesiones se fabrican con un script que puedes leer, así
que la tabla de arriba es una consecuencia comprobable.

Si una regla saliera con `n/d`, eso no es un cero: es que en ese historial no hubo ni una ocasión,
así que la regla no llegó a poder cumplirse. Confundir las dos cosas es el error que esta
herramienta persigue.

### Instalación

Para leer este documento no hace falta instalar nada: el instrumento viaja dentro y los dos comandos
de arriba lo ejecutan tal cual. Para usarlo a diario en Claude Code, el paquete y sus instrucciones
de desinstalación viven en
**[jleonceo/skill-adherencia-reglas](https://github.com/jleonceo/skill-adherencia-reglas)**.

### Para qué sirve el número

**Alta y baja se leen contra sí mismas, no contra el 100 %.** Una tasa suelta no dice nada: hay
que compararla con la de esa misma regla en otro momento, con la de otra regla del mismo historial,
o con lo que saldría por pura casualidad. El porqué está en «Lo que esta herramienta no ve», más
abajo, y conviene leerlo antes de usar esta tabla.

| La regla, comparada consigo misma | Lectura | Qué hacer con ella |
|---|---|---|
| alta y estable en el tiempo | ya es un hábito | sobra escrita, ocupa sitio |
| sube al cablearle un hook y luego cae | se recuerda a ratos | es la que más gana con mecanismo |
| baja y plana, pase lo que pase | escribirla no funciona | darle mecanismo o retirarla |
| `n/d` | no hubo ocasiones | no se pudo mirar, que no es un cero |

### Cómo se declara una regla

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

**`desde`** es la fecha de alta de la regla. Sin ella se juzgan meses en los que la regla no existía.
La primera medición de este proyecto dio 8,4 % sin acotar y 24,1 % acotando: la misma aritmética sobre
el objeto equivocado.

**`ambito`** son las zonas donde la regla aplica de verdad. Sin él se mide una obligación más ancha
que la escrita. La regla del ejemplo daba 26,4 % contra cualquier fichero y 62,7 % contra los que de
verdad iban dirigidos a alguien.

Las reglas del `reglas.json` que viene en el paquete no lo declaran, y es a propósito: en un
historial de tres sesiones cualquier ámbito dejaría la tabla entera en `n/d` y no se vería nada. En
cuanto lo apuntes a tu historial de verdad, es el primer campo que hay que añadir.

**`direccion`** distingue «después de X haz Y» de «haz Y antes de X». Muchas obligaciones son del
segundo tipo, y medidas al revés se hunden: una de ellas daba 7,7 % mal planteada y 36,4 % bien.

**`ventana`** es en cuántos pasos vale la respuesta. Mueve la cifra treinta y tres puntos, así que la
herramienta trae `--curva-ventana` para que puedas enseñarla junto al número.

### Lo primero que tienes que cambiar: las acciones

Una regla se declara como «tras el disparador X debe venir la respuesta Y», y X e Y salen de un mapa
que traduce llamadas a herramienta en verbos. De fábrica vienen quince, doce activas. Seis salen del
comando que ejecutas, seis del tipo de llamada y de la extensión del fichero, y las tres últimas
dependen de que tengas carpetas de doctrina, así que llegan con las listas vacías.

**Tu linter y tu desplegador no se llaman como los míos.** Empieza por mirar qué reconoce en tu casa:

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

Dos detalles que cuestan una tarde si nadie los dice. Declarar un nombre que ya existe lo **amplía**,
no lo sustituye: el tuyo se prueba primero y el de fábrica sigue detrás. Y un patrón inválido detiene
la herramienta en vez de medir cero, porque una acción rota que mide cero en silencio es el fallo
exacto que esto viene a evitar.

*Este bloque tenía sesenta y cinco líneas y repetía la referencia que ya está en `reglas.json` y en
`SKILL.md`. Tres copias del mismo hecho es como se separan las cifras, que es de lo que trata el
repositorio.*

### Lo que este número no dice

Tres secciones seguidas explicaban por qué no fiarse de la cifra, y eran un 16 % del documento. La
honestidad no está en la cantidad de párrafos. Van aquí las cinco cosas que de verdad cambian lo que
puedes concluir.

**No hay línea base de azar, y es el límite más serio.** Un 60 % no dice nada por sí solo si la
respuesta que buscas aparece cada pocas acciones de todos modos. Si commiteas por costumbre cada ocho
pasos, la regla «commitea tras tocar código» dará un 40 % aunque nunca hayas pensado en ella. Lo
interpretable son las comparaciones: la misma regla antes y después de ponerle un hook, un día contra
otro, una regla contra otra del mismo historial. Es un termómetro comparativo.

**Una sola respuesta paga varias obligaciones.** Tres ficheros escritos seguidos y un solo `pytest` al
final cuentan como tres cumplimientos. Esto infla la tasa, y en dirección «antes» más todavía: un
linter ejecutado una vez cubre todos los despliegues que quepan en la ventana.

**Mide que ejecutaste el comando, no que saliera bien.** Un `pytest` en rojo cuenta igual que uno en
verde. Si tu regla dice «no cierro con la suite en rojo», esto mide otra cosa parecida.

**No es una tasa de incumplimiento y no juzga la regla.** Una norma puede no aplicar a todos sus
disparadores. Un 20 % puede ser una regla ignorada o una regla mal escrita. Esa lectura es tuya. Y
para las reglas cuyo disparador es una intención, como «busca antes de afirmar que algo no existe»,
no hay rastro que contar hasta que ya se ha afirmado: esa familia necesita un hook.

**El formato que lee puede cambiar sin avisar.** La documentación de Claude Code dice que el de estos
ficheros es interno y cambia entre versiones, y recomienda `/export` en su lugar
([code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions)). Esta herramienta hace
lo que ahí se desaconseja. Probada contra Claude Code 2.x en julio de 2026; si el formato cambia
verás un recuento que baja sin motivo, no un error, y por eso el banco fabrica sus propias trazas.
Además tus transcripts se borran a los 30 días por defecto, así que cualquier medición «desde
siempre» tiene ese suelo. La ventana tampoco cruza sesiones: código al final de una y tests al
principio de la siguiente cuenta como incumplido.

### La vista que más enseña

```
python skills/adherencia-reglas/medir_adherencia.py --por-dia 7
```

Una tasa global promedia días muy distintos. Desglosada, la regla del ejemplo salió al **91 % el día
en que se cableó su hook**, sobre 76 ocasiones, y al **25 % al día siguiente**, sobre solo 4. Ese 25 %
no se puede leer como una caída: el instrumento le pone un asterisco justo por eso, porque cuatro
ocasiones no son una tasa. Una regla nueva se cumple mientras se recuerda, y para saber si eso pasa
aquí hacen falta más días con muestra suficiente.

### Verificación

160 casos en tres bancos, sobre trazas fabricadas y nunca sobre el historial real: un banco que dependa
de los datos de hoy cambia de resultado mañana.

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

**La excepción es `--acciones`, y conviene decirla en voz alta.** Esa vista existe justamente para
enseñar rutas del historial: sin ver una ruta de ejemplo no se puede saber si el vocabulario que
declaraste casa con tu trabajo. **Sí muestra fragmentos de tus rutas de fichero, por diseño.** Por
eso no entra en la promesa de arriba. Si vas a pegar su salida en un issue, míralo antes. Las demás vistas devuelven conteos y porcentajes, y ahí la promesa es entera.

El segundo existe porque el primero no probaba nada de lo que se encuentra quien la descarga: rutas
POSIX, vocabulario de otro proyecto, configuración mal escrita y otra estructura de carpetas. Ninguno
de esos casos da error. Todos devuelven números, y los números están mal.

Verificado por **mutación**, que es lo que separa un banco de un adorno: se sabotea el código a
propósito y cada sabotaje tiene que ponerlo rojo. **Eso no hay que creérselo: `python mutar.py` lo
hace delante de ti**, quince sabotajes contra los tres bancos, y dice cuántos se cazan y cuántos pasan
callando. Un sabotaje que nadie caza no es un fallo del código: es una línea que el banco no vigila.
Hoy son quince de quince, cero huecos. Si esa cifra baja al ejecutarlo, el banco ha dejado de cubrir algo
y el número que te dé la herramienta vale menos de lo que parece. El fichero medido se restaura al
terminar, y también si el proceso muere a mitad: `mutar.py` deja una copia intacta en disco mientras
dura el sabotaje, cualquier ejecución posterior la usa para reparar, y mientras esa copia siga ahí
`test_seguridad.py` se pone rojo.

Se probó matando el proceso a la fuerza.

La mutación encontró un hueco que tres lecturas a mano no vieron: al quitar la normalización de separadores de ruta, los casos de portabilidad de entonces
seguían verdes, porque probaban el filtro por carpeta y no la clasificación. Con rutas de Windows,
`\skills\` dejaba de parecerse a `/skills/` y tocar una skill pasaba a contarse como escribir un
documento cualquiera, sin una sola queja.

Y verificado contra el historial real, comprobando que **discrimina**: pares que se cumplen por
construcción dan entre 62 % y 86 %; tres pares sin relación causal dan 0,0 % los tres.

### Un detalle de formato que cuesta caro

Una línea del JSONL **no es** una llamada a herramienta. El formato agrupa los trozos de streaming por
identificador de mensaje, así que la misma llamada reaparece en varias líneas. Contarlas todas infla
el recuento un 58 % sobre 12 sesiones medidas. La inflación no es uniforme entre sesiones, de modo que
no basta con dividir al final: deforma la curva entera.

El fallo no da ningún síntoma. Los números salen mal en silencio.

Esta herramienta deduplica por identificador de bloque.

### Requisitos

Python 3.9 o superior. Biblioteca estándar, nada más. **Ese 3.9 está certificado** desde el 27/07/2026: nueve trabajos en verde, con 3.9, 3.11 y 3.13 sobre Windows, Linux y Mac. Hasta esa mañana aquí ponía «declarado, no certificado». Era cierto al escribirlo y dejó de serlo con el primer push, pero siguió publicado unas horas. Una nota de humildad caduca igual que una cifra. Esta caducó hacia el lado que hace parecer el repositorio peor de lo que es.

### Verificado en

Windows es donde vive el historial que se ha medido. Las rutas POSIX, el vocabulario de otro
proyecto y una estructura de carpetas distinta se cubren con trazas fabricadas en
`test_portabilidad.py`, no con un historial de Mac o Linux de verdad. **Esa prueba falta y conviene
saberlo antes de fiarse de una cifra.**

### Piezas hermanas

[guardianes-verificados-ia](https://github.com/jleonceo/guardianes-verificados-ia) es el paso
siguiente al de aquí: esto mide, aquello obliga. El resto del ecosistema está en el perfil.

---

## English

> **Read this first: the tool speaks Spanish, this page does not change that.** Nine of its eleven
> flags, all eleven configuration keys, the literal values `antes` and `despues`, the fifteen action
> verbs and every line it prints are in Spanish. Nothing here is translatable by renaming: a rule
> written with English keys is rejected, loudly and in Spanish. This page is the reference for that
> vocabulary, not a localised version of the program. The glossary sits at the end.

### The problem

Projects working with AI agents accumulate rules. In `CLAUDE.md`, in skills, in protocols. «Run the
linter before publishing». «Run the tests when you touch code». «Search before claiming something
doesn't exist».

They all get read. None get counted.

The case that started this: a rule with its own hook and its own owning skill, wired on 22/07/2026,
was followed **in 103 out of 132 opportunities, 78.0 %** (measured on 27 July 2026 with this
same version of the code, over a private history you do not have: what you can reproduce is the
example below). The day it was first measured, that same rule read 24 % in the morning and 80 % in
the afternoon, and none of the intermediate versions was miscalculated: each measured a different
object. Measuring a rule forces you to define it, and defining it turned out to be the work. The suspicion existed. The number didn't,
and without a number you can't decide anything.

### What it does

It reads the session files Claude Code writes to `~/.claude/projects/` and, for every rule you
declare, counts two things: how many times the triggering situation appeared, and how many times the
required response followed. It returns the rate. Nothing else. No language model involved, no
network, no dependencies.

```
python skills/adherencia-reglas/medir_adherencia.py --sesiones "~/.claude/projects/MY-PROJECT"
```

The package ships an example you can reproduce right now, without touching your own history:

```bash
python ejemplo/fabricar_ejemplo.py
python skills/adherencia-reglas/medir_adherencia.py --sesiones ejemplo/historial --reglas ejemplo/reglas_ejemplo.json
```

The first writes three toy sessions with a behaviour decided by hand. The second measures them. This
is what comes out. It will come out the same for you:

```
  regla                           tocaba  cumplio     tasa  umbral
  ----------------------------------------------------------------------------
  gate-tras-escribir-doc              11        8  72.7 %
  suite-tras-tocar-codigo              4        1  25.0 %*
```

`(*)` marks the ones with fewer than ten opportunities. That is not a rate, it is an anecdote with
decimals, and the tool says so on its own so that nobody quotes a 100 % built on two cases. The
example is generated rather than shipped as fixed text on purpose: if the generator and the measurer
ever disagree, the table changes and the CI notices.

A committed output file would agree with itself forever.

*This whole block existed only in the Spanish half until 27/07/2026. A foreign reader was handed the
claims and not the one thing they could check for themselves.*

### What the number is for

**High and low are read against themselves, not against 100 %.** A rate on its own says nothing. It
has to be compared with the same rule at another time, with another rule over the same history, or
with what pure chance would produce. The reasoning is under "What this tool cannot see", further
down. It is worth reading before you use this table.

| The rule, compared with itself | Reading | What to do with it |
|---|---|---|
| high and steady over time | already a habit | writing it down is wasted space |
| rises when you wire a hook, then falls | remembered in bursts | this is the one mechanism helps most |
| low and flat, whatever you do | writing it doesn't work | give it a mechanism or drop it |
| `n/d` | no opportunities | couldn't look, which is not a zero |

### Declaring a rule

In `reglas.json`:

```json
{
  "id": "tests-after-touching-code",
  "disparador": "escribir-codigo",
  "respuesta": "test",
  "ventana": 6,
  "direccion": "despues",
  "desde": "2026-01-15",
  "ambito": ["src/", "lib/"]
}
```

`escribir-codigo` and `test` are built in. If your rule needs a verb that doesn't exist yet, see the
actions section below: the tool rejects an action it doesn't know rather than measuring it as zero.

Four fields look optional and aren't:

**`desde`** is the date the rule came into force. Without it you judge months when the rule didn't
exist. This project's first measurement read 8.4 % unbounded and 24.1 % bounded: correct arithmetic
on the wrong object.

**`ambito`** lists where the rule actually applies. Without it you measure a broader obligation than
the one written down: 26.4 % against every file, 62.7 % against the ones actually addressed to
someone.

**`direccion`** separates «after X do Y» from «do Y before X». Many obligations are the second kind,
and measured backwards they collapse: one read 7.7 % stated wrongly and 36.4 % stated right.

**`ventana`** is how many steps the response has. It moves the figure by thirty-three points, so
`--curva-ventana` exists to show that curve alongside the number.

### Change the actions first

A rule reads «after trigger X, response Y must follow», and X and Y come from a map that turns tool
calls into verbs. Fifteen ship by default, twelve of them active. Six come from the command you run,
six from the call type and the file extension, and the last three depend on you having doctrine
folders, so they ship with empty lists.

**Your linter and your deployer are not named like mine.** Start by seeing what it recognises:

```
python skills/adherencia-reglas/medir_adherencia.py --acciones --sesiones "~/.claude/projects/MY-PROJECT"
```

Then declare what is missing in `reglas.json`. That file carries the full field reference with the
reasoning behind each one; only the shape goes here. **Keys and values stay Spanish:**

```json
{
  "acciones_shell": [["deploy", "flyctl deploy|vercel --prod"]],
  "reglas": [
    {"id": "lint-before-deploy", "disparador": "deploy", "respuesta": "lint",
     "ventana": 8, "direccion": "antes", "desde": "2026-01-15"}
  ]
}
```

Two details that cost an afternoon if nobody says them. Declaring a name that already exists
**widens** it rather than replacing it: yours is tried first and the factory one stays behind. And an
invalid pattern stops the tool instead of measuring zero, because a broken action silently measuring
zero is the exact failure this exists to prevent.

### What this number does not say

Three consecutive sections used to explain why not to trust the figure, a sixth of the document.
Honesty is not a matter of paragraph count. Here are the five things that actually change what you
can conclude.

**There is no chance baseline. That is the most serious limit.** A 60 % says nothing on its own
if the response you look for shows up every few actions anyway. If you commit out of habit every
eight steps, «commit after touching code» will read 40 % even if you never thought about it. What is
interpretable are comparisons: the same rule before and after wiring a hook, one day against
another, one rule against another in the same history. It is a comparative thermometer.

**One response pays several obligations.** Three files written in a row and a single `pytest` at the
end count as three compliances. That inflates the rate, and in the «antes» direction more so: one
linter run covers every deploy that fits in the window.

**It measures that you ran the command, not that it passed.** A red `pytest` counts like a green one.
If your rule says «I never close with a red suite», this measures something adjacent.

**It is not a violation rate and it does not judge the rule.** A norm may not apply to all its
triggers. A 20 % can be an ignored rule or a badly written one. That reading is yours. Rules
whose trigger is an intention, like «search before claiming something does not exist», leave no trace
to count until the claim is already made: that family needs a hook.

**The format it reads may change without notice.** Claude Code's documentation states that the format
of these files is internal and changes between versions, recommending `/export` instead
([code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions)). This tool does what
that page advises against. Tested against Claude Code 2.x in July 2026; if the format changes you get
a count that drops for no reason, not an error, which is why the bench fabricates its own traces.
Your transcripts are also deleted after 30 days by default, so any «since forever» measurement has
that floor. The window does not cross sessions either: code at the end of one and tests at the start
of the next counts as unmet.

### The most revealing view

```
python skills/adherencia-reglas/medir_adherencia.py --por-dia 7
```

A global rate averages very different days. Broken down, the example rule scored **91 % on the day its
hook was wired**, over 76 opportunities, and **25 % the day after**, over just 4. That 25 % cannot be
read as a drop: the tool flags it with an asterisk for exactly that reason, because four opportunities
are not a rate. A new rule is followed while it is still remembered, and telling whether that happens
here needs more days with a real sample.

### Verification

160 cases across three benches, over fabricated traces and never over the real history: a bench that
depends on today's data gives a different answer tomorrow.

```
cd skills/adherencia-reglas
python run_tests_adherencia.py     # 59 cases: the logic
python test_portabilidad.py        # 84 cases: the tool away from home
python test_seguridad.py           # 17 cases: that it takes nothing from your history
python mutar.py                    # 15 sabotages: checks the benches are worth anything
python cobertura.py                # which lines of the tool no case ever runs
```

`test_portabilidad.py` exists because the first bench tested none of what a new user hits on day one:
POSIX paths, another project's vocabulary, broken config and a different folder layout.
`test_seguridad.py` is the one that earns your trust: this tool reads your whole session history, so
fake canaries are planted in a toy history and required not to surface through the aggregate views or
any error path.

**One view is the exception and it has to be said out loud: `--acciones`.** That view exists to show
paths from your history: without seeing a sample path you cannot tell whether the vocabulary you
declared matches your work. It **does print fragments of your file paths, by design**. That is why it
sits outside the promise above. Look before you paste its output into an issue. Every other
view returns counts and percentages, and there the promise holds in full.

Verified by **mutation**, which is what separates a bench from an ornament: the code is deliberately
sabotaged and every sabotage must turn it red. **You don't have to take that on trust: `python
mutar.py` does it in front of you**, fifteen sabotages against the three benches, reporting how many
are caught and how many slip through in silence. A sabotage nobody catches is not a bug in the code:
it is a line no bench is watching. Today it is fifteen out of fifteen, zero gaps. If that number drops
when you run it, the bench has stopped covering something.

The measured file is restored on exit, and also if the process is killed mid-run: `mutar.py` keeps an
intact copy on disk while the sabotage is in place, any later run repairs from it, and while that copy
is there `test_seguridad.py` turns red. This was tested by force-killing the process. Mutation found a
gap three manual reviews had missed, where Windows paths stopped being classified as doctrine and
silently counted as ordinary documents.

Also verified against real history for **discrimination**: pairs that hold by construction score 62 %
to 86 %; three pairs with no causal link score 0.0 % each.

### A format detail that costs dearly

One JSONL line is **not** one tool call. The format groups streaming chunks by message id, so the same
call reappears across several lines. Counting them all inflates the total by 58 % over 12 measured
sessions. The inflation varies from session to session, so scaling the result down at the end doesn't
fix it: the whole curve is distorted. What makes the fault expensive is that it has no symptom. The
numbers come out quietly wrong. This tool deduplicates by block id.

### Requirements

Python 3.9+. Standard library only. **That 3.9 is certified** as of 27/07/2026: nine green jobs across 3.9, 3.11 and 3.13 on Windows, Linux and Mac. Until that morning this line read «declared, not certified». It was true when written and stopped being true on the first push, yet it stayed up for hours. A note of humility goes stale like any other figure. This one went stale towards the side that makes the repository look worse than it is.

### Tested on

Windows, which is where the measured history lives. POSIX paths, another project's vocabulary and a
different folder layout are covered with fabricated traces in `test_portabilidad.py`, not against a
real Mac or Linux history. **That test is missing and you should know it before trusting a figure.**

### Sibling repositories

[guardianes-verificados-ia](https://github.com/jleonceo/guardianes-verificados-ia) is the next step
after this one: this measures, that enforces. The rest of the ecosystem is on the profile.

### Glossary: the fifteen action verbs

`git-commit` commit · `git-add` stage · `git-push` push · `git-mirar` inspect (status, log, diff) ·
`test` run a suite · `shell` any other command · `leer-doc` read a document · `leer-codigo` read code ·
`escribir-doc` write a document · `escribir-codigo` write code · `buscar` search · `subagente` spawn a
subagent · `escribir-doctrina` write into a doctrine folder · `leer-skill` read a skill ·
`leer-rag` read a knowledge base file.

Direction takes `antes` (before) or `despues` (after). The window field is `ventana`, the start date
is `desde`, the scope is `ambito`, and the pass mark is `umbral`.

