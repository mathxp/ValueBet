from datetime import timedelta

from django.test import TestCase
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
