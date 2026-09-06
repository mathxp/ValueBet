from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Equipo, Partido


class RendimientoModeloApiTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local", api_football_id=97001)
        visita = Equipo.objects.create(nombre="Visita", api_football_id=97002)
        self.partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.FINALIZADO,
            resultado={"local": 1, "visitante": 0},
        )

    def test_datos_insuficientes_por_defecto(self):
        """No inventa una comparación con pocos datos -- lo dice explícitamente."""
        resp = self.client.get("/api/analisis/rendimiento/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["datos_suficientes"])
        self.assertEqual(data["predicciones_resueltas"], 0)

    def test_con_suficientes_analisis_resueltos_compara_contra_baseline(self):
        for _ in range(20):
            AnalisisPartido.objects.create(
                partido=self.partido,
                mercado="1X2",
                seleccion_evaluada="LOCAL",
                probabilidad_seleccion=0.6,
                probabilidad_implicita=0.5,
                cuota_mercado=Decimal("2.00"),
                recomendacion=AnalisisPartido.Recomendacion.NO_BET,
                prediccion_acertada=True,
            )
        resp = self.client.get("/api/analisis/rendimiento/")
        data = resp.json()
        self.assertTrue(data["datos_suficientes"])
        self.assertEqual(data["predicciones_resueltas"], 20)
        self.assertEqual(data["modelo"]["accuracy"], 1.0)
        # El baseline predice "ocurre" porque la implícita es 0.5 (umbral),
        # y sí ocurrió -- también debería acertar siempre en este caso armado.
        self.assertEqual(data["baseline_mercado"]["accuracy"], 1.0)
