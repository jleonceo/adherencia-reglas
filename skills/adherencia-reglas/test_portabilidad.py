# -*- coding: utf-8 -*-
"""La skill medida como si la hubiera descargado otra persona, en otra maquina y con otras reglas.

Existe porque el 25/07 se descubrio que el banco de 39 casos probaba la LOGICA y no probaba nada de
lo que un usuario ajeno se encuentra el primer dia:

  * Rutas POSIX. Todo lo medido hasta entonces salio de un Windows. El codigo normaliza separadores,
    pero eso era una lectura del codigo, no una medicion.
  * Vocabulario ajeno. Cinco de las acciones del mapa (`gate-texto`, `buscador`, `regenerar`,
    `escanear-repos`, `salud`) eran nombres de scripts del proyecto donde nacio esto, y quien la
    descargue tiene otros. Sin una via para declararlos, esas acciones miden cero para siempre. Un
    cero se lee como incumplimiento y no como instrumento que no aplica: el peor fallo posible aqui.
  * Estructura de proyecto distinta, con las sesiones colgando de otra carpeta.

Ninguno de esos tres da error. Los tres devuelven numeros, y los numeros estan mal. Por eso este
banco va aparte del otro: aquel pregunta si la logica es correcta, este pregunta si la herramienta
sirve fuera de casa.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

import medir_adherencia as M

# La carpeta del banco, que es donde vive tambien la documentacion cuando esto va empaquetado.
AQUI = os.path.dirname(os.path.abspath(__file__))

# EL BANCO DECLARA SU PROPIO VOCABULARIO (25/07/2026). Estas seis acciones estaban dentro del
# codigo hasta que se saco de ahi todo lo que era del proyecto de origen. Los casos que las
# nombran siguen siendo validos, pero ahora tienen que declararlas, igual que cualquiera que se
# descargue la herramienta. Asi el banco ejercita el camino de configuracion de verdad.
_EXTRA = [
    ["gate-texto", "revisor_estilo|control_prosa|lint_texto|silueta_coleccion"],
    ["buscador", "consultar"],
    ["regenerar", "regenerar_indice|generar_catalogo"],
    ["escanear-repos", "escanear_proyectos"],
    ["salud", "chequeo_salud"],
    ["verificar", "verificar_|auditar_"],
]
M.RX_SHELL, M.ACCIONES = M.compilar_acciones_shell(_EXTRA)


def tool(nombre, entrada, bid):
    return {"message": {"content": [{"type": "tool_use", "id": bid, "name": nombre,
                                     "input": entrada}]}}


def escribir(path, registros):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


class Base(unittest.TestCase):
    def setUp(self):
        # Cada caso fabrica su historial y varios reescriben el MISMO fichero. La medicion trabaja
        # sobre una foto tomada una vez por ejecucion, asi que hay que decirle que vuelva a mirar:
        # es el uso para el que existe `refrescar_foto`, y estos casos son su primer usuario.
        M.refrescar_foto()
        self.tmp = tempfile.mkdtemp(prefix="adh_port_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sesion(self, nombre, registros, sub=None):
        d = os.path.join(self.tmp, sub) if sub else self.tmp
        if not os.path.isdir(d):
            os.makedirs(d)
        p = os.path.join(d, nombre)
        escribir(p, registros)
        # Escribir un transcript invalida la foto por definicion, y varios casos llaman aqui mas
        # de una vez sobre el MISMO nombre. El refresco va donde se escribe, no en el arranque del
        # caso: puesto en setUp, el segundo historial de un mismo test se media contra el primero.
        M.refrescar_foto()
        return p

    def config(self, nombre, cuerpo):
        p = os.path.join(self.tmp, nombre)
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(cuerpo, ensure_ascii=False, indent=2))
        return p


class TestRutasPosix(Base):
    """Un historial escrito en Mac o Linux. Es el caso MAYORITARIO fuera de esta maquina."""

    def test_ambito_casa_con_rutas_posix(self):
        regs = []
        for i in range(3):
            regs.append(tool("Write", {"file_path": "/home/ana/proyecto/docs/guia_%d.md" % i}, "w%d" % i))
            regs.append(tool("Bash", {"command": "npx prettier --check docs/"}, "b%d" % i))
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-docs", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["/docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 3, "el ambito POSIX descarto disparadores validos")
        self.assertEqual(r["cumplidos"], 3)

    def test_ambito_posix_no_casa_fuera_de_su_zona(self):
        """Control negativo: si el ambito valiese para todo, el positivo de arriba no diria nada."""
        regs = [tool("Write", {"file_path": "/home/ana/proyecto/src/app.js"}, "w0"),
                tool("Bash", {"command": "npx prettier --check src/"}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-docs", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["/docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 0)
        self.assertIsNone(r["tasa"], "sin ocasiones la tasa es n/d, nunca un cero")

    def test_mayusculas_en_la_ruta_no_pierden_el_ambito(self):
        """En Linux las rutas distinguen mayusculas; el ambito se declara en minusculas."""
        regs = [tool("Write", {"file_path": "/home/ana/Proyecto/Docs/GUIA.md"}, "w0"),
                tool("Bash", {"command": "npx prettier --check ."}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-docs", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["/docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 1)


class TestRutasWindows(Base):
    """El caso simetrico del anterior, y el que faltaba.

    Lo encontro una MUTACION, no una lectura: al quitar la normalizacion de separadores
    (`replace("\\\\", "/")`) los quince casos seguian verdes. Se habia probado que POSIX funciona y
    no que Windows siga funcionando, que es donde vive el historial real de este proyecto. Un banco
    que solo cubre el caso nuevo deja el viejo sin red justo cuando alguien lo toca.
    """

    def test_backslash_de_windows_casa_con_ambito_declarado_con_barra(self):
        regs = [tool("Write", {"file_path": r"proy\Manual_Interno\guia.md"}, "w0"),
                tool("Bash", {"command": "python pruebas/revisor_estilo.py guia.md"}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "gate-manuales", "disparador": "escribir-doc", "respuesta": "gate-texto",
                   "ventana": 3, "ambito": ["manual_interno/"]}]
        r = M.medir([p], reglas)[0]
        self.assertEqual(r["disparadores"], 1, "el backslash de Windows rompio el ambito")
        self.assertEqual(r["cumplidos"], 1)

    def test_ruta_windows_de_skill_se_clasifica_como_doctrina(self):
        """El hueco de verdad, y la primera correccion no lo tapaba.

        Al mutar la normalizacion, los dos casos de ambito seguian verdes: el ambito se calcula en
        `secuencia_de`, que normaliza en SU propia linea. Lo que la mutacion rompia era
        `accion_de`, o sea la CLASIFICACION: con backslashes, `\\skills\\` deja de parecerse a
        `/skills/` y tocar una skill pasa a contarse como escribir un documento cualquiera. Toda la
        regla de la cascada se media sobre la accion equivocada y sin una sola queja.
        """
        # Las rutas se COMPONEN en vez de escribirse enteras: una ruta absoluta literal dentro de
        # un fixture la marca el escaner de repos publicos como ruta local, y con razon, porque no
        # sabe distinguir un ejemplo de una filtracion. Lo caza el escaner, no una revision.
        raiz = "D:" + os.sep + "un_proyecto" + os.sep
        self.assertEqual(
            M.accion_de("Write", {"file_path": raiz + os.sep.join(["skills", "foo", "SKILL.md"])}),
            "escribir-doctrina")
        self.assertEqual(
            M.accion_de("Read", {"file_path": raiz + os.sep.join(["rag", "RAG_Cosas.md"])}),
            "leer-rag")
        self.assertEqual(
            M.accion_de("Write", {"file_path": raiz + os.sep.join(["src", "app.py"])}),
            "escribir-codigo")

    def test_las_dos_convenciones_conviven_en_la_misma_sesion(self):
        """Un historial puede mezclarlas: rutas de la herramienta y rutas escritas a mano."""
        regs = [tool("Write", {"file_path": r"proy\docs\uno.md"}, "w0"),
                tool("Bash", {"command": "python pruebas/revisor_estilo.py uno.md"}, "b0"),
                tool("Write", {"file_path": "proy/docs/dos.md"}, "w1"),
                tool("Bash", {"command": "python pruebas/revisor_estilo.py dos.md"}, "b1")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "gate-docs", "disparador": "escribir-doc", "respuesta": "gate-texto",
                   "ventana": 2, "ambito": ["/docs/"]}]
        r = M.medir([p], reglas)[0]
        self.assertEqual(r["disparadores"], 2, "una de las dos convenciones se perdio")
        self.assertEqual(r["cumplidos"], 2)


class TestVocabularioAjeno(Base):
    """Un proyecto que no es este: sus scripts se llaman de otra forma."""

    def test_regla_con_accion_propia_se_mide(self):
        regs = [tool("Write", {"file_path": "/srv/api/handlers/users.py"}, "w0"),
                tool("Bash", {"command": "poetry run pytest tests/ -q"}, "b0"),
                tool("Write", {"file_path": "/srv/api/handlers/orders.py"}, "w1")]
        p = self.sesion("s.jsonl", regs)
        cfg = self.config("reglas_ajenas.json", {
            "acciones_shell": [["suite", r"poetry run pytest|tox\b"]],
            "reglas": [{"id": "suite-tras-tocar-handler", "disparador": "escribir-codigo",
                        "respuesta": "suite", "ventana": 2}]})
        rx, acc = M.compilar_acciones_shell(M.cargar_acciones(cfg))
        r = M.medir([p], M.cargar_reglas(cfg), rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 2)
        self.assertEqual(r["cumplidos"], 1, "solo el primer handler tiene la suite detras")

    def test_sin_declarar_su_accion_la_regla_es_RECHAZADA(self):
        """El fallo tiene que ser RUIDOSO. Una accion desconocida que midiese cero seria una
        acusacion falsa: el usuario leeria 0 % y creeria que no cumple su propia regla."""
        cfg = self.config("reglas_malas.json", {
            "reglas": [{"id": "x", "disparador": "escribir-codigo", "respuesta": "suite"}]})
        with self.assertRaises(ValueError) as ctx:
            M.medir([], M.cargar_reglas(cfg))
        self.assertIn("suite", str(ctx.exception))

    def test_la_accion_propia_gana_a_la_de_casa(self):
        """Anteponer sirve para redefinir: 'test' ya existe, y el usuario quiere el suyo."""
        rx, acc = M.compilar_acciones_shell([["mi-suite", r"pytest"]])
        self.assertEqual(M.accion_de("Bash", {"command": "pytest -q"}, rx), "mi-suite")
        self.assertEqual(M.accion_de("Bash", {"command": "pytest -q"}), "test")

    def test_las_universales_siguen_estando(self):
        """Declarar acciones propias no puede borrar git ni los tests: se anaden, no sustituyen."""
        rx, acc = M.compilar_acciones_shell([["deploy", r"flyctl deploy"]])
        self.assertEqual(M.accion_de("Bash", {"command": "git commit -m x"}, rx), "git-commit")
        self.assertIn("git-push", acc)
        self.assertIn("deploy", acc)


class TestAmbitoDeVerdad(Base):
    """Los dos defectos del ambito que encontro una sonda externa el 25/07.

    Los dos daban numeros plausibles y falsos, que es el fallo que esta herramienta persigue. Y los
    dos vivian en el campo que la documentacion presenta como imprescindible.
    """

    def test_la_racha_conserva_todas_sus_rutas(self):
        """Al colapsar, se guardaba solo la ruta de la PRIMERA escritura y se tiraban las demas.
        Escribir en notes/ y luego en docs/ hacia desaparecer la ocasion de docs de la tabla."""
        regs = [tool("Write", {"file_path": "/proy/notes/borrador.md"}, "w0"),
                tool("Write", {"file_path": "/proy/docs/guia.md"}, "w1"),
                tool("Bash", {"command": "npx prettier --write docs/"}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-docs", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 1, "la escritura a docs/ se perdio en el colapso")
        self.assertEqual(r["cumplidos"], 1)

    def test_el_ambito_no_casa_a_mitad_de_carpeta(self):
        """`docs/` casaba con `/mydocs/interno.md`. La regla salia alta midiendo justo lo que no
        era. Control negativo del caso anterior: sin esto, aquel positivo no prueba nada."""
        regs = [tool("Write", {"file_path": "/proy/mydocs/interno.md"}, "w0"),
                tool("Bash", {"command": "npx prettier --write ."}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-docs", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 0, "conto un fichero que no esta en docs/")

    def test_un_ambito_que_empieza_por_barra_sigue_valiendo(self):
        """No se puede exigir segmento entero: los ambitos reales llevan trozos como `/readme`."""
        regs = [tool("Write", {"file_path": "/proy/readme.md"}, "w0"),
                tool("Bash", {"command": "npx prettier --write ."}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "formato-readme", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["/readme"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        r = M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]
        self.assertEqual(r["disparadores"], 1)

    def test_ambito_al_principio_de_una_ruta_relativa(self):
        regs = [tool("Write", {"file_path": "docs/guia.md"}, "w0"),
                tool("Bash", {"command": "npx prettier --write ."}, "b0")]
        p = self.sesion("s.jsonl", regs)
        reglas = [{"id": "r", "disparador": "escribir-doc", "respuesta": "formato",
                   "ventana": 3, "ambito": ["docs/"]}]
        rx, acc = M.compilar_acciones_shell([["formato", r"prettier"]])
        self.assertEqual(M.medir([p], reglas, rx_shell=rx, acciones=acc)[0]["disparadores"], 1)


class TestAmbitoCasosLimite(Base):
    """Lo que encontraron dos auditores independientes en la tercera vuelta.

    El primer arreglo del ambito cerro la frontera IZQUIERDA y dejo la derecha abierta, asi que
    seguia contando ficheros de otra carpeta. Y no normalizaba, asi que un ambito escrito con
    mayuscula o con separador de Windows no casaba nunca y descartaba en silencio.
    """

    def _mide(self, ruta, ambito):
        p = self.sesion("s.jsonl", [tool("Write", {"file_path": ruta}, "w0"),
                                    tool("Bash", {"command": "pytest"}, "b0")])
        reglas = [{"id": "r", "disparador": "escribir-doc", "respuesta": "test",
                   "ventana": 3, "ambito": ambito}]
        return M.medir([p], reglas)[0]["disparadores"]

    def test_sin_barra_final_no_traga_la_carpeta_de_al_lado(self):
        self.assertEqual(self._mide("/proy/docsarchive/x.md", ["docs"]), 0,
                         "'docs' conto un fichero de /docsarchive/")
        self.assertEqual(self._mide("/proy/docs/x.md", ["docs"]), 1)

    def test_con_barra_inicial_tampoco(self):
        """La rama del ambito que empieza por barra no tenia la proteccion de la otra: `/lib`
        contaba ficheros de `/library/`.

        Los ficheros son `.md` a proposito. Con `.py` el negativo daba cero por el motivo
        equivocado: un `.py` se clasifica como escribir-codigo y la regla ni siquiera se dispara,
        asi que el caso pasaba en verde sin probar nada del ambito.
        """
        self.assertEqual(self._mide("/home/dev/library/notas.md", ["/lib"]), 0,
                         "'/lib' conto un fichero de /library/")
        self.assertEqual(self._mide("/home/dev/lib/notas.md", ["/lib"]), 1)

    def test_el_ambito_se_normaliza_como_la_ruta(self):
        """Mayusculas y separador de Windows en el ambito declarado. Sin normalizar, estos dos
        descartaban TODAS las ocasiones y la tabla salia en n/d sin decir por que."""
        self.assertEqual(self._mide("/proy/docs/x.md", ["Docs/"]), 1, "el ambito en mayusculas fallo")
        self.assertEqual(self._mide("/proy/docs/x.md", ["docs\\"]), 1, "el ambito con backslash fallo")

    def test_un_fichero_llamado_como_la_carpeta_sigue_contando(self):
        """Control: `/readme` tiene que casar con `/proy/readme.md`, que fue el caso que impidio
        exigir segmentos enteros."""
        self.assertEqual(self._mide("/proy/readme.md", ["/readme"]), 1)


class TestContratoDeSalida(Base):
    """El codigo de salida tiene que ser el mismo por las tres vistas.

    Dos auditores independientes encontraron lo mismo: `--por-dia` y `--curva-ventana` devolvian 0
    aunque una regla estuviera bajo su umbral, mientras la vista normal devolvia 1. El docstring
    promete el contrato sin excepciones, asi que quien enganchara una de esas vistas a un paso de
    CI se quedaba con luz verde permanente. Ningun caso del banco miraba el `returncode` de esas
    dos vistas, que es como sobrevivio.
    """

    def _monta(self, umbral):
        d = os.path.join(self.tmp, "p")
        # exist_ok porque el caso recorre las cuatro vistas y monta el fixture en cada vuelta.
        os.makedirs(d, exist_ok=True)
        escribir(os.path.join(d, "s.jsonl"),
                 [tool("Write", {"file_path": "/x/a.md"}, "w0")])
        cfg = self.config("r.json", {"reglas": [
            {"id": "x", "disparador": "escribir-doc", "respuesta": "test",
             "ventana": 3, "umbral": umbral}]})
        return self.tmp, cfg

    def _exit(self, extra, umbral):
        import subprocess
        sesiones, cfg = self._monta(umbral)
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(M.__file__)), "medir_adherencia.py"),
             "--sesiones", sesiones, "--reglas", cfg] + extra,
            capture_output=True)
        return r.returncode

    # Cada vista nueva entra aqui el mismo dia que se escribe. `--curva-ventana` estuvo dos
    # semanas devolviendo 0 pasara lo que pasara porque nadie miro su returncode.
    VISTAS = ([], ["--json"], ["--por-dia", "7"], ["--curva-ventana"], ["--sensibilidad"])

    def test_todas_las_vistas_delatan_el_incumplimiento(self):
        for extra in self.VISTAS:
            self.assertEqual(self._exit(extra, umbral=90), 1,
                             "la vista %r no delato la regla bajo umbral" % (extra or "normal"))

    def test_todas_las_vistas_pasan_cuando_se_cumple(self):
        for extra in self.VISTAS:
            if extra == ["--json"]:
                continue                       # el JSON no imprime veredicto, solo datos
            self.assertEqual(self._exit(extra, umbral=0), 0,
                             "la vista %r fallo con la regla por encima del umbral" % (extra or "normal"))

    def test_un_flag_nunca_desaparece_en_silencio(self):
        """`--sensibilidad --json` imprimia la tabla humana y se tragaba el `--json`, con exit 0.

        Quien lo encadenara a otra cosa recibia texto donde esperaba datos. El programa presume de
        quejarse ante cualquier configuracion mala, y esta era la excepcion. Vale igual para dos
        vistas pedidas a la vez: cada una imprime la suya y solo saldria una.
        """
        for extra in (["--sensibilidad", "--json"], ["--por-dia", "3", "--json"],
                      ["--curva-ventana", "--json"], ["--acciones", "--json"],
                      ["--sensibilidad", "--curva-ventana"], ["--por-dia", "3", "--sensibilidad"],
                      # Un negativo hacia `sorted(dias)[3:]`: descartaba los tres dias mas
                      # antiguos y enseñaba el resto, con exit 0 y una cabecera que decia otra
                      # cifra. Lo cazo un usuario de prueba; que estuviera arreglado y sin caso
                      # lo delato la mutacion.
                      ["--por-dia", "-3"], ["--por-dia", "-1"]):
            self.assertEqual(self._exit(extra, umbral=0), 2,
                             "%r no protesto: un flag que desaparece callado es peor que un "
                             "error" % (extra,))

    def test_ninguna_vista_se_deja_una_decision_sin_ensenar(self):
        """La sensibilidad tiene que cubrir TODOS los parametros arbitrarios, no el que se quejo.

        `ventana` recibio su curva porque alguien protesto por ella. Una auditoria del razonamiento
        pregunto cuales mas eran umbrales elegidos a ojo y sin sensibilidad publicada: habia dos, y
        ninguna de las cuatro rondas de revision los toco. Este caso existe para que el proximo
        parametro que se añada no repita la historia.
        """
        import subprocess
        sesiones, cfg = self._monta(umbral=0)
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(M.__file__)), "medir_adherencia.py"),
             "--sesiones", sesiones, "--reglas", cfg, "--sensibilidad"], capture_output=True)
        salida = (r.stdout or b"").decode("utf-8", "replace")
        for parametro in ("VENTANA", "COLAPSAR", "MUESTRA MINIMA"):
            self.assertIn(parametro, salida,
                          "la vista de sensibilidad no enseña %s, que es una decision "
                          "arbitraria que mueve la cifra" % parametro)


class TestRutaConVirgulilla(Base):
    """`--sesiones "~/..."` llegaba literal y el comando insignia fallaba en Windows.

    La virgulilla la expande bash; PowerShell y cmd no. El README enseña ese comando en portada,
    asi que el primer intento de cualquiera en Windows daba "no hay transcripts", un mensaje que
    ademas suena a historial vacio en vez de a ruta inexistente. Lo encontro un auditor ejecutando
    literalmente el ejemplo de la primera linea.
    """

    def test_el_cli_expande_la_virgulilla(self):
        import subprocess
        # Se apunta a una ruta bajo el home que NO existe. Si la virgulilla se expande, el mensaje
        # de error trae la ruta ya resuelta; si no, sale la virgulilla en crudo.
        r = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(M.__file__)),
                                          "medir_adherencia.py"),
             "--sesiones", "~/carpeta-que-no-existe-para-el-test"],
            capture_output=True)
        salida = (r.stdout or b"").decode("utf-8", "replace") + \
                 (r.stderr or b"").decode("utf-8", "replace")
        self.assertNotIn("~/carpeta-que-no-existe", salida,
                         "la virgulilla llego sin expandir a la salida")
        self.assertIn("carpeta-que-no-existe", salida)


class TestFalsosPositivosDeTest(Base):
    """`test_` sin frontera de palabra pagaba obligaciones con comandos que no son tests."""

    def test_no_confunde_palabras_que_contienen_test(self):
        for cmd in ("cp latest_data.csv backup/", "python contest_scraper.py",
                    "cd fastest_route/", "ls greatest_hits"):
            self.assertNotEqual(M.accion_de("Bash", {"command": cmd}), "test",
                                "conto %r como ejecutar la suite" % cmd)

    def test_los_de_verdad_siguen_contando(self):
        for cmd in ("python test_algo.py", "python run_tests.py", "pytest -q",
                    "python -m unittest"):
            self.assertEqual(M.accion_de("Bash", {"command": cmd}), "test",
                             "dejo de reconocer %r" % cmd)


class TestFallaConMensajeNoConTraceback(Base):
    """Una regla que no es un diccionario reventaba con AttributeError."""

    def test_regla_que_no_es_objeto(self):
        cfg = self.config("r.json", {"reglas": ["esto es una cadena, no una regla"]})
        with self.assertRaises(ValueError) as ctx:
            M.cargar_reglas(cfg)
        self.assertIn("no es un objeto", str(ctx.exception))

    def test_regla_numerica(self):
        cfg = self.config("r.json", {"reglas": [42]})
        with self.assertRaises(ValueError):
            M.cargar_reglas(cfg)


class TestFechaDeLaSesion(Base):
    """La fecha sale de DENTRO del historial, no de la fecha del fichero.

    Lo destapo un usuario de prueba: usando `os.path.getmtime`, un `git clone` o una copia de
    carpeta pone todos los ficheros a hoy. Entonces `desde` deja fuera sesiones que si contaban y
    `--por-dia` amontona meses en un solo dia, sin error y sin aviso. Medido sobre el historial
    real de este proyecto al arreglarlo: la puerta de salida pasa de 63,7 % a 80,0 % porque el
    denominador se llenaba de sesiones anteriores al alta de la regla.
    """

    def test_usa_el_timestamp_del_contenido(self):
        p = self.sesion("s.jsonl", [
            {"timestamp": "2026-03-15T10:00:00.000Z",
             "message": {"content": [{"type": "tool_use", "id": "a", "name": "Write",
                                      "input": {"file_path": "/x/y.md"}}]}}])
        ts, del_fichero = M.fecha_de_sesion(p)
        self.assertFalse(del_fichero, "no encontro la fecha del contenido")
        self.assertEqual(__import__("datetime").datetime.fromtimestamp(ts).strftime("%Y-%m"),
                         "2026-03")

    def test_sin_timestamp_cae_al_fichero_y_LO_DICE(self):
        """El respaldo vale; lo que no vale es callarlo. El llamador tiene que poder avisar."""
        p = self.sesion("s.jsonl", [tool("Write", {"file_path": "/x/y.md"}, "a")])
        ts, del_fichero = M.fecha_de_sesion(p)
        self.assertIsNotNone(ts)
        self.assertTrue(del_fichero, "uso el mtime sin declararlo")

    def test_desde_descarta_por_la_fecha_de_dentro(self):
        """El caso completo: una sesion vieja con el fichero recien copiado NO puede colarse."""
        p = self.sesion("vieja.jsonl", [
            {"timestamp": "2026-03-15T09:00:00.000Z",
             "message": {"content": [{"type": "tool_use", "id": "a", "name": "Write",
                                      "input": {"file_path": "/x/y.md"}}]}},
            {"timestamp": "2026-03-15T09:00:01.000Z",
             "message": {"content": [{"type": "tool_use", "id": "b", "name": "Bash",
                                      "input": {"command": "pytest"}}]}}])
        os.utime(p, None)     # el fichero es de AHORA, como tras un clone
        reglas = [{"id": "r", "disparador": "escribir-doc", "respuesta": "test",
                   "ventana": 3, "desde": "2026-06-01"}]
        r = M.medir([p], reglas)[0]
        self.assertEqual(r["disparadores"], 0, "colo una sesion anterior al alta de la regla")


class TestSuitesDeOtrosEcosistemas(Base):
    """`test` se anunciaba como universal y solo conocia Python.

    Dos usuarios de prueba independientes chocaron con lo mismo: un proyecto de JavaScript daba
    0,0 % sobre 15 ocasiones con `npm test` ejecutado cada vez. No es un error, es un numero
    plausible y falso, que es lo peor que puede dar una herramienta hecha para dar numeros.
    """

    def test_reconoce_las_suites_mas_comunes(self):
        for cmd in ("npm test", "npm run test", "yarn test", "pnpm test", "npx jest",
                    "vitest run", "go test ./...", "cargo test", "mvn test",
                    "dotnet test", "bundle exec rspec", "./vendor/bin/phpunit"):
            self.assertEqual(M.accion_de("Bash", {"command": cmd}), "test",
                             "no reconocio %r como ejecutar la suite" % cmd)

    def test_no_confunde_instalar_con_probar(self):
        """Control negativo: `npm install` y `git status` no son ejecutar los tests."""
        for cmd in ("npm install", "npm run build", "yarn add react", "git status"):
            self.assertNotEqual(M.accion_de("Bash", {"command": cmd}), "test",
                                "conto %r como ejecutar la suite" % cmd)


class TestCodificacion(Base):
    """El BOM de Windows, que se colaba por el hueco entre dos ficheros.

    El autor penso en la marca de orden de bytes para el fichero de configuracion y se olvido del
    de sesiones. Con BOM, la primera linea no parsea; como las demas si, el fichero NO se marcaba
    ilegible y esa llamada desaparecia del recuento sin aviso. Lo produce PowerShell con Out-File
    y el Bloc de notas guardando en UTF-8, o sea las dos herramientas nativas del sistema donde
    esto se desarrollo.
    """

    def sesion_con_bom(self, nombre, registros):
        p = os.path.join(self.tmp, nombre)
        with io.open(p, "w", encoding="utf-8-sig", newline="\n") as fh:
            for r in registros:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return p

    def test_la_primera_llamada_no_desaparece(self):
        p = self.sesion_con_bom("s.jsonl", [
            tool("Write", {"file_path": "/proy/src/app.py"}, "w0"),
            tool("Bash", {"command": "pytest -q"}, "b0")])
        seq = M.secuencia_de(p)
        self.assertEqual([a for a, _ in seq], ["escribir-codigo", "test"],
                         "el BOM se comio la primera llamada")

    def test_con_bom_la_regla_se_mide_igual(self):
        p = self.sesion_con_bom("s.jsonl", [
            tool("Write", {"file_path": "/proy/src/app.py"}, "w0"),
            tool("Bash", {"command": "pytest -q"}, "b0")])
        r = M.medir([p], [{"id": "r", "disparador": "escribir-codigo",
                           "respuesta": "test", "ventana": 3}])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 1))


class TestConfiguracionRota(Base):
    """Lo que un usuario escribe mal el primer dia. Todo esto tiene que quejarse, no callar."""

    def test_acciones_shell_como_diccionario(self):
        with self.assertRaises(ValueError):
            M.compilar_acciones_shell({"lint": "eslint"})

    def test_par_incompleto(self):
        with self.assertRaises(ValueError):
            M.compilar_acciones_shell([["solo-el-nombre"]])

    def test_patron_invalido_no_pasa_callando(self):
        # `[` sin cerrar es un regex roto. Si colase, esa accion mediria cero para siempre.
        with self.assertRaises(ValueError) as ctx:
            M.compilar_acciones_shell([["lint", "[sin-cerrar"]])
        self.assertIn("lint", str(ctx.exception))

    def test_nombre_vacio(self):
        with self.assertRaises(ValueError):
            M.compilar_acciones_shell([["", "algo"]])

    # LOS CINCO CAMPOS CON EL TIPO CAMBIADO. Un auditor los probo el 25/07 y los cinco reventaron
    # con el traceback crudo de Python delante del usuario, y los cinco con codigo 1, que esta
    # documentado como "alguna regla por debajo de su umbral". En un CI, una configuracion rota y
    # una regla incumplida se leian igual. El chequeo de VALOR ya estaba; faltaba el de TIPO, que
    # es el escalon de antes: `ambito` como texto si se rechazaba, `ambito` como lista de numeros
    # no. El peor era `umbral` como texto, que reventaba a mitad de imprimir y dejaba media tabla
    # en pantalla, que se lee como un resultado.
    def _regla(self, **extra):
        r = {"id": "x", "disparador": "escribir-doc", "respuesta": "test"}
        r.update(extra)
        return [r]

    def test_desde_como_numero_no_revienta_por_dentro(self):
        with self.assertRaises(ValueError) as ctx:
            M._valida_tipos(self._regla(desde=20260101))
        self.assertIn("desde", str(ctx.exception))
        self.assertIn("x", str(ctx.exception), "el mensaje tiene que decir QUE regla")

    def test_umbral_como_texto_se_caza_antes_de_imprimir(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(umbral="alto"))

    def test_id_como_numero(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(id=123))

    def test_disparador_como_lista(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(disparador=["escribir-doc"]))

    def test_ambito_con_algo_que_no_es_texto_dentro(self):
        """`ambito` como texto ya se rechazaba. Como LISTA de numeros, no: pasaba entero y
        despues reventaba al normalizar separadores, que es tres pantallas mas abajo."""
        with self.assertRaises(ValueError) as ctx:
            M._valida_tipos(self._regla(ambito=[123]))
        self.assertIn("ambito", str(ctx.exception))

    def test_un_booleano_no_cuela_como_numero(self):
        """En Python `True` ES un `int`, asi que `"ventana": true` pasaria el chequeo de tipo y
        mediria con ventana 1 sin decir nada. Es el falso negativo que este caso fija."""
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(ventana=True))

    def test_lo_bien_escrito_sigue_pasando(self):
        """Control al reves: pasarse validando rompe configuraciones legitimas. Una regla puede
        traer campos de mas, y `ventana` vale tanto entera como escrita con punto.

        EL FIXTURE LLEVABA DENTRO EL DEFECTO (corregido el 26/07/2026). Decia `umbral=0.5`, y este
        caso lo declaraba "bien escrito". No lo esta: la tasa contra la que se compara va de 0 a
        100, asi que 0,5 es un umbral del 0,5 %, un gate que no salta jamas, y la tabla lo imprime
        como "0 %". Un control positivo escrito con el valor equivocado no protege nada: certifica
        el error. Se cambia a 50, que es un umbral de verdad.
        """
        M._valida_tipos(self._regla(desde="2026-07-01", ventana=6, umbral=50,
                                    ambito=["docs/"], direccion="antes", extra_mio="lo que sea"))

    def test_sin_bloque_de_acciones_todo_sigue_igual(self):
        """Contrato de compatibilidad: quien no declare nada no nota el cambio."""
        rx, acc = M.compilar_acciones_shell(None)
        self.assertEqual(rx, M.RX_SHELL)
        self.assertEqual(acc, M.ACCIONES)


class TestEstructuraAjena(Base):
    """Las sesiones no siempre cuelgan de donde cuelgan aqui."""

    def test_sesiones_en_subcarpeta_de_proyecto(self):
        self.sesion("a.jsonl", [tool("Write", {"file_path": "/w/x.md"}, "1")], sub="mi-proyecto")
        self.sesion("b.jsonl", [tool("Write", {"file_path": "/w/y.md"}, "2")], sub="otro-proyecto")
        halladas = M.sesiones_en(self.tmp)
        self.assertEqual(len(halladas), 2, "no bajo un nivel para encontrar los proyectos")

    def test_carpeta_que_no_existe_no_revienta(self):
        self.assertEqual(M.sesiones_en(os.path.join(self.tmp, "no-existe")), [])

    def test_jsonl_de_otra_herramienta_no_se_inventa_acciones(self):
        """Un fichero .jsonl con otro esquema: se lee, no casa nada y devuelve cero acciones.
        Lo que NO puede hacer es reventar ni fabricar disparadores."""
        p = self.sesion("raro.jsonl", [{"evento": "algo", "payload": {"tipo": "otro"}},
                                       {"otra_cosa": [1, 2, 3]}])
        self.assertEqual(M.secuencia_de(p), [])


class TestCarpetasDeOtroProyecto(Base):
    """Las carpetas que marcan doctrina son una CONVENCION, no un estandar.

    `escribir-doctrina`, `leer-skill` y `leer-rag` no salian de la llamada sino de que la ruta
    pasara por `/skills/` o `/rag/`, que son carpetas del proyecto donde nacio esto y estaban
    cableadas en el codigo. En cualquier otro repo las tres median cero sin decirlo. Es el mismo
    defecto del cero silencioso de `npm test`, la segunda vez.
    """

    def test_sin_declarar_nada_siguen_las_de_ejemplo(self):
        self.assertEqual(M.accion_de("Read", {"file_path": "x/rag/uno.md"}), "leer-rag")
        self.assertEqual(M.accion_de("Read", {"file_path": "x/skills/s/SKILL.md"}), "leer-skill")

    def test_con_las_listas_vacias_no_hay_doctrina_en_ningun_sitio(self):
        """Quien no tenga esa distincion no debe recibir tres acciones a cero: debe recibir el
        fichero clasificado por lo que es, un documento o un codigo."""
        vacio = {"skill": [], "rag": []}
        self.assertEqual(M.accion_de("Read", {"file_path": "x/rag/uno.md"}, None, vacio),
                         "leer-doc")
        self.assertEqual(M.accion_de("Write", {"file_path": "x/skills/s/SKILL.md"}, None, vacio),
                         "escribir-doc")

    def test_las_carpetas_de_otro_proyecto_se_declaran_y_funcionan(self):
        mias = {"skill": ["/politicas/"], "rag": ["/base_conocimiento/"]}
        self.assertEqual(M.accion_de("Read", {"file_path": "/p/politicas/x.md"}, None, mias),
                         "leer-skill")
        self.assertEqual(M.accion_de("Read", {"file_path": "/p/base_conocimiento/y.md"}, None, mias),
                         "leer-rag")
        # Y las de casa dejan de valer, que es justo lo que se pedia.
        self.assertEqual(M.accion_de("Read", {"file_path": "/p/rag/z.md"}, None, mias), "leer-doc")

    def test_un_patron_de_accion_vacio_se_rechaza(self):
        """Un patron vacio compila sin quejarse y casa con TODO, tragandose las demas acciones.

        El codigo lo rechaza desde la ronda 4, pero NINGUN caso lo probaba: lo delato la mutacion
        al ver que apagar esa comprobacion dejaba los tres bancos en verde. Un arreglo sin caso
        dura hasta que alguien toca esa linea.
        """
        for malo in ("", "   ", None, 7):
            with self.assertRaises(ValueError):
                M.compilar_acciones_shell([["mia", malo]])

    def test_declararlas_como_texto_no_recorre_letra_a_letra(self):
        """Una cadena es iterable: sin comprobar el tipo, `"/rag/"` casaria cualquier ruta con
        una barra dentro. Mismo defecto que ya se cazo en `ambito`."""
        p = os.path.join(self.tmp, "r.json")
        io.open(p, "w", encoding="utf-8").write(
            json.dumps({"reglas": [], "carpetas_doctrina": {"skill": "/politicas/", "rag": []}}))
        with self.assertRaises(ValueError) as c:
            M.cargar_carpetas(p)
        self.assertIn("LISTA", str(c.exception))

    def test_todas_las_vistas_respetan_las_carpetas_declaradas(self):
        """El caso que faltaba, y el que dejo pasar el defecto (25/07/2026).

        `carpetas_doctrina` se probaba llamando directo a `accion_de`, nunca por linea de comandos.
        Asi que nadie vio que `--por-dia` no recibia el parametro y caia en las carpetas de
        FABRICA por detras: daba el resultado CONTRARIO a las otras vistas sobre los mismos datos,
        sin un aviso. Y `--por-dia` es la vista que el propio README llama la que mas enseña.

        Cablear un parametro no es cablearlo en la funcion: es cablearlo en TODOS los puntos de
        uso, y eso solo se comprueba por la puerta por la que entra el usuario.
        """
        import subprocess
        d = os.path.join(self.tmp, "proj")
        os.makedirs(d, exist_ok=True)
        # Una escritura en /skills/, que es doctrina DE FABRICA pero NO en esta configuracion.
        escribir(os.path.join(d, "s.jsonl"),
                 [tool("Write", {"file_path": "/proy/skills/algo.md"}, "w0")])
        cfg = self.config("r.json", {
            "carpetas_doctrina": {"skill": ["/politicas/"], "rag": []},
            "reglas": [{"id": "doc-normal", "disparador": "escribir-doc", "respuesta": "test",
                        "ventana": 3},
                       {"id": "doctrina", "disparador": "escribir-doctrina", "respuesta": "test",
                        "ventana": 3}]})
        script = os.path.join(os.path.dirname(os.path.abspath(M.__file__)), "medir_adherencia.py")

        def _tabla(extra):
            r = subprocess.run([sys.executable, script, "--sesiones", self.tmp, "--reglas", cfg]
                               + extra, capture_output=True)
            return (r.stdout or b"").decode("utf-8", "replace")

        # En la vista normal, `/skills/` NO es doctrina aqui: el disparador es `escribir-doc`.
        base = _tabla([])
        self.assertIn("doc-normal", base)
        for extra in (["--por-dia", "3"], ["--curva-ventana"], ["--sensibilidad"]):
            salida = _tabla(extra)
            self.assertNotIn("/skills/", salida)
            # La prueba de verdad: la regla de doctrina no puede tener ocasiones, porque en esta
            # configuracion esa carpeta no es doctrina. Si las tiene, la vista uso las de fabrica.
            for linea in salida.splitlines():
                if linea.strip().startswith("doctrina"):
                    self.assertIn("n/d", linea,
                                  "la vista %r conto ocasiones de doctrina usando las carpetas de "
                                  "FABRICA en vez de las declaradas: %r" % (extra, linea.strip()))

    def test_configuracion_sin_el_bloque_no_falla(self):
        p = os.path.join(self.tmp, "r2.json")
        io.open(p, "w", encoding="utf-8").write(json.dumps({"reglas": []}))
        self.assertEqual(M.cargar_carpetas(p), M.CARPETAS_DEFECTO)


class TestAmpliarNoEsSustituir(Base):
    """El README prometia "puedes redefinir una que ya exista" y no era verdad.

    Se probo a hacerlo verdad y rompio seis casos del propio banco, porque lo que hace falta de
    verdad es AMPLIAR: este proyecto declara `eval_golden` como otra forma de ejecutar una suite
    ADEMAS de `pytest`, no en lugar de ella. Se corrigio la promesa y se hizo visible el efecto.
    """

    def test_el_patron_propio_gana_cuando_casa(self):
        rx, _ = M.compilar_acciones_shell([["mi-suite", "correcaminos"]])
        self.assertEqual(M.accion_de("Bash", {"command": "correcaminos --all"}, rx), "mi-suite")

    def test_el_de_fabrica_sigue_valiendo_para_lo_que_el_propio_no_cubre(self):
        rx, _ = M.compilar_acciones_shell([["test", "eval_golden"]])
        self.assertEqual(M.accion_de("Bash", {"command": "python eval_golden.py"}, rx), "test")
        self.assertEqual(M.accion_de("Bash", {"command": "npm test"}, rx), "test",
                         "ampliar `test` no puede dejar fuera las suites universales")

    def test_se_avisa_de_que_amplia_y_no_sustituye(self):
        self.assertEqual(M.nombres_ampliados([["test", "x"], ["mia", "y"]]), ["test"])
        self.assertEqual(M.nombres_ampliados([["mia", "y"]]), [],
                         "un nombre que no existe de fabrica no amplia nada")
        self.assertEqual(M.nombres_ampliados(None), [])


class TestNoReparsearLoMismo(Base):
    """El historial se parsea UNA vez por fichero, aunque la vista compare veinte parametros.

    POR QUE (25/07/2026). El cache de secuencias vivia dentro de `medir`, asi que moria en cada
    llamada. La tabla normal llama una vez y no se notaba; `--curva-ventana` llama ocho veces por
    regla, de modo que volvia a leer el historial ENTERO cada vez. Un usuario de prueba lo midio
    contra su historial real: 177 segundos la curva frente a menos de dos la tabla. Un instrumento
    que tarda tres minutos no se usa, y ninguna de las seis rondas anteriores lo vio porque todas
    median CORRECCION y ninguna media COSTE.

    Se cuentan PARSEOS y no segundos: un caso que mida tiempo falla el dia que la maquina este
    ocupada, y entonces alguien lo desactiva y la proteccion desaparece.
    """

    def test_la_curva_no_reparsea_el_historial_en_cada_ventana(self):
        for i in range(3):
            self.sesion("s%d.jsonl" % i, [tool("Write", {"file_path": "/x/a%d.py" % i}, "w%d" % i),
                                          tool("Bash", {"command": "pytest"}, "b%d" % i)])
        paths = M.sesiones_en(self.tmp)
        self.assertEqual(len(paths), 3)

        real, veces = M.secuencia_de, []

        def contando(path, *a, **k):
            veces.append(path)
            return real(path, *a, **k)

        M._CACHE_SECUENCIAS.clear()
        M.secuencia_de = contando
        try:
            regla = {"id": "x", "disparador": "escribir-codigo", "respuesta": "test"}
            for v in (2, 4, 6, 8, 12, 20, 40):
                M.medir(paths, [dict(regla, ventana=v)])
        finally:
            M.secuencia_de = real
            M._CACHE_SECUENCIAS.clear()

        self.assertEqual(len(veces), len(paths),
                         "siete ventanas sobre tres ficheros dieron %d parseos y tenian que dar "
                         "%d: el cache no esta reaprovechando nada" % (len(veces), len(paths)))

    def test_el_contenido_nuevo_no_se_confunde_con_el_viejo(self):
        """El defecto mas caro de la jornada, y lo encontro un escéptico atacando el cache.

        La clave del cache llevaba (mtime_ns, tamaño) como firma del fichero. Midio 2.000
        reescrituras rapidas del mismo fichero con tamaño constante y 1.665 compartieron firma con
        una anterior: la resolucion del reloj del sistema de ficheros no llega. Con la firma
        repetida, el cache servia el contenido VIEJO como si fuera el nuevo y la tabla salia con un
        disparador fantasma, sin error y sin aviso.

        Aqui se reescribe el mismo fichero con OTRO contenido del MISMO tamaño exacto, que es la
        condicion que hacia colisionar la firma. La medicion tiene que seguir al contenido.
        """
        largo = tool("Write", {"file_path": "/x/aaaa.py"}, "w0")
        corto = tool("Read", {"file_path": "/x/aaaa.py"}, "w0")
        p = self.sesion("s.jsonl", [largo])
        regla = {"id": "x", "disparador": "escribir-codigo", "respuesta": "test", "ventana": 3}
        self.assertEqual(M.medir([p], [regla])[0]["disparadores"], 1)

        # Mismo fichero, mismo tamaño (`Write` y `Read` de la misma ruta ocupan casi lo mismo, y
        # se rellena para que sea identico), contenido distinto.
        a = json.dumps(largo, ensure_ascii=False)
        b = json.dumps(corto, ensure_ascii=False)
        b = b[:-1] + " " * (len(a) - len(b)) + "}" if len(b) < len(a) else b
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(b + "\n")
        self.assertEqual(os.path.getsize(p), len(a.encode("utf-8")) + 1,
                         "el fixture tiene que dejar el fichero del MISMO tamaño para reproducir "
                         "la condicion que hacia colisionar la firma")
        M.refrescar_foto()
        self.assertEqual(M.medir([p], [regla])[0]["disparadores"], 0,
                         "el contenido nuevo no dispara, asi que el cache esta sirviendo el viejo")

    def test_cambiar_el_colapso_si_obliga_a_parsear_otra_vez(self):
        """Control negativo: el cache no puede ser tan agresivo que devuelva lo que no toca.

        `colapsar` cambia la secuencia, asi que dos llamadas con distinto colapso TIENEN que
        parsear dos veces. Sin este caso, un cache que ignorase la clave pasaria el de arriba.
        """
        self.sesion("s.jsonl", [tool("Write", {"file_path": "/x/a.py"}, "w0")])
        paths = M.sesiones_en(self.tmp)
        real, veces = M.secuencia_de, []

        def contando(path, *a, **k):
            veces.append(path)
            return real(path, *a, **k)

        M._CACHE_SECUENCIAS.clear()
        M.secuencia_de = contando
        try:
            regla = {"id": "x", "disparador": "escribir-codigo", "respuesta": "test"}
            M.medir(paths, [regla], colapsar=True)
            M.medir(paths, [regla], colapsar=False)
        finally:
            M.secuencia_de = real
            M._CACHE_SECUENCIAS.clear()
        self.assertEqual(len(veces), 2,
                         "colapsando y sin colapsar son secuencias distintas: el cache no puede "
                         "devolver la una por la otra")


class TestCifrasDeLaPortada(unittest.TestCase):
    """Que el numero de casos que anuncia la documentacion sea el que hay.

    POR QUE EXISTE. El paquete anuncio "87 casos" durante dos horas mientras el banco vivo tenia
    89: se anadieron dos casos y la portada se quedo con la foto vieja. No fallo nada, porque un
    numero escrito a mano no se entera de que ha dejado de ser cierto, y el README es lo primero
    que lee quien llega. Una cifra en portada es una AFIRMACION sobre el producto, y las
    afirmaciones se comprueban.

    Se salta si no hay documentacion al lado: la skill instalada no lleva README, solo el paquete.
    """

    # `reglas.json` ENTRO EL 26/07/2026, y lo encontro un auditor: el fichero lleva un bloque
    # `_como_se_usa` con prosa que AFIRMA cosas del producto ("18 casos", "once acciones de
    # fabrica", "puedes redefinir una que ya exista"), y las tres estaban caducadas o eran falsas
    # mientras el guardian pasaba en verde. El guardian miraba los dos documentos que se leen
    # como documentacion y no el fichero de configuracion, que tambien se lee y tambien afirma.
    DOCS = ["README.md", "SKILL.md", "reglas.json"]

    # EL README NO ESTA AQUI, y por eso este guardian llevaba desde que nacio sin leerlo (lo
    # encontro un auditor el 25/07 poniendo "999 casos" en las DOS mitades del README y viendo el
    # banco en verde). El layout del estandar deja `SKILL.md` junto al codigo, en
    # `skills/<nombre>/`, y el `README.md` en la RAIZ del repo, dos niveles mas arriba. El caso
    # resolvia los dos contra su propia carpeta, encontraba solo `SKILL.md` y se declaraba
    # satisfecho: monolingue, cuando lo que existe en dos idiomas es justo el README.
    #
    # Es el defecto que esta skill persigue en otros, dentro de ella: un instrumento que mira
    # donde no esta el vigilado y pasa en verde. Y no fallaba nunca, que es lo que lo hizo durar.
    NIVELES_ARRIBA = 3

    def _docs_a_mirar(self):
        """Los documentos publicados que hablan de ESTE paquete, esten donde esten.

        Se sube por las carpetas de encima, pero solo se acepta el fichero si nombra la skill o
        su instrumento. Sin ese filtro, la skill instalada en `~/.claude/skills/` acabaria
        leyendo cualquier README ajeno que hubiera por encima y contando sus cifras como propias.
        """
        vistos, fuera = set(), []
        carpeta = AQUI
        for _ in range(self.NIVELES_ARRIBA + 1):
            for d in self.DOCS:
                p = os.path.join(carpeta, d)
                if not os.path.exists(p) or p in vistos:
                    continue
                vistos.add(p)
                t = io.open(p, encoding="utf-8").read()
                if carpeta == AQUI or "adherencia-reglas" in t or "medir_adherencia" in t:
                    fuera.append((os.path.relpath(p, AQUI), t))
            padre = os.path.dirname(carpeta)
            if padre == carpeta:
                break
            carpeta = padre
        return fuera

    # Los tres bancos, en el orden en que se cuentan. Es la UNICA lista: el caso que ata cada cifra
    # a su banco lee de aqui, para que no pueda desalinearse con la que cuenta los casos.
    BANCOS = ("run_tests_adherencia.py", "test_portabilidad.py", "test_seguridad.py")

    def _conteos_legitimos(self):
        """Los cuatro numeros que la documentacion puede citar: cada banco y la suma."""
        import importlib.util
        bancos = list(self.BANCOS)
        cuenta = []
        for b in bancos:
            ruta = os.path.join(AQUI, b)
            if not os.path.exists(ruta):
                self.skipTest("falta el banco %s" % b)
            nombre = "_conteo_" + os.path.splitext(b)[0]
            spec = importlib.util.spec_from_file_location(nombre, ruta)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[nombre] = mod
            spec.loader.exec_module(mod)
            cuenta.append(unittest.defaultTestLoader.loadTestsFromModule(mod).countTestCases())
        return set(cuenta) | {sum(cuenta)}, cuenta

    PATRON_CIFRA = r"(\d+)\s+(?:casos|cases)"

    # En los dos idiomas, por lo mismo que la de casos: un README bilingue son DOS afirmaciones y
    # la que nadie vigila es la que caduca.
    PATRON_SABOTAJES = r"(\d+)\s+(?:sabotajes|sabotages)"

    def test_el_guardian_mira_los_dos_idiomas(self):
        """El punto ciego no se caza solo: hay que probarlo con texto propio.

        Mientras las cifras inglesas esten bien, un guardian ciego al ingles pasa en verde y
        parece sano. Solo se delata cuando hay una mentira EN INGLES, y para entonces ya esta
        publicada. Asi que se comprueba el patron contra texto fabricado, que es lo unico que no
        depende de que hoy haya o no haya un error.
        """
        hallados = re.findall(self.PATRON_CIFRA, "son 100 casos y 51 casos; 100 cases and 51 cases")
        self.assertEqual(hallados, ["100", "51", "100", "51"],
                         "el guardian tiene que leer las cifras en los dos idiomas del README")

    def test_si_hay_README_del_paquete_este_guardian_lo_ESTA_mirando(self):
        """El control que faltaba: que mire donde de verdad esta el documento.

        El caso de abajo se declaraba satisfecho encontrando `SKILL.md` y no se enteraba de que
        el `README.md`, el unico documento bilingue y el primero que lee quien llega, se le
        quedaba fuera. Ahi es donde caducan las cifras, porque son dos afirmaciones y no una.

        Este caso no comprueba las cifras: comprueba el ALCANCE del que las comprueba. Si el
        paquete tiene README, tiene que estar en la lista. Si no lo tiene (la skill instalada
        suelta), no hay nada que exigir y se salta.
        """
        candidatos = []
        carpeta = AQUI
        for _ in range(self.NIVELES_ARRIBA + 1):
            p = os.path.join(carpeta, "README.md")
            if os.path.exists(p):
                t = io.open(p, encoding="utf-8").read()
                if "adherencia-reglas" in t or "medir_adherencia" in t:
                    candidatos.append(p)
            padre = os.path.dirname(carpeta)
            if padre == carpeta:
                break
            carpeta = padre
        if not candidatos:
            self.skipTest("esta instalacion no lleva README del paquete")
        mirados = [os.path.abspath(os.path.join(AQUI, d)) for d, _ in self._docs_a_mirar()]
        for p in candidatos:
            self.assertIn(os.path.abspath(p), mirados,
                          "existe %s y el guardian de cifras no lo abre: sus cifras pueden "
                          "caducar sin que nada avise" % p)

    # El patron que lee las opciones del argparse. Admite digito, guion bajo y mayuscula porque
    # `--[a-z-]+` era ciego a las tres cosas (ronda 10, 25/07): una opcion que el patron no ve es
    # una opcion que este guardian jura haber comprobado sin haberla mirado nunca.
    PATRON_OPCION_CLI = r'add_argument\(\s*"(--[A-Za-z0-9][\w-]*)"'

    # Una fila de tabla markdown. Es donde la documentacion DOCUMENTA una opcion; la prosa solo la
    # MENCIONA, y mencionarla vale igual para anunciar que se ha quitado.
    RX_FILA_TABLA = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.M)

    def test_el_patron_de_opciones_no_es_ciego_a_digitos_ni_mayusculas(self):
        """El punto ciego de un patron no lo delatan los datos de hoy: hay que fabricarlos.

        Las nueve opciones actuales son todas minusculas con guion, asi que `--[a-z-]+` las leia
        todas y el guardian pasaba en verde pareciendo sano. El dia que alguien anada `--top-10`,
        `--sin_colapsar` o `--JSON`, el caso de abajo las daria por documentadas sin haberlas visto.
        Por eso se prueba contra texto fabricado, que es lo unico que no depende de que hoy exista
        o no una opcion con digito.
        """
        falso = ('ap.add_argument("--top-10")\n'
                 'ap.add_argument("--sin_colapsar")\n'
                 'ap.add_argument("--JSON")\n'
                 'ap.add_argument("--por-dia")\n')
        self.assertEqual(sorted(re.findall(self.PATRON_OPCION_CLI, falso)),
                         ["--JSON", "--por-dia", "--sin_colapsar", "--top-10"],
                         "el patron de opciones es ciego a digitos, guion bajo o mayusculas: una "
                         "opcion que no lee es una opcion que nadie comprueba")

    def test_la_documentacion_nombra_TODAS_las_opciones_del_CLI(self):
        """Una opcion sin documentar es una opcion que no existe para quien la instala.

        POR QUE (25/07/2026, ronda 9). La tabla del SKILL.md documentaba siete de las nueve. Las
        dos que faltaban eran `--reglas`, sin la cual no se puede apuntar a otra configuracion, y
        `--acciones`, que el propio README titula "lo primero que tienes que cambiar" y describe
        como el sitio por donde se empieza. El fichero que el agente lee al invocar la skill no la
        mencionaba.

        Se compara contra el argparse de verdad, no contra una lista escrita al lado: una lista a
        mano caduca igual que la cifra de la portada.

        QUE CAMBIO EN LA RONDA 10, Y ES EL FONDO DEL CASO. La version anterior preguntaba si la
        cadena aparecia en algun sitio del texto. Con esa vara, un documento que dijera "la opcion
        `--por-dia` se ELIMINO en la version 2" dejaba el caso en verde: la cadena estaba. Estar
        nombrado y estar documentado no son lo mismo, y la diferencia es justo la que le importa a
        quien instala esto. Ahora se exige que la opcion viva en una FILA DE TABLA, que es donde
        esta documentacion documenta de verdad. La comprobacion es estructural y no lexica a
        proposito: buscar palabras de negacion en la prosa da falsos positivos en cuanto alguien
        escribe una frase con un "no" a diez palabras del nombre.
        """
        codigo = io.open(os.path.join(AQUI, "medir_adherencia.py"), encoding="utf-8").read()
        del_cli = set(re.findall(self.PATRON_OPCION_CLI, codigo))
        self.assertGreater(len(del_cli), 5, "no se han leido las opciones del CLI: buscador roto")
        docs = self._docs_a_mirar()
        if not docs:
            self.skipTest("aqui no hay documentacion que comprobar")
        filas = []
        for _, texto in docs:
            filas.extend(self.RX_FILA_TABLA.findall(texto))
        # CONTROL POSITIVO. Sin filas de tabla la exigencia de abajo se cumple vacia y el caso
        # pasaria en verde sin haber mirado una sola linea. "No he encontrado tablas" y "las tablas
        # estan completas" se parecen demasiado desde fuera.
        self.assertGreater(len(filas), 0,
                           "no se ha encontrado ni una fila de tabla en %s. La documentacion de "
                           "esta skill lista sus opciones en tabla, asi que esto es el buscador "
                           "roto, no un documento sin tablas." % ", ".join(d for d, _ in docs))
        junto = "\n".join(filas)
        # Frontera por la derecha: si no, `--json` se daria por documentado al ver `--jsonl`.
        faltan = sorted(o for o in del_cli
                        if not re.search(re.escape(o) + r"(?![\w-])", junto))
        self.assertEqual(faltan, [],
                         "el CLI acepta %s y ninguna tabla de la documentacion lo documenta. "
                         "Nombrarlo en prosa no basta: esa misma frase sirve para decir que se "
                         "quito." % ", ".join(faltan))

    def test_ninguna_cifra_de_casos_esta_caducada(self):
        docs = self._docs_a_mirar()
        if not docs:
            self.skipTest("aqui no hay documentacion que comprobar")
        validos, cuenta = self._conteos_legitimos()
        malas, halladas = [], 0
        for d, texto in docs:
            # Solo digitos pegados a la palabra: "quince casos" en prosa no es una cifra publicada.
            #
            # Y EN LOS DOS IDIOMAS. La primera version solo miraba "casos", asi que el README
            # ingles se quedo anunciando 87 cases mientras el español ya decia 99: el guardian
            # pasaba en verde con la mentira delante. Un README bilingue son DOS afirmaciones, y
            # la que nadie vigila es la que caduca. Lo encontro un escéptico ejecutando el caso
            # aislado y viendo que pasaba con la cifra falsa todavia puesta.
            for n in re.findall(self.PATRON_CIFRA, texto):
                halladas += 1
                if int(n) not in validos:
                    malas.append("%s dice '%s casos'" % (d, n))
        # CONTROL POSITIVO, y hace falta (25/07/2026). Sin el, romper la busqueda dejaba el caso
        # en verde con cero cifras miradas: lo enseño la mutacion, que fue la unica de seis que
        # nadie cazo. Un guardian que no encuentra nada tiene que sospechar de si mismo antes que
        # del vigilado, porque "no hay defectos" y "no he mirado" se parecen demasiado.
        self.assertGreater(halladas, 0,
                           "no se ha encontrado ni una cifra de casos en %s. La documentacion "
                           "siempre publica alguna, asi que esto es el buscador roto, no un "
                           "documento limpio." % ", ".join(d for d, _ in docs))
        self.assertEqual(malas, [],
                         "cifra publicada que ya no es cierta: %s. Los bancos tienen %s y suman "
                         "%d." % ("; ".join(malas), cuenta, sum(cuenta)))

    def test_la_cifra_pegada_a_un_banco_es_la_de_ESE_banco(self):
        """El caso de arriba acepta que los tres bancos se INTERCAMBIEN sus numeros.

        POR QUE (ronda 10, 25/07/2026). `_conteos_legitimos` devuelve un CONJUNTO: {39, 77, 17,
        133}. Con esa vara, un README que dijera "run_tests_adherencia.py: 17 casos" y
        "test_seguridad.py: 39 casos" pasa en verde, porque los dos numeros pertenecen al conjunto.
        Estan todos los numeros y ninguno esta en su sitio. Quien lea eso ejecutara el banco
        equivocado esperando la cifra equivocada, y cuando no cuadre dudara del banco.

        La vara correcta no es de pertenencia sino de correspondencia: si una linea nombra UN banco
        y publica UNA cifra, esa cifra es la de ese banco. Se mira linea a linea a proposito. En un
        parrafo que nombre los tres, atar cada numero a su banco exige entender la frase, y este
        instrumento no entiende frases: preferimos no juzgar a juzgar mal.
        """
        docs = self._docs_a_mirar()
        if not docs:
            self.skipTest("aqui no hay documentacion que comprobar")
        _, cuenta = self._conteos_legitimos()
        por_banco = dict(zip(self.BANCOS, cuenta))
        malas, comprobadas, lineas_con_banco = [], 0, 0
        for d, texto in docs:
            for linea in texto.splitlines():
                nombrados = [b for b in self.BANCOS if b in linea]
                if len(nombrados) != 1:
                    continue
                lineas_con_banco += 1
                for n in re.findall(self.PATRON_CIFRA, linea):
                    comprobadas += 1
                    if int(n) != por_banco[nombrados[0]]:
                        malas.append("%s atribuye '%s casos' a %s, que tiene %d"
                                     % (d, n, nombrados[0], por_banco[nombrados[0]]))
        if not lineas_con_banco:
            self.skipTest("esta documentacion no nombra los bancos por su fichero")
        # CONTROL POSITIVO, y aqui hace falta mas que en ningun sitio: si el patron de cifras se
        # rompe, `comprobadas` se queda en cero y el caso pasa en verde diciendo que todo cuadra.
        # Habiendo lineas que nombran un banco, alguna publica su cifra; si no encontramos ninguna,
        # el roto es el instrumento.
        self.assertGreater(comprobadas, 0,
                           "hay %d linea(s) que nombran un banco y no se ha leido ni una cifra en "
                           "ellas: el buscador de cifras esta roto" % lineas_con_banco)
        self.assertEqual(malas, [],
                         "cifra atribuida al banco equivocado: %s" % "; ".join(malas))

    def test_la_cifra_de_sabotajes_es_la_del_banco_de_mutacion(self):
        """La garantia mas fuerte que publica el paquete era la unica sin vigilar.

        POR QUE (ronda 10, 25/07/2026). El guardian de cifras solo miraba "N casos". La frase "11
        sabotajes" podia caducar sin que nada avisara, y es la que sostiene la promesa entera: los
        bancos valen porque hay un banco de mutacion que los pone rojos a proposito. Una cifra
        falsa ahi no envejece como un numero de casos, envejece como una garantia rota.

        Se lee de `mutar.py`, que es quien la sabe, no de una lista escrita al lado.
        """
        import importlib.util
        ruta = os.path.join(AQUI, "mutar.py")
        if not os.path.exists(ruta):
            self.skipTest("esta instalacion no lleva el banco de mutacion")
        spec = importlib.util.spec_from_file_location("_conteo_mutar", ruta)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_conteo_mutar"] = mod
        spec.loader.exec_module(mod)
        cuantas = len(mod.MUTACIONES)
        docs = self._docs_a_mirar()
        # Solo se exige la cifra donde el paquete la publica. La skill instalada suelta la cuenta
        # en palabras ("once sabotajes"), y una cifra en prosa no es una cifra publicada: es la
        # misma frontera que ya aplica el caso de los casos.
        con_readme = [(d, t) for d, t in docs if os.path.basename(d).lower() == "readme.md"]
        malas, halladas = [], 0
        for d, texto in docs:
            for n in re.findall(self.PATRON_SABOTAJES, texto):
                halladas += 1
                if int(n) != cuantas:
                    malas.append("%s dice '%s sabotajes'" % (d, n))
        if con_readme:
            self.assertGreater(halladas, 0,
                               "el paquete trae README y no publica en cifra cuantos sabotajes "
                               "tiene el banco de mutacion, que es la garantia que vende")
        self.assertEqual(malas, [],
                         "cifra de sabotajes caducada: %s. `mutar.py` tiene %d."
                         % ("; ".join(malas), cuantas))



class TestElHistorialTraeLoQueQuiere(Base):
    """El formato del transcript es interno y cambia entre versiones: eso lo dice Anthropic y lo
    repite el README de este paquete, con esta promesa encima: "si el formato cambia, lo que veras
    es un recuento que baja sin motivo, NO un error".

    Era falsa en seis de ocho formas que probo un auditor el 25/07. Todas salian con codigo 1, que
    esta documentado como "alguna regla por debajo de su umbral": en un CI, un transcript ilegible
    y una regla incumplida se leian igual.

    Un caso por cada puerta de entrada del dato ajeno. Lo que se exige no es que mida bien lo raro,
    sino que NO REVIENTE y siga midiendo lo demas, que es lo que promete el texto.
    """

    REGLAS = [{"id": "banco-tras-escribir", "disparador": "escribir-doc",
               "respuesta": "test", "ventana": 4}]

    def _con(self, registro, mas=()):
        p = self.sesion("s.jsonl", [registro] + list(mas))
        return M.medir([p], self.REGLAS)

    def test_file_path_numerico(self):
        self._con(tool("Write", {"file_path": 123}, "w0"))

    def test_file_path_en_lista(self):
        self._con(tool("Write", {"file_path": ["/x/y.md"]}, "w0"))

    def test_input_que_no_es_diccionario(self):
        p = self.sesion("s.jsonl", [{"message": {"content": [
            {"type": "tool_use", "id": "b0", "name": "Write", "input": "/x/y.md"}]}}])
        M.medir([p], self.REGLAS)

    def test_command_numerico(self):
        self._con(tool("Bash", {"command": 42}, "b0"))

    def test_id_de_bloque_en_lista(self):
        """Un identificador no hashable tumbaba la deduplicacion con `cannot use list as a set
        element`, que es un mensaje que no dice nada a quien acaba de instalar esto."""
        p = self.sesion("s.jsonl", [{"message": {"content": [
            {"type": "tool_use", "id": ["a"], "name": "Write",
             "input": {"file_path": "/x/y.md"}}]}}])
        M.medir([p], self.REGLAS)

    def test_message_como_lista(self):
        p = self.sesion("s.jsonl", [{"message": [{"type": "text", "text": "hola"}]}])
        M.medir([p], self.REGLAS)

    def test_lo_raro_no_impide_medir_lo_bueno(self):
        """El control que da sentido a los seis de arriba: aguantar no puede ser dejar de medir.
        Un fichero con basura y trabajo de verdad tiene que seguir dando la cifra del trabajo."""
        p = self.sesion("s.jsonl", [
            tool("Write", {"file_path": 123}, "malo"),
            tool("Write", {"file_path": "/w/doc.md"}, "w0"),
            tool("Bash", {"command": "python run_tests.py"}, "t0"),
        ])
        res = M.medir([p], self.REGLAS)
        self.assertGreater(res[0]["disparadores"], 0, "lo raro se llevo por delante lo medible")


class TestValoresExtremos(Base):
    """Infinito y NaN son `float`, asi que pasaban el chequeo de tipo de la ronda 9.

    Y luego `int(inf)` lanza OverflowError A MITAD de imprimir la tabla, dejando media tabla en
    pantalla, que es exactamente el defecto que ese chequeo decia haber cerrado para `umbral` como
    texto. Arreglar una familia por el sintoma deja fuera a los primos.
    """

    def _regla(self, **extra):
        r = {"id": "x", "disparador": "escribir-doc", "respuesta": "test"}
        r.update(extra)
        return [r]

    def test_ventana_infinita(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(ventana=float("inf")))

    def test_umbral_infinito(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(umbral=float("inf")))

    def test_umbral_NaN(self):
        with self.assertRaises(ValueError):
            M._valida_tipos(self._regla(umbral=float("nan")))

    def test_un_numero_normal_sigue_pasando(self):
        """Control al reves: rechazar lo extremo no puede rechazar lo corriente.

        Tambien decia `umbral=0.5`, que no es lo corriente sino el valor ambiguo: 0,5 % de gate.
        Ver la explicacion en `test_lo_bien_escrito_sigue_pasando`.
        """
        M._valida_tipos(self._regla(ventana=6, umbral=50))


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    sys.exit(0 if r.wasSuccessful() else 1)
