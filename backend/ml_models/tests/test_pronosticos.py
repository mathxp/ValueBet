from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from db_models.models import Equipo, Partido, PronosticoRegistrado
from ml_models.pronosticos import etiqueta_fecha, evaluar_registrados, registrar_proximos


def _partido(local, visita, dias, estado=Partido.Estado.FINALIZADO, resultado=None, liga="Primera División", **extra):
    return Partido.objects.create(
        equipo_local=local,
        equipo_visitante=visita,
        liga=liga,
        temporada="2026",
        fecha_hora=timezone.now() + timedelta(days=dias),
        estado=estado,
        resultado=resultado or {},
        **extra,
    )


class PronosticosTests(TestCase):
    def setUp(self):
        self.a = Equipo.objects.create(nombre="A", api_football_id=95001)
        self.b = Equipo.objects.create(nombre="B", api_football_id=95002)
        for i in range(8):
            _partido(self.a, self.b, -(i + 1) * 7, resultado={"local": 2, "visitante": 0})

    def test_etiqueta_fecha_liga_y_copa(self):
        prox = _partido(self.a, self.b, 3, estado=Partido.Estado.PROGRAMADO)
        self.assertEqual(etiqueta_fecha(prox), "Fecha 9")
        copa = _partido(
            self.a, self.b, 5, estado=Partido.Estado.PROGRAMADO, liga="Copa Chile",
            metricas_avanzadas={"ronda": "Semifinal · ida"},
        )
        self.assertEqual(etiqueta_fecha(copa), "Semifinal · ida")

    def test_registra_y_evalua(self):
        from ml_models.tasks import project_xg_for_upcoming_matches

        prox = _partido(self.a, self.b, 2, estado=Partido.Estado.PROGRAMADO)
        project_xg_for_upcoming_matches(hours_ahead=24 * 21)
        self.assertEqual(registrar_proximos(), 1)
        reg = PronosticoRegistrado.objects.get(partido=prox)
        self.assertEqual(reg.pick_1x2, "LOCAL")
        self.assertEqual(reg.pick_seguro, "1X")

        prox.estado = Partido.Estado.FINALIZADO
        prox.resultado = {"local": 1, "visitante": 1}
        prox.save()
        self.assertEqual(evaluar_registrados(), 1)
        reg.refresh_from_db()
        self.assertFalse(reg.acierto_1x2)
        self.assertTrue(reg.acierto_seguro)
        # 1-1 = 2 goles: acierta solo si el pick era "menos de 2.5"
        self.assertEqual(reg.acierto_goles, reg.pick_goles == "UNDER")


class NotificacionesTests(TestCase):
    def test_sin_configurar_no_hace_nada(self):
        from trading_engine.notificaciones import avisar_pronosticos_seguros, enviar

        with override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID=""):
            self.assertFalse(enviar("hola"))
            self.assertEqual(avisar_pronosticos_seguros(), 0)

    def test_configurado_envia_y_marca_notificado(self):
        from trading_engine.notificaciones import avisar_pronosticos_seguros

        a = Equipo.objects.create(nombre="A", api_football_id=96001)
        b = Equipo.objects.create(nombre="B", api_football_id=96002)
        p = _partido(a, b, 0.5, estado=Partido.Estado.PROGRAMADO)
        PronosticoRegistrado.objects.create(
            partido=p, competicion="Liga", etiqueta_fecha="Fecha 1", prob_local=0.7, prob_empate=0.2,
            prob_visitante=0.1, pick_1x2="LOCAL", pick_seguro="1X", prob_seguro=0.9,
        )
        with override_settings(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="c"), mock.patch(
            "trading_engine.notificaciones.requests.post"
        ) as post:
            self.assertEqual(avisar_pronosticos_seguros(), 1)
            self.assertEqual(avisar_pronosticos_seguros(), 0)  # no repite
        self.assertEqual(post.call_count, 1)
        self.assertIn("A o empate", post.call_args.kwargs["json"]["text"])
