# -*- coding: utf-8 -*-
"""
medir_adherencia.py - de las reglas que escribiste, ¿cuáles se cumplen de verdad?

POR QUE EXISTE (25/07/2026)
---------------------------
Un proyecto acumula reglas: en CLAUDE.md, en skills, en protocolos. Se leen y se dan por buenas.
Nadie cuenta nunca cuántas se cumplen, porque para contarlo hay que abrir el historial de sesiones y
el historial se abre para otras cosas.

Este proyecto lo midió el 25/07 y le salió que la regla "pasa la puerta de salida antes de publicar
un texto", con hook y skill propia, se cumplía en 72 de 90 ocasiones. La sospecha existía desde por
la mañana; el número no existía hasta que se contó.

Esa cifra empezó siendo 24 % y acabó en 80 % a lo largo del mismo día, y ninguna de las versiones
intermedias estaba mal calculada: cada una medía un objeto distinto (todos los ficheros o solo los
dirigidos a alguien, desde siempre o desde el alta de la regla, datando por la fecha del fichero o
por la que trae dentro). Medir una regla obliga a definirla, y ahí está el trabajo de verdad.

QUE HACE
--------
Lee los transcripts que Claude Code ya guarda en `~/.claude/projects/` y, por cada regla declarada
en `reglas.json`, cuenta dos cosas: cuántas veces apareció su DISPARADOR y cuántas veces la
RESPUESTA llegó dentro de una ventana de N pasos. Devuelve la tasa.

  exit 0  todas las reglas por encima de su umbral (o sin umbral declarado)
  exit 1  alguna regla por debajo de su umbral
  exit 2  no se pudo medir (sin sesiones legibles)

LO QUE NO ES, y hay que decirlo antes de que alguien lea el porcentaje:

  - NO es una tasa de incumplimiento. Una regla puede no aplicar a todos sus disparadores (la
    puerta de salida no se le pasa a un borrador interno). Es una tasa de HABITO: con qué
    frecuencia la acción sigue a su disparador sin que nadie lo recuerde.
  - Y la tasa DEPENDE DE COMO ESTE DEFINIDA LA REGLA, que es el descubrimiento del 25/07. La
    puerta de salida estaba definida de tres maneras a la vez: su skill dice "artefacto para que
    lo lea otra persona, NO borradores internos", su hook dispara por palabras del prompt, y este
    instrumento medía cualquier `.md`. Las tres tasas: 26,4 %, 38,0 % y 62,7 % sobre los mismos
    datos. Por eso existe el campo `ambito`: sin declarar a qué ficheros aplica una regla, su
    porcentaje no significa nada.
  - NO juzga si la regla es buena. Un 20 % puede ser una regla ignorada o una regla mal escrita.
  - NO infiere las reglas: se declaran a mano en `reglas.json`. Deducirlas del texto de un
    CLAUDE.md es trabajo de juicio y vive en el cuerpo de la skill, no aquí.

READ-ONLY sobre el historial. No escribe nada fuera de su salida por pantalla.

UN AVISO DE FORMATO QUE CUESTA CARO. Una línea del JSONL NO es una llamada a herramienta: el
formato agrupa los trozos de streaming por id de mensaje, así que la misma llamada reaparece en
varias líneas. Contarlas todas infla el recuento un 58 % (medido sobre 12 sesiones) y no lo infla
por igual en todos los tramos, así que deforma cualquier curva. Aquí se deduplica por id de bloque.
El fallo no da ningún síntoma: los números salen silenciosamente mal.
"""
from __future__ import print_function

import argparse
import datetime
import io
import json
import os
import re
import sys

# LA CONSOLA DE WINDOWS ARRANCA EN CP1252 Y ESO ROMPE LA SALIDA (25/07/2026). Probando la skill
# contra un proyecto que no era el suyo, la cabecera salio con un rombo negro donde iba un punto
# medio, y el `--help` habria reventado con UnicodeEncodeError en cuanto una tilde del docstring
# llegase a stdout. Los textos que imprime el script se escribieron ya sin tildes a proposito,
# pero eso no cubre lo que argparse saca del docstring ni lo que imprima quien lo modifique.
# Se arregla en el unico sitio donde se puede arreglar de raiz, y si el interprete es viejo o el
# terminal no admite el cambio, se sigue como antes: esto no puede tumbar la herramienta.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass

# POR DEBAJO DE ESTE NUMERO DE OCASIONES, LA TASA NO ES UNA TASA (25/07/2026). Midiendo la propia
# jornada en que se construyo la skill salieron dos "100 %" y dos "0 %" que venian de una o dos
# ocasiones. Un porcentaje sobre dos casos se lee igual que uno sobre mil, y ahi es donde alguien
# saca una conclusion falsa. Se marcan con un asterisco en vez de esconderlos.
MUESTRA_MINIMA = 10

AQUI = os.path.dirname(os.path.abspath(__file__))
SESIONES_DEFECTO = os.path.expanduser(os.path.join("~", ".claude", "projects"))

# POR DEFECTO NO SE ENTRA EN LAS SUBCARPETAS, y la razon merece decirse. Dentro de la carpeta de un
# proyecto viven las sesiones de la conversacion principal (58 aqui) y, colgando de ella, las de
# CADA subagente lanzado (6.750 aqui). Barrer las dos cosas mezcla dos universos y da una cifra que
# no se puede comparar con nada: la conducta de la sesion principal y la de agentes efimeros que
# reciben una instruccion cerrada. Se miden por separado, con `--subagentes` para incluirlos.
REGLAS_DEFECTO = os.path.join(AQUI, "reglas.json")

# ---------------------------------------------------------------------------------------------
# El mapa de acciones: de una llamada a herramienta a un verbo del dominio. Sin esta traducción
# las secuencias son ilegibles, porque `Bash` no dice nada y `git-commit` sí.
# ---------------------------------------------------------------------------------------------
REGLAS_SHELL = [
    ("git-commit",   r"\bgit\s+(?:-C\s+\S+\s+)?commit\b"),
    ("git-add",      r"\bgit\s+(?:-C\s+\S+\s+)?add\b"),
    ("git-push",     r"\bgit\s+(?:-C\s+\S+\s+)?push\b"),
    ("git-mirar",    r"\bgit\s+(?:-C\s+\S+\s+)?(?:status|log|diff|show)\b"),
    # Las suites de los ecosistemas mas comunes. El patron solo conocia Python y el README
    # anunciaba `test` entre las acciones UNIVERSALES: dos usuarios de prueba independientes
    # chocaron con lo mismo el 25/07, un 0,0 % sobre 15 ocasiones en un proyecto de JavaScript
    # con `npm test` ejecutado cada vez. Un cero silencioso en la unica accion que se vendia
    # como de fiar.
    ("test",         r"\brun_tests|\btest_|\bunittest|\bpytest"
                     r"|npm (?:run )?test|yarn test|pnpm test|jest|vitest|mocha"
                     r"|go test|cargo test|mvn test|gradle test|dotnet test"
                     r"|rspec|phpunit|ctest|bundle exec rake test"),
    ("shell",        r"."),
]
RX_SHELL = [(n, re.compile(p, re.I)) for n, p in REGLAS_SHELL]

# El cajon donde cae lo que no casa con ninguna accion. Se puede redefinir para adelantarlo, pero
# no se puede echar: sin el, una llamada sin clasificar no se contaria en ningun sitio.
COMODIN_SHELL = "shell"

# LAS CINCO ULTIMAS DEL MAPA SON DE ESTE PROYECTO, NO DE NADIE MAS (25/07/2026). `gate-texto`,
# `buscador`, `regenerar`, `escanear-repos` y `salud` eran nombres de scripts del proyecto donde
# nacio esto, y quien la descargue tiene otros. Sin una via para declararlos, solo medirian bien las
# acciones universales (git, tests, escrituras, lecturas) y las demas quedan de adorno, midiendo
# siempre cero. Por eso `reglas.json` admite un bloque `acciones_shell`, y por eso este mapa se
# queda como EJEMPLO por defecto en vez de como unica verdad.
ACCIONES_BASE = {"escribir-doc", "escribir-codigo", "escribir-doctrina", "leer-doc", "leer-codigo",
                 "leer-skill", "leer-rag", "buscar", "subagente"}
ACCIONES = ACCIONES_BASE | {n for n, _ in REGLAS_SHELL}

# TRES DE ESAS TAMPOCO ERAN UNIVERSALES, y esta es la segunda vez que pasa (25/07/2026).
# `escribir-doctrina`, `leer-skill` y `leer-rag` no salen de la llamada: salen de en que CARPETA
# cae el fichero, y esas carpetas eran una convencion del proyecto donde nacio esto, cableada en
# el codigo. En cualquier otro repo las tres median cero para siempre y sin decirlo, que es
# exactamente el defecto que se habia arreglado semanas antes para `npm test`. La primera vez se
# saco a configuracion lo que se llamaba como los scripts del proyecto; faltaba lo que se llamaba
# como sus CARPETAS. Lo encontro una suite escrita desde el README sin ver el codigo.
#
# Si alguien no tiene estas carpetas, deja las listas vacias y sus ficheros cuentan como
# documento o como codigo, que es lo que son. Vacio aqui NO es un cero: es que esa distincion no
# existe en su proyecto.
CARPETAS_DEFECTO = {"skill": ["/skills/"], "rag": ["/rag/", "/rag_"]}


def compilar_acciones_shell(extra):
    """Antepone las acciones del usuario a las de por defecto, y devuelve (lista, nombres).

    Van DELANTE porque el mapa se recorre en orden y la ultima entrada es un comodin que casa con
    cualquier cosa: puestas detras no llegarian a probarse nunca.

    DECLARAR UN NOMBRE QUE YA EXISTE LO AMPLIA, NO LO SUSTITUYE (25/07/2026). El README prometia
    "puedes redefinir una que ya exista" y eso era falso: el patron de fabrica sigue detras y
    acaba casando igual, asi que quien declarase `git-commit` con su propio patron veria los
    commits contarse como siempre. Lo encontro una suite escrita desde el README sin mirar el
    codigo, que es la unica forma de cazar esto: leyendo el codigo, anteponer PARECE redefinir.

    Se arreglo la promesa y no la conducta, despues de probar la conducta contraria y ver que
    rompia seis casos del propio banco. Ampliar es lo que hace falta de verdad: este proyecto
    declara `["test", "eval_golden|verificador_minimo"]` porque son SUS formas de ejecutar una
    suite, ADEMAS de `pytest` y `npm test`, no en lugar de ellas. Sustituir dejaria fuera las
    universales sin que nadie lo pidiera. Ahora se avisa por pantalla cuando un nombre amplia a
    uno de fabrica, para que la diferencia no se descubra leyendo una tasa rara.
    """
    if extra is None:
        return RX_SHELL, set(ACCIONES)
    if not isinstance(extra, list):
        raise ValueError("`acciones_shell` tiene que ser una LISTA de pares [nombre, patron]")
    compiladas = []
    for i, par in enumerate(extra):
        if not isinstance(par, (list, tuple)) or len(par) != 2:
            raise ValueError("`acciones_shell`[%d] no es un par [nombre, patron]: %r" % (i, par))
        nombre, patron = par
        if not isinstance(nombre, str) or not nombre:
            raise ValueError("`acciones_shell`[%d] tiene un nombre vacio o no textual" % i)
        if not isinstance(patron, str) or not patron.strip():
            raise ValueError("`acciones_shell`[%d] (%s) tiene el patron vacio. Un patron\n"
                             "vacio casa con TODO y se traga las demas acciones sin avisar."
                             % (i, nombre))
        try:
            compiladas.append((nombre, re.compile(patron, re.I)))
        except (re.error, TypeError) as e:
            # Un patron roto que pasara callando dejaria esa accion a cero para siempre, y un cero
            # se lee como incumplimiento en vez de como instrumento averiado.
            raise ValueError("`acciones_shell`[%d] (%s) tiene un patron invalido: %s"
                             % (i, nombre, e))
    lista = compiladas + RX_SHELL
    return lista, ACCIONES_BASE | {n for n, _ in lista}


def nombres_ampliados(extra):
    """Los nombres del usuario que ya existian de fabrica, para poder avisarlo.

    Va aparte y no como tercer valor de `compilar_acciones_shell` porque esa firma ya la usan los
    tres bancos y cambiarla los rompe a todos. Una funcion nueva no rompe a nadie.
    """
    if not isinstance(extra, list):
        return []
    suyos = {p[0] for p in extra if isinstance(p, (list, tuple)) and len(p) == 2
             and isinstance(p[0], str)}
    return sorted(suyos & {n for n, _ in RX_SHELL})

EXT_CODIGO = (".py", ".ps1", ".js", ".ts", ".sql", ".sh", ".yaml", ".yml", ".json")


def accion_de(nombre, entrada, rx_shell=None, carpetas=None):
    """Traduce una llamada a herramienta en una acción del dominio, o None si no cuenta.

    `carpetas` dice qué rutas son doctrina en ESTE proyecto. Sin él se usan las de ejemplo, que
    son las del proyecto donde nació la herramienta y no tienen por qué ser las de nadie más.
    """
    car = CARPETAS_DEFECTO if carpetas is None else carpetas
    skill = [t.lower() for t in car.get("skill", [])]
    rag = [t.lower() for t in car.get("rag", [])]
    if nombre in ("Bash", "PowerShell"):
        cmd = entrada.get("command") or ""
        if not isinstance(cmd, str):
            # Un `command` numerico o en lista sale de otra herramienta o de un formato nuevo.
            # No es una accion que sepamos nombrar, y `re.search` sobre un entero es un TypeError.
            return COMODIN_SHELL
        for etiqueta, rx in (rx_shell or RX_SHELL):
            if rx.search(cmd):
                return etiqueta
        return COMODIN_SHELL
    if nombre in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        crudo = entrada.get("file_path") or ""
        if not isinstance(crudo, str):
            crudo = ""      # ruta en lista o numerica: no se inventa, se ignora la entrada
        fp = crudo.replace("\\", "/").lower()
        # La doctrina viva se distingue del resto: tocarla dispara obligaciones propias (la
        # cascada, regenerar las vistas) que no aplican a cualquier fichero. Quien no tenga esa
        # distinción deja las listas vacías y todo cae en documento o código, que es lo que son.
        if any(t in fp for t in skill + rag):
            return "escribir-doctrina"
        return "escribir-codigo" if fp.endswith(EXT_CODIGO) else "escribir-doc"
    if nombre in ("Read", "NotebookRead"):
        fp = (entrada.get("file_path") or "").replace("\\", "/").lower()
        if any(t in fp for t in skill):
            return "leer-skill"
        if any(t in fp for t in rag):
            return "leer-rag"
        return "leer-codigo" if fp.endswith(EXT_CODIGO) else "leer-doc"
    if nombre in ("Grep", "Glob"):
        return "buscar"
    if nombre in ("Task", "Agent"):
        return "subagente"
    return None


# Rutas dentro de una orden de shell. SIN expresion regular a proposito: la primera version usaba
# una, con clases de caracteres anidadas, y se comio diez minutos de CPU en un comando largo por
# retroceso catastrofico. Partir por espacios no retrocede nunca y hace lo mismo aqui.
EXT_RUTA = (".md", ".py", ".json", ".ps1", ".yml", ".yaml", ".txt", ".js", ".ipynb", ".sql")


def rutas_en_orden(cmd):
    """Los argumentos de una orden que parecen rutas de fichero.

    Deliberadamente estrecho: hace falta separador Y extension conocida. Un criterio ancho
    recogeria opciones y URLs, y meteria ruido justo donde el ambito decide si una respuesta
    cuenta. Se anadio el 26/07/2026, cuando la lectura estricta dio 0,0 % en todas las reglas
    porque una orden de shell no trae `file_path` y su lista de rutas salia vacia. Un cero que
    sale siempre no es una medida.
    """
    fuera = []
    for token in cmd.replace("	", " ").split():
        limpio = token.strip("\"'()<>,;")
        if len(limpio) > 300:
            continue
        if "/" not in limpio and "\\" not in limpio:
            continue
        if not limpio.lower().endswith(EXT_RUTA):
            continue
        fuera.append(limpio.replace("\\", "/").lower())
    return fuera


def secuencia_de(path, colapsar=True, rx_shell=None, carpetas=None):
    """Acciones en orden. Devuelve None si el fichero no se pudo leer en absoluto.

    COLAPSAR ES UNA DECISION DE DISEÑO, no un detalle (25/07/2026). Si escribo tres ficheros
    seguidos, ¿son tres ocasiones de pasar el corrector o una? Se cuenta UNA: la obligacion es
    "antes de entregar", y una racha de escrituras sin nada en medio es una sola entrega. Editar
    tres veces el mismo documento tampoco son tres deberes distintos.

    La diferencia no es pequeña. Sobre las 58 sesiones de este proyecto, la puerta de salida sale
    al 24,1 % colapsando y al 19,4 % contando cada escritura, porque el denominador pasa de 829 a
    1.687. Se elige la lectura CONSERVADORA (denominador menor, tasa mayor), que es la que menos
    exagera el incumplimiento. Con `--sin-colapsar` se ve la otra.
    """
    fuera, vistos, lineas_ok = [], set(), 0
    try:
        # utf-8-sig y no utf-8: una marca de orden de bytes al principio del fichero hacia
        # que la primera linea no parseara. Las demas si, asi que el fichero NO se marcaba
        # ilegible y esa llamada desaparecia del recuento en silencio. Lo produce PowerShell
        # con Out-File y el Bloc de notas guardando en UTF-8.
        fh = io.open(path, encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    with fh:
        for ln in fh:
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            lineas_ok += 1
            msg = d.get("message")
            if not isinstance(msg, dict):
                continue        # `message` como lista: no es el formato que sabemos leer
            for b in (msg.get("content") or []):
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                if not isinstance(b.get("input", {}), dict):
                    continue    # `input` como texto: el bloque no dice que fichero toco
                bid = b.get("id")
                if isinstance(bid, (list, dict, set)):
                    bid = None  # no es hashable: se trata como bloque sin identificador
                if bid is not None:
                    if bid in vistos:
                        continue           # mismo bloque, otra linea de streaming
                    vistos.add(bid)
                inp = b.get("input") or {}
                a = accion_de(b.get("name") or "", inp, rx_shell, carpetas)
                if not a:
                    continue
                # El mismo `.replace` que en `accion_de`, y hay que arreglarlo en LOS DOS sitios:
                # la primera pasada de la ronda 10 cerro uno y este seguia reventando con un
                # `file_path` numerico. Arreglar la mitad de un defecto deja la otra mitad con
                # aspecto de estar arreglada, que es el patron que mas veces ha aparecido hoy.
                _fp = inp.get("file_path") or ""
                ruta = (_fp if isinstance(_fp, str) else "").replace("\\", "/").lower()
                # UNA ORDEN DE SHELL TAMBIEN TOCA FICHEROS, y hasta el 26/07/2026 no se miraba.
                # `python gate.py Libro/cap3.md` no trae `file_path`, asi que su lista de rutas
                # salia VACIA. Se noto al medir la lectura estricta: daba 0,0 % en todas las
                # reglas, y eso no era un hallazgo, era el instrumento midiendo el objeto
                # equivocado. Un cero que sale siempre no es una medida.
                rutas_extra = []
                if not ruta:
                    cmd = inp.get("command")
                    if isinstance(cmd, str):
                        rutas_extra = rutas_en_orden(cmd)
                propias = [ruta] if ruta else rutas_extra
                if colapsar and fuera and fuera[-1][0] == a:
                    for x in propias:
                        if x not in fuera[-1][1]:
                            fuera[-1][1].append(x)    # la racha guarda TODAS sus rutas
                    continue
                fuera.append((a, list(propias)))
    return fuera if lineas_ok else None


def cargar_acciones(path):
    """Las `acciones_shell` que declare el fichero de configuración, o None si no declara.

    Se lee aparte de las reglas para que `cargar_reglas` siga devolviendo una lista y no rompa a
    quien ya la llamaba, incluidos los casos del banco.
    """
    with io.open(path, encoding="utf-8-sig") as fh:
        datos = json.load(fh)
    return datos.get("acciones_shell") if isinstance(datos, dict) else None


def cargar_carpetas(path):
    """Las `carpetas_doctrina` que declare la configuración, validadas, o las de ejemplo.

    Se valida aquí y no al usarlas porque una carpeta mal escrita no revienta: deja su acción a
    cero para siempre, y un cero se lee como incumplimiento en vez de como configuración rota.
    """
    with io.open(path, encoding="utf-8-sig") as fh:
        datos = json.load(fh)
    if not isinstance(datos, dict) or "carpetas_doctrina" not in datos:
        return CARPETAS_DEFECTO
    car = datos["carpetas_doctrina"]
    if not isinstance(car, dict):
        raise ValueError("`carpetas_doctrina` tiene que ser un objeto con las claves `skill` y "
                         "`rag`, cada una con su lista de trozos de ruta")
    fuera = {}
    for clave in ("skill", "rag"):
        v = car.get(clave, [])
        if isinstance(v, str):
            # Una cadena es iterable y se recorreria LETRA A LETRA, casando cualquier ruta que
            # tenga una `s`. Mismo defecto que ya se cazo en `ambito`.
            raise ValueError("`carpetas_doctrina.%s` es texto y tiene que ser una LISTA de "
                             "textos: [\"%s\"]" % (clave, v))
        if not isinstance(v, list) or any(not isinstance(t, str) or not t.strip() for t in v):
            raise ValueError("`carpetas_doctrina.%s` tiene que ser una lista de trozos de ruta "
                             "no vacios" % clave)
        fuera[clave] = v
    return fuera


def _sin_claves_repetidas(pares):
    """Convierte los pares de un objeto JSON en dict, FALLANDO si alguna clave viene dos veces.

    JSON permite claves repetidas y `json.load` se queda con la ultima sin decir nada. En un
    fichero de configuracion eso es una perdida silenciosa: dos bloques `"reglas"` y solo se mide
    el segundo. Lo mismo dentro de una regla, donde una `"ventana"` repetida cambia la tasa.
    """
    vistas = set()
    repetidas = []
    for k, _ in pares:
        if k in vistas:
            repetidas.append(k)
        vistas.add(k)
    if repetidas:
        raise ValueError("clave repetida en el fichero de configuracion: %s. JSON lo permite y "
                         "el lector se queda con la ultima, asi que la primera desaparece sin "
                         "aviso: si son dos bloques de reglas, solo se mide uno."
                         % ", ".join(sorted(set(repetidas))))
    return dict(pares)


def cargar_reglas(path):
    """Lee las reglas del fichero de configuración y las valida. CA1 y CA5."""
    with io.open(path, encoding="utf-8-sig") as fh:
        crudo = fh.read()
    try:
        # LOS DOS GUARDAS DE AQUI SON DE LA RONDA 10 (26/07/2026) y los dos tapan un fallo que
        # sale por consola con aspecto de otra cosa.
        #
        # `object_pairs_hook` existe porque JSON PERMITE CLAVES REPETIDAS y `json.load` se queda
        # callado con la ultima. Un fichero con dos bloques `"reglas"` (lo normal al pegar una
        # configuracion debajo de otra) mide solo el segundo, y la mitad de las reglas desaparece
        # sin que nada lo diga. No hay forma de distinguirlo mirando la tabla: salen menos filas,
        # y menos filas es exactamente lo que se espera de un fichero con menos reglas.
        datos = json.loads(crudo, object_pairs_hook=_sin_claves_repetidas)
    except RecursionError:
        # Un JSON muy anidado revienta el parser con RecursionError, que NO es un ValueError, asi
        # que se escapaba del `except` de arriba y llegaba al usuario como traceback crudo con
        # codigo 1. El 1 esta documentado como "alguna regla por debajo de su umbral": en un CI,
        # un fichero ilegible y un incumplimiento real se leian igual.
        raise ValueError("%s esta anidado a demasiada profundidad para poder leerlo. No es una "
                         "regla incumplida: es un fichero que no se ha podido abrir." % path)
    reglas = datos.get("reglas") if isinstance(datos, dict) else datos
    if not isinstance(reglas, list) or not reglas:
        raise ValueError("%s no declara ninguna regla" % path)
    for i, r in enumerate(reglas):
        if not isinstance(r, dict):
            raise ValueError("la regla nº%d no es un objeto: %r. Cada regla es un diccionario "
                             "con al menos id, disparador y respuesta." % (i + 1, r))
    for r in reglas if isinstance(reglas, list) else []:
        if r.get("direccion") not in (None, "", "antes", "despues"):
            raise ValueError("regla %r: direccion debe ser 'antes' o 'despues'" % r.get("id", "?"))
    obligatorios = ("id", "disparador", "respuesta")
    for r in reglas:
        faltan = [k for k in obligatorios if not r.get(k)]
        if faltan:
            raise ValueError("regla %r sin los campos %s" % (r.get("id", "?"), ", ".join(faltan)))
    _valida_tipos(reglas)
    return reglas


# Que tipo tiene que tener cada campo, y como llamarlo al quejarse. Lo que NO esta aqui se ignora
# a proposito: una regla puede llevar campos de mas.
_TIPOS = {
    "id":         ((str,), "texto"),
    "disparador": ((str,), "texto"),
    "respuesta":  ((str,), "texto"),
    "desde":      ((str,), "texto con la fecha, como \"2026-07-01\""),
    "direccion":  ((str,), "texto"),
    "ventana":    ((int, float), "numero"),
    "umbral":     ((int, float), "numero"),
    "ambito":     ((list, tuple), "lista de textos"),
    "aviso":      ((str,), "texto"),
}


def _valida_tipos(reglas):
    """Rechaza un campo con el tipo equivocado ANTES de usarlo, y con el nombre de la regla dentro.

    POR QUE (25/07/2026, ronda 9). Un auditor probo cinco configuraciones con el tipo cambiado y
    las cinco reventaron con el traceback crudo de Python delante del usuario: `desde` como numero
    daba `AttributeError: 'int' object has no attribute 'split'`, `umbral` como texto reventaba a
    MITAD de la tabla dejandola truncada en pantalla, y `disparador` como lista daba `cannot use
    'list' as a set element`. Los cinco salian con codigo 1.

    El codigo 1 es lo peor del asunto. Esta documentado como "alguna regla por debajo de su
    umbral", o sea un incumplimiento legitimo: en un CI, una configuracion rota y una regla
    incumplida se leen igual. Lo que corresponde es el 2, que es "no se pudo medir".

    Los casos de VALOR ya estaban cubiertos (ambito como texto, ventana negativa, ids repetidos,
    regex invalida). Lo que faltaba era el TIPO, que es el escalon de antes.
    """
    for r in reglas:
        quien = r.get("id") if isinstance(r.get("id"), str) else "?"
        for campo, (tipos, nombre) in _TIPOS.items():
            if campo not in r or r[campo] is None:
                continue
            v = r[campo]
            if isinstance(v, bool) or not isinstance(v, tipos):
                raise ValueError(
                    "regla %r: el campo %r tiene que ser %s y viene %s (%r). Un campo con el tipo "
                    "cambiado no da error donde se escribe, sino mucho despues y en forma de "
                    "numero raro." % (quien, campo, nombre, type(v).__name__, v))
        # NI INFINITO NI NaN. Los dos son `float` y pasaban el chequeo de tipo, y luego
        # `int(inf)` lanza OverflowError a MITAD de imprimir la tabla, que es el mismo defecto que
        # este bloque dice haber cerrado para `umbral` como texto. `NaN` da ValueError.
        for campo in ("ventana", "umbral"):
            v = r.get(campo)
            if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
                raise ValueError("regla %r: %r vale %r, que no es un numero con el que se pueda "
                                 "medir nada" % (quien, campo, v))
        if isinstance(r.get("ambito"), (list, tuple)):
            malos = [z for z in r["ambito"] if not isinstance(z, str)]
            if malos:
                raise ValueError("regla %r: 'ambito' es una lista de textos y trae %r" %
                                 (quien, malos[0]))

        # UN `id` CON SALTO DE LINEA FALSIFICA UNA FILA DE LA TABLA (26/07/2026, ronda 10). La
        # tabla se imprime con `%-30s`, asi que un identificador con `\n` dentro parte la fila en
        # dos y la segunda mitad sale sin cifras: se lee como una regla mas que no midio nada. El
        # tabulador y el retorno de carro hacen lo mismo con las columnas. Nada de esto da error,
        # y no hay ningun uso legitimo: un identificador es una etiqueta de una linea.
        if isinstance(r.get("id"), str) and any(c in r["id"] for c in "\n\r\t"):
            raise ValueError("regla %r: el 'id' lleva un salto de linea o un tabulador dentro. La "
                             "tabla se alinea por columnas, asi que eso no da error: parte la fila "
                             "en dos y la mitad de abajo se lee como otra regla sin medir."
                             % r["id"].replace("\n", "\\n").replace("\t", "\\t"))

        # `"ventana": 6.9` SE TRUNCABA A 6 CALLANDO. El campo es un numero de pasos y el tipo
        # admite float porque un `6.0` escrito asi es legitimo. Un 6,9 no: no existe media llamada
        # a herramienta, y quien lo escribe espera 7 o espera un aviso, no un 6 silencioso que
        # mueve la tasa sin decirlo.
        for campo in ("ventana",):
            v = r.get(campo)
            if isinstance(v, float) and v == v and v not in (float("inf"), float("-inf")) \
                    and v != int(v):
                raise ValueError("regla %r: %r vale %r y se mide en pasos enteros. Se truncaba a "
                                 "%d sin avisar, que cambia la tasa en silencio."
                                 % (quien, campo, v, int(v)))

        # `umbral` SIN RANGO DEJABA PASAR UN 0,9 COMO "0 %". Es un porcentaje y se compara contra
        # una tasa que va de 0 a 100. Quien escribe 0.9 pensando en "el 90 %" obtiene un gate que
        # no salta nunca, y la tabla se lo enseña redondeado a "0 %", que parece un umbral puesto
        # a proposito. Por encima de 100 el gate salta siempre.
        u = r.get("umbral")
        if isinstance(u, (int, float)) and not isinstance(u, bool) and u == u:
            if not (0 <= u <= 100):
                raise ValueError("regla %r: 'umbral' es un porcentaje de 0 a 100 y vale %r. Fuera "
                                 "de ese rango el gate no salta nunca o salta siempre."
                                 % (quien, u))
            # Y EL TRAMO AMBIGUO, que es el que de verdad se cuela. Un `0.9` esta DENTRO del rango
            # (es un umbral del 0,9 %), asi que el chequeo de arriba no lo ve. Pero nadie pone un
            # gate al 0,9 %: quien escribe eso esta escribiendo una fraccion y quiere decir 90 %.
            # El resultado es un gate que no salta jamas, y la tabla lo imprime como "0 %", que se
            # lee como un umbral deliberadamente bajo. No se adivina cual de los dos queria: se
            # para y se le pregunta, que es lo unico honesto cuando las dos lecturas son posibles.
            if 0 < u < 1:
                raise ValueError("regla %r: 'umbral' vale %r y no se puede adivinar que quieres. "
                                 "Como porcentaje es 0,9 %%, un gate que no salta nunca y que la "
                                 "tabla imprime como '0 %%'. Si querias el %d %%, escribe %d."
                                 % (quien, u, round(u * 100), round(u * 100)))


_CACHE_FECHA = {}


def fecha_de_sesion(path):
    """Momento de la sesion, sacado de DENTRO del fichero y no de su fecha en disco.

    LO ENCONTRO UN USUARIO DE PRUEBA (25/07/2026), y es el fallo mas caro de los que quedaban.
    Se usaba `os.path.getmtime`, que es la fecha del FICHERO: un `git clone`, una copia de carpeta
    o una restauracion de backup la ponen a hoy, y entonces `desde` deja fuera sesiones que si
    contaban y `--por-dia` amontona meses de trabajo en un solo dia. Sin error, sin aviso, con la
    tabla saliendo igual de convincente.

    Los transcripts traen `timestamp` ISO en sus registros. Se coge el PRIMERO que aparezca, que
    es cuando empezo la sesion. Si el fichero no trae ninguno (formato antiguo, o de juguete), se
    vuelve al mtime, que es lo unico que queda, y `fecha_es_del_fichero` lo dice para que el
    llamador pueda avisar en vez de callar.
    """
    if path in _CACHE_FECHA:
        return _CACHE_FECHA[path]
    ts = None
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as fh:
            for i, linea in enumerate(fh):
                if i > 400:            # si en 400 registros no hay fecha, no la hay
                    break
                if '"timestamp"' not in linea:
                    continue
                try:
                    crudo = json.loads(linea).get("timestamp")
                except ValueError:
                    continue
                if not crudo:
                    continue
                try:
                    limpio = str(crudo).replace("Z", "+00:00")
                    ts = datetime.datetime.fromisoformat(limpio).timestamp()
                except ValueError:
                    continue
                if ts:
                    break
    except OSError:
        ts = None
    propia = ts is None
    if ts is None:
        try:
            ts = os.path.getmtime(path)
        except OSError:
            ts = None
    _CACHE_FECHA[path] = (ts, propia)
    return _CACHE_FECHA[path]


def en_ambito(rutas, ambito):
    """True si alguna de las rutas de la racha cae dentro del ambito declarado.

    Dos correcciones que salieron de una sonda externa el 25/07:

      * Se miran TODAS las rutas de la racha, no solo la primera. Al colapsar repeticiones, una
        escritura a `notes/` seguida de otra a `docs/` se fundia en una sola y se quedaba con la
        primera, asi que un ambito de `docs/` descartaba una ocasion que si contaba.
      * El trozo tiene que empezar en un LIMITE de ruta. Antes bastaba con aparecer en cualquier
        posicion, y `docs/` casaba con `/mydocs/interno.md`: la regla salia alta midiendo
        exactamente los ficheros equivocados.
    """
    for ruta in rutas:
        for z in ambito:
            # El trozo se normaliza igual que la ruta. Sin esto, un `Docs/` escrito con mayuscula
            # o un `docs\\` con separador de Windows no casaban nunca y descartaban ocasiones sin
            # una sola queja: el aviso de filtrado solo salta cuando se descarta TODO.
            z = z.replace("\\", "/").lower()
            if not z:
                continue
            desde = 0
            while True:
                i = ruta.find(z, desde)
                if i < 0:
                    break
                desde = i + 1
                izq = i == 0 or ruta[i - 1] == "/" or z.startswith("/")
                fin = i + len(z)
                # El punto valia como frontera y dejaba pasar `/docs.old/`. Solo cierra si
                # lo que sigue es una barra, o si estamos al final del NOMBRE del fichero.
                der = (z.endswith("/") or fin == len(ruta) or ruta[fin] == "/"
                       or (ruta[fin] == "." and "/" not in ruta[fin:]))
                if izq and der:
                    return True
    return False


def _fecha(txt):
    y, m, d = (int(x) for x in txt.split("-"))
    return datetime.datetime(y, m, d).timestamp()


# Las secuencias ya parseadas, compartidas entre llamadas a `medir`. Parsear el historial es lo
# unico caro que hace esto, y las vistas que comparan parametros llaman a `medir` decenas de veces
# sobre los MISMOS ficheros.
_CACHE_SECUENCIAS = {}


# LA FOTO DEL HISTORIAL, tomada una vez y declarada (25/07/2026). Aqui hubo dos intentos fallidos
# y los dos merecen quedar escritos, porque son la misma leccion por dos caminos.
#
# El primero indexaba el cache por (mtime_ns, tamaño). Un escéptico lo rompio con un experimento
# que hay que citar entero: de 2.000 reescrituras rapidas del mismo fichero con tamaño constante,
# 1.665 compartieron firma con una anterior, porque la resolucion del reloj del sistema de ficheros
# no llega. Con la firma repetida, el cache servia el contenido VIEJO como si fuera el nuevo, sin
# un aviso. Es justo el fallo que esta herramienta persigue en otros, dentro de ella misma.
#
# El segundo hasheaba el contenido en CADA consulta al cache. Correcto y carisimo: la curva de
# ventanas paso de 6 a 43 segundos, porque hacia 1.392 lecturas completas donde hacen falta 58.
#
# Lo que se hace ahora: el hash de cada fichero se calcula UNA vez por ejecucion. Eso convierte el
# cache en lo que siempre debio ser, una FOTO coherente del historial: todas las vistas miden el
# mismo estado en vez de mezclar lecturas de momentos distintos, que era el defecto de fondo. Si
# el fichero cambia a mitad, la medicion no se entera, y eso ES el comportamiento correcto: mezclar
# dos versiones dentro de la misma tabla daria una cifra que no corresponde a ningun momento real.
# Quien use esto como libreria y quiera volver a mirar, llama a `refrescar_foto()`.
def refrescar_foto():
    """Olvida el historial leido. Lo necesita quien mida dos veces en el mismo proceso.

    La medicion trabaja sobre una FOTO: cada fichero se lee y se parsea una vez, y todas las
    vistas miden ese mismo estado. Si un transcript cambia a mitad, la tabla no se entera, y eso
    es lo correcto: mezclar dos versiones dentro de la misma tabla daria una cifra que no
    corresponde a ningun momento real. Quien quiera volver a mirar, llama aqui.

    AQUI HUBO DOS INTENTOS FALLIDOS y los dos merecen quedar escritos. El primero indexaba el
    cache por (mtime_ns, tamaño); un escéptico lo rompio midiendo 2.000 reescrituras rapidas del
    mismo fichero con tamaño constante, de las que 1.665 compartieron firma con una anterior
    porque la resolucion del reloj del sistema de ficheros no llega: el cache servia el contenido
    VIEJO sin un aviso. El segundo hasheaba el contenido en cada consulta, correcto y carisimo: la
    curva de ventanas paso de 6 a 43 segundos. El tercero cacheaba ese hash, y entonces UNA
    MUTACION enseño que quitarlo de la clave no rompia ningun caso, o sea que no hacia nada. La
    coherencia no la daba el hash: la da esta funcion.
    """
    _CACHE_SECUENCIAS.clear()


def _clave_cache(path, colapsar, rx_shell, carpetas):
    """Clave por CONTENIDO, nunca por `id()`.

    El primer intento usaba `id(rx_shell)`, y Python recicla identificadores en cuanto un objeto
    se libera: dos configuraciones distintas podian compartir numero y una recibia la secuencia de
    la otra. Lo cazo el propio banco a los dos minutos, con dos casos de ambito que empezaron a
    fallar sin que nadie los tocara. Un cache mal indexado no es lento: es incorrecto, y devuelve
    numeros creibles.
    """
    rx = tuple((n, r.pattern) for n, r in (rx_shell or RX_SHELL))
    car = CARPETAS_DEFECTO if carpetas is None else carpetas
    cp = tuple(sorted((k, tuple(v)) for k, v in car.items()))
    # El hash NO va en la clave, y esto lo dijo una mutacion. Quitarlo de aqui no rompia ningun
    # caso, o sea que no hacia nada: la coherencia no la da la clave, la da la FOTO, que se toma
    # una vez y se refresca a mano con `refrescar_foto()`. Mantener un hash por fichero para
    # decorar una clave es coste sin funcion, y encima da la impresion de una proteccion que no
    # existe. Se calcula igual al tomar la foto, para saber que se ha leido cada fichero entero.
    return (path, bool(colapsar), rx, cp)


def medir(paths, reglas, colapsar=True, rx_shell=None, acciones=None, carpetas=None,
          estricto=False):
    """Por regla: disparadores, cumplidos, tasa y sesiones ilegibles.

    La tasa es None cuando no hubo disparadores. Cero de cero no es 0 % ni 100 %: es que no se pudo
    mirar, y confundirlo con un cero es el error que este proyecto persigue en todos sus gates.
    """
    # CA5: fallar ruidosamente, no en silencio. Los tres casos de abajo salieron probando limites
    # el 25/07 y los tres pasaban callando, que es la forma mas cara de estar mal.
    vistos_id = set()
    for r in reglas:
        for campo in ("disparador", "respuesta"):
            validas = acciones or ACCIONES
            if r[campo] not in validas:
                raise ValueError("la regla %r usa la accion desconocida %r. Conocidas: %s"
                                 % (r["id"], r[campo], ", ".join(sorted(validas))))
        # Un `ambito` escrito como cadena en vez de lista es el peor de los tres: `any(z in ruta
        # for z in "manuales/")` itera por CARACTERES, asi que filtra segun si la ruta contiene una
        # "m" o una "/". Da resultados sin sentido y no se queja.
        if r.get("ambito") is not None and isinstance(r["ambito"], str):
            raise ValueError("la regla %r declara `ambito` como texto. Tiene que ser una LISTA: "
                             "una cadena se recorre por caracteres y filtra al azar." % r["id"])
        try:
            v = int(r.get("ventana", 6))
        except (TypeError, ValueError):
            raise ValueError("la regla %r tiene una ventana no numerica: %r" % (r["id"], r.get("ventana")))
        if v < 1:
            raise ValueError("la regla %r tiene ventana %d. Con cero o menos no se mira nada y la "
                             "tasa sale 0 %% sin decir por que." % (r["id"], v))
        if r["id"] in vistos_id:
            raise ValueError("hay dos reglas con el id %r: en la tabla saldrian como filas gemelas "
                             "sin poder distinguirlas." % r["id"])
        vistos_id.add(r["id"])

    # EL CACHE VIVE FUERA, Y NO ES UN DETALLE (25/07/2026). Estaba aqui dentro, o sea que moria en
    # cada llamada. La vista normal llama a `medir` una vez y no se notaba nada; `--curva-ventana`
    # la llama ocho veces por regla y `--sensibilidad` mas, asi que cada una volvia a parsear los
    # 58 ficheros del historial ENTEROS. Medido por un usuario de prueba contra su historial real:
    # 177 segundos la curva frente a menos de 2 la tabla normal, y la documentacion recomienda la
    # curva como la vista que mas enseña. Un instrumento que tarda tres minutos no se usa.
    #
    # La clave lleva los parametros que cambian el parseo. `ventana` y `desde` no estan porque no
    # intervienen: filtran DESPUES, sobre la secuencia ya construida, que es justo lo que permite
    # reaprovecharla entre ventanas distintas.
    cache = _CACHE_SECUENCIAS
    salida = []
    for r in reglas:
        corte = _fecha(r["desde"]) if r.get("desde") else 0.0
        ventana = int(r.get("ventana", 6))
        disp = cumpl = ilegibles = filtrados = 0
        for p in paths:
            if corte:
                ts, _ = fecha_de_sesion(p)
                if ts is None or ts < corte:
                    continue
            clave = _clave_cache(p, colapsar, rx_shell, carpetas)
            if clave not in cache:
                cache[clave] = secuencia_de(p, colapsar, rx_shell, carpetas)
            seq = cache[clave]
            if seq is None:
                ilegibles += 1
                continue
            ambito = r.get("ambito") or []
            acciones = [x[0] for x in seq]
            for i, (a, rutas) in enumerate(seq):
                if a != r["disparador"]:
                    continue
                if ambito and not en_ambito(rutas, ambito):
                    filtrados += 1                 # cae fuera del alcance declarado
                    continue
                disp += 1
                # DIRECCION (25/07/2026). Muchas obligaciones del proyecto son "haz X ANTES de Y",
                # no "despues de X haz Y": escanear los repos antes de publicar, buscar antes de
                # afirmar que algo no existe, planificar antes de construir. Con solo la mirada
                # hacia adelante esas reglas salen hundidas y el numero no significa nada. Se vio
                # midiendo el escaner de repos, que daba 7,7 % por estar planteado al reves.
                if r.get("direccion") == "antes":
                    ventana_vista = acciones[max(0, i - ventana):i]
                else:
                    ventana_vista = acciones[i + 1:i + 1 + ventana]
                # ¿VALE CUALQUIER RESPUESTA, O SOLO LA QUE CAE EN EL MISMO AMBITO?
                #
                # Hasta el 26/07/2026 la ventana solo miraba NOMBRES de accion, sin ruta: escribir
                # `Libro/cap3.md` y pasar el gate sobre OTRO fichero cualquiera contaba como
                # cumplido. El `ambito` filtraba el disparador y NUNCA la respuesta. Lo encontro
                # una auditoria y no estaba declarado en ningun sitio; buscado en el corpus con
                # `consultar.py` antes de afirmarlo.
                #
                # NO se cambia el valor por defecto. Mover el criterio despues de ver el resultado
                # es mover la metrica post-hoc, que es justo lo que este instrumento predica contra.
                # Se anade como MEDIDA de sensibilidad: `--respuesta-en-ambito` da la lectura
                # estricta y la diferencia entre las dos dice cuanto pesaba el supuesto.
                if estricto and ambito:
                    tramo = (seq[max(0, i - ventana):i] if r.get("direccion") == "antes"
                             else seq[i + 1:i + 1 + ventana])
                    if any(acc == r["respuesta"] and en_ambito(rt, ambito) for acc, rt in tramo):
                        cumpl += 1
                elif r["respuesta"] in ventana_vista:
                    cumpl += 1
        salida.append({"id": r["id"], "disparador": r["disparador"], "respuesta": r["respuesta"],
                       "fuente": r.get("fuente", ""), "umbral": r.get("umbral"),
                       "disparadores": disp, "cumplidos": cumpl, "ilegibles": ilegibles,
                       "filtrados_por_ambito": filtrados,
                       "tasa": (100.0 * cumpl / disp) if disp else None})
    return salida


def sesiones_en(raiz, subagentes=False):
    """Transcripts de la conversacion PRINCIPAL, sin los de subagentes.

    La estructura de disco es `projects/<proyecto>/<sesion>.jsonl`, y colgando de ahi las sesiones
    de cada subagente. Asi que hay dos formas legitimas de apuntar: a un proyecto concreto o a la
    raiz que los contiene a todos. Sin este segundo caso, ejecutar el instrumento SIN argumentos
    fallaba con "no hay transcripts", que es el defecto que aparecio el 25/07 al probar los codigos
    de salida. Un instrumento que no arranca de fabrica no lo usa nadie.
    """
    if not subagentes:
        try:
            aqui = sorted(os.path.join(raiz, f) for f in os.listdir(raiz) if f.endswith(".jsonl"))
        except OSError:
            return []
        if aqui:
            return aqui
        fuera = []                                    # la raiz no es un proyecto: baja UN nivel
        for d in sorted(os.listdir(raiz)):
            sub = os.path.join(raiz, d)
            if not os.path.isdir(sub):
                continue
            try:
                fuera += [os.path.join(sub, f) for f in sorted(os.listdir(sub))
                          if f.endswith(".jsonl")]
            except OSError:
                continue
        return fuera
    fuera = []
    for base, _, ficheros in os.walk(raiz):
        for f in ficheros:
            if f.endswith(".jsonl"):
                fuera.append(os.path.join(base, f))
    return sorted(fuera)


def _veredicto(res):
    """0 si todas las reglas con umbral lo cumplen, 1 si alguna no.

    Vive aparte porque las tres vistas tienen que dar el MISMO veredicto. Antes solo la tabla por
    defecto miraba los umbrales y las otras dos salian siempre en 0: quien pusiera `--por-dia` en
    un paso de CI se quedaba sin gate sin enterarse.
    """
    bajos = [r for r in res if r.get("umbral") is not None and r.get("tasa") is not None
             and r["tasa"] < r["umbral"]]
    if bajos:
        print("\nPor debajo de su umbral: %s" % ", ".join(r["id"] for r in bajos))
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--sesiones", default=SESIONES_DEFECTO)
    ap.add_argument("--reglas", default=REGLAS_DEFECTO)
    ap.add_argument("--sin-colapsar", action="store_true",
                    help="cuenta cada escritura en vez de cada racha (denominador mayor)")
    ap.add_argument("--subagentes", action="store_true",
                    help="incluye las sesiones de subagentes, que son otro universo")
    # `default=None` y no `0` a proposito (26/07/2026). Con el cero por defecto, `--por-dia 0` era
    # indistinguible de no haber pedido la vista, y caia a la tabla normal callando.
    ap.add_argument("--por-dia", type=int, default=None, metavar="N",
                    help="desglosa los ultimos N dias: una tasa global esconde si la regla se "
                         "cumplio el dia que se implanto y se olvido despues")
    ap.add_argument("--respuesta-en-ambito", action="store_true",
                    dest="respuesta_en_ambito",
                    help="exige que la respuesta caiga en el MISMO ambito que el disparador. Por "
                         "defecto vale cualquiera, que es el supuesto mas grande del instrumento")
    ap.add_argument("--sensibilidad", action="store_true",
                    help="cuanto mueve la cifra CADA decision arbitraria del instrumento: la "
                         "ventana, el colapso de rachas y la muestra minima. Si al cambiarlas se "
                         "mueve mas que la diferencia que quieres defender, esa cifra no aguanta")
    ap.add_argument("--curva-ventana", action="store_true",
                    help="muestra como cambia la tasa con la ventana: sin esto, un numero suelto "
                         "esconde que el parametro lo mueve casi 30 puntos")
    ap.add_argument("--json", action="store_true", help="salida en JSON para encadenar")
    ap.add_argument("--acciones", action="store_true",
                    help="vuelca las acciones detectadas en TU historial, con su frecuencia. "
                         "Es por donde se empieza: sin saber que hay, no se puede declarar una regla")
    args = ap.parse_args(argv)

    # UN FLAG QUE DESAPARECE EN SILENCIO ES LO CONTRARIO DE FALLAR RUIDOSAMENTE (25/07/2026).
    # `--sensibilidad --json` imprimia la tabla humana y se tragaba el `--json` sin decir nada,
    # con exit 0. Quien lo encadenara a otra cosa recibia texto donde esperaba JSON. El resto del
    # programa presume de quejarse ante una configuracion mala; esto era la excepcion.
    # UN NUMERO NEGATIVO AQUI DABA UNA TABLA PLAUSIBLE Y FALSA (25/07/2026). `--por-dia -3` hacia
    # `sorted(dias)[3:]`, o sea DESCARTAR los tres dias mas antiguos y enseñar todos los demas, con
    # exit 0 y una cabecera que decia "ultimos 32 dias" cuando se habian pedido 3. La skill presume
    # de fallar ruidosamente ante una ventana negativa, pero esa garantia era solo para el campo de
    # la regla, no para este flag. Lo encontro un usuario de prueba probando lo que a nadie se le
    # habia ocurrido.
    # El cero va con el negativo (26/07/2026, ronda 10) y no estaba. `0` es el valor por defecto,
    # asi que `--por-dia 0` no se distinguia de no haber pedido la vista: el flag se evaluaba como
    # falso, la vista no salia y aparecia LA TABLA NORMAL, en silencio y con exit 0. Quien lo
    # escriba en un script cree estar viendo el desglose por dias y esta viendo el agregado. Es el
    # mismo fallo que el negativo, con la diferencia de que el negativo al menos era raro de
    # teclear; el cero sale solo de una variable vacia: `--por-dia $DIAS` con `DIAS` sin definir.
    if args.por_dia is not None and args.por_dia <= 0:
        print("`--por-dia` pide cuantos dias enseñar, asi que %d no significa nada. Ni el negativo\n"
              "ni el cero fallaban: el negativo daba una tabla con MAS dias de los pedidos y el\n"
              "cero devolvia la tabla normal como si no hubieras pedido nada. Las dos cosas son\n"
              "peores que un error, porque salen bien." % args.por_dia, file=sys.stderr)
        return 2

    # EL INSTRUMENTO SABOTEADO NO MIDE, AVISA Y PARA (26/07/2026, ronda 10). `mutar.py` deja una
    # copia intacta en disco mientras hay un sabotaje puesto, y la borra al restaurar. Si esa copia
    # sigue ahi, este fichero ESTA MUTADO: una ejecucion anterior no llego a su restauracion,
    # normalmente porque mataron el proceso. Hasta hoy, medir en ese estado daba una tabla entera,
    # con exit 0 y sin una palabra: numeros creibles salidos de un motor roto a proposito. Es el
    # peor resultado posible de esta herramienta, y el mas facil de creerse.
    residuo = os.path.abspath(__file__) + ".original"
    if os.path.exists(residuo):
        print("PARA: hay un %s en disco, o sea que este fichero esta MUTADO.\n"
              "Una pasada de mutar.py no llego a restaurarlo (proceso interrumpido). Cualquier\n"
              "cifra que salga ahora viene de un motor saboteado a proposito y parecera normal.\n"
              "Restaura con: python mutar.py   (rescata el residuo antes de empezar)."
              % os.path.basename(residuo), file=sys.stderr)
        return 2

    vistas = [n for n, v in (("--por-dia", args.por_dia is not None),
                             ("--curva-ventana", args.curva_ventana),
                             ("--sensibilidad", args.sensibilidad), ("--acciones", args.acciones))
              if v]
    if args.json and vistas:
        print("`--json` solo vale para la tabla normal. %s imprime su propia vista y no tiene\n"
              "equivalente en JSON, asi que pedir las dos cosas a la vez daria texto donde\n"
              "esperas datos. Quita una de las dos." % ", ".join(vistas), file=sys.stderr)
        return 2
    if len(vistas) > 1:
        print("Pediste %s a la vez y cada una imprime una vista distinta. Elige una."
              % " y ".join(vistas), file=sys.stderr)
        return 2


    try:
        reglas = cargar_reglas(args.reglas)
        # El mapa de acciones sale del MISMO fichero que las reglas: quien declara una regla sobre
        # "haber pasado el linter" tiene que poder decir en el mismo sitio como se llama su linter.
        declaradas = cargar_acciones(args.reglas)
        rx_shell, acciones = compilar_acciones_shell(declaradas)
        ampliadas = nombres_ampliados(declaradas)
        # Y las carpetas que en ESTE proyecto son doctrina, por lo mismo: quien tenga sus normas
        # en `docs/politicas/` no puede depender de que aqui pusieramos `skills/`.
        carpetas = cargar_carpetas(args.reglas)
    except (OSError, ValueError) as e:
        print("No se pudieron cargar las reglas: %s" % e, file=sys.stderr)
        return 2

    # La virgulilla la expande bash, no PowerShell ni cmd. Sin esto, el comando que el README
    # enseña en portada fallaba en Windows con un mensaje que ademas sonaba a historial vacio.
    args.sesiones = os.path.expanduser(args.sesiones)
    paths = sesiones_en(args.sesiones, args.subagentes)
    if not paths:
        print("No hay transcripts en %s. No es un cero: es que no se pudo mirar." % args.sesiones,
              file=sys.stderr)
        return 2

    # SIN `--sesiones` SE LEE TODO, Y ESO HAY QUE DECIRLO (25/07/2026). Un usuario de prueba
    # ejecuto la herramienta sin acotar y le salieron rutas de un proyecto que no tenia nada que
    # ver con el que queria medir. El valor por defecto es la carpeta de TODOS los proyectos, asi
    # que la tabla mezcla historiales distintos y las tasas dejan de significar lo que uno cree.
    # A veces es lo que se busca; casi nunca es lo que se espera la primera vez.
    # El aviso mira lo que HAY, no como se llego. Antes solo saltaba con la ruta por defecto,
    # asi que apuntar a una copia del historial con varios proyectos dentro mezclaba callando.
    if True:
        proyectos = sorted(set(os.path.basename(os.path.dirname(p)) for p in paths))
        if len(proyectos) > 1:
            # SIN LOS NOMBRES, y esto es una correccion de la ronda 10. Las carpetas de
            # `~/.claude/projects` NO son etiquetas: son la ruta de trabajo de cada proyecto
            # codificada, asi que decirlas publica en que trabaja quien ejecuta esto. Un auditor
            # lo enseño con un historial fabricado y salio
            # `C--Users-EncarnacionVillalobos-clientes-DESPIDO-CONFIDENCIAL` por las SEIS vistas,
            # incluida la tabla normal. Contradecia lo que el README acababa de prometer en ese
            # mismo commit: que fuera de `--acciones` la promesa es entera.
            #
            # El aviso sigue haciendo falta, porque mezclar proyectos falsea las tasas. Lo que no
            # hace falta es nombrarlos: el numero ya dice que hay mas de uno, y quien quiera
            # saber cuales mira su propia carpeta.
            print("  Leyendo %d sesiones de %d proyectos a la vez. Sin --sesiones se mide TODO"
                  % (len(paths), len(proyectos)), file=sys.stderr)
            print("  el historial junto, y las tasas mezclan proyectos distintos.", file=sys.stderr)

    # AMPLIAR NO ES SUSTITUIR, Y CALLARLO ES LO QUE HACE DAÑO (25/07/2026). Quien declara un
    # nombre que ya existe suele creer que lo esta reemplazando, porque eso prometia el README.
    # Lo que pasa es que su patron va delante y el de fabrica sigue detras, asi que una llamada
    # que case con los dos se contara por el suyo y una que solo case con el de fabrica se
    # contara igual que antes. Es util, pero no es lo que uno espera, y sin decirlo se descubre
    # mirando una tasa que no cuadra.
    if ampliadas:
        print("  Ampliando accion(es) de fabrica: %s. Tu patron va delante, pero el de fabrica "
              "sigue" % ", ".join(ampliadas), file=sys.stderr)
        print("  detras: lo que no case con el tuyo se seguira contando con el suyo.",
              file=sys.stderr)

    if args.acciones:
        # POR DONDE SE EMPIEZA (25/07/2026). Lo pidio un analisis externo y tiene razon: para
        # declarar una regla hay que saber que verbos existen EN TU historial, y hasta ahora eso
        # solo se averiguaba leyendo el codigo o por prueba y error. Aqui no hay reglas ni tasas:
        # solo el inventario de lo que hay, que es lo primero que uno necesita ver.
        import collections
        cuenta = collections.Counter()
        muestras = {}
        for p_ in paths:
            seq = secuencia_de(p_, not args.sin_colapsar, rx_shell, carpetas)
            for a, rutas in (seq or []):
                cuenta[a] += 1
                if a not in muestras and rutas:
                    muestras[a] = rutas[0]
        if not cuenta:
            print("Ninguna accion reconocida en %d sesion(es). No es un cero: es que no habia "
                  "llamadas a herramienta que traducir." % len(paths))
            return 2
        print("=" * 76)
        print("ACCIONES DETECTADAS EN TU HISTORIAL  --  %d sesiones" % len(paths))
        print("=" * 76)
        print("  %-24s %8s   %s" % ("accion", "veces", "ejemplo"))
        print("  " + "-" * 72)
        for a, n in cuenta.most_common():
            print("  %-24s %8d   %s" % (a, n, (muestras.get(a) or "")[:40]))
        print()
        print("Estas son las que puedes usar como `disparador` y como `respuesta` en reglas.json.")
        print("Si tu linter, tu desplegador o tu generador no aparecen aqui, es que nadie los ha")
        print("declarado todavia: anadelos en `acciones_shell` con su patron y vuelve a mirar.")
        print("Una accion con MUCHAS apariciones dentro de `shell` suele ser una que merece nombre.")
        # EL VEREDICTO TAMBIEN AQUI (26/07/2026, ronda 10). Esta vista devolvia 0 pasara lo que
        # pasara, y `_veredicto` existe justamente porque las vistas tienen que coincidir: cuando
        # solo la tabla por defecto miraba los umbrales, quien ponia `--por-dia` en un CI se
        # quedaba sin gate sin enterarse. `--acciones` era la que faltaba, y era la peor de las
        # cuatro, porque el README la titula "por aqui se empieza": es la primera que alguien mete
        # en un script. Un cero que significa "he impreso una tabla" y un cero que significa
        # "ninguna regla esta por debajo de su umbral" no se distinguen desde fuera.
        try:
            res_ = medir(paths, reglas, colapsar=not args.sin_colapsar, rx_shell=rx_shell,
                         acciones=acciones, carpetas=carpetas)
        except ValueError as e:
            print("Regla mal declarada: %s" % e, file=sys.stderr)
            return 2
        return _veredicto(res_)

    try:
        res = medir(paths, reglas, colapsar=not args.sin_colapsar, rx_shell=rx_shell,
                    acciones=acciones, carpetas=carpetas, estricto=args.respuesta_en_ambito)
    except ValueError as e:
        print("Regla mal declarada: %s" % e, file=sys.stderr)
        return 2

    if args.por_dia is not None:
        # POR QUE EXISTE (25/07/2026). La tasa global de la puerta era 62,7 %, y desglosada por dia
        # aparecio lo que el agregado tapaba: 85 % el 22/07, que es el dia en que se cableo, y 25 %
        # al dia siguiente. Una regla nueva se cumple mientras se recuerda. Eso no se ve en un
        # numero unico, y es justo lo que hay que saber para decidir si necesita mecanismo.
        import collections, datetime as _dt
        por_dia = collections.defaultdict(list)
        sin_fecha_propia = 0
        for p_ in paths:
            ts_, del_fichero = fecha_de_sesion(p_)
            if ts_ is None:
                continue
            if del_fichero:
                sin_fecha_propia += 1
            d_ = _dt.datetime.fromtimestamp(ts_).strftime("%Y-%m-%d")
            por_dia[d_].append(p_)
        dias = sorted(por_dia)[-args.por_dia:]
        print("=" * 76)
        print("ADHERENCIA POR DIA  --  ultimos %d dias con sesiones" % len(dias))
        print("=" * 76)
        # Truncar a 20 hacia que dos reglas con el mismo prefijo dieran columnas identicas con
        # valores opuestos. Se numeran y se lista la correspondencia debajo.
        etiquetas = ["%d %s" % (i + 1, r["id"][:18]) for i, r in enumerate(reglas)]
        print("  %-12s %7s  %s" % ("dia", "sesion", "  ".join("%-20s" % e for e in etiquetas)))
        for d_ in dias:
            fila = []
            for r0 in reglas:
                rr = medir(por_dia[d_], [dict(r0, desde="")], colapsar=not args.sin_colapsar,
                           rx_shell=rx_shell, acciones=acciones, carpetas=carpetas)[0]
                if rr["tasa"] is None:
                    fila.append("  n/d")
                else:
                    fila.append("%3.0f %% (%d)%s" % (rr["tasa"], rr["disparadores"],
                                "*" if rr["disparadores"] < MUESTRA_MINIMA else ""))
            print("  %-12s %7d  %s" % (d_, len(por_dia[d_]), "  ".join("%-20s" % x for x in fila)))
        print()
        print("Entre parentesis, cuantas ocasiones hubo ese dia. Un 100 % de una sola ocasion no")
        print("es una tendencia; la columna de ocasiones esta para no confundirlos.")
        if len(reglas) > 1:
            print()
            for i, r in enumerate(reglas):
                print("  %d = %s" % (i + 1, r["id"]))
        if sin_fecha_propia:
            print()
            print("  AVISO: %d sesion(es) no traen fecha dentro y se han datado por la fecha del"
                  % sin_fecha_propia)
            print("  FICHERO. Si ese historial se ha copiado o clonado, esa fecha es la de la copia")
            print("  y este desglose por dia no significa nada.")
        return _veredicto(res)

    if args.curva_ventana:
        # POR QUE ESTA OPCION EXISTE (25/07/2026). Probando la sensibilidad del parametro salio que
        # la tasa de la puerta va del 49,7 % con ventana 2 al 83,0 % con ventana 40, sobre los
        # MISMOS datos. Un numero suelto oculta que una eleccion arbitraria lo mueve casi treinta
        # puntos. Quien publique una tasa deberia poder enseñar su curva.
        ventanas = (2, 3, 4, 6, 8, 12, 20, 40)
        print("=" * 76)
        print("SENSIBILIDAD A LA VENTANA  --  la misma regla con distinto plazo de respuesta")
        print("=" * 76)
        print("  %-30s %s" % ("regla", "  ".join("v=%-4d" % v for v in ventanas)))
        for r0 in reglas:
            fila = []
            for v in ventanas:
                rr = medir(paths, [dict(r0, ventana=v)], colapsar=not args.sin_colapsar,
                           rx_shell=rx_shell, acciones=acciones, carpetas=carpetas)[0]
                fila.append("  n/d " if rr["tasa"] is None else "%5.1f" % rr["tasa"])
            print("  %-30s %s" % (r0["id"][:30], "  ".join("%-6s" % x for x in fila)))
        print()
        print("Si la fila se mueve mucho, el numero que publiques depende del plazo que elijas.")
        return _veredicto(res)

    if args.sensibilidad:
        # LA PREGUNTA GENERALIZADA (25/07/2026). `ventana` recibio su curva porque alguien se quejo
        # de ella en concreto. Una auditoria del RAZONAMIENTO de la jornada, no de sus defectos,
        # pregunto lo siguiente: que OTROS numeros de esta herramienta son un umbral elegido a ojo
        # y publicado sin su sensibilidad. Habia dos mas, y ninguna de las cuatro rondas de
        # revision los toco, porque cada ronda reacciono a una queja concreta y nadie generalizo.
        # Esta vista existe para que no haya un cuarto.
        print("=" * 76)
        print("SENSIBILIDAD  --  cuanto mueve la cifra cada decision arbitraria")
        print("=" * 76)

        ventanas = (2, 3, 4, 6, 8, 12, 20, 40)
        print()
        print("  1. VENTANA: en cuantos pasos vale la respuesta. Por defecto 6.")
        print("     %-28s %s" % ("regla", "  ".join("v=%-4d" % v for v in ventanas)))
        for r0 in reglas:
            fila = []
            for v in ventanas:
                rr = medir(paths, [dict(r0, ventana=v)], colapsar=not args.sin_colapsar,
                           rx_shell=rx_shell, acciones=acciones, carpetas=carpetas)[0]
                fila.append("  n/d " if rr["tasa"] is None else "%5.1f" % rr["tasa"])
            print("     %-28s %s" % (r0["id"][:28], "  ".join("%-6s" % x for x in fila)))

        print()
        print("  2. COLAPSAR: una racha de escrituras seguidas, una ocasion o varias.")
        print("     %-28s %-14s %-14s" % ("regla", "colapsando", "cada una"))
        for r0 in reglas:
            fila = []
            for col in (True, False):
                rr = medir(paths, [r0], colapsar=col, rx_shell=rx_shell, acciones=acciones,
                           carpetas=carpetas)[0]
                fila.append("n/d" if rr["tasa"] is None
                            else "%5.1f %% (%d)" % (rr["tasa"], rr["disparadores"]))
            print("     %-28s %-14s %-14s" % (r0["id"][:28], fila[0], fila[1]))
        print("     Por defecto se colapsa, que es la lectura conservadora: menos denominador y")
        print("     por tanto menos exageracion del incumplimiento. `--sin-colapsar` da la otra.")

        print()
        print("  2-bis. LA RESPUESTA, ¿en el MISMO ambito que el disparador o en cualquiera?")
        print("     %-28s %-14s %-14s" % ("regla", "cualquiera", "mismo ambito"))
        hay_ambito = False
        for r0 in reglas:
            if not (r0.get("ambito") or []):
                continue
            hay_ambito = True
            fila = []
            for est in (False, True):
                rr = medir(paths, [r0], rx_shell=rx_shell, acciones=acciones,
                           carpetas=carpetas, estricto=est)[0]
                fila.append("n/d" if rr["tasa"] is None
                            else "%5.1f %% (%d)" % (rr["tasa"], rr["disparadores"]))
            print("     %-28s %-14s %-14s" % (r0["id"][:28], fila[0], fila[1]))
        if not hay_ambito:
            print("     (ninguna regla declara `ambito`: esta decision no le afecta a ninguna)")
        print("     Por defecto vale CUALQUIERA, y es el supuesto mas grande del instrumento:")
        print("     la ventana compara nombres de accion SIN ruta, asi que escribir un documento")
        print("     y pasar el gate sobre otro fichero cuenta como cumplido. `--respuesta-en-ambito`")
        print("     da la lectura estricta. El defecto no se cambio al descubrirlo (26/07/2026):")
        print("     mover el criterio despues de ver el resultado es mover la metrica post-hoc.")

        print()
        print("  3. MUESTRA MINIMA: por debajo de cuantas ocasiones la tasa deja de ser una tasa.")
        print("     Ahora vale %d. No mueve ningun porcentaje: decide cuales se marcan como" %
              MUESTRA_MINIMA)
        print("     anecdota, que es lo unico que evita que alguien cite un 100 % de dos casos.")
        print("     %-28s %s" % ("umbral", "  ".join("%-5d" % u for u in (2, 5, 10, 20, 30))))
        marcadas = []
        for u in (2, 5, 10, 20, 30):
            marcadas.append(sum(1 for r in res if r["disparadores"] < u))
        print("     %-28s %s" % ("reglas marcadas de %d" % len(res),
                                 "  ".join("%-5d" % m for m in marcadas)))

        print()
        print("Ninguna de las tres es un descubrimiento: son decisiones que alguien tomo. Si al")
        print("cambiarlas la cifra se mueve mas que la diferencia que quieres defender, esa cifra")
        print("no aguanta el peso que le estas poniendo.")
        return _veredicto(res)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        # COBERTURA ANTES DE LA TABLA (25/07/2026). Probando el instrumento contra el historial de
        # OTRO proyecto salieron cuatro "n/d" seguidos, y esa pantalla se puede leer como "todo
        # perfecto" o como "roto" con la misma facilidad. La causa real era que esas sesiones no
        # tenian ni una sola llamada a herramienta. Decirlo por delante evita las dos lecturas.
        # Con rx_shell y carpetas, que antes no se le pasaban: el recuento de cabecera se hacia
        # con el mapa de fabrica y podia no cuadrar con la tabla de debajo, calculada con el del
        # usuario. Dos cifras de la misma pantalla contando cosas distintas.
        #
        # Y POR EL CACHE, que era el segundo sitio sin el. `medir` acababa de parsear estos mismos
        # ficheros y aqui se volvian a parsear enteros solo para poner un numero en la cabecera:
        # la vista mas simple tardaba el DOBLE que la curva, que hace ocho veces mas trabajo.
        def _seq(x):
            clave = _clave_cache(x, not args.sin_colapsar, rx_shell, carpetas)
            if clave not in _CACHE_SECUENCIAS:
                _CACHE_SECUENCIAS[clave] = secuencia_de(x, not args.sin_colapsar, rx_shell,
                                                        carpetas)
            return _CACHE_SECUENCIAS[clave]

        acciones = sum(len(s) for s in (_seq(x) for x in paths) if s)
        print("=" * 76)
        print("ADHERENCIA A LAS REGLAS PROPIAS  --  %d sesiones, %d acciones"
              % (len(paths), acciones))
        print("=" * 76)
        if not acciones:
            print("  Esas sesiones no contienen ninguna llamada a herramienta, asi que no hay nada")
            print("  que medir. Es ausencia de dato, no un cero.")
            print()
        print("  %-30s %7s %8s %8s  %s" % ("regla", "tocaba", "cumplio", "tasa", "umbral"))
        print("  " + "-" * 76)
        for r in res:
            if r["tasa"] is None:
                tasa = "  n/d  "
            else:
                flojo = "*" if r["disparadores"] < MUESTRA_MINIMA else " "
                tasa = "%5.1f %%%s" % (r["tasa"], flojo)
            umbral = "" if r["umbral"] is None else "%d %%" % r["umbral"]
            print("  %-30s %7d %8d %8s  %s" % (r["id"][:30], r["disparadores"],
                                               r["cumplidos"], tasa, umbral))
            if r["fuente"]:
                print("      %s" % r["fuente"])
            # EL CERO SILENCIOSO (descubierto el 25/07 probando controles). Si el ambito filtra
            # TODOS los disparadores, la tasa sale n/d y parece que la regla no se activo nunca.
            # La causa real suele ser otra: el ambito filtra por RUTA, y una accion de consola no
            # tiene fichero, asi que declarar ambito en una regla disparada por un comando lo
            # descarta todo. Se avisa en vez de dejar el cero mudo.
            if r["disparadores"] and r["filtrados_por_ambito"]:
                total = r["disparadores"] + r["filtrados_por_ambito"]
                print("      (el ambito dejo fuera %d de %d ocasiones, el %.0f %%)"
                      % (r["filtrados_por_ambito"], total,
                         100.0 * r["filtrados_por_ambito"] / total))
            if r["disparadores"] == 0 and r["filtrados_por_ambito"]:
                print("      AVISO: el ambito descarto los %d disparadores que habia. Si el"
                      % r["filtrados_por_ambito"])
                print("      disparador es una accion sin fichero (un comando), el ambito no aplica.")
        print()
        if any(r["tasa"] is not None and r["disparadores"] < MUESTRA_MINIMA for r in res):
            print("(*) menos de %d ocasiones: eso no es una tasa, es una anecdota con decimales."
                  % MUESTRA_MINIMA)
        ilegibles_total = max((r["ilegibles"] for r in res), default=0)
        if ilegibles_total:
            print()
            print("  AVISO: %d sesion(es) no se pudieron leer y quedan FUERA de estas cifras."
                  % ilegibles_total)
            print("  No son un cero: son ocasiones que no se pudieron mirar.")
        sin_propia = sum(1 for p_ in paths if fecha_de_sesion(p_)[1])
        if sin_propia and any(r.get("desde") for r in reglas):
            print()
            print("  AVISO: %d de %d sesiones no traen fecha dentro y se datan por la fecha del"
                  % (sin_propia, len(paths)))
            print("  FICHERO. Si ese historial se copio o se clono, esa fecha es la de la copia, y")
            print("  el filtro `desde` de las reglas esta comparando contra ella.")
        print()
        print("La tasa es de HABITO, no de incumplimiento: una regla puede no aplicar a todos sus")
        print("disparadores. Sirve para decidir que hacer con cada una, no para repartir culpas.")

    return _veredicto(res)


if __name__ == "__main__":
    sys.exit(main())
