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
    def _score(self, ev, **overrides):
        base = dict(
            ev=ev,
            data_quality_score=80,
            confidence_score=80,
            calibrado=True,
            partidos_local=15,
            partidos_visitante=15,
            es_anomalia=False,
        )
        base.update(overrides)
        return calcular_value_score(**base)

    def test_cero_si_ev_no_es_positivo(self):
        self.assertEqual(self._score(0), 0)
        self.assertEqual(self._score(-0.1), 0)
        self.assertEqual(self._score(None), 0)

    def test_cero_si_es_anomalia_aunque_el_ev_sea_positivo(self):
        self.assertEqual(self._score(0.3, es_anomalia=True), 0)

    def test_mayor_confianza_da_mayor_score_con_el_mismo_ev(self):
        bajo = self._score(0.2, confidence_score=30)
        alto = self._score(0.2, confidence_score=90)
        self.assertLess(bajo, alto)

    def test_mayor_ev_da_mayor_score_con_la_misma_confianza(self):
        chico = self._score(0.05)
        grande = self._score(0.3)
        self.assertLess(chico, grande)

    def test_sin_calibracion_da_menor_score(self):
        con_curva = self._score(0.2, calibrado=True)
        sin_curva = self._score(0.2, calibrado=False)
        self.assertLess(sin_curva, con_curva)

    def test_menos_partidos_da_menor_estabilidad(self):
        pocos = self._score(0.2, partidos_local=3, partidos_visitante=3)
        muchos = self._score(0.2, partidos_local=15, partidos_visitante=15)
        self.assertLess(pocos, muchos)

    def test_ev_al_limite_confiable_satura_los_30_puntos_de_ev(self):
        from trading_engine.risk_manager import EDGE_MAXIMO_CONFIABLE

        en_el_limite = self._score(EDGE_MAXIMO_CONFIABLE)
        mas_alla_no_deberia_llegar_aca = self._score(EDGE_MAXIMO_CONFIABLE * 2)
        # calcular_value_score no topa el EV en sí (eso lo hace edge_extremo
        # en risk_manager antes de llegar acá) -- pero el componente EV del
        # score sí satura en 30, así que ambos casos deberían dar el mismo
        # puntaje si todo lo demás es igual.
        self.assertEqual(en_el_limite, mas_alla_no_deberia_llegar_aca)
