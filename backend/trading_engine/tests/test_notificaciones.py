from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from db_models.models import (
    ClaveVapid,
    Equipo,
    Notificacion,
    Partido,
    PronosticoRegistrado,
    SuscripcionPush,
)
from trading_engine import notificaciones as nt


def _registro(partido, prob=0.9, **extra):
    return PronosticoRegistrado.objects.create(
        partido=partido, competicion="Liga de Primera", etiqueta_fecha="Fecha 29", prob_local=0.7,
        prob_empate=0.2, prob_visitante=0.1, pick_1x2="LOCAL", pick_seguro="1X", prob_seguro=prob, **extra,
    )


class NotificacionesTests(TestCase):
    def setUp(self):
        self.a = Equipo.objects.create(nombre="Colo Colo", api_football_id=97001)
        self.b = Equipo.objects.create(nombre="La Serena", api_football_id=97002)

    def _partido(self, horas, **extra):
        return Partido.objects.create(
            equipo_local=self.a, equipo_visitante=self.b, temporada="2026", liga="Primera División",
            fecha_hora=timezone.now() + timedelta(hours=horas), **extra,
        )

    def test_claves_vapid_se_generan_una_sola_vez(self):
        c1 = nt.claves_vapid()
        c2 = nt.claves_vapid()
        self.assertEqual(c1.pk, c2.pk)
        self.assertEqual(ClaveVapid.objects.count(), 1)
        self.assertTrue(c1.privada.startswith("-----BEGIN PRIVATE KEY-----"))

    def test_pronostico_seguro_notifica_una_vez(self):
        _registro(self._partido(10), prob=0.82)
        _registro(self._partido(12), prob=0.60)  # bajo el umbral: no se anuncia
        with mock.patch.object(nt, "enviar_push") as push:
            self.assertEqual(nt.avisar_pronosticos_seguros(), 1)
            self.assertEqual(nt.avisar_pronosticos_seguros(), 0)
        self.assertEqual(Notificacion.objects.count(), 1)
        self.assertIn("Colo Colo o empate", Notificacion.objects.get().titulo)
        push.assert_called_once()

    def test_resultado_de_fecha_solo_cuando_termina_completa(self):
        p1 = self._partido(-30)
        p2 = self._partido(-28)
        _registro(p1, acierto_1x2=True, acierto_seguro=True)
        r2 = _registro(p2)  # aún sin evaluar
        with mock.patch.object(nt, "enviar_push"):
            self.assertEqual(nt.avisar_resultados_de_fecha(), 0)
            PronosticoRegistrado.objects.filter(pk=r2.pk).update(acierto_1x2=False, acierto_seguro=True)
            self.assertEqual(nt.avisar_resultados_de_fecha(), 1)
            self.assertEqual(nt.avisar_resultados_de_fecha(), 0)  # no repite
        self.assertEqual(Notificacion.objects.get().titulo, "📊 Fecha 29: acertamos 2 de 2")

    def test_push_borra_suscripciones_revocadas(self):
        from pywebpush import WebPushException

        SuscripcionPush.objects.create(endpoint="https://push.example/x", p256dh="k", auth="a")
        notif = Notificacion.objects.create(clave="t", tipo="SISTEMA", titulo="hola")
        respuesta = mock.Mock(status_code=410)
        with mock.patch("pywebpush.webpush", side_effect=WebPushException("gone", response=respuesta)):
            self.assertEqual(nt.enviar_push(notif), 0)
        self.assertEqual(SuscripcionPush.objects.count(), 0)


class NotificacionesApiTests(TestCase):
    def test_listar_y_marcar_leidas(self):
        Notificacion.objects.create(clave="a", tipo="SISTEMA", titulo="uno")
        Notificacion.objects.create(clave="b", tipo="SISTEMA", titulo="dos")
        resp = self.client.get("/api/notificaciones/")
        self.assertEqual(resp.json()["no_leidas"], 2)
        self.client.post("/api/notificaciones/")
        self.assertEqual(self.client.get("/api/notificaciones/").json()["no_leidas"], 0)

    def test_suscribir_y_desuscribir(self):
        clave = self.client.get("/api/push/").json()["clave_publica"]
        self.assertGreater(len(clave), 80)
        sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "p", "auth": "a"}}
        self.assertEqual(self.client.post("/api/push/", sub, content_type="application/json").status_code, 201)
        self.assertEqual(SuscripcionPush.objects.count(), 1)
        self.client.delete("/api/push/", {"endpoint": sub["endpoint"]}, content_type="application/json")
        self.assertEqual(SuscripcionPush.objects.count(), 0)
