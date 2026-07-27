# -*- coding: utf-8 -*-
"""test_gemelo.py - vigila que este repositorio y su gemelo no se separen.

POR QUE EXISTE (27/07/2026). El estudio y el paquete publican EL MISMO codigo: ocho ficheros
identicos byte a byte, verificado con md5. Uno lleva el analisis y el otro se instala, pero el
instrumento es el mismo, y tiene que serlo: un estudio que no trae su herramienta no se puede
reproducir, y un paquete que no trae la suya no se puede instalar.

El coste de eso es que cada arreglo hay que escribirlo DOS VECES, a mano, en dos sitios. Ese mismo
dia se corrigio una frase falsa del flujo de CI y hubo que copiarla a los dos. Salio bien porque
alguien se acordo. El dia que no se acuerde, un repositorio queda arreglado y el otro sigue
publicando el fallo, y los dos siguen dando verde por su cuenta, porque cada uno solo se mira a si
mismo. Un repositorio cuya tesis es que una cifra publicada es una afirmacion que se comprueba no
puede depender de que alguien se acuerde.

Lo que hace: se trae la lista de ficheros del gemelo, compara los que existen en los dos y exige
que sean identicos. Los que existen solo en uno son de empaquetado y se listan, no se exigen.

DOS AVISOS HONESTOS SOBRE ESTE GUARDIAN:

1. Entre el push a un repositorio y el push al otro, ESTE BANCO SE PONE ROJO A PROPOSITO. No es un
   fallo intermitente: es la unica ventana en la que los dos arboles difieren de verdad, y taparla
   seria devolver el problema. Se arregla subiendo el hermano.
2. Sin red no comprueba nada, y en ese caso sale con 2 en vez de con 0. Un guardian que aprueba
   cuando no ha podido mirar convierte cada duda en una puerta abierta.
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import sys

try:
    from urllib.request import urlopen, Request
except ImportError:                                        # Python 2
    from urllib2 import urlopen, Request

AQUI = os.path.dirname(os.path.abspath(__file__))

# El gemelo de este repositorio. La linea cambia en cada uno de los dos y es lo unico que cambia.
GEMELO = "jleonceo/skill-adherencia-reglas"
RAMA = "main"

# EL CENSO. Tres listas, y entre las tres cubren todo lo que publica cualquiera de los dos. Añadir
# un fichero obliga a declararlo aqui, que es el momento en que alguien decide si viaja al hermano.
VIGILADOS = [
    ".github/workflows/ci.yml", ".gitignore", "LICENSE",
    "ejemplo/fabricar_ejemplo.py",
    "ejemplo/historial/sesion_regla_a_medias.jsonl",
    "ejemplo/historial/sesion_regla_cumplida.jsonl",
    "ejemplo/historial/sesion_regla_ignorada.jsonl",
    "ejemplo/reglas_ejemplo.json",
    "skills/adherencia-reglas/SKILL.md",
    "skills/adherencia-reglas/cobertura.py",
    "skills/adherencia-reglas/medir_adherencia.py",
    "skills/adherencia-reglas/mutar.py",
    "skills/adherencia-reglas/reglas.json",
    "skills/adherencia-reglas/run_tests_adherencia.py",
    "skills/adherencia-reglas/test_portabilidad.py",
    "skills/adherencia-reglas/test_seguridad.py",
]
PUEDEN_DIFERIR = {
    "README.md": "uno cuenta el estudio y el otro explica como se instala",
    "test_gemelo.py": "cada copia nombra al OTRO repositorio en su constante GEMELO",
}
SOLO_EN_UNO = {
    ".claude-plugin/marketplace.json": "el manifiesto de plugin, solo en el paquete",
    "skills/adherencia-reglas/LICENSE": "la licencia dentro de la skill empaquetada",
}
DECLARADOS = set(VIGILADOS) | set(PUEDEN_DIFERIR) | set(SOLO_EN_UNO)


def _andar(raiz):
    """`os.walk` con el error ARRIBA. Sin `onerror` se tragaba una carpeta ilegible y perdia su
    subarbol entero sin imprimir una linea."""
    def reventar(err):
        raise err
    return os.walk(raiz, onerror=reventar)


def _sha(datos):
    """Sobre el contenido con los saltos de linea normalizados.

    Sin esto, un clon de Windows con `core.autocrlf` en marcha difiere de la copia del servidor en
    TODOS los ficheros de texto y el guardian grita siempre, que es igual de inutil que callarse.
    """
    return hashlib.sha256(datos.replace(b"\r\n", b"\n")).hexdigest()


# UNA VIA LOCAL PARA PODER PROBAR EL GUARDIAN. `GEMELO_LOCAL` apunta a un clon en disco y
# sustituye a la red. No es una comodidad: un guardian que solo se puede ejercitar contra el
# servidor no se puede probar EN LAS DOS DIRECCIONES antes de confiar en el, y uno que nunca ha
# salido rojo no ha demostrado que sepa hacerlo. Los dos casos de `test_gemelo_local.py` lo usan.
LOCAL = os.environ.get("GEMELO_LOCAL")


def _listar_remoto():
    if LOCAL:
        fuera = set()
        for raiz, dirs, ficheros in _andar(LOCAL):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in ficheros:
                fuera.add(os.path.relpath(os.path.join(raiz, f), LOCAL).replace(os.sep, "/"))
        return fuera
    arbol = json.loads(_pedir(
        "https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (GEMELO, RAMA)
    ).decode("utf-8"))
    if arbol.get("truncated"):
        raise RuntimeError("la API corto el arbol del gemelo: la lista esta incompleta")
    raros = [n.get("path") for n in arbol.get("tree", []) if n.get("type") not in ("blob", "tree")]
    if raros:
        raise RuntimeError("nodos que no son fichero ni carpeta (submodulos?): %s" % raros)
    return set(n["path"] for n in arbol.get("tree", []) if n.get("type") == "blob")


def _leer_remoto(rel):
    if LOCAL:
        return io.open(os.path.join(LOCAL, rel.replace("/", os.sep)), "rb").read()
    return _pedir("https://raw.githubusercontent.com/%s/%s/%s" % (GEMELO, RAMA, rel))


def _pedir(url):
    req = Request(url, headers={"User-Agent": "test-gemelo"})
    return urlopen(req, timeout=30).read()


def main():
    print("=" * 78)
    print("GEMELO  --  este repositorio contra %s" % GEMELO)
    print("=" * 78)

    if LOCAL:
        # Era un interruptor de apagado: `GEMELO_LOCAL=.` comparaba el repositorio consigo mismo y
        # daba verde siempre, con los contadores identicos. Y puesto en el flujo de CI de los dos,
        # el guardian aprobaba el commit que lo desactivaba.
        if os.path.realpath(LOCAL) == os.path.realpath(AQUI):
            print("  GEMELO_LOCAL apunta a este mismo repositorio. Eso no es un gemelo. Sale con 2.")
            return 2
        if os.environ.get("CI"):
            print("  GEMELO_LOCAL dentro de un flujo de CI: ahi la comparacion va contra el")
            print("  servidor, y un clon local la convierte en un interruptor de apagado.")
            return 2
        print("  (comparando contra el clon local %s, no contra el servidor)" % LOCAL)
    try:
        remotos = _listar_remoto()
    except Exception as e:
        print("  NO SE PUDO COMPROBAR: %s" % e)
        print("  Sin red no hay comparacion, y un guardian que aprueba sin haber mirado no es un")
        print("  guardian. Sale con 2 para que no se confunda con un verde.")
        return 2

    if not remotos:
        print("  NO SE PUDO COMPROBAR: el arbol de %s vino vacio." % GEMELO)
        return 2

    locales = set()
    for raiz, dirs, ficheros in _andar(AQUI):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in ficheros:
            rel = os.path.relpath(os.path.join(raiz, f), AQUI).replace(os.sep, "/")
            locales.add(rel)

    quejas, no_leidos = [], []

    # 1. Lo declarado tiene que ESTAR en los dos: aqui se cazan las bajas, los renombrados, los
    #    cambios de caja y un arbol del gemelo movido bajo otro prefijo.
    for rel in VIGILADOS:
        if rel not in locales:
            quejas.append("declarado y NO esta aqui: %s" % rel)
        if rel not in remotos:
            quejas.append("declarado y NO esta en el gemelo: %s" % rel)

    # 2. Lo que aparece sin declarar tambien suspende. Un guardian que solo mira lo que ya conoce
    #    deja de vigilar en cuanto alguien añade algo.
    for rel in sorted((locales | remotos) - DECLARADOS):
        if rel.startswith(".git/"):
            continue
        quejas.append("sin declarar, decide si tiene que viajar al gemelo: %s" % rel)

    # 3. Y lo declarado que esta en los dos, que coincida.
    for rel in VIGILADOS:
        if rel not in locales or rel not in remotos:
            continue
        try:
            remoto = _leer_remoto(rel)
        except Exception as e:
            no_leidos.append((rel, str(e)))
            continue
        local = io.open(os.path.join(AQUI, rel.replace("/", os.sep)), "rb").read()
        if _sha(local) != _sha(remoto):
            quejas.append("SEPARADOS: %s" % rel)

    print("  vigilados: %d   pueden diferir: %d   solo en uno: %d"
          % (len(VIGILADOS), len(PUEDEN_DIFERIR), len(SOLO_EN_UNO)))

    # El orden importa: la separacion se imprime ANTES que los fallos de lectura. Al reves, un
    # error 500 en un fichero cualquiera tapaba el unico mensaje que este guardian existe para dar.
    if quejas:
        print()
        print("  *** LOS GEMELOS SE HAN SEPARADO ***")
        for q in quejas:
            print("    %s" % q)
        if no_leidos:
            print()
            for rel, e in no_leidos:
                print("    NO LEIDO  %s  (%s)" % (rel, e))
        print()
        print("  Si acabas de arreglar algo aqui, subelo tambien al otro. La ventana entre los dos")
        print("  push es la unica en la que este rojo es esperado, y el CI la reintenta.")
        return 1

    if no_leidos:
        print()
        for rel, e in no_leidos:
            print("  NO LEIDO  %s  (%s)" % (rel, e))
        print("  Un fichero que no se pudo leer no es un fichero que coincida.")
        return 2

    print()
    print("  Los %d ficheros vigilados coinciden, y no ha aparecido ninguno sin declarar."
          % len(VIGILADOS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
