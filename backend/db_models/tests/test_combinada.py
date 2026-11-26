from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Combinada, Equipo, Partido


class CombinadaTests(TestCase):
    def setUp(self):
        self.combinada = Combinada.objects.create(
            cuota_combinada=Decimal("3.610"),
            probabilidad_combinada=0.36,
            valor_esperado=0.30,
            kelly_fraccion_usada=0.1,
            stake=Decimal("100.00"),
        )

        # Dos patas de partidos distintos, para probar que el M2M funciona.
        for i in range(2):
            local = Equipo.objects.create(nombre=f"Local {i}", api_football_id=95100 + i)
            visita = Equipo.objects.create(nombre=f"Visita {i}", api_football_id=95200 + i)
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

    def test_nace_recomendada_con_dos_patas(self):
        self.assertEqual(self.combinada.estado, Combinada.Estado.RECOMENDADA)
        self.assertIsNone(self.combinada.pnl)
        self.assertEqual(self.combinada.patas.count(), 2)

    def test_aceptar(self):
        self.combinada.aceptar()
        self.assertEqual(self.combinada.estado, Combinada.Estado.ACEPTADA)

    def test_descartar(self):
        self.combinada.descartar()
        self.assertEqual(self.combinada.estado, Combinada.Estado.DESCARTADA)

    def test_marcar_ganada_calcula_pnl_sobre_la_cuota_combinada(self):
        self.combinada.aceptar()
        self.combinada.marcar_ganada()
        self.assertEqual(self.combinada.estado, Combinada.Estado.GANADA)
        # stake=100, cuota=3.610 -> pnl = 100 * (3.610 - 1) = 261.00
        self.assertEqual(self.combinada.pnl, Decimal("261.00"))

    def test_marcar_perdida_calcula_pnl_negativo(self):
        self.combinada.aceptar()
        self.combinada.marcar_perdida()
        self.assertEqual(self.combinada.pnl, Decimal("-100.00"))

    def test_marcar_anulada_no_afecta_pnl(self):
        self.combinada.aceptar()
        self.combinada.marcar_anulada()
        self.assertEqual(self.combinada.estado, Combinada.Estado.ANULADA)
        self.assertEqual(self.combinada.pnl, Decimal("0"))

    def test_revertir_a_aceptada_deshace_un_ganada_por_error(self):
        self.combinada.aceptar()
        self.combinada.marcar_ganada()
        self.combinada.revertir_a_aceptada()
        self.assertEqual(self.combinada.estado, Combinada.Estado.ACEPTADA)
        self.assertIsNone(self.combinada.pnl)
