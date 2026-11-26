import io
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from PIL import Image

from db_models.models import Equipo, Partido, PronosticoRegistrado, TablaCompeticion


def _fila(pos, equipo, pts, forma):
    return {"pos": pos, "equipo": equipo, "pts": pts, "pj": 28, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0,
            "dif": 0, "nota": "", "forma": forma}


class ContenidoTests(TestCase):
    def setUp(self):
        self.a = Equipo.objects.create(nombre="Colo Colo", api_football_id=99001)
        self.b = Equipo.objects.create(nombre="D. La Serena", api_football_id=99002)
        for i in range(8):
            Partido.objects.create(
                equipo_local=self.a, equipo_visitante=self.b, liga="Primera División", temporada="2026",
                fecha_hora=timezone.now() - timedelta(days=7 * (i + 1)), estado=Partido.Estado.FINALIZADO,
                resultado={"local": 2, "visitante": 1},
            )
        self.proximo = Partido.objects.create(
            equipo_local=self.a, equipo_visitante=self.b, liga="Primera División", temporada="2026",
            fecha_hora=timezone.now() + timedelta(days=2), estado=Partido.Estado.PROGRAMADO,
        )
        from ml_models.tasks import project_xg_for_upcoming_matches

        project_xg_for_upcoming_matches(hours_ahead=24 * 21)
        TablaCompeticion.objects.create(
            slug="liga", nombre="Liga de Primera", temporada="2026", fuente="https://x", datos={
                "grupos": [{"nombre": "", "filas": [
                    _fila(1, "Colo Colo", 64, ["G", "G", "G", "G", "E"]),
                    _fila(2, "La Serena", 40, ["P", "P", "E", "P", "P"]),
                ]}],
                "llaves": [], "campeon": "Colo Colo",
            },
        )
        p = Partido.objects.filter(estado=Partido.Estado.FINALIZADO).first()
        PronosticoRegistrado.objects.create(
            partido=p, competicion="Liga de Primera", etiqueta_fecha="Fecha 28", prob_local=0.6, prob_empate=0.2,
            prob_visitante=0.2, pick_1x2="LOCAL", pick_seguro="1X", prob_seguro=0.8, acierto_1x2=True,
            acierto_seguro=True, acierto_goles=True,
        )

    def test_genera_todas_las_categorias_bajo_el_limite_de_x(self):
        from contenido.generador import generar_contenido, largo_x

        piezas = generar_contenido()
        categorias = {p["categoria"] for p in piezas}
        self.assertTrue({"previa", "recap", "simulacion", "tablas"} <= categorias)
        for p in piezas:
            self.assertLessEqual(largo_x(p["texto"]), 280, p["id"])
        previa = next(p for p in piezas if p["categoria"] == "previa")
        self.assertIn("Colo Colo o empate", previa["texto"])

    def test_cada_imagen_es_un_png_1200x675(self):
        from contenido.generador import generar_contenido
        from contenido.imagenes import render

        for p in generar_contenido():
            if p["imagen"]:
                img = Image.open(io.BytesIO(render(p["datos"])))
                self.assertEqual(img.size, (1200, 675), p["id"])

    def test_api_lista_e_imagen(self):
        lista = self.client.get("/api/contenido/?refrescar=1").json()
        self.assertTrue(lista)
        self.assertNotIn("datos", lista[0])
        resp = self.client.get("/api/contenido/imagen/", {"id": lista[0]["id"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/api/contenido/imagen/", {"id": "no-existe"}).status_code, 404)
