from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from ml_models.pipelines.quality import (
    calcular_confidence_score,
    calcular_data_quality_score,
    calcular_value_score,
)


class DataQualityScoreTests(SimpleTestCase):
    def test_maximo_con_historial_completo_y_reciente(self):
        ahora = timezone.now()
        score = calcular_data_quality_score(15, 15, ahora, ahora)
        self.assertEqual(score, 100)

    def test_bajo_con_pocos_partidos(self):
        ahora = timezone.now()
        score = calcular_data_quality_score(1, 15, ahora, ahora)
        # El componente de cantidad usa el mínimo entre ambos equipos.
        self.assertLess(score, 40)

    def test_cero_sin_ningun_partido(self):
        self.assertEqual(calcular_data_quality_score(0, 0, None, None), 0)

    def test_penaliza_antiguedad(self):
        ahora = timezone.now()
        viejo = ahora - timedelta(days=90)
        score_reciente = calcular_data_quality_score(15, 15, ahora, ahora)
        score_viejo = calcular_data_quality_score(15, 15, viejo, viejo)
        self.assertLess(score_viejo, score_reciente)


class ConfidenceScoreTests(SimpleTestCase):
    def test_mas_partidos_da_mas_confianza_a_igual_data_quality(self):
        confianza_pocos = calcular_confidence_score(80, 1, 1)
        confianza_muchos = calcular_confidence_score(80, 15, 15)
        self.assertLess(confianza_pocos, confianza_muchos)

    def test_nunca_supera_al_data_quality_score(self):
        for partidos in (1, 3, 8, 15):
            with self.subTest(partidos=partidos):
                confianza = calcular_confidence_score(80, partidos, partidos)
                self.assertLessEqual(confianza, 80)


class ValueScoreTests(SimpleTestCase):
    def test_cero_si_ev_no_es_positivo(self):
        self.assertEqual(calcular_value_score(0, 90), 0)
        self.assertEqual(calcular_value_score(-0.1, 90), 0)
        self.assertEqual(calcular_value_score(None, 90), 0)

    def test_mayor_confianza_da_mayor_score_con_el_mismo_ev(self):
        bajo = calcular_value_score(0.2, 30)
        alto = calcular_value_score(0.2, 90)
        self.assertLess(bajo, alto)

    def test_mayor_ev_da_mayor_score_con_la_misma_confianza(self):
        chico = calcular_value_score(0.05, 80)
        grande = calcular_value_score(0.3, 80)
        self.assertLess(chico, grande)
