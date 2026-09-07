from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from db_models.models import Equipo, Partido
from ml_models.predictor import (
    MatchPredictor,
    _poisson_pmf,
    distribucion_goles_totales,
    probabilidad_over,
    probabilidades_1x2_por_poisson,
)


class PoissonPmfTests(SimpleTestCase):
    def test_suma_a_uno_aproximadamente(self):
        total = sum(_poisson_pmf(k, 2.0) for k in range(60))
        self.assertAlmostEqual(total, 1.0, places=3)


class Probabilidades1x2Tests(SimpleTestCase):
    def test_suman_uno(self):
        probs = probabilidades_1x2_por_poisson(1.8, 0.9)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=3)

    def test_favorito_correcto(self):
        probs = probabilidades_1x2_por_poisson(2.5, 0.8)
        self.assertGreater(probs["LOCAL"], probs["VISITANTE"])
        self.assertGreater(probs["LOCAL"], probs["EMPATE"])

    def test_partido_parejo_da_mas_empate_que_uno_dispar(self):
        probs_parejo = probabilidades_1x2_por_poisson(1.2, 1.2)
        probs_dispar = probabilidades_1x2_por_poisson(3.0, 0.3)
        self.assertGreater(probs_parejo["EMPATE"], probs_dispar["EMPATE"])


class DistribucionGolesTotalesTests(SimpleTestCase):
    def test_distribucion_suma_uno(self):
        dist = distribucion_goles_totales(1.5, 1.2)
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=3)

    def test_probabilidad_over_decrece_con_la_linea(self):
        dist = distribucion_goles_totales(1.5, 1.2)
        p_05 = probabilidad_over(dist, 0.5)
        p_25 = probabilidad_over(dist, 2.5)
        p_45 = probabilidad_over(dist, 4.5)
        self.assertGreater(p_05, p_25)
        self.assertGreater(p_25, p_45)


class MatchPredictorTests(TestCase):
    def setUp(self):
        self.local = Equipo.objects.create(nombre="Local FC", api_football_id=91001)
        self.visita = Equipo.objects.create(nombre="Visita FC", api_football_id=91002)

    def _crear_partido(self, metricas):
        return Partido.objects.create(
            equipo_local=self.local,
            equipo_visitante=self.visita,
            fecha_hora=timezone.now() + timedelta(days=1),
            metricas_avanzadas=metricas,
        )

    def test_sin_xg_predecir_goles_retorna_none(self):
        partido = self._crear_partido({})
        self.assertIsNone(MatchPredictor().predecir_goles(partido))

    def test_sin_xg_predecir_retorna_none(self):
        """Corrección deliberada: sin datos reales, el sistema se abstiene en
        vez de usar un prior inventado -- ver docstring de predictor.py."""
        partido = self._crear_partido({})
        self.assertIsNone(MatchPredictor().predecir(partido))

    def test_con_xg_predecir_goles_retorna_la_proyeccion(self):
        partido = self._crear_partido({"xg_local": 1.8, "xg_visitante": 0.9})
        self.assertEqual(MatchPredictor().predecir_goles(partido), (1.8, 0.9))

    def test_con_xg_predecir_da_probabilidades_validas(self):
        partido = self._crear_partido({"xg_local": 1.8, "xg_visitante": 0.9})
        probs = MatchPredictor().predecir(partido)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=3)
        self.assertGreater(probs["LOCAL"], probs["VISITANTE"])

    def test_probabilidad_over_none_sin_datos(self):
        partido = self._crear_partido({})
        self.assertIsNone(MatchPredictor().predecir_probabilidad_over(partido, 2.5))

    def test_probabilidad_over_con_datos(self):
        partido = self._crear_partido({"xg_local": 2.0, "xg_visitante": 1.5})
        prob = MatchPredictor().predecir_probabilidad_over(partido, 2.5)
        self.assertGreater(prob, 0.0)
        self.assertLess(prob, 1.0)
