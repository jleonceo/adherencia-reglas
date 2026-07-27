#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fabricar_ejemplo.py - genera el historial de juguete que el README usa como ejemplo.

POR QUE EXISTE (26/07/2026)
---------------------------
El README ensenaba una tabla de salida y el repo no traia ningun historial. Esos numeros salian
de un historial privado que no viaja con el paquete, y el texto no lo decia: quien clonaba el
repo no podia reproducir ni una cifra. Una auditoria lo marco como defecto de publicacion.

Ahora el ejemplo se GENERA, no se copia. Este script escribe tres sesiones de juguete con un
comportamiento decidido a mano, asi que la tabla del README es una consecuencia comprobable:
cualquiera la reproduce con dos ordenes y sale igual, byte a byte.

QUE FABRICA, Y POR QUE ASI
--------------------------
Tres sesiones que ilustran los tres casos que importan:

  s1  la regla del gate se cumple SIEMPRE   5 de 5
  s2  la misma regla se cumple A MEDIAS     3 de 6   <- la que mas gana con un hook
  s3  la regla de la suite no se cumple     1 de 4   <- o pasa a mecanismo, o se retira

Agregado sobre las tres: gate 8 de 11 (72,7 %) y suite 1 de 4 (25 %, marcada como anecdota por
muestra corta). Esas son las cifras que el README publica, y salen de ejecutar esto.

No hay nada real aqui: ni rutas de nadie, ni nombres, ni fechas de trabajo. Es el mismo criterio
que usan los bancos del paquete, y por la misma razon: un ejemplo que depende del historial de
quien lo escribio deja de funcionar el dia que ese historial cambia.

USO
---
  python ejemplo/fabricar_ejemplo.py
  python skills/adherencia-reglas/medir_adherencia.py --sesiones ejemplo/historial \\
         --reglas ejemplo/reglas_ejemplo.json
"""
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
HISTORIAL = os.path.join(AQUI, "historial")

# Fecha fija: el ejemplo no puede cambiar segun el dia en que se genere.
DIA = "2026-07-20T%02d:%02d:00.000Z"


def uso(nombre, entrada, hora, minuto, bid):
    return json.dumps({
        "type": "assistant",
        "timestamp": DIA % (hora, minuto),
        "message": {"id": bid, "content": [
            {"type": "tool_use", "id": bid, "name": nombre, "input": entrada}]},
    }, ensure_ascii=False)


def escribir_doc(n, hora, minuto):
    return uso("Write", {"file_path": "docs/capitulo_%d.md" % n, "content": "..."},
               hora, minuto, "w%d" % n)


def tocar_codigo(n, hora, minuto):
    return uso("Write", {"file_path": "src/modulo_%d.py" % n, "content": "..."},
               hora, minuto, "c%d" % n)


def pasar_gate(n, hora, minuto):
    return uso("Bash", {"command": "python gate_texto.py docs/capitulo_%d.md" % n},
               hora, minuto, "g%d" % n)


def pasar_suite(n, hora, minuto):
    return uso("Bash", {"command": "python run_tests.py"}, hora, minuto, "t%d" % n)


def leer_algo(n, hora, minuto):
    return uso("Read", {"file_path": "notas/%d.md" % n}, hora, minuto, "r%d" % n)


def sesiones():
    """(nombre, lineas) de las tres sesiones. El comportamiento esta decidido, no es azar."""
    # s1: cada documento pasa su gate. Cinco de cinco.
    s1 = []
    for i in range(5):
        s1 += [escribir_doc(i, 9, i * 2), pasar_gate(i, 9, i * 2 + 1)]

    # s2: la mitad. Tres de seis. Las tres que fallan van AL FINAL y con lecturas en medio, y
    # eso no es cosmetica: si se intercalaran, la ventana de una escritura sin gate alcanzaria
    # el gate de la siguiente y contaria como cumplida. El primer intento de este ejemplo salio
    # al 90,9 % por eso exactamente, y la tabla no ensenaba lo que su texto prometia.
    s2 = []
    for i in range(3):
        s2 += [escribir_doc(i, 11, i * 3), pasar_gate(i, 11, i * 3 + 1)]
    for i in range(3, 6):
        s2 += [escribir_doc(i, 11, i * 3),
               leer_algo(i, 11, i * 3 + 1), leer_algo(i + 10, 11, i * 3 + 2)]

    # s3: codigo tocado cuatro veces y una sola ejecucion de la suite, al final. Solo alcanza a
    # la ultima escritura dentro de la ventana, asi que sale 1 de 4.
    s3 = []
    for i in range(4):
        s3 += [tocar_codigo(i, 13, i * 4), leer_algo(i, 13, i * 4 + 1)]
    # y una sola vez la suite MUY lejos, para que se vea que la ventana importa
    s3.append(pasar_suite(0, 13, 40))

    return [("sesion_regla_cumplida.jsonl", s1),
            ("sesion_regla_a_medias.jsonl", s2),
            ("sesion_regla_ignorada.jsonl", s3)]


def main():
    if not os.path.isdir(HISTORIAL):
        os.makedirs(HISTORIAL)
    for nombre, lineas in sesiones():
        with io.open(os.path.join(HISTORIAL, nombre), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas) + "\n")
        print("  escrita %s  (%d llamadas)" % (nombre, len(lineas)))
    print("\nAhora:")
    print("  python skills/adherencia-reglas/medir_adherencia.py \\")
    print("         --sesiones ejemplo/historial --reglas ejemplo/reglas_ejemplo.json")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
