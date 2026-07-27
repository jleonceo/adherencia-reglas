# -*- coding: utf-8 -*-
"""Banco de `medir_adherencia.py`. Se escribe ANTES que el cuerpo, como manda la spec.

Los casos salen de los siete criterios de aceptación del peldaño 4, y las trazas son FABRICADAS a
propósito: un banco que dependa del historial real cambia de resultado cada día y deja de ser banco.

La deuda que este banco existe para no repetir: el observatorio de degradación pasaba sus ocho casos
con un fallo dentro que le inflaba el denominador un 288 %, porque ningún caso cubría «una respuesta
ocupa varias líneas». Aquí eso es el caso 7 y se verifica por mutación.
"""
from __future__ import print_function

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import medir_adherencia as m

# EL BANCO DECLARA SU PROPIO VOCABULARIO (25/07/2026). Estas seis acciones estaban dentro del
# codigo hasta que se saco de ahi todo lo que era del proyecto de origen. Los casos que las
# nombran siguen siendo validos, pero ahora tienen que declararlas, igual que cualquiera que se
# descargue la herramienta. Asi el banco ejercita el camino de configuracion de verdad.
_EXTRA = [
    ["gate-texto", "revisor_estilo|control_prosa|lint_texto|control_transmision"
                   "|gate_voz|silueta_coleccion"],
    ["buscador", "consultar"],
    ["regenerar", "regenerar_indice|generar_catalogo"],
    ["escanear-repos", "escanear_proyectos"],
    ["salud", "chequeo_salud"],
    ["verificar", "verificar_|auditar_"],
    # `eval_golden` y `verificador_minimo` son formas de ejecutar un banco propias de este
    # proyecto, y salieron del patron de fabrica junto con las demas. Los casos 15 y 33 miden el
    # RECALL de esos patrones, asi que tienen que estar declarados para que sigan midiendo algo.
    ["test", "eval_golden|verificador_minimo"],
]
m.RX_SHELL, m.ACCIONES = m.compilar_acciones_shell(_EXTRA)


def linea(nombre, entrada, bid, mid="msg_1"):
    """Una línea de transcript con una llamada a herramienta dentro."""
    return json.dumps({"type": "assistant", "message": {
        "role": "assistant", "id": mid,
        "content": [{"type": "tool_use", "id": bid, "name": nombre, "input": entrada}]}})


class Base(unittest.TestCase):
    def setUp(self):
        # Cada caso fabrica su historial y varios reescriben el MISMO fichero. La medicion trabaja
        # sobre una foto tomada una vez por ejecucion, asi que hay que decirle que vuelva a mirar:
        # es el uso para el que existe `refrescar_foto`, y estos casos son su primer usuario.
        m.refrescar_foto()
        self.tmp = tempfile.mkdtemp(prefix="adh_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sesion(self, nombre, lineas):
        p = os.path.join(self.tmp, nombre)
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas) + "\n")
        return p

    def escribir_doc(self, bid, mid="msg_1"):
        return linea("Write", {"file_path": "proy/x/doc.md"}, bid, mid)

    def gate(self, bid, mid="msg_2"):
        return linea("Bash", {"command": "python pruebas/revisor_estilo.py doc.md"}, bid, mid)

    def ruido(self, bid, mid="msg_r"):
        return linea("Read", {"file_path": "proy/x/otro.md"}, bid, mid)


REGLA = {"id": "puerta", "disparador": "escribir-doc", "respuesta": "gate-texto",
         "ventana": 6, "fuente": "skill transmision-conocimiento", "desde": "2000-01-01"}


class TestControles(Base):
    """CA6: control positivo y negativo. Sin los dos, el instrumento no discrimina."""

    def test_1_control_positivo(self):
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        r = m.medir([p], [REGLA])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 1))

    def test_2_control_negativo(self):
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.ruido("b2")])
        r = m.medir([p], [REGLA])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 0))

    def test_3_sin_disparadores_no_inventa_tasa(self):
        """Cero de cero no es 0 % ni 100 %: es «no se pudo mirar»."""
        p = self.sesion("s.jsonl", [self.ruido("b1")])
        r = m.medir([p], [REGLA])[0]
        self.assertEqual(r["disparadores"], 0)
        self.assertIsNone(r["tasa"], "sin disparadores la tasa tiene que ser None, no 0")


class TestVentana(Base):
    """CA de la ventana: la respuesta tardía no cuenta."""

    def _relleno(self, n):
        """Pasos intermedios ALTERNADOS: con el colapso, cuatro Read seguidos son un solo paso y
        el caso mediria el colapso en vez de la ventana."""
        fuera = []
        for i in range(n):
            if i % 2:
                fuera.append(linea("Grep", {"pattern": "x"}, "g%d" % i, "mg%d" % i))
            else:
                fuera.append(self.ruido("r%d" % i, "m%d" % i))
        return fuera

    def test_4_respuesta_dentro_de_la_ventana(self):
        ls = [self.escribir_doc("b0")] + self._relleno(4)
        ls.append(self.gate("bg"))
        p = self.sesion("s.jsonl", ls)
        self.assertEqual(m.medir([p], [REGLA])[0]["cumplidos"], 1)

    def test_5_respuesta_fuera_de_la_ventana(self):
        ls = [self.escribir_doc("b0")] + self._relleno(8)
        ls.append(self.gate("bg"))
        p = self.sesion("s.jsonl", ls)
        self.assertEqual(m.medir([p], [REGLA])[0]["cumplidos"], 0,
                         "con ventana 6, una respuesta en el paso 9 no cuenta")


class TestFecha(Base):
    """CA2: una regla no se juzga antes de existir. Medir meses en los que no había regla
    produce una cifra bien calculada sobre el objeto equivocado."""

    def test_6_sesion_anterior_al_alta_no_entra(self):
        p = self.sesion("s.jsonl", [self.escribir_doc("b1")])
        os.utime(p, (946684800, 946684800))          # 1 de enero de 2000
        regla = dict(REGLA, desde="2026-07-22")
        self.assertEqual(m.medir([p], [regla])[0]["disparadores"], 0)


class TestUnaLineaNoEsUnaLlamada(Base):
    """CA de fondo, y la deuda del observatorio: el JSONL agrupa los trozos de streaming por id de
    mensaje, así que la misma llamada reaparece en varias líneas. Contarlas todas infla el
    denominador. Medido en el proyecto: un 58 % en el minador y un 288 % en el observatorio."""

    def test_7_la_misma_llamada_repetida_cuenta_una_vez(self):
        """OJO AL DISEÑO DEL CASO (corregido el 25/07 por una mutacion que salio CIEGA).

        La primera version ponia tres escrituras seguidas con el mismo id, y pasaba igual sin
        deduplicar: el colapso de repeticiones inmediatas ya las juntaba, asi que el caso medía el
        colapso y no la deduplicacion. Con una lectura EN MEDIO, el colapso no las junta y solo la
        deduplicacion puede dar 1. Un test puede dejar de proteger cuando cambia el diseño, y sin
        pasar mutaciones nadie se entera.
        """
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.ruido("r0", "m9"),
                                    self.escribir_doc("b1"), self.gate("bg")])
        r = m.medir([p], [REGLA])[0]
        self.assertEqual(r["disparadores"], 1,
                         "dos lineas con el MISMO id de bloque son una sola llamada")

    def test_7b_ids_distintos_siguen_contando(self):
        """Control positivo del anterior: deduplicar no puede tragarse llamadas legitimas.

        Con el colapso por defecto, tres escrituras SEGUIDAS son una racha (una sola entrega), asi
        que se comprueban las dos lecturas: la conservadora da 1 y la literal da 3. Lo que este
        caso vigila es que las tres llamadas se HAYAN VISTO, no que se cuenten de una manera.
        """
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.escribir_doc("b2", "m2"),
                                    self.escribir_doc("b3", "m3")])
        self.assertEqual(m.medir([p], [REGLA])[0]["disparadores"], 1)
        self.assertEqual(m.medir([p], [REGLA], colapsar=False)[0]["disparadores"], 3)


class TestRobustez(Base):
    def test_8_repetible(self):
        """CA4: dos ejecuciones sobre los mismos datos dan lo mismo."""
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        self.assertEqual(m.medir([p], [REGLA]), m.medir([p], [REGLA]))

    def test_9_regla_mal_escrita_falla_ruidosamente(self):
        """CA5: una acción que no existe en el mapa es un error del usuario, y callar lo esconde."""
        with self.assertRaises(ValueError):
            m.medir([], [dict(REGLA, disparador="accion-que-no-existe")])

    def test_10_sesion_ilegible_no_cuenta_como_incumplimiento(self):
        """CA3: «no se pudo mirar» nunca es «no se cumplio»."""
        p = os.path.join(self.tmp, "rota.jsonl")
        io.open(p, "w", encoding="utf-8").write("{{{ esto no es json\n")
        r = m.medir([p], [REGLA])[0]
        self.assertEqual(r["disparadores"], 0)
        self.assertEqual(r["ilegibles"], 1)

    def test_11_es_read_only(self):
        """CA7: medir no escribe nada en el arbol de sesiones."""
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        antes = sorted(os.listdir(self.tmp))
        mtime = os.path.getmtime(p)
        m.medir([p], [REGLA])
        self.assertEqual(sorted(os.listdir(self.tmp)), antes)
        self.assertEqual(os.path.getmtime(p), mtime)


class TestConfiguracion(unittest.TestCase):
    """CA1: las reglas se declaran fuera del codigo."""

    def test_12_las_reglas_se_leen_de_fichero(self):
        tmp = tempfile.mkdtemp(prefix="adhcfg_")
        try:
            p = os.path.join(tmp, "reglas.json")
            io.open(p, "w", encoding="utf-8").write(json.dumps({"reglas": [REGLA]}))
            self.assertEqual(m.cargar_reglas(p)[0]["id"], "puerta")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_13_config_invalida_no_pasa_en_silencio(self):
        tmp = tempfile.mkdtemp(prefix="adhcfg_")
        try:
            p = os.path.join(tmp, "reglas.json")
            io.open(p, "w", encoding="utf-8").write(json.dumps({"reglas": [{"id": "x"}]}))
            with self.assertRaises(ValueError):
                m.cargar_reglas(p)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)




class TestRecallDeLaPuerta(Base):
    """El defecto que encontro la validacion contra datos reales (25/07/2026).

    La puerta de salida tiene cuatro instrumentos y se puede ejecutar por partes. El clasificador
    solo reconocia cuatro nombres y perdia tres formas legitimas. Medirlo exigio buscar por nombre
    de fichero SIN usar el regex del instrumento: comprobarlo contra si mismo da siempre 100 %.
    """

    def _con(self, cmd):
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"),
                                    linea("Bash", {"command": cmd}, "b2", "m2")])
        return m.medir([p], [REGLA])[0]["cumplidos"]

    def test_15_los_instrumentos_de_la_puerta_cuentan(self):
        for cmd in ("python pruebas/revisor_estilo.py x.md",
                    "python evals/gate_transmision_det.py x.md",
                    "python evals/gate_voz.py x.md",
                    "python evals/silueta_coleccion.py --coleccion d"):
            self.assertEqual(self._con(cmd), 1, "no reconoce %r como puerta" % cmd)

    def test_16_control_negativo_otros_gates_no_cuentan(self):
        """Un gate que NO es de calidad de texto no puede colarse como si lo fuera."""
        for cmd in ("python pruebas/gate_rutas.py",
                    "python metricas/uso_contexto.py --picos",
                    "python ci_gate.py"):
            self.assertEqual(self._con(cmd), 0, "%r no es la puerta de salida" % cmd)




class TestAmbito(Base):
    """El campo que nacio del descubrimiento del 25/07: la misma regla medida con tres alcances
    distintos daba 26,4 %, 38,0 % y 62,7 % sobre los mismos datos. Sin declarar a que ficheros
    aplica una regla, su porcentaje no significa nada."""

    def _sesion_mixta(self):
        return self.sesion("s.jsonl", [
            linea("Write", {"file_path": "proy/x/Manual_Interno/manual.md"}, "b1", "m1"),
            self.gate("g1", "m2"),
            linea("Write", {"file_path": "proy/x/scratchpad/borrador.md"}, "b2", "m3"),
            self.ruido("r1", "m4")])

    def test_17_sin_ambito_entran_los_dos(self):
        r = m.medir([self._sesion_mixta()], [REGLA])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (2, 1))

    def test_18_con_ambito_solo_entra_el_declarado(self):
        regla = dict(REGLA, ambito=["manual_interno/"])
        r = m.medir([self._sesion_mixta()], [regla])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 1),
                         "el borrador de scratchpad queda fuera del alcance")

    def test_19_ambito_que_no_casa_con_nada_da_n_d(self):
        """Control negativo: un ambito mal escrito no puede parecer un 100 %."""
        regla = dict(REGLA, ambito=["carpeta_que_no_existe/"])
        r = m.medir([self._sesion_mixta()], [regla])[0]
        self.assertEqual(r["disparadores"], 0)
        self.assertIsNone(r["tasa"])




class TestCeroSilencioso(Base):
    """El defecto que destapo probar controles sobre datos reales (25/07/2026).

    El ambito filtra por RUTA. Una accion de consola no tiene fichero, asi que declarar ambito en
    una regla disparada por un comando descarta TODOS sus disparadores y la tasa sale n/d, como si
    la regla no se hubiera activado nunca. La causa verdadera queda muda.
    """

    def test_20_el_ambito_que_descarta_todo_deja_rastro(self):
        p = self.sesion("s.jsonl", [linea("Bash", {"command": "git add x"}, "b1", "m1"),
                                    linea("Bash", {"command": "git commit -m x"}, "b2", "m2")])
        regla = {"id": "add-commit", "disparador": "git-add", "respuesta": "git-commit",
                 "ventana": 3, "desde": "2000-01-01", "ambito": ["manuales/"]}
        r = m.medir([p], [regla])[0]
        self.assertEqual(r["disparadores"], 0)
        self.assertEqual(r["filtrados_por_ambito"], 1,
                         "sin este contador el cero es mudo y nadie sabe por que")

    def test_21_sin_ambito_ese_mismo_par_se_mide(self):
        """Control positivo: el par existe, lo que fallaba era el filtro."""
        p = self.sesion("s.jsonl", [linea("Bash", {"command": "git add x"}, "b1", "m1"),
                                    linea("Bash", {"command": "git commit -m x"}, "b2", "m2")])
        regla = {"id": "add-commit", "disparador": "git-add", "respuesta": "git-commit",
                 "ventana": 3, "desde": "2000-01-01"}
        r = m.medir([p], [regla])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 1))




class TestDescubrimientoDeSesiones(Base):
    """Un instrumento que no arranca de fabrica no lo usa nadie (25/07/2026).

    Los transcripts viven en `projects/<proyecto>/<sesion>.jsonl`. Apuntar a la raiz que contiene
    los proyectos tiene que funcionar igual que apuntar a uno concreto, y sin tragarse las sesiones
    de subagentes, que cuelgan un nivel mas abajo y son otro universo.
    """

    def _arbol(self):
        raiz = os.path.join(self.tmp, "projects")
        proy = os.path.join(raiz, "mi-proyecto")
        subag = os.path.join(proy, "subagents")
        os.makedirs(subag)
        for ruta in (os.path.join(proy, "a.jsonl"), os.path.join(proy, "b.jsonl"),
                     os.path.join(subag, "c.jsonl")):
            io.open(ruta, "w", encoding="utf-8").write("{}\n")
        return raiz, proy

    def test_22_apuntando_al_proyecto(self):
        _, proy = self._arbol()
        self.assertEqual(len(m.sesiones_en(proy)), 2)

    def test_23_apuntando_a_la_raiz_de_proyectos(self):
        raiz, _ = self._arbol()
        self.assertEqual(len(m.sesiones_en(raiz)), 2,
                         "la raiz tiene que bajar un nivel, o el instrumento no arranca de fabrica")

    def test_24_los_subagentes_no_entran_salvo_que_se_pidan(self):
        raiz, _ = self._arbol()
        self.assertEqual(len(m.sesiones_en(raiz, subagentes=True)), 3)




class TestDireccion(Base):
    """Muchas reglas son "haz X ANTES de Y" (25/07/2026).

    Con solo la mirada hacia adelante, esas reglas salen hundidas y su numero no significa nada.
    Se vio midiendo "escanear los repos antes de publicar", que daba 7,7 % por estar planteado al
    reves.
    """

    def _sesion(self):
        return self.sesion("s.jsonl", [
            linea("Bash", {"command": "python escanear_proyectos.py"}, "b1", "m1"),
            linea("Bash", {"command": "git push origin main"}, "b2", "m2")])

    def test_25_hacia_atras_lo_cuenta(self):
        regla = {"id": "escaneo-antes", "disparador": "git-push", "respuesta": "escanear-repos",
                 "ventana": 4, "direccion": "antes", "desde": "2000-01-01"}
        r = m.medir([self._sesion()], [regla])[0]
        self.assertEqual((r["disparadores"], r["cumplidos"]), (1, 1))

    def test_26_la_misma_regla_hacia_adelante_no_lo_ve(self):
        """Control: es la MISMA traza. Lo que cambia es hacia donde se mira."""
        regla = {"id": "escaneo-antes", "disparador": "git-push", "respuesta": "escanear-repos",
                 "ventana": 4, "desde": "2000-01-01"}
        self.assertEqual(m.medir([self._sesion()], [regla])[0]["cumplidos"], 0)

    def test_27_direccion_invalida_falla_ruidosamente(self):
        import json as _j, tempfile as _t
        d = _t.mkdtemp(prefix="adhdir_")
        ruta = os.path.join(d, "r.json")
        io.open(ruta, "w", encoding="utf-8").write(_j.dumps({"reglas": [
            {"id": "x", "disparador": "git-push", "respuesta": "escanear-repos",
             "direccion": "hacia-el-lado"}]}))
        with self.assertRaises(ValueError):
            m.cargar_reglas(ruta)
        shutil.rmtree(d, ignore_errors=True)




class TestLimitesDeParametros(Base):
    """Los tres que pasaban CALLANDO, encontrados probando limites el 25/07."""

    def test_28_ambito_como_texto_falla(self):
        """El peor: una cadena se recorre por caracteres y filtra segun si la ruta lleva una 'm'."""
        with self.assertRaises(ValueError):
            m.medir([], [dict(REGLA, ambito="manuales/")])

    def test_29_ventana_menor_que_uno_falla(self):
        for v in (0, -5):
            with self.assertRaises(ValueError):
                m.medir([], [dict(REGLA, ventana=v)])

    def test_30_ventana_no_numerica_falla(self):
        with self.assertRaises(ValueError):
            m.medir([], [dict(REGLA, ventana="seis")])

    def test_31_ids_duplicados_fallan(self):
        with self.assertRaises(ValueError):
            m.medir([], [dict(REGLA), dict(REGLA)])

    def test_32_control_positivo_lo_valido_sigue_pasando(self):
        """Sin esto, las cuatro validaciones de arriba podrian estar rechazandolo todo."""
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        r = m.medir([p], [dict(REGLA, ambito=["/x/"], ventana="6")])[0]
        self.assertEqual(r["disparadores"], 1, "ventana numerica en texto y ambito lista son validos")




class TestRecallDeLosBancos(Base):
    """Segundo recall del dia, con el mismo metodo: buscar por nombre SIN usar el patron."""

    def _con(self, cmd):
        p = self.sesion("s.jsonl", [linea("Write", {"file_path": "x.py"}, "b1", "m1"),
                                    linea("Bash", {"command": cmd}, "b2", "m2")])
        regla = {"id": "banco", "disparador": "escribir-codigo", "respuesta": "test",
                 "ventana": 6, "desde": "2000-01-01"}
        return m.medir([p], [regla])[0]["cumplidos"]

    def test_33_las_formas_de_ejecutar_un_banco_cuentan(self):
        for cmd in ("python run_tests_x.py", "python test_x.py", "python -m pytest",
                    "python -m unittest", "python eval_referencia.py", "python comprobador_basico.py"):
            self.assertEqual(self._con(cmd), 1, "no reconoce %r como banco" % cmd)

    def test_34_los_chequeos_de_gobernanza_NO_son_el_banco(self):
        """Control negativo deliberado: verificar_* es gobernanza y tiene accion propia. Contarlo
        como banco haria pasar por 'ejecute la suite del codigo que toque' algo que no lo es."""
        for cmd in ("python verificar_pendientes.py", "python verificar_caducados.py"):
            self.assertEqual(self._con(cmd), 0, "%r no es el banco del codigo tocado" % cmd)




class TestEstres(Base):
    """Los limites de tamaño, medidos el 25/07: 60.000 lineas en 0,2 s y una linea de 1 MB en
    0,16 s. Se dejan como caso para que un cambio futuro no los rompa en silencio."""

    def test_35_fichero_con_muchas_lineas(self):
        ls = [linea("Write", {"file_path": "x%d.md" % i}, "b%d" % i, "m%d" % i)
              for i in range(3000)]
        p = self.sesion("s.jsonl", ls)
        seq = m.secuencia_de(p)
        self.assertEqual(len(seq), 1, "3000 escrituras seguidas son UNA racha con el colapso")
        self.assertEqual(len(m.secuencia_de(p, colapsar=False)), 3000)

    def test_36_linea_muy_larga_no_rompe(self):
        p = self.sesion("s.jsonl", [linea("Bash", {"command": "echo " + "x" * 200000}, "b1")])
        # La racha guarda una LISTA de rutas desde el 25/07: una accion de consola no tiene
        # fichero, asi que su lista va vacia.
        self.assertEqual(m.secuencia_de(p), [("shell", [])])

    def test_37_rutas_con_espacios_y_acentos(self):
        p = self.sesion("s.jsonl", [linea("Write", {"file_path": "Mis Documentos/año/ñ.md"},
                                          "b1")])
        seq = m.secuencia_de(p)
        self.assertEqual(seq[0][0], "escribir-doc")
        self.assertTrue(any("año" in r for r in seq[0][1]),
                        "la ruta se conserva para poder filtrar por ambito")




class TestMuestraPequena(Base):
    """Un porcentaje sobre dos casos se lee igual que uno sobre mil (25/07/2026).

    Salio midiendo la jornada en que se construyo la skill: dos "100 %" y dos "0 %" que venian de
    una o dos ocasiones. La cifra se marca, no se esconde.
    """

    def test_38_hay_umbral_de_muestra_declarado(self):
        self.assertGreaterEqual(m.MUESTRA_MINIMA, 2,
                                "sin umbral, una anecdota con decimales pasa por tasa")

    def test_39_la_tasa_se_calcula_igual_sea_grande_o_pequena(self):
        """El umbral es para AVISAR, no para ocultar: la cifra sigue siendo la que es."""
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        r = m.medir([p], [REGLA])[0]
        self.assertEqual(r["tasa"], 100.0)
        self.assertEqual(r["disparadores"], 1)


class TestLasTresQueEncontroUnForASTERO(Base):
    """Tres lineas de clasificacion que 136 casos no vigilaban, y las tres cambian la cifra.

    DE DONDE SALEN (26/07/2026). El 25/07 este proyecto aprendio que un mutador escrito por el
    autor hereda el punto ciego del autor: catorce sabotajes propios, catorce cazados, y un tercero
    escribio doce distintos de los que sobrevivieron nueve. La leccion se aplico al medidor de
    compacts, que paso de 14 sabotajes a 23. No se aplico AQUI: esta skill siguio publicando "once
    sabotajes, once cazados, cero huecos", que es la misma cifra que ya se sabia que no medía la
    calidad del banco sino el acuerdo entre dos cosas de la misma cabeza.

    Un auditor externo escribio dieciocho contra estos tres bancos. Cazamos trece. De las cinco
    supervivientes, dos eran equivalentes (no cambian el resultado sobre datos reales) y TRES eran
    huecos de verdad. Son estos. El banco no crece porque se nos ocurriera mirar mas: crece porque
    lo miro alguien que no lo escribio.
    """

    def test_40_las_cuatro_herramientas_de_escritura_cuentan_como_escritura(self):
        """La linea mas consecuente del instrumento, y no la vigilaba ningun caso.

        `accion_de` clasifica Write, Edit, MultiEdit y NotebookEdit como escritura. Si alguien deja
        solo `Write`, no salta nada: los tres bancos siguen verdes y la herramienta sigue dando
        porcentajes. Lo que cambia es el DENOMINADOR, que es de donde sale todo lo demas. Medido en
        vivo por el auditor sobre el historial real: dejando fuera `Edit`, `puerta-de-salida` sube
        del 79,0 % al 86,7 % y sus ocasiones caen de 100 a 30, y `banco-tras-tocar-codigo` pasa de
        1.297 disparadores a 502. Una tasa que sube porque el instrumento ha dejado de mirar es
        exactamente el fallo que esta skill existe para no cometer.
        """
        for herramienta in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.assertEqual(m.accion_de(herramienta, {"file_path": "x/doc.md"}),
                             "escribir-doc",
                             "%s deja de contar como escritura: el denominador se encoge y la "
                             "tasa sube sola" % herramienta)
            self.assertEqual(m.accion_de(herramienta, {"file_path": "x/motor.py"}),
                             "escribir-codigo",
                             "%s deja de contar como escritura de codigo" % herramienta)

    def test_41_Task_y_Agent_siguen_siendo_la_accion_subagente(self):
        """Sin este verbo, cualquier regla sobre subagentes mide cero y se lee como incumplida.

        Un cero de este instrumento no se distingue a simple vista de un cero real, y esa confusion
        es la que la propia skill declara "el peor fallo posible aqui".
        """
        for herramienta in ("Task", "Agent"):
            self.assertEqual(m.accion_de(herramienta, {}), "subagente",
                             "%s deja de ser una accion: toda regla sobre subagentes mediria cero "
                             "sin que nada avise" % herramienta)

    def test_42_la_fecha_se_busca_mas_alla_del_primer_registro(self):
        """El respaldo por mtime es "el fallo mas caro de los que quedaban" y no tenia caso propio.

        `fecha_de_sesion` recorre hasta 400 registros buscando el `timestamp` de dentro del
        fichero. Si alguien reduce ese limite, se cae al mtime en silencio: `fecha_es_del_fichero`
        pasa a True, `desde` empieza a dejar fuera sesiones que si contaban y `--por-dia` amontona
        meses en un dia. El docstring de la funcion lo explica entero; lo que faltaba era el caso.
        """
        m.refrescar_foto()
        m._CACHE_FECHA.clear()
        # El timestamp llega en el registro 50, que es normal: las primeras lineas de un transcript
        # son metadatos y resumenes sin sello de tiempo.
        lineas = [json.dumps({"type": "summary", "summary": "relleno %d" % i}) for i in range(50)]
        lineas.append(json.dumps({"type": "assistant", "timestamp": "2026-07-20T10:00:00.000Z",
                                  "message": {"role": "assistant", "id": "m1", "content": []}}))
        p = self.sesion("tardia.jsonl", lineas)
        ts, del_fichero = m.fecha_de_sesion(p)
        self.assertFalse(del_fichero,
                         "la fecha ha salido del mtime teniendo un timestamp en el registro 50: "
                         "el respaldo se ha comido el camino bueno y no lo dice")
        self.assertIsNotNone(ts)
        # `fecha_de_sesion` devuelve epoch, no un datetime: se compara en el mismo huso en que se
        # escribio el sello para que el caso no dependa de donde se ejecute.
        import datetime
        leida = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(leida, "2026-07-20",
                         "el timestamp del registro 50 no se ha leido: la fecha viene de otro sitio")


class TestLosNueveMenoresDeLaRonda10(Base):
    """Seis defectos que no daban error: devolvian algo creible y equivocado.

    Ninguno de los seis tumbaba nada. Todos imprimian una tabla, salian con codigo 0 y se leian
    como una medicion normal, que es el unico fallo que esta herramienta no se puede permitir.
    """

    def _reglas(self, obj):
        p = os.path.join(self.tmp, "reglas.json")
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
        return p

    def test_43_por_dia_cero_no_cae_a_la_tabla_normal(self):
        """`0` era el valor por defecto, asi que pedirlo era indistinguible de no pedirlo.

        Sale solo de una variable vacia en un script: `--por-dia $DIAS` con `DIAS` sin definir.
        Devolvia la tabla agregada con exit 0 y quien lo leyera creeria estar viendo el desglose.
        """
        p = self.sesion("s.jsonl", [self.escribir_doc("b1"), self.gate("b2")])
        self.assertEqual(m.main(["--sesiones", self.tmp, "--reglas", self._reglas({"reglas": [REGLA]}),
                                 "--por-dia", "0"]), 2,
                         "`--por-dia 0` sigue cayendo a la tabla normal en silencio")
        self.assertEqual(m.main(["--sesiones", self.tmp, "--reglas", self._reglas({"reglas": [REGLA]}),
                                 "--por-dia", "-3"]), 2)
        # Control positivo: sin el flag la tabla normal tiene que seguir saliendo con 0.
        self.assertEqual(m.main(["--sesiones", self.tmp,
                                 "--reglas", self._reglas({"reglas": [REGLA]})]), 0,
                         "la tabla normal ha dejado de funcionar")
        self.assertTrue(os.path.exists(p))

    def test_44_acciones_da_el_mismo_veredicto_que_las_demas_vistas(self):
        """La vista que el README titula "por aqui se empieza" era la unica sin gate.

        Devolvia 0 pasara lo que pasara. Un cero que significa "he impreso una tabla" y un cero que
        significa "ninguna regla esta por debajo de su umbral" no se distinguen desde un CI.
        """
        self.sesion("s.jsonl", [self.escribir_doc("b1"), self.ruido("b2")])   # dispara y NO cumple
        bajo = dict(REGLA, umbral=90)
        self.assertEqual(m.main(["--sesiones", self.tmp,
                                 "--reglas", self._reglas({"reglas": [bajo]}), "--acciones"]), 1,
                         "`--acciones` devuelve 0 con una regla por debajo de su umbral")
        alto = dict(REGLA, umbral=None)
        self.assertEqual(m.main(["--sesiones", self.tmp,
                                 "--reglas", self._reglas({"reglas": [alto]}), "--acciones"]), 0,
                         "`--acciones` devuelve error sin ninguna regla incumplida")

    def test_45_un_id_con_salto_de_linea_no_falsifica_una_fila(self):
        """La tabla se alinea por columnas, asi que un `\\n` parte la fila y la mitad de abajo se
        lee como otra regla que no midio nada. No da error y no hay uso legitimo."""
        for malo in ("puerta\notra", "puerta\tcol", "puerta\rx"):
            with self.assertRaises(ValueError):
                m.cargar_reglas(self._reglas({"reglas": [dict(REGLA, id=malo)]}))
        # Control positivo: un id normal sigue cargando.
        m.cargar_reglas(self._reglas({"reglas": [REGLA]}))

    def test_46_una_clave_repetida_no_gana_la_ultima_callando(self):
        """JSON permite claves repetidas y el lector se queda con la ultima.

        Dos bloques `"reglas"` (lo que sale de pegar una configuracion debajo de otra) median solo
        el segundo, y la mitad de las reglas desaparecia. Menos filas es justo lo que se espera de
        un fichero con menos reglas, asi que no hay forma de verlo mirando la tabla.
        """
        crudo = ('{"reglas": [%s], "reglas": [%s]}'
                 % (json.dumps(REGLA), json.dumps(dict(REGLA, id="otra"))))
        with self.assertRaises(ValueError) as c:
            m.cargar_reglas(self._reglas(crudo))
        self.assertIn("reglas", str(c.exception))

    def test_47_una_ventana_con_decimales_no_se_trunca_callando(self):
        """`6.9` se medía como 6 y movia la tasa sin decirlo. No hay media llamada a herramienta."""
        with self.assertRaises(ValueError):
            m.cargar_reglas(self._reglas({"reglas": [dict(REGLA, ventana=6.9)]}))
        # `6.0` SI es legitimo: es un entero escrito con punto, no una ventana partida.
        m.cargar_reglas(self._reglas({"reglas": [dict(REGLA, ventana=6.0)]}))

    def test_48_un_umbral_fuera_de_0_100_no_pasa(self):
        """`0.9` pensando en "el 90 %" daba un gate que no salta nunca, y la tabla lo redondeaba a
        "0 %", que parece un umbral puesto a proposito."""
        for malo in (0.9, -1, 101, 900):
            with self.assertRaises(ValueError):
                m.cargar_reglas(self._reglas({"reglas": [dict(REGLA, umbral=malo)]}))
        for bueno in (0, 50, 100):
            m.cargar_reglas(self._reglas({"reglas": [dict(REGLA, umbral=bueno)]}))

    def test_49_un_json_muy_anidado_da_no_se_pudo_medir_y_no_traceback(self):
        """`RecursionError` no es `ValueError`, asi que se escapaba y llegaba con codigo 1.

        El 1 esta documentado como "alguna regla por debajo de su umbral": en un CI, un fichero
        ilegible y un incumplimiento real se leian igual.
        """
        hondo = "[" * 20000 + "]" * 20000
        with self.assertRaises(ValueError):
            m.cargar_reglas(self._reglas(hondo))


class TestSeparadoresDeLaOrden(unittest.TestCase):
    """Una orden de shell separa sus argumentos con espacios O con tabuladores.

    Estos dos casos fijan el COMPORTAMIENTO, y conviene saber lo que NO hacen. Se escribieron para
    vigilar un `cmd.replace("\\t", " ")` que habia justo antes del `split()`, y al intentar
    ponerlos rojos saboteando esa linea siguieron en verde: `split()` sin argumentos ya parte por
    cualquier espacio en blanco, asi que aquel `replace` no hacia nada y se quito. Un caso que no
    sabe ponerse rojo no vigila su objeto, y aqui el objeto no existia.

    Lo que si sostienen es que una orden tabulada se lea igual que una espaciada, que es lo que la
    herramienta promete al clasificar rutas dentro de un comando.
    """

    def test_el_tabulador_separa_igual_que_el_espacio(self):
        con_tab = m.rutas_en_orden("pytest\ttests/unit/test_a.py")
        con_espacio = m.rutas_en_orden("pytest tests/unit/test_a.py")
        self.assertEqual(con_tab, ["tests/unit/test_a.py"])
        self.assertEqual(con_tab, con_espacio,
                         "una orden separada por tabulador da otro resultado que con espacio")

    def test_varios_tabuladores_seguidos(self):
        """Tabuladores consecutivos no fabrican tokens vacios ni pegan dos rutas en una."""
        self.assertEqual(m.rutas_en_orden("pytest\t\tsrc/a.py\tsrc/b.py"),
                         ["src/a.py", "src/b.py"])

    def test_los_otros_espacios_en_blanco_tambien_separan(self):
        """Retorno de carro y salto de linea aparecen en ordenes de varias lineas, que es como se
        escriben en un CI. Si alguien sustituye el `split()` por un `split(" ")`, esto lo caza."""
        self.assertEqual(m.rutas_en_orden("pytest \\\n  src/a.py\r\n  src/b.py"),
                         ["src/a.py", "src/b.py"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
