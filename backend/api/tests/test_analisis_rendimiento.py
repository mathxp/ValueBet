from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import AnalisisPartido, Equipo, Partido


class RendimientoModeloApiTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local", api_football_id=97001)
        visita = Equipo.objects.create(nombre="Visita", api_football_id=97002)
        self.partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.FINALIZADO,
            resultado={"local": 1, "visitante": 0},
        )

    def test_datos_insuficientes_por_defecto(self):
        """No inventa una comparación con pocos datos -- lo dice explícitamente."""
        resp = self.client.get("/api/analisis/rendimiento/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["datos_suficientes"])
        self.assertEqual(data["predicciones_resueltas"], 0)

    def test_con_suficientes_analisis_resueltos_compara_contra_baseline(self):
        for _ in range(20):
            AnalisisPartido.objects.create(
                partido=self.partido,
                mercado="1X2",
                seleccion_evaluada="LOCAL",
                probabilidad_seleccion=0.6,
                probabilidad_implicita=0.5,
                cuota_mercado=Decimal("2.00"),
                recomendacion=AnalisisPartido.Recomendacion.NO_BET,
                prediccion_acertada=True,
            )
        resp = self.client.get("/api/analisis/rendimiento/")
        data = resp.json()
        self.assertTrue(data["datos_suficientes"])
        self.assertEqual(data["predicciones_resueltas"], 20)
        self.assertEqual(data["modelo"]["accuracy"], 1.0)
        # El baseline predice "ocurre" porque la implícita es 0.5 (umbral),
        # y sí ocurrió -- también debería acertar siempre en este caso armado.
        self.assertEqual(data["baseline_mercado"]["accuracy"], 1.0)
        # roi_value_bets ya no vive acá -- ver RendimientoValueBetsApiTests
        # (rendimiento() es "todas las predicciones", no mezcla con value bets).
        self.assertNotIn("roi_value_bets", data)


class RendimientoValueBetsApiTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local VB", api_football_id=97003)
        visita = Equipo.objects.create(nombre="Visita VB", api_football_id=97004)
        self.partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.FINALIZADO,
            resultado={"local": 1, "visitante": 0},
        )

    def _crear_value_bet(self, acertada, ev=0.2, edge=0.1):
        return AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion_evaluada="LOCAL",
            probabilidad_seleccion=0.6,
            probabilidad_implicita=0.5,
            cuota_mercado=Decimal("2.00"),
            recomendacion=AnalisisPartido.Recomendacion.VALUE_BET,
            ev=ev,
            edge=edge,
            prediccion_acertada=acertada,
            recomendacion_acertada=acertada,
            stake_sugerido=Decimal("100.00"),
            pnl_teorico=Decimal("100.00") if acertada else Decimal("-100.00"),
        )

    def test_datos_insuficientes_por_defecto(self):
        resp = self.client.get("/api/analisis/rendimiento-value-bets/")
        data = resp.json()
        self.assertFalse(data["datos_suficientes"])
        self.assertEqual(data["resueltas"], 0)

    def test_no_mezcla_con_no_bet(self):
        """Un NO_BET resuelto no debería contar como value bet resuelta."""
        AnalisisPartido.objects.create(
            partido=self.partido,
            mercado="1X2",
            seleccion_evaluada="LOCAL",
            probabilidad_seleccion=0.6,
            probabilidad_implicita=0.5,
            cuota_mercado=Decimal("2.00"),
            recomendacion=AnalisisPartido.Recomendacion.NO_BET,
            prediccion_acertada=True,
        )
        resp = self.client.get("/api/analisis/rendimiento-value-bets/")
        self.assertEqual(resp.json()["resueltas"], 0)

    def test_con_suficiente_muestra_calcula_win_rate_y_roi(self):
        for _ in range(15):
            self._crear_value_bet(acertada=True)
        for _ in range(5):
            self._crear_value_bet(acertada=False)

        resp = self.client.get("/api/analisis/rendimiento-value-bets/")
        data = resp.json()
        self.assertTrue(data["datos_suficientes"])
        self.assertEqual(data["resueltas"], 20)
        self.assertAlmostEqual(data["win_rate"], 0.75)
        # PNL: 15*100 - 5*100 = 1000, stake: 20*100 = 2000 -> ROI 50%
        self.assertAlmostEqual(data["roi_teorico"], 0.5)
        self.assertAlmostEqual(data["ev_promedio"], 0.2)
        self.assertAlmostEqual(data["edge_promedio"], 0.1)


class RendimientoPorMercadoApiTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local PM", api_football_id=97005)
        visita = Equipo.objects.create(nombre="Visita PM", api_football_id=97006)
        self.partido = Partido.objects.create(
            equipo_local=local,
            equipo_visitante=visita,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.FINALIZADO,
            resultado={"local": 1, "visitante": 0},
        )

    def _crear_analisis(self, mercado, acertada, recomendacion=AnalisisPartido.Recomendacion.NO_BET):
        return AnalisisPartido.objects.create(
            partido=self.partido,
            mercado=mercado,
            seleccion_evaluada="LOCAL",
            probabilidad_seleccion=0.6,
            probabilidad_implicita=0.5,
            cuota_mercado=Decimal("2.00"),
            recomendacion=recomendacion,
            prediccion_acertada=acertada,
        )

    def test_sin_datos_retorna_lista_vacia(self):
        resp = self.client.get("/api/analisis/rendimiento-por-mercado/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_excluye_general(self):
        for _ in range(20):
            self._crear_analisis("GENERAL", True)
        resp = self.client.get("/api/analisis/rendimiento-por-mercado/")
        self.assertEqual(resp.json(), [])

    def test_no_mezcla_mercados_distintos(self):
        """1X2 bien calibrado (20/20 aciertos) y Over/Under mal calibrado (0/20)
        no deberían promediarse juntos -- cada uno con su propio número."""
        for _ in range(20):
            self._crear_analisis("1X2", True)
        for _ in range(20):
            self._crear_analisis("OVER_UNDER_4.5", False)

        resp = self.client.get("/api/analisis/rendimiento-por-mercado/")
        filas = resp.json()
        # Una fila por mercado, no una por cada AnalisisPartido -- el
        # ordering default del modelo (-fecha_analisis) rompía el .distinct()
        # de esto silenciosamente (cada fila con fecha distinta "no era
        # duplicada" para SQL), así que esto es la regresión real a cubrir.
        self.assertEqual(len(filas), 2)
        data = {fila["mercado"]: fila for fila in filas}

        self.assertTrue(data["1X2"]["datos_suficientes"])
        self.assertEqual(data["1X2"]["accuracy"], 1.0)
        self.assertTrue(data["OVER_UNDER_4.5"]["datos_suficientes"])
        self.assertEqual(data["OVER_UNDER_4.5"]["accuracy"], 0.0)

    def test_mercado_con_pocos_casos_queda_insuficiente(self):
        for _ in range(5):
            self._crear_analisis("OVER_UNDER_2.5", True)
        resp = self.client.get("/api/analisis/rendimiento-por-mercado/")
        data = {fila["mercado"]: fila for fila in resp.json()}
        self.assertFalse(data["OVER_UNDER_2.5"]["datos_suficientes"])
        self.assertEqual(data["OVER_UNDER_2.5"]["predicciones_resueltas"], 5)
