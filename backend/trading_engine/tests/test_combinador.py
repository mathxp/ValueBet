from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, CalibracionMercado, Combinada, ConfiguracionRiesgo, Equipo, Partido
from trading_engine.combinador import MAX_PATAS, generar_combinada


class CombinadorTests(TestCase):
    def setUp(self):
        # Bankroll grande y fracción de Kelly normal -- que el stake no sea
        # lo que determine si la combinada pasa o no en estos tests.
        ConfiguracionRiesgo.objects.update_or_create(
            pk=1,
            defaults={
                "paper_bankroll": Decimal("100000"),
                "kelly_fraction": 0.25,
                "max_stake_per_bet": Decimal("50000"),
                "min_edge_threshold": 0.03,
            },
        )
        CalibracionMercado.objects.create(mercado="1X2", puntos=[], n_total=100)
        self.equipos = [
            Equipo.objects.create(nombre=f"Equipo {i}", api_football_id=99000 + i) for i in range(12)
        ]

    def _crear_partido_con_analisis(
        self, index, mercado="1X2", seleccion="LOCAL", probabilidad=0.6, cuota=Decimal("1.90")
    ):
        local, visita = self.equipos[index * 2], self.equipos[index * 2 + 1]
        partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now() + timedelta(days=1),
            estado=Partido.Estado.PROGRAMADO,
        )
        AnalisisPartido.objects.create(
            partido=partido,
            mercado=mercado,
            seleccion_evaluada=seleccion,
            probabilidad_seleccion=probabilidad,
            cuota_mercado=cuota,
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
        )
        return partido

    def test_sin_candidatos_no_genera_nada(self):
        self.assertIsNone(generar_combinada())

    def test_una_sola_candidata_no_alcanza(self):
        self._crear_partido_con_analisis(0)
        self.assertIsNone(generar_combinada())

    def test_arma_combinada_con_dos_patas_de_partidos_distintos(self):
        self._crear_partido_con_analisis(0)
        self._crear_partido_con_analisis(1)

        combinada = generar_combinada()
        self.assertIsNotNone(combinada)
        self.assertEqual(combinada.patas.count(), 2)
        self.assertEqual(len({p.partido_id for p in combinada.patas.all()}), 2)
        # cuota 1.90 * 1.90 = 3.61
        self.assertEqual(combinada.cuota_combinada, Decimal("3.610"))
        self.assertAlmostEqual(combinada.probabilidad_combinada, 0.36, places=6)

    def test_nunca_mas_de_max_patas(self):
        # Edge chico por pata (~5%) a propósito: con 5 candidatas, 3 patas ya
        # componen bastante -- si el edge por pata fuera el default (~14%)
        # el combinado superaría EDGE_MAXIMO_CONFIABLE y la combinada se
        # bloquearía como anomalía, que es otro comportamiento (ya cubierto
        # por test_edge_combinado_extremo_bloquea_la_combinada), no el que
        # este test quiere ejercitar.
        for i in range(5):
            self._crear_partido_con_analisis(i, probabilidad=0.6, cuota=Decimal("1.75"))

        combinada = generar_combinada()
        self.assertIsNotNone(combinada)
        self.assertLessEqual(combinada.patas.count(), MAX_PATAS)

    def test_nunca_dos_patas_del_mismo_partido(self):
        """Si el mismo partido tiene dos candidatas (ej. 1X2 y Doble
        Oportunidad), se usa solo la de mayor probabilidad."""
        partido = self._crear_partido_con_analisis(0, mercado="1X2", probabilidad=0.6, cuota=Decimal("1.80"))
        AnalisisPartido.objects.create(
            partido=partido,
            mercado="DOBLE_OPORTUNIDAD",
            seleccion_evaluada="1X",
            probabilidad_seleccion=0.75,  # más alta -- esta debería ganar
            cuota_mercado=Decimal("1.40"),
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
        )
        self._crear_partido_con_analisis(1)

        combinada = generar_combinada()
        self.assertEqual(combinada.patas.count(), 2)
        pata_del_primer_partido = combinada.patas.get(partido=partido)
        self.assertEqual(pata_del_primer_partido.mercado, "DOBLE_OPORTUNIDAD")

    def test_ignora_mercado_sin_calibracion(self):
        """Defensa en profundidad: aunque llegara una VALUE_BET de un mercado
        sin curva de calibración (no debería pasar del escáner, pero por las
        dudas), el combinador no debe usarla como pata."""
        self._crear_partido_con_analisis(0, mercado="OVER_UNDER_2.5", probabilidad=0.7, cuota=Decimal("1.80"))
        self._crear_partido_con_analisis(1)
        self._crear_partido_con_analisis(2)

        combinada = generar_combinada()
        self.assertIsNotNone(combinada)
        mercados_usados = {p.mercado for p in combinada.patas.all()}
        self.assertNotIn("OVER_UNDER_2.5", mercados_usados)

    def test_probabilidad_por_debajo_del_minimo_queda_afuera(self):
        self._crear_partido_con_analisis(0, probabilidad=0.5)  # debajo de PROBABILIDAD_MINIMA_PATA (0.55)
        self._crear_partido_con_analisis(1, probabilidad=0.5)
        self.assertIsNone(generar_combinada())

    def test_edge_combinado_extremo_bloquea_la_combinada(self):
        """3 patas con ~15% de edge cada una componen a más de 50% combinado --
        eso supera EDGE_MAXIMO_CONFIABLE y evaluar_apuesta debe bloquearla como
        anomalía, no recomendarla solo porque cada pata se veía razonable."""
        for i in range(3):
            self._crear_partido_con_analisis(i, probabilidad=0.65, cuota=Decimal("1.77"))
        self.assertIsNone(generar_combinada())

    def test_no_duplica_una_combinada_ya_recomendada(self):
        self._crear_partido_con_analisis(0)
        self._crear_partido_con_analisis(1)

        primera = generar_combinada()
        segunda = generar_combinada()

        self.assertEqual(primera.id, segunda.id)
        self.assertEqual(Combinada.objects.count(), 1)
