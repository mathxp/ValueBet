from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Equipo, Partido


class ReconciliarTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local", api_football_id=95001)
        visita = Equipo.objects.create(nombre="Visita", api_football_id=95002)
        # 2-1: gana el local, 3 goles totales (over 2.5, under 3.5).
        self.partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.FINALIZADO,
            resultado={"local": 2, "visitante": 1},
        )

    def test_1x2_value_bet_acertada_calcula_pnl(self):
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion_evaluada="LOCAL",
            probabilidad_seleccion=0.55,
            cuota_mercado=Decimal("2.00"),
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
            kelly_fraccion_usada=0.25,
            stake_sugerido=Decimal("100.00"),
        )
        analisis.reconciliar()
        self.assertTrue(analisis.prediccion_acertada)
        self.assertTrue(analisis.recomendacion_acertada)
        self.assertEqual(analisis.pnl_teorico, Decimal("100.00"))
        self.assertIsNotNone(analisis.resuelto_en)

    def test_1x2_value_bet_fallida_calcula_pnl_negativo(self):
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion_evaluada="VISITANTE",
            probabilidad_seleccion=0.3,
            cuota_mercado=Decimal("3.00"),
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
            kelly_fraccion_usada=0.25,
            stake_sugerido=Decimal("50.00"),
        )
        analisis.reconciliar()
        self.assertFalse(analisis.prediccion_acertada)
        self.assertFalse(analisis.recomendacion_acertada)
        self.assertEqual(analisis.pnl_teorico, Decimal("-50.00"))

    def test_no_bet_no_calcula_recomendacion_acertada_ni_pnl(self):
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion_evaluada="EMPATE",
            probabilidad_seleccion=0.25,
            cuota_mercado=Decimal("3.50"),
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
            motivo_no_bet="Edge inferior al umbral mínimo configurado.",
        )
        analisis.reconciliar()
        # El resultado real fue LOCAL, no EMPATE -> la predicción no acertó.
        self.assertFalse(analisis.prediccion_acertada)
        self.assertIsNone(analisis.recomendacion_acertada)
        self.assertIsNone(analisis.pnl_teorico)

    def test_over_under_prediccion_acertada(self):
        # 2+1=3 goles -> "más de 2.5" es correcto.
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="OVER_UNDER_2.5",
            seleccion_evaluada="OVER",
            probabilidad_seleccion=0.6,
            cuota_mercado=Decimal("1.80"),
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
        )
        analisis.reconciliar()
        self.assertTrue(analisis.prediccion_acertada)

    def test_over_under_prediccion_fallida(self):
        # 3 goles no supera la línea de 3.5 -> "más de 3.5" es incorrecto.
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="OVER_UNDER_3.5",
            seleccion_evaluada="OVER",
            probabilidad_seleccion=0.4,
            cuota_mercado=Decimal("2.20"),
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
        )
        analisis.reconciliar()
        self.assertFalse(analisis.prediccion_acertada)

    def test_under_acertado_cuando_no_se_supera_la_linea(self):
        analisis = AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="OVER_UNDER_3.5",
            seleccion_evaluada="UNDER",
            probabilidad_seleccion=0.6,
            cuota_mercado=Decimal("1.60"),
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
        )
        analisis.reconciliar()
        self.assertTrue(analisis.prediccion_acertada)
