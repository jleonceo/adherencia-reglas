Versión en español: [README.md](README.md)

# adherencia-reglas

> This repository holds the method and the figures. To install the tool as a Claude Code plugin, use its twin [skill-adherencia-reglas](https://github.com/jleonceo/skill-adherencia-reglas).

> **Read this first: the tool speaks Spanish, this page does not change that.** Nine of its ten
> flags, all its configuration keys, the literal values `antes` and `despues`, the fifteen action
> verbs and every line it prints are in Spanish. Nothing here is translatable by renaming: a rule
> written with English keys is rejected, loudly and in Spanish. This page is the reference for that
> vocabulary, not a localised version of the program. The glossary sits at the end.

## Why it is called that

«Adherencia» is not a word anyone says out loud in Spanish either. It comes from medicine, where it
names the part of a treatment a patient actually follows, as opposed to the part the doctor wrote
on the prescription. The same thing happens to the rules you write for your agent: some get
followed and some stay on the page. If the word compliance comes to you first, use that. It means
the same.

## What Claude Code is and why this sits on your disk

Claude Code is Anthropic's tool that puts an AI model to work inside your computer, with permission
to open files, run commands and write code. As it works it keeps notes. Every conversation leaves a
file in the `~/.claude/projects/` folder, and inside it is the ordered list of everything that
happened: which command ran, which file was opened, what got written and in what order.

It does not keep that for you. It keeps it so a session can be resumed where you left it. But there
it sits on your disk. It turns out to be the most faithful record there is of how the work
actually went. This program reads it and sends nothing anywhere.

One warning worth giving early: by default those files are deleted after 30 days, so any «since
forever» measurement has that floor.

## The problem

Projects working with AI agents accumulate rules. They live in a file called `CLAUDE.md` that the
agent reads on startup, and also in skills and protocols. «Run the linter before publishing». «Run
the tests when you touch code». «Search before claiming something doesn't exist».

They all get read. None get counted.

The case that started this: a rule with its own hook and its own owning skill, wired on 22/07/2026,
was followed **in 103 out of 132 opportunities, 78.0 %** (measured on 27 July 2026 with this same
version of the code, over a private history you do not have: what you can reproduce is the example
below). The day it was first measured, that same rule read 24 % in the morning and 80 % in the
afternoon, and none of the intermediate versions was miscalculated: each measured a different
object. The suspicion existed. The number didn't, and without a number you can't decide anything.

So **measuring a rule forces you to define it**. Defining it turned out to be the work.

## How the program decides a rule was followed

This is the first question anyone with judgement asks. It sounds like a verdict, so it comes before
any number.

**There is no verdict.** No language model reads your work and offers an opinion on whether it was
done well. What there is instead is a proximity count between two things written down in the
record, and the whole procedure fits in four steps.

The first turns every tool call into a verb. The record stores raw calls, along the lines of «`Bash`
with this command inside» or «`Write` on this path», and none of that can be compared with a rule
written in prose. So there is a map of fifteen verbs. A `Bash` whose command matches `pytest`,
`npm test` or `cargo test` becomes `test`. A `Write` on a file ending in `.py` is
`escribir-codigo`; on anything else, `escribir-doc`. A `Grep` is `buscar`, a `Read` is `leer-doc` or
`leer-codigo` depending on the extension. A command matching no pattern falls into `shell`, the
catch-all.

The second flattens consecutive repeats. Three files written one after another are one occasion to
run the linter, not three, because the obligation is «before delivering» and there was only one
delivery. This decision genuinely moves the figure: one project rule goes from 57.1 % to 20.0 %
depending on whether a run of writes counts as one occasion or several. `--sin-colapsar` shows the
other reading.

The third counts the occasions. For each rule you declare a trigger and a response, both picked
from those fifteen verbs. Every appearance of the trigger verb is an occasion where the rule
applied. That is the denominator. If you also declared an `ambito`, only the occasions touching
files in those folders count.

The fourth checks whether the response arrived nearby. It reads the next N steps, N being the
`ventana` you set. If the response verb appears inside that window, the occasion counts as met. If
it does not appear, it does not count. For rules of the «do Y before X» kind you set
`direccion: antes` and the previous N steps get read instead.

The rate is met divided by occasions. That is the entire algorithm.

**A worked example.** The rule says «if you touch code, run the suite»: trigger `escribir-codigo`,
response `test`, window 3. The session, already translated into verbs, came out like this:

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

There are three occasions, at steps 1, 3 and 6. The first looks at steps 2 to 4 and finds the
`test`: met. The second looks at 4 to 6 and finds it too: met. The third looks at 7 to 9, where
there is no suite at all: unmet. Two out of three, 66.7 %.

Notice that a single `pytest` paid for the first two. That inflates the rate and it is declared
below, among the limits.

## What this method cannot see

Its limits come straight out of the mechanics above. They are not details. The program does not
know whether you did the right thing. It knows two actions appeared near each other.

**There is no chance baseline. That is the most serious limit.** A 60 % says nothing on its own if
the response you look for shows up every few actions anyway. If you commit out of habit every eight
steps, «commit after touching code» will read 40 % even if you never thought about it. What is
interpretable are comparisons: the same rule before and after wiring a hook, one day against
another, one rule against another in the same history. It is a comparative thermometer.

**One response pays several obligations**, as the example just showed. In the «antes» direction it
weighs more still: one linter run covers every deploy that fits in the window.

**It measures that you ran the command, not that it passed.** A red `pytest` counts like a green
one. If your rule says «I never close with a red suite», this measures something adjacent.

**The vocabulary is yours and the map does not guess it.** The verbs come from regular expressions
over the command text and from the file extension. If your linter, your deployer or your generator
are named differently, none of their calls is recognised and their verb measures zero forever. That
is why the first thing to run is `--acciones`, which shows what it recognises at your place.

**A response counts even if it touched a different file.** The `ambito` filters the trigger and not
the response, so writing `Libro/cap3.md` and running the linter over some other document counts as
met. It is the biggest assumption in the instrument and it stays as it is on purpose, because
moving the criterion after seeing the result is moving the metric. The strict reading is requested
with `--respuesta-en-ambito`, and the gap between the two says how much the assumption weighed.

**The window does not cross sessions.** Code at the end of one and tests at the start of the next
counts as unmet.

**It is not a violation rate and it does not judge the rule.** A norm may not apply to all its
triggers. A 20 % can be an ignored rule or a badly written one. That reading is yours. Rules
whose trigger is an intention, like «search before claiming something does not exist», leave no
trace to count until the claim is already made: that family needs a hook.

**The format it reads may change without notice.** Claude Code's documentation states that the
format of these files is internal and changes between versions, recommending `/export` instead
([code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions)). This tool does what
that page advises against. Tested against Claude Code 2.x in July 2026; if the format changes you
get a count that drops for no reason, not an error, which is why the bench fabricates its own
traces.

## Try it right now

You do not need a history of your own. The package ships three toy sessions, generated by a script
you can read:

```bash
python ejemplo/fabricar_ejemplo.py
python skills/adherencia-reglas/medir_adherencia.py --sesiones ejemplo/historial --reglas ejemplo/reglas_ejemplo.json
```

The first command writes the three sessions, with behaviour decided by hand. The second measures
them. This is what comes out on screen, whole and untrimmed. It will come out the same for you:

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

That asterisk is half the package. Four opportunities are no rate at all, and a tool that hands you
«25 %» without saying so is handing you an anecdote with decimals dressed up as a measurement. If a
rule came out as `n/d`, that is not a zero either: it means there was not a single opportunity in
that history, so the rule never got the chance to be met, and confusing the two is the error this
tool exists to prevent. The example is generated rather than shipped as fixed text for a related
reason. Until 26/07/2026 this block showed a table taken from a private history the repository did
not include, so whoever cloned it could not reproduce a single figure, which left a reader holding
claims and nothing to check them against. Now the table above is a checkable consequence.

## If you have none of this installed

You need Python 3.9 or newer and nothing else. The program uses the standard library, downloads no
dependencies and never touches the network. The two commands above work on a freshly cloned
repository, with nothing installed and without Claude Code.

That 3.9 is **certified** as of 27/07/2026: nine green jobs across 3.9, 3.11 and 3.13 on Windows,
Linux and Mac. Until that morning this line read «declared, not certified». It was true when
written and stopped being true on the first push, yet it stayed up for hours, which is worth
telling because a note of humility goes stale exactly like any other figure and nobody goes back to
check the modest claims. This one went stale towards the side that makes the repository look worse
than it is.

What you do need Claude Code for is having a history. Without it you can reproduce the example and
read the code, but there are no rules of yours to measure. To measure your own, point the program
at your folder:

```
python skills/adherencia-reglas/medir_adherencia.py --sesiones "~/.claude/projects/MY-PROJECT"
```

Replace `MY-PROJECT` with your folder name: look inside `~/.claude/projects` and use the project
you want to measure. Keep the quotes, because Claude Code builds that name from your working path
and it can contain spaces.

On macOS and on most Linux the interpreter is called `python3`, not `python`. The commands on this
page were written on Windows.

## What the number is for

For deciding what to do with each rule you have written down. Nothing else. That is plenty enough:
until now the decision was taken on a hunch.

A rate on its own is no use for that. It has to be compared with the same rule at another time,
with another rule over the same history, or with what pure chance would produce.

| The rule, compared with itself | Reading | What to do with it |
|---|---|---|
| high and steady over time | already a habit | writing it down is wasted space |
| rises when you wire a hook, then falls | remembered in bursts | this is the one mechanism helps most |
| low and flat, whatever you do | writing it doesn't work | give it a mechanism or drop it |
| `n/d` | no opportunities | couldn't look, which is not a zero |

## Declaring a rule

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

**`direccion`** separates «after X do Y» from «do Y before X». Many obligations are the second kind
and measured backwards they collapse: one read 7.7 % stated wrongly and 36.4 % stated right.

**`ventana`** is how many steps the response has. It moves the figure by thirty-three points, so
`--curva-ventana` exists to show that curve alongside the number.

The rules shipped in `reglas.json` declare no scope. That is deliberate: over a three-session
history any scope would leave the whole table at `n/d` and nothing would be visible. The moment you
point it at a real history, that is the first field to add.

## Change the actions first

Fifteen verbs ship by default, twelve of them active. Six come from the command you run, six from
the call type and the file extension, and the last three depend on you having doctrine folders, so
they ship with empty lists.

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
**widens** it rather than replacing it: yours is tried first and the factory one stays behind. And
an invalid pattern stops the tool instead of measuring zero, because a broken action silently
measuring zero is the exact failure this exists to prevent.

## The most revealing view

```
python skills/adherencia-reglas/medir_adherencia.py --por-dia 7
```

A global rate averages very different days. Broken down, the example rule scored **91 % on the day
its hook was wired**, over 76 opportunities, and **25 % the day after**, over just 4. That 25 %
cannot be read as a drop: the tool flags it with an asterisk for exactly that reason, because four
opportunities are not a rate. A new rule is followed while it is still remembered, and telling
whether that happens here needs more days with a real sample.

## Verification

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
any error path. One view is the exception and it has to be said out loud: `--acciones` exists to
show paths from your history, because without seeing a sample path you cannot tell whether the
vocabulary you declared matches your work. It **does print fragments of your file paths, by
design**. That is why it sits outside the promise above. Look before you paste its output into an
issue. Every other view returns counts and percentages, and there the promise holds in full.

Verified by **mutation**, which is what separates a bench from an ornament: the code is deliberately
sabotaged and every sabotage must turn it red. **You don't have to take that on trust: `python
mutar.py` does it in front of you**, fifteen sabotages against the three benches, reporting how many
are caught and how many slip through in silence. A sabotage nobody catches is not a bug in the code:
it is a line no bench is watching. Today it is fifteen out of fifteen, zero gaps. If that number
drops when you run it, the bench has stopped covering something.

The measured file is restored on exit, and also if the process is killed mid-run: `mutar.py` keeps an
intact copy on disk while the sabotage is in place, any later run repairs from it, and while that copy
is there `test_seguridad.py` turns red. This was tested by force-killing the process. Mutation found a
gap three manual reviews had missed, where Windows paths stopped being classified as doctrine and
silently counted as ordinary documents.

Also verified against real history for **discrimination**: pairs that hold by construction score 62 %
to 86 %; three pairs with no causal link score 0.0 % each.

## A format detail that costs dearly

One JSONL line is **not** one tool call. The format groups streaming chunks by message id, so the same
call reappears across several lines. Counting them all inflates the total by 58 % over 12 measured
sessions. The inflation varies from session to session, so scaling the result down at the end doesn't
fix it: the whole curve is distorted. What makes the fault expensive is that it has no symptom. The
numbers come out quietly wrong. This tool deduplicates by block id.

## Tested on

Windows, which is where the measured history lives. POSIX paths, another project's vocabulary and a
different folder layout are covered with fabricated traces in `test_portabilidad.py`, not against a
real Mac or Linux history. **That test is missing and you should know it before trusting a figure.**

## Installation

To read this document you need to install nothing: the instrument travels inside and the commands
above run it as is. To use it day to day inside Claude Code, the package and its uninstall
instructions live at
**[jleonceo/skill-adherencia-reglas](https://github.com/jleonceo/skill-adherencia-reglas)**.

## Sibling repositories

[guardianes-verificados-ia](https://github.com/jleonceo/guardianes-verificados-ia) is the next step
after this one: this measures, that enforces. The rest of the ecosystem is on the profile.

## Glossary: the fifteen action verbs

`git-commit` commit · `git-add` stage · `git-push` push · `git-mirar` inspect (status, log, diff) ·
`test` run a suite · `shell` any other command · `leer-doc` read a document · `leer-codigo` read code ·
`escribir-doc` write a document · `escribir-codigo` write code · `buscar` search · `subagente` spawn a
subagent · `escribir-doctrina` write into a doctrine folder · `leer-skill` read a skill ·
`leer-rag` read a knowledge base file.

Direction takes `antes` (before) or `despues` (after). The window field is `ventana`, the start date
is `desde`, the scope is `ambito`, and the pass mark is `umbral`.
