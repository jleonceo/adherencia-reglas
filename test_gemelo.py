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

# Ficheros que PUEDEN diferir, con su motivo. La lista es corta a proposito: cada entrada es una
# renuncia a vigilar algo, y si crece deja de haber guardian.
SE_PERMITE_QUE_DIFIERAN = {
    "README.md": "uno cuenta el estudio y el otro explica como se instala: son documentos distintos",
    "test_gemelo.py": "cada copia nombra al OTRO repositorio en su constante GEMELO",
}


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
        for raiz, dirs, ficheros in os.walk(LOCAL):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in ficheros:
                fuera.add(os.path.relpath(os.path.join(raiz, f), LOCAL).replace(os.sep, "/"))
        return fuera
    arbol = json.loads(_pedir(
        "https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (GEMELO, RAMA)
    ).decode("utf-8"))
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
    for raiz, dirs, ficheros in os.walk(AQUI):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in ficheros:
            rel = os.path.relpath(os.path.join(raiz, f), AQUI).replace(os.sep, "/")
            locales.add(rel)

    comunes = sorted(remotos & locales)
    distintos, no_leidos = [], []
    for rel in comunes:
        if rel in SE_PERMITE_QUE_DIFIERAN:
            continue
        try:
            remoto = _leer_remoto(rel)
        except Exception as e:
            no_leidos.append((rel, str(e)))
            continue
        local = io.open(os.path.join(AQUI, rel.replace("/", os.sep)), "rb").read()
        if _sha(local) != _sha(remoto):
            distintos.append(rel)

    print("  comunes: %d   vigilados: %d   exentos: %d"
          % (len(comunes), len(comunes) - len([c for c in comunes if c in SE_PERMITE_QUE_DIFIERAN]),
             len([c for c in comunes if c in SE_PERMITE_QUE_DIFIERAN])))

    solo_aqui = sorted(locales - remotos - set([".gitignore"]))
    solo_aqui = [f for f in solo_aqui if not f.startswith(".git/")]
    if solo_aqui:
        print()
        print("  solo en este repositorio (empaquetado, no se exige):")
        for f in solo_aqui:
            print("    %s" % f)

    if no_leidos:
        print()
        for rel, e in no_leidos:
            print("  NO LEIDO  %s  (%s)" % (rel, e))
        print("  Un fichero que no se pudo leer no es un fichero que coincida.")
        return 2

    if distintos:
        print()
        print("  *** LOS GEMELOS SE HAN SEPARADO ***")
        for f in distintos:
            print("    %s" % f)
        print()
        print("  Si acabas de arreglar algo aqui, subelo tambien al otro. Si acabas de subirlo al")
        print("  otro, este banco se pondra verde solo en cuanto llegue: la ventana entre los dos")
        print("  push es la unica en la que este rojo es esperado.")
        return 1

    print()
    print("  Los dos arboles coinciden en todo lo vigilado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
