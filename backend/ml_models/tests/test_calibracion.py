from django.test import SimpleTestCase

from ml_models.pipelines.calibracion import (
    MIN_MUESTRA_CALIBRACION,
    aplicar_calibracion,
    calcular_brier_score,
    calcular_buckets,
    calcular_log_loss,
    calcular_reporte,
    construir_curva_calibracion,
)


class CalcularBrierScoreTests(SimpleTestCase):
    def test_prediccion_perfecta_da_cero(self):
        pares = [(1.0, 1), (0.0, 0), (1.0, 1)]
        self.assertAlmostEqual(calcular_brier_score(pares), 0.0)

    def test_prediccion_50_50_da_un_cuarto(self):
        pares = [(0.5, 1), (0.5, 0)]
        self.assertAlmostEqual(calcular_brier_score(pares), 0.25)

    def test_prediccion_totalmente_opuesta_da_uno(self):
        pares = [(1.0, 0), (0.0, 1)]
        self.assertAlmostEqual(calcular_brier_score(pares), 1.0)


class CalcularLogLossTests(SimpleTestCase):
    def test_prediccion_50_50_da_log_2(self):
        pares = [(0.5, 1), (0.5, 0)]
        self.assertAlmostEqual(calcular_log_loss(pares), 0.6931, places=3)

    def test_prediccion_mala_penaliza_mas_que_buena(self):
        buena = calcular_log_loss([(0.9, 1), (0.9, 1)])
        mala = calcular_log_loss([(0.1, 1), (0.1, 1)])
        self.assertLess(buena, mala)


class CalcularBucketsTests(SimpleTestCase):
    def test_agrupa_por_rango_de_probabilidad(self):
        pares = [(0.15, 0), (0.15, 1), (0.85, 1), (0.85, 1)]
        buckets = calcular_buckets(pares, n_buckets=5)
        # bucket 0-20%: dos casos, ocurrió la mitad
        bucket_bajo = next(b for b in buckets if b.rango == "0-20%")
        self.assertEqual(bucket_bajo.n, 2)
        self.assertAlmostEqual(bucket_bajo.frecuencia_real, 0.5)
        # bucket 80-100%: dos casos, ocurrieron los dos
        bucket_alto = next(b for b in buckets if b.rango == "80-100%")
        self.assertEqual(bucket_alto.n, 2)
        self.assertAlmostEqual(bucket_alto.frecuencia_real, 1.0)

    def test_bucket_vacio_no_inventa_numeros(self):
        buckets = calcular_buckets([(0.15, 1)], n_buckets=5)
        bucket_alto = next(b for b in buckets if b.rango == "80-100%")
        self.assertEqual(bucket_alto.n, 0)
        self.assertIsNone(bucket_alto.prob_promedio)
        self.assertIsNone(bucket_alto.frecuencia_real)


class CalcularReporteTests(SimpleTestCase):
    def test_muestra_insuficiente_no_calcula_nada(self):
        pares = [(0.6, 1)] * (MIN_MUESTRA_CALIBRACION - 1)
        reporte = calcular_reporte("1X2", pares)
        self.assertFalse(reporte.datos_suficientes)
        self.assertIsNone(reporte.brier_score)
        self.assertIsNone(reporte.log_loss)
        self.assertEqual(reporte.buckets, [])

    def test_muestra_suficiente_calcula_metricas(self):
        pares = [(0.6, 1)] * MIN_MUESTRA_CALIBRACION
        reporte = calcular_reporte("1X2", pares)
        self.assertTrue(reporte.datos_suficientes)
        self.assertIsNotNone(reporte.brier_score)
        self.assertIsNotNone(reporte.log_loss)
        self.assertTrue(reporte.buckets)


class ConstruirCurvaCalibracionTests(SimpleTestCase):
    def test_sin_buckets_confiables_retorna_none(self):
        # Un solo caso en un bucket -- no alcanza el mínimo de muestra por punto.
        pares = [(0.15, 1)]
        self.assertIsNone(construir_curva_calibracion(pares, min_n=10))

    def test_con_dos_buckets_confiables_arma_la_curva(self):
        pares = [(0.15, 1 if i % 2 == 0 else 0) for i in range(20)] + [(0.85, 1) for _ in range(20)]
        curva = construir_curva_calibracion(pares, min_n=10)
        self.assertIsNotNone(curva)
        self.assertEqual(len(curva), 2)

    def test_un_solo_bucket_confiable_tambien_arma_curva(self):
        """Caso real: Over/Under 0.5 -- casi todos los partidos proyectan
        probabilidad alta, así que todos los casos reales caen en el mismo
        bucket. No es falta de muestra (acá hay 50), es que la variable casi
        no tiene rango donde repartirse -- un solo punto bien medido sigue
        siendo evidencia real, no una corrección inventada."""
        pares = [(0.93, 1) for _ in range(47)] + [(0.93, 0) for _ in range(3)]
        curva = construir_curva_calibracion(pares, min_n=10)
        self.assertIsNotNone(curva)
        self.assertEqual(len(curva), 1)


class AplicarCalibracionTests(SimpleTestCase):
    def test_sin_curva_retorna_la_probabilidad_cruda(self):
        self.assertEqual(aplicar_calibracion(None, 0.5), 0.5)

    def test_interpola_entre_dos_puntos_medidos(self):
        # Historial real: cuando el modelo predijo 40%, en realidad pasó 30%;
        # cuando predijo 60%, en realidad pasó 50% -- el modelo sobreestima
        # de forma pareja en ese tramo (10 puntos de más). Una predicción
        # nueva de 50% (justo al medio) debería corregirse a 40%.
        curva = [(0.4, 0.3), (0.6, 0.5)]
        self.assertAlmostEqual(aplicar_calibracion(curva, 0.5), 0.4)

    def test_extrapola_fuera_del_rango_medido_sin_inventar_una_pendiente_nueva(self):
        curva = [(0.4, 0.3), (0.6, 0.5)]
        # Por encima del rango medido, sigue la misma pendiente del último tramo.
        self.assertAlmostEqual(aplicar_calibracion(curva, 0.8), 0.7)

    def test_nunca_sale_del_rango_0_1(self):
        curva = [(0.4, 0.1), (0.6, 0.2)]
        self.assertLessEqual(aplicar_calibracion(curva, 5.0), 1.0)
        self.assertGreaterEqual(aplicar_calibracion(curva, -5.0), 0.0)
