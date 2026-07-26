# -*- coding: utf-8 -*-
"""Que lineas del instrumento NO ejecuta ningun caso del banco.

POR QUE EXISTE (25/07/2026). Tres rondas de auditores encontraron catorce defectos en un dia, y
todos se buscaron a mano: alguien imaginaba un caso raro y lo probaba. Eso encuentra lo que se te
ocurre y deja intacto lo que no. La pregunta que ningun auditor puede responder mirando es cual es
el TROZO DE CODIGO que nadie ha ejecutado nunca, y esa se responde midiendo.

Usa `trace`, de la biblioteca estandar, porque el paquete no puede depender de nada externo. Lo que
hace `coverage.py` en condiciones normales, aqui reducido a lo que hace falta: ejecutar los bancos,
apuntar que lineas se pisan y restar.

    python cobertura.py            resumen y lineas sin ejecutar
    python cobertura.py --detalle  ademas, el codigo de cada linea

No es una nota que haya que subir a cien. Una linea sin cubrir es una PREGUNTA: ¿es un camino que
nadie recorre porque no puede pasar, o es un agujero por donde entro alguno de los catorce?
"""
from __future__ import print_function

import io
import os
import sys
import trace

AQUI = os.path.dirname(os.path.abspath(__file__))
MEDIDO = os.path.join(AQUI, "medir_adherencia.py")
BANCOS = ["run_tests_adherencia.py", "test_portabilidad.py", "test_seguridad.py"]

# Lineas que no son codigo ejecutable y no cuentan como agujero: en blanco, comentarios, el cuerpo
# de un docstring y las cabeceras que Python solo evalua al importar.
def _ejecutables(path):
    fuera = set()
    dentro_doc = False
    delim = None
    for i, linea in enumerate(io.open(path, encoding="utf-8").readlines(), 1):
        s = linea.strip()
        if dentro_doc:
            fuera.add(i)
            if delim in s:
                dentro_doc = False
            continue
        if not s or s.startswith("#"):
            fuera.add(i)
            continue
        for d in ('"""', "'''"):
            if s.startswith(d):
                if s.count(d) == 1:
                    dentro_doc, delim = True, d
                fuera.add(i)
                break
    total = len(io.open(path, encoding="utf-8").readlines())
    return set(range(1, total + 1)) - fuera


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    detalle = "--detalle" in argv

    contador = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix, sys.exec_prefix])
    sys.path.insert(0, AQUI)
    cwd = os.getcwd()
    os.chdir(AQUI)

    # SE IMPORTAN COMO MODULO Y SE CARGAN SUS CASOS A MANO. El primer intento ejecutaba el fichero
    # del banco con `runctx` y salio 9,7 % de cobertura, que era FALSO: cada banco termina con
    # `loadTestsFromModule(sys.modules["__main__"])`, y bajo `runctx` el modulo `__main__` es este
    # medidor, no el banco. Cargaba cero casos, no ejecutaba nada y la cifra parecia alarmante.
    # Un instrumento nuevo que da una cifra creible a la primera hay que mirarlo dos veces.
    import importlib.util
    import unittest

    def _cargar(banco):
        nombre = os.path.splitext(banco)[0]
        spec = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, banco))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = mod
        spec.loader.exec_module(mod)
        return mod

    def _ejecutar_todos():
        suite = unittest.TestSuite()
        cargador = unittest.defaultTestLoader
        for banco in BANCOS:
            suite.addTests(cargador.loadTestsFromModule(_cargar(banco)))
        n = suite.countTestCases()
        unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)
        return n

    try:
        contador.runfunc(_ejecutar_todos)
        casos = _ejecutar_todos.__dict__.get("n", None)
    finally:
        os.chdir(cwd)

    pisadas = set()
    for (fichero, linea), veces in contador.results().counts.items():
        if os.path.abspath(fichero) == MEDIDO and veces:
            pisadas.add(linea)

    ejecutables = _ejecutables(MEDIDO)
    sin_cubrir = sorted(ejecutables - pisadas)
    pct = 100.0 * (len(ejecutables) - len(sin_cubrir)) / max(1, len(ejecutables))

    print("=" * 78)
    print("COBERTURA DEL INSTRUMENTO  --  %d lineas ejecutables" % len(ejecutables))
    print("=" * 78)
    print("  cubiertas por el banco : %d  (%.1f %%)" % (len(ejecutables) - len(sin_cubrir), pct))
    print("  SIN EJECUTAR NUNCA     : %d" % len(sin_cubrir))
    if sin_cubrir:
        lineas = io.open(MEDIDO, encoding="utf-8").readlines()
        print()
        print("  Cada una es una pregunta: ¿camino imposible, o agujero sin vigilar?")
        print()
        bloques, actual = [], []
        for n in sin_cubrir:
            if actual and n == actual[-1] + 1:
                actual.append(n)
            else:
                if actual:
                    bloques.append(actual)
                actual = [n]
        if actual:
            bloques.append(actual)
        for b in bloques:
            marca = "L%d" % b[0] if len(b) == 1 else "L%d-%d" % (b[0], b[-1])
            print("  %-12s %s" % (marca, lineas[b[0] - 1].strip()[:60]))
            if detalle:
                for n in b[1:]:
                    print("  %-12s %s" % ("", lineas[n - 1].strip()[:60]))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
