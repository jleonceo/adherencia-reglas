# -*- coding: utf-8 -*-
"""Sabotea el instrumento a proposito y comprueba que el banco se pone rojo.

POR QUE EXISTE (25/07/2026). El README y el SKILL.md presentan la verificacion por mutacion como
lo que separa un banco de un adorno, y hasta hoy el paquete NO traia con que hacerla: quien se lo
descargara tenia que creerse esa afirmacion en vez de comprobarla. Lo encontro un escéptico
buscando el script y no hallando ninguno. Una cifra de confianza que el lector no puede reproducir
es justo lo contrario de lo que esta herramienta predica.

QUE HACE. Rompe una linea del codigo, ejecuta los tres bancos y mira si alguno falla. Si ninguno
falla, esa linea no esta protegida por nadie: el banco pasaria igual con el defecto dentro.

    python mutar.py            las mutaciones de serie
    python mutar.py --lista    solo dice cuales son, sin tocar nada

COMO SE RESTAURA EL FICHERO, que es lo delicado. Aqui decia "se restaura siempre, incluso si algo
revienta a mitad", y era FALSO: el `finally` de Python no llega a ejecutarse si al proceso lo matan
sin poder atenderlo -- `Stop-Process -Force`, "Finalizar tarea", el timeout de un CI que manda
SIGKILL, la bateria. Un esceptico lo tumbo el 25/07 matando el proceso a los 400 ms: el fichero
quedo con la mutacion nº1 clavada dentro, en silencio, hasta que alguien mirase el `git diff`. El
instrumento que persigue ese fallo en otros lo tenia dentro, y encima anunciado al reves.

Ahora la promesa la sostiene el DISCO, no el flujo del programa:

  1. antes de tocar nada se guarda una copia intacta en `medir_adherencia.py.original`;
  2. al arrancar, si esa copia esta ahi, es que la ejecucion anterior murio a mitad: se restaura
     antes de hacer nada mas y se dice por pantalla;
  3. al acabar bien, la copia se borra -- su sola existencia es la señal.

Y como una señal que nadie mira no sirve, `test_seguridad.py` tiene un caso que se pone ROJO
mientras esa copia siga en el arbol. Ese caso se salta cuando lo lanza este script (variable
`MUTACION_EN_CURSO`), porque durante la mutacion el residuo es lo normal; fuera de aqui, no.

UNA MUTACION QUE NADIE CAZA NO ES UN FALLO DEL CODIGO: es un hueco del banco. Y es la unica forma
de saber que un caso sigue protegiendo lo que protegia, porque un caso puede quedarse ciego cuando
el codigo cambia debajo sin que nada lo avise.
"""
from __future__ import print_function

import io
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MEDIDO = os.path.join(AQUI, "medir_adherencia.py")
# La copia intacta, en disco. Existe SOLO mientras hay una mutacion puesta: si esta ahi al
# arrancar, la ejecucion anterior no llego a su `finally` y el fichero medido esta saboteado.
RESIDUO = MEDIDO + ".original"
BANCOS = ["run_tests_adherencia.py", "test_portabilidad.py", "test_seguridad.py"]

# Cada entrada rompe UNA decision del instrumento. Se eligen las que, si fallasen en silencio,
# darian numeros creibles y equivocados, que es el fallo que esto persigue.
MUTACIONES = [
    ("el ambito deja de exigir frontera por la derecha",
     'der = (z.endswith("/") or fin == len(ruta) or ruta[fin] == "/"',
     'der = (True or z.endswith("/") or fin == len(ruta) or ruta[fin] == "/"'),
    ("el ambito deja de exigir frontera por la izquierda",
     'izq = i == 0 or ruta[i - 1] == "/" or z.startswith("/")',
     'izq = True'),
    ("el ambito deja de normalizar separadores de ruta",
     'z = z.replace("\\\\", "/").lower()',
     'z = z.lower()'),
    ("`test` pierde la frontera de palabra y cuenta `latest_datos.csv`",
     r'r"\brun_tests|\btest_|\bunittest|\bpytest"',
     r'r"run_tests|test_|unittest|pytest"'),
    ("una regla con forma invalida pasa callando",
     "if not isinstance(r, dict):",
     "if False:"),
    ("la fecha vuelve a salir del fichero en vez del contenido",
     "if path in _CACHE_FECHA:",
     "if True:"),
    ("las carpetas de doctrina vuelven a estar cableadas",
     "car = CARPETAS_DEFECTO if carpetas is None else carpetas",
     "car = CARPETAS_DEFECTO"),
    ("un patron de accion vacio deja de rechazarse",
     "if not isinstance(patron, str) or not patron.strip():",
     "if False:"),
    ("el veredicto deja de mirar los umbrales",
     'bajos = [r for r in res if r.get("umbral") is not None and r.get("tasa") is not None',
     'bajos = [r for r in [] if r.get("umbral") is not None and r.get("tasa") is not None'),
    ("el cache deja de distinguir el colapso y mezcla dos lecturas",
     "    return (path, bool(colapsar), rx, cp)",
     "    return (path, rx, cp)"),
    ("`--por-dia` con negativo o cero vuelve a pasar callando",
     "    if args.por_dia is not None and args.por_dia <= 0:",
     "    if False:"),
    # LAS TRES DE ABAJO NO LAS ESCRIBIMOS NOSOTROS (26/07/2026), y esa es toda la diferencia.
    #
    # Las once de arriba son propias y las once se cazaban: cero huecos, y la cifra se publicaba.
    # Solo que un mutador escrito por el autor hereda el punto ciego del autor, asi que ese "cero"
    # no medía la calidad del banco, medía el acuerdo entre dos cosas de la misma cabeza. Un
    # auditor externo escribio dieciocho, cazamos trece, dos de las supervivientes eran
    # equivalentes y estas TRES eran huecos de verdad. Las tres tocan la CLASIFICACION, que es de
    # donde sale el denominador: al romperlas la tabla sigue saliendo, con numeros mas altos.
    ("solo `Write` cuenta como escritura: ni Edit, ni MultiEdit, ni NotebookEdit",
     'if nombre in ("Write", "Edit", "MultiEdit", "NotebookEdit"):',
     'if nombre in ("Write",):'),
    ("`Task` y `Agent` dejan de ser acciones y el verbo `subagente` desaparece",
     'if nombre in ("Task", "Agent"):',
     'if nombre in ("__que_no_existe__",):'),
    ("la fecha de sesion solo mira el primer registro y se cae al mtime callando",
     "                if i > 400:            # si en 400 registros no hay fecha, no la hay",
     "                if i > 0:            # si en 400 registros no hay fecha, no la hay"),
    # 27/07/2026. Nace de un `replace` del tabulador que no hacia nada, porque `split()` sin
    # argumentos ya parte por cualquier espacio en blanco. Al quitarlo hubo que dejar cableado lo
    # que de verdad sostiene el comportamiento, que es el `split()` desnudo: partir solo por
    # espacio pierde las ordenes tabuladas y las escritas en varias lineas, que es como se
    # escriben en un CI.
    ("la orden solo se parte por espacio y pierde tabuladores y saltos de linea",
     "    for token in cmd.split():",
     '    for token in cmd.split(" "):'),
]


def _rescatar_residuo():
    """Deshace una mutacion que se quedo puesta porque al proceso anterior lo mataron.

    Esto es lo que sostiene la promesa del docstring. El `finally` de mas abajo cubre los errores
    y el Ctrl+C; NO cubre que te maten el proceso, y ese caso deja el instrumento saboteado. La
    copia en disco si lo cubre, porque sobrevive a la muerte del proceso que la escribio.
    """
    if not os.path.exists(RESIDUO):
        return False
    io.open(MEDIDO, "w", encoding="utf-8", newline="\n").write(
        io.open(RESIDUO, encoding="utf-8").read())
    os.remove(RESIDUO)
    print("  [!] La ejecucion anterior murio con una mutacion puesta. Fichero RESTAURADO.")
    print("      (si te extraña: eso es lo que pasa al matar el proceso a mitad)")
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # El rescate va ANTES de mirar los argumentos, y a proposito: `--lista` no toca nada, pero si
    # el arbol esta saboteado hay que deshacerlo igual. Quien viene a preguntar tambien repara.
    _rescatar_residuo()
    if "--lista" in argv:
        for desc, _, _ in MUTACIONES:
            print("  %s" % desc)
        return 0

    original = io.open(MEDIDO, encoding="utf-8").read()
    io.open(RESIDUO, "w", encoding="utf-8", newline="\n").write(original)
    # Los bancos que lanzo yo tienen que poder ver el residuo sin ponerse rojos: aqui es lo normal.
    entorno = dict(os.environ, MUTACION_EN_CURSO="1")
    cazadas = huecos = sin_aplicar = 0
    print("=" * 78)
    print("VERIFICACION POR MUTACION  --  %d sabotajes contra %d bancos"
          % (len(MUTACIONES), len(BANCOS)))
    print("=" * 78)
    try:
        for desc, viejo, nuevo in MUTACIONES:
            if viejo not in original:
                print("  %-52s SIN APLICAR (el codigo cambio)" % desc[:52])
                sin_aplicar += 1
                continue
            io.open(MEDIDO, "w", encoding="utf-8", newline="\n").write(
                original.replace(viejo, nuevo, 1))
            rojos = []
            for b in BANCOS:
                r = subprocess.run([sys.executable, b], capture_output=True, cwd=AQUI, env=entorno)
                if r.returncode != 0:
                    rojos.append(b.replace(".py", ""))
            if rojos:
                cazadas += 1
                print("  %-52s cazada" % desc[:52])
            else:
                huecos += 1
                print("  %-52s *** HUECO ***" % desc[:52])
            io.open(MEDIDO, "w", encoding="utf-8", newline="\n").write(original)
    finally:
        io.open(MEDIDO, "w", encoding="utf-8", newline="\n").write(original)
        # El residuo se borra AL FINAL y solo aqui: mientras exista, el arbol esta bajo sospecha y
        # `test_seguridad.py` lo dice en rojo. Borrarlo antes seria apagar la alarma.
        if os.path.exists(RESIDUO):
            os.remove(RESIDUO)

    print()
    print("  cazadas: %d   huecos: %d   sin aplicar: %d" % (cazadas, huecos, sin_aplicar))
    if huecos:
        print("  Un hueco no es un fallo del codigo: es una linea que el banco no vigila.")
    if sin_aplicar:
        print("  'Sin aplicar' tampoco es aprobado: esas lineas se quedaron sin probar.")
    return 1 if (huecos or sin_aplicar) else 0


if __name__ == "__main__":
    sys.exit(main())
