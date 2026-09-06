from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Equipo, Operacion, Partido
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
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                precio_back=Decimal("3.00"),
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
        precios = [
            MarketPrice(
                market_id=str(self.partido.id),
                mercado="1X2",
                seleccion="LOCAL",
                precio_back=Decimal("3.00"),
                precio_lay=None,
                volumen_disponible=None,
            ),
        ]
        scanner = OddsScanner(exchange_client=FakeExchangeClient(precios))
        scanner.escanear_partido(self.partido)
        scanner.escanear_partido(self.partido)

        self.assertEqual(Operacion.objects.count(), 1)

    def test_dos_lineas_de_over_under_solo_genera_una_recomendacion(self):
        """Las líneas de Over/Under están correlacionadas -- el escáner debe
        quedarse solo con la de mejor EV, no recomendar las dos."""
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
