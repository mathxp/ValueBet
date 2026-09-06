from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import Equipo, Operacion, Partido


class OperacionTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local", api_football_id=94001)
        visita = Equipo.objects.create(nombre="Visita", api_football_id=94002)
        partido = Partido.objects.create(
            equipo_local=local, equipo_visitante=visita, fecha_hora=timezone.now()
        )
        self.operacion = Operacion.objects.create(
            partido=partido,
            mercado="1X2",
            seleccion="LOCAL",
            probabilidad_modelo=0.6,
            cuota_apostada=Decimal("2.00"),
            valor_esperado=0.2,
            kelly_fraccion_usada=0.25,
            stake=Decimal("100.00"),
        )

    def test_nace_recomendada(self):
        self.assertEqual(self.operacion.estado, Operacion.Estado.RECOMENDADA)
        self.assertIsNone(self.operacion.pnl)

    def test_aceptar(self):
        self.operacion.aceptar()
        self.assertEqual(self.operacion.estado, Operacion.Estado.ACEPTADA)

    def test_descartar(self):
        self.operacion.descartar()
        self.assertEqual(self.operacion.estado, Operacion.Estado.DESCARTADA)

    def test_marcar_ganada_calcula_pnl_correcto(self):
        self.operacion.aceptar()
        self.operacion.marcar_ganada()
        self.assertEqual(self.operacion.estado, Operacion.Estado.GANADA)
        # stake=100, cuota=2.00 -> pnl = 100 * (2.00 - 1) = 100
        self.assertEqual(self.operacion.pnl, Decimal("100.00"))

    def test_marcar_perdida_calcula_pnl_correcto(self):
        self.operacion.aceptar()
        self.operacion.marcar_perdida()
        self.assertEqual(self.operacion.estado, Operacion.Estado.PERDIDA)
        self.assertEqual(self.operacion.pnl, Decimal("-100.00"))
