from decimal import Decimal

from django.test import SimpleTestCase

from trading_engine.risk_manager import (
    calcular_kelly_completo,
    calcular_valor_esperado,
    evaluar_apuesta,
)


class CalcularValorEsperadoTests(SimpleTestCase):
    def test_edge_positivo(self):
        self.assertAlmostEqual(calcular_valor_esperado(0.6, 2.0), 0.2)

    def test_sin_edge(self):
        self.assertAlmostEqual(calcular_valor_esperado(0.5, 2.0), 0.0)

    def test_edge_negativo(self):
        self.assertLess(calcular_valor_esperado(0.4, 2.0), 0)


class CalcularKellyCompletoTests(SimpleTestCase):
    def test_kelly_positivo_con_edge(self):
        # p=0.6, cuota=2.0 -> b=1, f* = (b*p - q)/b = (0.6-0.4)/1 = 0.2
        self.assertAlmostEqual(calcular_kelly_completo(0.6, 2.0), 0.2)

    def test_kelly_cero_sin_edge(self):
        self.assertEqual(calcular_kelly_completo(0.4, 2.0), 0.0)

    def test_kelly_nunca_negativo(self):
        # p=0.1, cuota=2.0 -> f* matemático sería negativo; nunca se apuesta "en contra"
        self.assertEqual(calcular_kelly_completo(0.1, 2.0), 0.0)

    def test_cuota_invalida_da_cero(self):
        self.assertEqual(calcular_kelly_completo(0.6, 1.0), 0.0)
        self.assertEqual(calcular_kelly_completo(0.6, 0.5), 0.0)


class EvaluarApuestaTests(SimpleTestCase):
    def test_value_bet_detectada(self):
        evaluacion = evaluar_apuesta(
            probabilidad_modelo=0.6,
            cuota_decimal=2.2,
            bankroll=Decimal("1000"),
            kelly_fraccion=0.25,
            min_edge=0.03,
            stake_maximo=Decimal("500"),
        )
        self.assertTrue(evaluacion.es_apuesta_de_valor)
        self.assertGreater(evaluacion.stake_sugerido, Decimal("0"))

    def test_sin_edge_no_es_value_bet(self):
        evaluacion = evaluar_apuesta(
            probabilidad_modelo=0.45,
            cuota_decimal=2.2,
            bankroll=Decimal("1000"),
            min_edge=0.03,
        )
        self.assertFalse(evaluacion.es_apuesta_de_valor)
        self.assertEqual(evaluacion.stake_sugerido, Decimal("0.00"))

    def test_respeta_el_tope_de_stake_maximo(self):
        evaluacion = evaluar_apuesta(
            probabilidad_modelo=0.9,
            cuota_decimal=5.0,
            bankroll=Decimal("100000"),
            stake_maximo=Decimal("50"),
        )
        self.assertLessEqual(evaluacion.stake_sugerido, Decimal("50"))

    def test_fraccion_de_kelly_reduce_el_stake(self):
        base = dict(probabilidad_modelo=0.7, cuota_decimal=2.5, bankroll=Decimal("1000"), stake_maximo=Decimal("10000"))
        completo = evaluar_apuesta(**base, kelly_fraccion=1.0)
        cuarto = evaluar_apuesta(**base, kelly_fraccion=0.25)
        self.assertGreater(completo.stake_sugerido, cuarto.stake_sugerido)
