from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Combinada, Equipo, Partido


class CombinadaActionsApiTests(TestCase):
    def setUp(self):
        self.combinada = Combinada.objects.create(
            cuota_combinada=Decimal("3.610"),
            probabilidad_combinada=0.36,
            valor_esperado=0.30,
            kelly_fraccion_usada=0.1,
            stake=Decimal("100.00"),
        )
        local = Equipo.objects.create(nombre="Local API", api_football_id=96100)
        visita = Equipo.objects.create(nombre="Visita API", api_football_id=96200)
        partido = Partido.objects.create(
            equipo_local=local, equipo_visitante=visita, fecha_hora=timezone.now()
        )
        analisis = AnalisisPartido.objects.create(
            partido=partido,
            mercado="1X2",
            seleccion_evaluada="LOCAL",
            probabilidad_seleccion=0.6,
            cuota_mercado=Decimal("1.90"),
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
        )
        self.combinada.patas.add(analisis)

    def test_get_incluye_las_patas(self):
        resp = self.client.get(f"/api/combinadas/{self.combinada.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["patas"]), 1)

    def test_aceptar_y_marcar_ganada(self):
        self.client.post(f"/api/combinadas/{self.combinada.id}/aceptar/")
        resp = self.client.post(f"/api/combinadas/{self.combinada.id}/marcar-ganada/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()["pnl"]), Decimal("261.00"))

    def test_marcar_ganada_sin_aceptar_da_conflicto(self):
        resp = self.client.post(f"/api/combinadas/{self.combinada.id}/marcar-ganada/")
        self.assertEqual(resp.status_code, 409)
