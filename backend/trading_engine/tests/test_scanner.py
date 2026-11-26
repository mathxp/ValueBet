from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, CalibracionMercado, ConfiguracionRiesgo, Equipo, Operacion, Partido
from trading_engine.exchange_client import MarketPrice
from trading_engine.scanner import OddsScanner


class FakeExchangeClient:
    """Exchange de prueba: devuelve una lista fija de precios, sin tocar la BD."""

    def __init__(self, precios):
        self._precios = precios

    def get_market_odds(self, market_id):
        return self._precios

    def get_account_balance(self):
        return Decimal("1000.00")


def _crear_finalizado(local, visitante, dias_atras, gl, gv):
    from datetime import timedelta

    return Partido.objects.create(
        equipo_local=local,
        equipo_visitante=visitante,
        fecha_hora=timezone.now() - timedelta(days=dias_atras),
        estado=Partido.Estado.FINALIZADO,
        resultado={"local": gl, "visitante": gv},
    )


class OddsScannerTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        self.local = Equipo.objects.create(nombre="Local Scanner", api_football_id=98001)
        self.visita = Equipo.objects.create(nombre="Visita Scanner", api_football_id=98002)

        # Historial real: el local golea siempre 3-0 -- suficiente para que
        # haya rating confiable y quede muy favorito en la proyección.
        for i in range(10):
            _crear_finalizado(self.local, self.visita, dias_atras=i + 1, gl=3, gv=0)

        self.partido = Partido.objects.create(
            equipo_local=self.local,
            equipo_visitante=self.visita,
            fecha_hora=timezone.now() + timedelta(days=1),
            estado=Partido.Estado.PROGRAMADO,
        )

        # El escáner lee xG desde metricas_avanzadas -- no lo calcula solo.
        # En producción lo deja ahí ml_models.tasks.project_xg_for_upcoming_matches
        # (ver core/celery.py); acá se corre explícito para simular el pipeline real.
        from ml_models.tasks import project_xg_for_upcoming_matches

        project_xg_for_upcoming_matches()
        self.partido.refresh_from_db()

    def test_sin_cuotas_registra_no_bet_general_y_no_genera_operaciones(self):
        scanner = OddsScanner(exchange_client=FakeExchangeClient([]))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido)
        self.assertEqual(analisis.mercado, "GENERAL")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.NO_BET)

    def test_cuota_generosa_genera_value_bet_y_operacion(self):
        # El escáner exige una curva de calibración medida antes de recomendar
        # un 1X2 (mismo gate que ya tenía Over/Under, ver sin_calibracion en
        # scanner.py) -- curva "identidad" (no corrige nada) para aislar el
        # comportamiento que prueba este test.
        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                # 1.20 da ~15.6% de edge sobre la probabilidad real del modelo para
                # este fixture -- generoso pero no tan extremo como para disparar
                # la alerta de edge extremo (ver EDGE_MAXIMO_CONFIABLE).
                precio_back=Decimal("1.20"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(len(operaciones), 1)
        self.assertEqual(Operacion.objects.count(), 1)
        self.assertEqual(Operacion.objects.first().estado, Operacion.Estado.RECOMENDADA)

        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="1X2")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.VALUE_BET)
        self.assertEqual(analisis.motivo_no_bet, "")

    def test_cuota_ajustada_no_genera_value_bet(self):
        """Una cuota que ya refleja bien la probabilidad real no debería
        generar una recomendación, aunque haya datos de sobra."""
        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="VISITANTE",
                precio_back=Decimal("1.05"),  # el modelo le da muy poca chance al visitante
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="1X2")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.NO_BET)
        self.assertTrue(analisis.motivo_no_bet)

    def test_no_duplica_operacion_en_un_segundo_escaneo(self):
        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                precio_back=Decimal("1.20"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        scanner.escanear_partido(self.partido)
        scanner.escanear_partido(self.partido)

        self.assertEqual(Operacion.objects.count(), 1)

    def test_vuelve_a_recomendar_si_la_operacion_anterior_ya_fue_descartada(self):
        """Una Operacion DESCARTADA (a mano, o por el auto-retracto de arriba)
        no debe bloquear una recomendación nueva para siempre -- si la señal
        vuelve a calificar en un escaneo posterior (ej. la cuota se recuperó),
        tiene que poder crear una Operacion nueva."""
        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)
        vieja = Operacion.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion="LOCAL",
            probabilidad_modelo=0.6,
            cuota_apostada=Decimal("1.20"),
            valor_esperado=0.15,
            kelly_fraccion_usada=0.05,
            stake=Decimal("10.00"),
            estado=Operacion.Estado.DESCARTADA,
        )
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                precio_back=Decimal("1.20"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(len(operaciones), 1)
        self.assertNotEqual(operaciones[0].id, vieja.id)
        self.assertEqual(Operacion.objects.filter(mercado="1X2", seleccion="LOCAL").count(), 2)

    def test_dos_lineas_de_over_under_solo_genera_una_recomendacion(self):
        """Las líneas de Over/Under están correlacionadas -- el escáner debe
        quedarse solo con una, no recomendar las dos."""
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="OVER_UNDER_1.5",
                seleccion="OVER",
                precio_back=Decimal("3.00"),
                precio_lay=None,
                volumen_disponible=None,
            ),
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="OVER_UNDER_2.5",
                seleccion="OVER",
                precio_back=Decimal("3.50"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        scanner.escanear_partido(self.partido)

        self.assertLessEqual(Operacion.objects.filter(mercado__startswith="OVER_UNDER").count(), 1)

    def test_entre_lineas_correlacionadas_elige_la_mas_cercana_a_la_proyeccion(self):
        """
        Reproduce un patrón visto en producción: si el modelo proyecta más
        goles que el mercado, el EV crece a medida que la línea se aleja del
        promedio (paga más cuota) -- quedarse con "la de mayor EV" terminaba
        eligiendo siempre la línea más extrema disponible (la menos
        confiable, más sensible a la cola de la distribución), aunque
        líneas más centrales también tuvieran edge real. Ahora debe elegir
        la línea numéricamente más cercana a su propia proyección de goles.
        """
        from ml_models.predictor import MatchPredictor

        total_proyectado = sum(MatchPredictor().predecir_goles(self.partido))
        lineas = ["1.5", "2.5", "3.5"]  # 4.5 ya no es una línea válida -- ver LINEAS_OVER_UNDER_VALIDAS
        # Cuotas crecientes con la línea -- reproduce el patrón real donde el
        # EV aparente crece monótonamente hacia la línea más extrema, pero
        # todas dentro de un rango creíble (no disparan la alerta de edge
        # extremo por sí solas).
        # Derivadas de la probabilidad del propio modelo (EV +6%, +10%, +14%)
        # para que la prueba no dependa de los números exactos de la proyección.
        predictor = MatchPredictor()
        cuotas_por_linea = {
            linea: str(round((1 + extra) / predictor.predecir_probabilidad_over(self.partido, float(linea)), 2))
            for linea, extra in (("1.5", 0.06), ("2.5", 0.10), ("3.5", 0.14))
        }
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado=f"OVER_UNDER_{linea}",
                seleccion="OVER",
                precio_back=Decimal(cuotas_por_linea[linea]),
                precio_lay=None,
                volumen_disponible=None,
            )
            for linea in lineas
        ]

        # El escáner exige una curva de calibración medida antes de recomendar
        # un Over/Under (ver sin_calibracion en scanner.py) -- acá se simula
        # una curva "identidad" (no corrige nada) solo para poder probar la
        # elección de línea de forma aislada, sin mezclar con el efecto de
        # una calibración real.
        for linea in lineas:
            CalibracionMercado.objects.create(
                mercado=f"OVER_UNDER_{linea}", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=1071
            )

        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(len(operaciones), 1)
        linea_esperada = min(lineas, key=lambda l: abs(float(l) - total_proyectado))
        self.assertEqual(operaciones[0].mercado, f"OVER_UNDER_{linea_esperada}")

    def test_retracta_operacion_recomendada_que_ya_no_califica(self):
        """Si una Operacion quedó RECOMENDADA en un escaneo anterior pero la
        cuota actual ya no da valor (se movió, o ahora no pasa un umbral
        nuevo), el escáner debe descartarla -- no dejarla mostrada como
        vigente cuando el análisis más reciente ya no la respalda."""
        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)
        operacion = Operacion.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion="VISITANTE",
            probabilidad_modelo=0.4,
            cuota_apostada=Decimal("3.000"),
            valor_esperado=0.2,
            kelly_fraccion_usada=0.05,
            stake=Decimal("10.00"),
            estado=Operacion.Estado.RECOMENDADA,
        )
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="VISITANTE",
                precio_back=Decimal("1.05"),  # ya no da valor -- ver test_cuota_ajustada_no_genera_value_bet
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        scanner.escanear_partido(self.partido)

        operacion.refresh_from_db()
        self.assertEqual(operacion.estado, Operacion.Estado.DESCARTADA)

    def test_1x2_sin_calibracion_no_genera_value_bet(self):
        """
        1X2 tiene el mismo gate que Over/Under: sin curva de calibración
        medida contra resultados reales (ver manage.py backtest_modelo
        --guardar-calibracion), un edge aparente positivo no alcanza para
        recomendar -- antes de esto, 1X2 quedaba afuera de este chequeo (ver
        predictor.py:predecir_probabilidad_1x2).
        """
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                precio_back=Decimal("1.20"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="1X2")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.ANOMALIA)
        self.assertIn("calibración", analisis.motivo_no_bet)

    def test_over_under_sin_calibracion_no_genera_value_bet(self):
        """
        Reproduce el caso real (Limache vs Cobresal): un Over/Under con edge
        aparente positivo no debe recomendarse si todavía no hay una curva de
        calibración medida contra resultados reales para ese mercado (ver
        manage.py backtest_modelo --guardar-calibracion) -- la probabilidad
        cruda del Poisson, sin calibrar, no alcanza por sí sola.
        """
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="OVER_UNDER_3.5",
                seleccion="OVER",
                precio_back=Decimal("2.25"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="OVER_UNDER_3.5")
        # ANOMALIA, no NO_BET -- había edge aparente, se bloqueó por falta de
        # validación del mercado, no por falta de valor (ver scanner.py).
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.ANOMALIA)
        self.assertIn("calibración", analisis.motivo_no_bet)

    def test_edge_extremo_da_anomalia_no_no_bet(self):
        """Reproduce el otro camino a ANOMALIA: edge aparente positivo pero
        estadísticamente inverosímil (ver EDGE_MAXIMO_CONFIABLE)."""
        CalibracionMercado.objects.create(
            mercado="OVER_UNDER_1.5", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=1071
        )
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="OVER_UNDER_1.5",
                seleccion="OVER",
                precio_back=Decimal("10.00"),  # edge absurdo para cualquier probabilidad razonable
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="OVER_UNDER_1.5")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.ANOMALIA)
        self.assertIn("anóma", analisis.motivo_no_bet.lower())

    def test_ignora_linea_4_5_aunque_venga_en_las_cuotas(self):
        """4.5 ya no es una línea confiable (ver LINEAS_OVER_UNDER_VALIDAS) --
        el escáner debe ignorarla incluso si el exchange la sigue ofreciendo
        (ej. cuotas capturadas antes de excluirla)."""
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="OVER_UNDER_4.5",
                seleccion="OVER",
                precio_back=Decimal("6.00"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        self.assertFalse(Operacion.objects.filter(mercado="OVER_UNDER_4.5").exists())


class ProbabilidadMinimaTests(TestCase):
    """Un edge positivo no alcanza si la selección es demasiado incierta --
    ver PROBABILIDAD_MINIMA_SELECCION en scanner.py: la idea explícita del
    usuario es "tratar de acertar", no solo maximizar EV puro apostando a
    selecciones que van a perder la mayoría de las veces."""

    def setUp(self):
        from datetime import timedelta

        self.local = Equipo.objects.create(nombre="Parejo Local", api_football_id=98011)
        self.visita = Equipo.objects.create(nombre="Parejo Visita", api_football_id=98012)

        # Historial parejo (empates 1-1) -- el visitante queda con ~28% de
        # probabilidad de ganar: un underdog real, no un caso extremo.
        for i in range(10):
            _crear_finalizado(self.local, self.visita, dias_atras=i + 1, gl=1, gv=1)

        self.partido = Partido.objects.create(
            equipo_local=self.local,
            equipo_visitante=self.visita,
            fecha_hora=timezone.now() + timedelta(days=1),
            estado=Partido.Estado.PROGRAMADO,
        )

        from ml_models.tasks import project_xg_for_upcoming_matches

        project_xg_for_upcoming_matches()
        self.partido.refresh_from_db()

        CalibracionMercado.objects.create(mercado="1X2", puntos=[[0.0, 0.0], [1.0, 1.0]], n_total=3204)

    def _precio_visitante(self, cuota):
        return [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="VISITANTE",
                # ~28% de probabilidad real -- a esta cuota da ~11% de edge,
                # positivo y nada extremo (lejos de EDGE_MAXIMO_CONFIABLE).
                precio_back=Decimal(cuota),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]

    def test_edge_positivo_pero_probabilidad_baja_no_genera_value_bet(self):
        scanner = OddsScanner(exchange_client=FakeExchangeClient(self._precio_visitante("3.90")))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(operaciones, [])
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="1X2")
        # NO_BET, no ANOMALIA -- el edge en sí es confiable, solo que es una
        # selección de baja probabilidad para recomendarla sola.
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.NO_BET)
        self.assertIn("probabilidad de acierto", analisis.motivo_no_bet.lower())
        self.assertGreater(analisis.edge, 0)

    def test_bajando_el_piso_configurado_la_misma_apuesta_si_se_recomienda(self):
        """El piso es un parámetro de ConfiguracionRiesgo, editable desde el
        dashboard -- confirma que de verdad lo lee de ahí, no que esté
        hardcodeado."""
        config = ConfiguracionRiesgo.actual()
        config.probabilidad_minima_seleccion = 0.20
        config.save()

        scanner = OddsScanner(exchange_client=FakeExchangeClient(self._precio_visitante("3.90")))
        operaciones = scanner.escanear_partido(self.partido)

        self.assertEqual(len(operaciones), 1)
        analisis = AnalisisPartido.objects.get(partido=self.partido, mercado="1X2")
        self.assertEqual(analisis.recomendacion, AnalisisPartido.Recomendacion.VALUE_BET)
