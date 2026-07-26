# -*- coding: utf-8 -*-
"""Lo que esta herramienta NO puede hacer, comprobado en vez de prometido.

Esta skill lee el historial COMPLETO de sesiones. Ahi dentro hay nombres de personas, cuentas
bancarias, documentos de identidad, claves pegadas por descuido y rutas del disco de quien la use.
Es, con diferencia, el fichero mas sensible de la carpeta.

Su salida son agregados: un identificador de regla, dos conteos y un porcentaje. Eso se puede
comprobar leyendo el codigo, y leerlo no es garantizarlo. Un cambio futuro que anadiese "y el
fichero donde fallo" a un mensaje de error convertiria un contador inofensivo en una fuga, y ninguna
revision lo pararia porque sonaria util.

De ahi los CANARIOS: se planta material sensible dentro de un historial de juguete y se exige que no
aparezca en NINGUNA de las cuatro vistas. Es la misma idea del portero de PII de este proyecto, que
bloquea por lo conocido con cero falsos positivos, reducida a lo que aqui se puede comprobar sin
depender de nada externo: el paquete tiene que seguir siendo stdlib pura para poder publicarse.

Los canarios son inventados. Un fixture con datos reales seria el propio agujero que vigila.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
MEDIDOR = os.path.join(AQUI, "medir_adherencia.py")

# Material sensible de mentira, uno por clase de las que el portero de PII vigila. Si alguno de
# estos aparece en la salida, es que la herramienta esta volcando contenido del historial.
CANARIOS = {
    "nombre":  "Encarnacion Villalobos Perez",
    # Formato realista pero INVALIDOS a proposito: el IBAN lleva el digito de control roto y la
    # letra del NIF no es la que le toca. Con valores validos, el escaner de repos publicos de este
    # proyecto los marcaba como PII de verdad, y con razon: no sabe distinguir un canario de una
    # filtracion. Un canario solo necesita ser una cadena unica que no aparezca por casualidad.
    "iban":    "ES0021000418450200051332",
    "nif":     "12345678X",
    "clave":   "clave-ficticia-CANARIO-NO-DEBE-SALIR",
    "ruta":    "/home/quien-sea/privado/nomina_enero.pdf",
    "cuerpo":  "TEXTO-INTERNO-DE-LA-CONVERSACION-QUE-NO-DEBE-VIAJAR",
}


def tool(nombre, entrada, bid):
    return {"message": {"content": [{"type": "tool_use", "id": bid, "name": nombre,
                                     "input": entrada}]}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="adh_seg_")
        self.sesiones = os.path.join(self.tmp, "proyecto")
        os.makedirs(self.sesiones)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def historial_con_canarios(self):
        """Un historial plausible con material sensible en todos los sitios donde cabe."""
        regs = []
        for i in range(4):
            regs.append({"message": {"content": [
                {"type": "text", "text": CANARIOS["cuerpo"] + " " + CANARIOS["nombre"]}]}})
            regs.append(tool("Write", {"file_path": CANARIOS["ruta"],
                                       "content": CANARIOS["iban"]}, "w%d" % i))
            regs.append(tool("Bash", {"command": "curl -H 'Authorization: %s' https://x/%s"
                                      % (CANARIOS["clave"], CANARIOS["nif"])}, "b%d" % i))
            regs.append(tool("Bash", {"command": "python run_tests.py"}, "t%d" % i))
        p = os.path.join(self.sesiones, "sesion.jsonl")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            for r in regs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return p

    def reglas(self):
        """Se escribe UNA vez. Reescribirlo en cada ejecucion le cambia la fecha y el test de
        solo-lectura acusaba a la herramienta de haber tocado un fichero que tocaba el fixture."""
        p = os.path.join(self.tmp, "reglas.json")
        if not os.path.exists(p):
            io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps({
                "reglas": [{"id": "banco-tras-escribir", "disparador": "escribir-doc",
                            "respuesta": "test", "ventana": 4}]}, ensure_ascii=False))
        return p

    def ejecutar(self, *extra):
        cmd = [sys.executable, MEDIDOR, "--sesiones", self.tmp, "--reglas", self.reglas()]
        r = subprocess.run(cmd + list(extra), capture_output=True)
        return (r.stdout or b"").decode("utf-8", "replace") + \
               (r.stderr or b"").decode("utf-8", "replace")


class TestNoFiltra(Base):
    """Ningun canario puede salir por ninguna de las cuatro vistas."""

    def _comprobar(self, salida, vista):
        for clase, valor in CANARIOS.items():
            self.assertNotIn(valor, salida,
                             "la vista %s volco el canario de tipo %s" % (vista, clase))

    def test_vista_normal(self):
        self.historial_con_canarios()
        self._comprobar(self.ejecutar(), "normal")

    def test_vista_json(self):
        self.historial_con_canarios()
        self._comprobar(self.ejecutar("--json"), "json")

    def test_vista_por_dia(self):
        self.historial_con_canarios()
        self._comprobar(self.ejecutar("--por-dia", "7"), "por-dia")

    def test_vista_curva_ventana(self):
        self.historial_con_canarios()
        self._comprobar(self.ejecutar("--curva-ventana"), "curva-ventana")

    def test_vista_sensibilidad(self):
        """La quinta vista. El banco cubria cuatro de seis y la promesa publicada decia "ninguna",
        que es una afirmacion sobre TODAS. Lo conto un auditor el 25/07."""
        self.historial_con_canarios()
        self._comprobar(self.ejecutar("--sensibilidad"), "sensibilidad")

    def test_la_vista_de_acciones_SI_ensena_rutas_y_esta_declarado(self):
        """La sexta vista es la excepcion, y hay que fijarla en un caso o no es una excepcion:
        es un agujero con una nota al lado.

        `--acciones` existe para enseñar que rutas del historial casan con cada accion declarada.
        Sin ver una ruta de ejemplo, nadie puede saber si su vocabulario cubre su trabajo, que es
        lo primero que hay que ajustar al instalar esto. O sea que enseña rutas POR DISENO.

        Este caso no exige que calle. Exige lo contrario: que siga enseñandolas, para que si algun
        dia alguien la "arregla" saltando la promesa por otro lado, se entere aqui. Y deja escrito
        que la promesa de las otras cinco vistas es entera, no aproximada.
        """
        self.historial_con_canarios()
        salida = self.ejecutar("--acciones")
        self.assertIn(CANARIOS["ruta"], salida,
                      "--acciones ha dejado de enseñar rutas: o cambio el diseño, o esta rota. "
                      "Si el cambio es a proposito, este caso y el README se corrigen JUNTOS.")
        for clase, valor in CANARIOS.items():
            if clase == "ruta":
                continue
            self.assertNotIn(valor, salida,
                             "--acciones enseña rutas, y solo rutas: se le ha colado un %s" % clase)

    def test_el_canario_ESTA_en_el_fichero(self):
        """Control del control. Sin esto, los cuatro de arriba pasarian con un fichero vacio y
        estariamos midiendo que la nada no filtra nada."""
        p = self.historial_con_canarios()
        crudo = io.open(p, encoding="utf-8").read()
        for clase, valor in CANARIOS.items():
            self.assertIn(valor, crudo, "el fixture no planto el canario %s" % clase)

    def test_la_herramienta_SI_midio_ese_historial(self):
        """Segundo control: que la salida no lleve canarios porque no leyo nada seria un aprobado
        falso. Tiene que haber medido de verdad."""
        self.historial_con_canarios()
        datos = json.loads(self.ejecutar("--json"))
        self.assertGreater(datos[0]["disparadores"], 0, "no llego a medir el historial")


class TestErroresTampocoFiltran(Base):
    """El camino de error es por donde se suelen escapar las cosas: un mensaje que 'ayuda'."""

    def test_jsonl_corrupto_no_vuelca_su_contenido(self):
        p = os.path.join(self.sesiones, "roto.jsonl")
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            "{esto no es json y lleva dentro %s y %s\n" % (CANARIOS["iban"], CANARIOS["nombre"]))
        salida = self.ejecutar()
        for clase, valor in CANARIOS.items():
            self.assertNotIn(valor, salida, "el aviso de fichero ilegible volco el %s" % clase)

    def test_fichero_ilegible_no_tumba_la_herramienta(self):
        """Falla CERRADO y sigue: un historial con una sesion rota no puede dejar sin medir el
        resto, porque entonces la respuesta seria 'nada' y se leeria como 'cero'."""
        self.historial_con_canarios()
        io.open(os.path.join(self.sesiones, "roto.jsonl"), "wb").write(b"\xff\xfe\x00basura")
        datos = json.loads(self.ejecutar("--json"))
        self.assertGreater(datos[0]["disparadores"], 0, "una sesion rota tumbo toda la medicion")


class TestSoloLectura(Base):
    """Una herramienta que abre todo tu historial no puede tocar nada."""

    def _foto(self, raiz):
        f = {}
        for dp, _, fn in os.walk(raiz):
            for x in fn:
                r = os.path.join(dp, x)
                f[r] = (os.path.getsize(r), os.path.getmtime(r))
        return f

    def test_no_escribe_ni_altera_los_transcripts(self):
        self.historial_con_canarios()
        self.reglas()          # el fichero de reglas lo crea el fixture, no la herramienta:
                               # si se crea DESPUES de la foto, el test se acusa a si mismo
        antes = self._foto(self.tmp)
        self.ejecutar()
        self.ejecutar("--json")
        despues = self._foto(self.tmp)
        self.assertEqual(sorted(antes), sorted(despues), "aparecio o desaparecio algun fichero")
        for r in antes:
            self.assertEqual(antes[r], despues[r], "modifico %s" % os.path.basename(r))

    def test_no_escribe_junto_al_propio_instrumento(self):
        """Ni siquiera un log discreto en su carpeta: quien lo instale decide donde va su rastro."""
        antes = set(os.listdir(AQUI))
        self.historial_con_canarios()
        self.ejecutar()
        nuevos = set(os.listdir(AQUI)) - antes - {"__pycache__"}
        self.assertEqual(nuevos, set(), "dejo ficheros nuevos: %s" % nuevos)



class TestElNombreDelProyectoTampocoSale(Base):
    """Las carpetas de `~/.claude/projects` son la ruta de trabajo, no una etiqueta.

    `C--Users-Fulano-clientes-DESPIDO-CONFIDENCIAL` dice en que trabaja quien ejecuta esto, con
    quien y desde donde. Sacarlo por pantalla es la misma clase de fuga que sacar un IBAN, y este
    caso existe porque los seis canarios de arriba no cubrian esa clase: viven DENTRO del fichero,
    y este vive en la RUTA.

    El fixture monta DOS carpetas a proposito. Con una sola, el aviso que las nombraba no llegaba
    a dispararse y el banco pasaba en verde sobre una vista que si filtraba.
    """

    PROYECTOS = ["C--Users-Fulano-clientes-DESPIDO-CONFIDENCIAL",
                 "C--Users-Fulano-fusion-ACME-secreta"]

    def dos_proyectos(self):
        for proy in self.PROYECTOS:
            carpeta = os.path.join(self.tmp, proy)
            os.makedirs(carpeta)
            regs = []
            for i in range(4):
                regs.append(tool("Write", {"file_path": "/w/doc%d.md" % i}, "w%d" % i))
                regs.append(tool("Bash", {"command": "python run_tests.py"}, "t%d" % i))
            with io.open(os.path.join(carpeta, "sesion.jsonl"), "w",
                         encoding="utf-8", newline=chr(10)) as fh:
                for r in regs:
                    fh.write(json.dumps(r, ensure_ascii=False) + chr(10))

    def _sin_nombres(self, salida, vista):
        for proy in self.PROYECTOS:
            self.assertNotIn(proy, salida,
                             "la vista %s publico el nombre del proyecto" % vista)
            # Y tampoco por partes: el trozo identificable basta para saber de que se trata.
            self.assertNotIn("DESPIDO-CONFIDENCIAL", salida,
                             "la vista %s publico parte del nombre" % vista)

    def test_las_seis_vistas_callan_el_nombre_del_proyecto(self):
        self.dos_proyectos()
        for extra, vista in [((), "normal"), (("--json",), "json"),
                             (("--por-dia", "7"), "por-dia"),
                             (("--curva-ventana",), "curva-ventana"),
                             (("--sensibilidad",), "sensibilidad"),
                             (("--acciones",), "acciones")]:
            self._sin_nombres(self.ejecutar(*extra), vista)

    def test_el_aviso_de_mezcla_SIGUE_saliendo(self):
        """Control al reves. La fuga se cierra quitando los nombres, no quitando el aviso: mezclar
        proyectos falsea las tasas y eso hay que decirlo. Sin este caso, el arreglo facil seria
        callar del todo, y entonces la cifra mezclada se leeria como buena."""
        self.dos_proyectos()
        self.assertIn("proyectos a la vez", self.ejecutar(),
                      "se llevo por delante el aviso de mezcla")

    def test_el_canario_ESTA_en_la_ruta(self):
        """Control del control: sin esto, los de arriba pasarian con las carpetas mal montadas."""
        self.dos_proyectos()
        hay = [d for d in os.listdir(self.tmp) if "DESPIDO" in d]
        self.assertEqual(len(hay), 1, "el fixture no monto la carpeta con el canario")


def hay_mutacion_puesta(residuo=None):
    """True si el arbol tiene una mutacion clavada de una ejecucion de `mutar.py` que murio.

    `mutar.py` guarda una copia intacta en `medir_adherencia.py.original` mientras dura el
    sabotaje y la borra al acabar. Que esa copia siga ahi significa que el proceso no llego a su
    `finally` -- lo mataron -- y que el instrumento esta saboteado AHORA MISMO.
    """
    return os.path.exists(residuo or (MEDIDOR + ".original"))


class TestElInstrumentoNoQuedoSaboteado(unittest.TestCase):
    """Que nadie mida con una mutacion dentro sin enterarse.

    POR QUE (25/07/2026). El docstring de `mutar.py` prometia restaurar el fichero "incluso si algo
    revienta a mitad". Un esceptico lo tumbo matando el proceso a los 400 ms: el `finally` de Python
    no se ejecuta cuando al proceso lo matan sin darle turno, y `medir_adherencia.py` se quedo con
    una mutacion dentro, en silencio, hasta que alguien mirase el `git diff`. Peor todavia: el
    siguiente que midiera algo lo haria con el instrumento roto y saldrian numeros creibles.

    La copia en disco sobrevive a la muerte del proceso y por eso puede sostener la promesa. Pero
    una señal que nadie mira no sirve de nada: esto es quien la mira.
    """

    def test_no_hay_una_mutacion_clavada_en_el_arbol(self):
        if os.environ.get("MUTACION_EN_CURSO"):
            self.skipTest("lo lanza mutar.py: aqui el residuo es lo normal")
        self.assertFalse(
            hay_mutacion_puesta(),
            "queda una mutacion puesta en medir_adherencia.py de una ejecucion que murio a mitad.\n"
            "         Los numeros que salgan ahora NO valen. Restauralo con:  python mutar.py")

    def test_el_guardian_SI_ve_el_residuo_cuando_lo_hay(self):
        """Control positivo. Sin esto, el de arriba pasaria igual con la comprobacion rota, y
        "no hay mutacion" y "no he mirado" se parecen demasiado."""
        tmp = tempfile.mkdtemp(prefix="adh_mut_")
        try:
            falso = os.path.join(tmp, "medir_adherencia.py.original")
            self.assertFalse(hay_mutacion_puesta(falso), "lo vio antes de existir")
            io.open(falso, "w", encoding="utf-8").write(u"copia de mentira")
            self.assertTrue(hay_mutacion_puesta(falso), "no vio el residuo estando puesto")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    sys.exit(0 if r.wasSuccessful() else 1)
