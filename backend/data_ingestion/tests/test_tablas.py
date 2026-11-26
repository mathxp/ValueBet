from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from data_ingestion.tablas import _parsear_grupo, _parsear_llaves


def _tabla(filas):
    html = "<table>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in fila) + "</tr>" for fila in filas
    ) + "</table>"
    return BeautifulSoup(html, "html.parser").find("table")


class ParsearLlavesTests(SimpleTestCase):
    def test_final_entre_semifinales_y_penales(self):
        # Orden real de Wikipedia (Copa de la Liga 2026): la final aparece
        # entre las dos semifinales.
        tabla = _tabla(
            [
                ["Semifinales", "Final"],
                ["Coquimbo Unido", "1", "0", "1 (5)"],
                ["Unión La Calera", "0", "1", "1 (4)"],
                ["Coquimbo Unido", "3"],
                ["O'Higgins", "0"],
                ["O'Higgins", "1", "1", "2 (4)"],
                ["Ñublense", "2", "0", "2 (2)"],
            ]
        )
        llaves = _parsear_llaves(tabla)
        rondas = [(ll["ronda"], ll["local"], ll["visitante"], ll["ganador"]) for ll in llaves]
        self.assertEqual(rondas[0], ("Final", "Coquimbo Unido", "O'Higgins", "Coquimbo Unido"))
        self.assertIn(("Semifinales", "Coquimbo Unido", "Unión La Calera", "Coquimbo Unido"), rondas)
        self.assertIn(("Semifinales", "O'Higgins", "Ñublense", "O'Higgins"), rondas)
        semi = next(ll for ll in llaves if ll["visitante"] == "Unión La Calera")
        self.assertEqual(semi["detalle"], "1-0, 0-1 (pen. 5-4)")

    def test_cruce_pendiente_con_sembrado(self):
        tabla = _tabla(
            [
                ["8. vos de Final", "Semifinales"],
                ["12", "Coquimbo Unido", "2", "2", "4"],
                ["7", "Cobreloa", "1", "1", "2"],
                ["12", "Coquimbo Unido"],
                ["2", "Universidad de Chile"],
                ["2", "Universidad de Chile", "1", "1", "2"],
                ["8", "Everton", "0", "1", "1"],
            ]
        )
        llaves = _parsear_llaves(tabla)
        semi = llaves[0]
        self.assertEqual(semi["ronda"], "Semifinales")
        self.assertIsNone(semi["ganador"])
        self.assertIsNone(semi["global_local"])
        self.assertEqual(llaves[1]["ronda"], "Octavos de final")


class ParsearGrupoTests(SimpleTestCase):
    def test_columna_clasificacion_con_rowspan(self):
        cabecera = ["Pos.", "Equipo", "Pts.", "PJ", "G", "E", "P", "GF", "GC", "Dif.", "Clasificación"]
        tabla = _tabla(
            [
                cabecera,
                ["1", "Coquimbo Unido", "14", "6", "4", "2", "0", "9", "5", "+4", "Semifinales"],
                ["4", "Deportes Concepción", "1", "6", "0", "1", "5", "6", "13", "−7"],
            ]
        )
        filas = _parsear_grupo(tabla, cabecera)
        self.assertEqual(filas[0]["nota"], "Semifinales")
        self.assertEqual(filas[1]["dif"], -7)
        self.assertEqual(filas[1]["nota"], "")


class CampeonMatematicoTests(SimpleTestCase):
    def _grupo(self, pts_lider, pts_segundo, pj):
        filas = [{"equipo": "Colo Colo", "pts": pts_lider, "pj": pj}, {"equipo": "U. de Chile", "pts": pts_segundo, "pj": pj}]
        filas += [{"equipo": f"E{i}", "pts": 0, "pj": pj} for i in range(14)]
        return [{"nombre": "", "filas": filas}]

    def test_campeon_a_falta_de_dos_fechas(self):
        from data_ingestion.tablas import campeon_matematico

        self.assertEqual(campeon_matematico(self._grupo(64, 54, 28)), "Colo Colo")

    def test_todavia_alcanzable(self):
        from data_ingestion.tablas import campeon_matematico

        self.assertIsNone(campeon_matematico(self._grupo(64, 58, 28)))
