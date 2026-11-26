from datetime import datetime, timezone

from django.test import TestCase

from data_ingestion.equipos import Resolver
from data_ingestion.espn import LIGA_PRINCIPAL, _americana_a_decimal, _sincronizar_evento
from db_models.models import HistorialCuotas
from db_models.models import Equipo, Partido


def _evento(home, away, score_home, score_away, estado="post", odds=None, notas=None, slug=None):
    return {
        "id": "1",
        "date": "2026-11-28T21:00Z",
        "season": {"year": 2026, **({"slug": slug} if slug else {})},
        "status": {"type": {"name": "STATUS_FULL_TIME", "state": estado, "completed": estado == "post"}},
        "competitions": [
            {
                **({"odds": [odds]} if odds else {}),
                "notes": notas or [],
                "competitors": [
                    {"homeAway": "home", "score": score_home, "team": {"displayName": home, "logo": ""}},
                    {"homeAway": "away", "score": score_away, "team": {"displayName": away, "logo": ""}},
                ]
            }
        ],
    }


class SincronizarEventoTests(TestCase):
    def setUp(self):
        self.colo = Equipo.objects.create(nombre="Colo Colo", api_football_id=1)
        self.serena = Equipo.objects.create(nombre="D. La Serena", api_football_id=2)
        self.stats = {"creados": 0, "actualizados": 0, "cuotas": 0, "sin_equipo": set()}

    def test_actualiza_partido_existente_con_alias_de_nombre(self):
        partido = Partido.objects.create(
            equipo_local=self.colo,
            equipo_visitante=self.serena,
            temporada="2026",
            liga=LIGA_PRINCIPAL,
            fecha_hora=datetime(2026, 11, 28, 21, tzinfo=timezone.utc),
        )
        _sincronizar_evento(_evento("Colo-Colo", "La Serena", "3", "1"), LIGA_PRINCIPAL, Resolver(), self.stats)

        partido.refresh_from_db()
        self.assertEqual(partido.estado, Partido.Estado.FINALIZADO)
        self.assertEqual(partido.resultado, {"local": 3, "visitante": 1})
        self.assertEqual(self.stats["actualizados"], 1)
        self.assertEqual(Partido.objects.count(), 1)

    def test_crea_partido_programado_sin_resultado(self):
        _sincronizar_evento(_evento("Colo Colo", "La Serena", "0", "0", estado="pre"), LIGA_PRINCIPAL, Resolver(), self.stats)

        partido = Partido.objects.get()
        self.assertEqual(partido.estado, Partido.Estado.PROGRAMADO)
        self.assertEqual(partido.resultado, {})
        self.assertEqual(self.stats["creados"], 1)

    def test_equipo_desconocido_no_crea_nada(self):
        _sincronizar_evento(_evento("Equipo Fantasma", "La Serena", "1", "0"), LIGA_PRINCIPAL, Resolver(), self.stats)

        self.assertEqual(Partido.objects.count(), 0)
        self.assertEqual(self.stats["sin_equipo"], {"Equipo Fantasma"})


ODDS = {
    "overUnder": 2.5,
    "moneyline": {
        "home": {"close": {"odds": "-120"}},
        "draw": {"close": {"odds": "+285"}},
        "away": {"close": {"odds": "+270"}},
    },
    "total": {"over": {"close": {"odds": "-170"}}, "under": {"close": {"odds": "+120"}}},
}


class CuotasYCopaTests(TestCase):
    def setUp(self):
        self.colo = Equipo.objects.create(nombre="Colo Colo", api_football_id=1)
        self.serena = Equipo.objects.create(nombre="D. La Serena", api_football_id=2)
        self.stats = {"creados": 0, "actualizados": 0, "cuotas": 0, "sin_equipo": set()}

    def test_conversion_cuota_americana(self):
        self.assertEqual(float(_americana_a_decimal("+285")), 3.85)
        self.assertAlmostEqual(float(_americana_a_decimal("-120")), 1.833, places=3)
        self.assertIsNone(_americana_a_decimal("N/A"))

    def test_guarda_cuotas_previas_y_no_duplica(self):
        ev = _evento("Colo Colo", "La Serena", "0", "0", estado="pre", odds=ODDS)
        _sincronizar_evento(ev, LIGA_PRINCIPAL, Resolver(), self.stats)
        _sincronizar_evento(ev, LIGA_PRINCIPAL, Resolver(), self.stats)
        self.assertEqual(HistorialCuotas.objects.filter(mercado="1X2").count(), 3)
        self.assertEqual(HistorialCuotas.objects.filter(mercado="OVER_UNDER_2.5").count(), 2)

    def test_partido_de_copa_guarda_ronda_y_no_choca_con_la_liga(self):
        _sincronizar_evento(_evento("Colo Colo", "La Serena", "2", "0"), LIGA_PRINCIPAL, Resolver(), self.stats)
        copa = _evento(
            "Colo Colo", "La Serena", "0", "0", estado="pre", slug="semifinals",
            notas=[{"headline": "1st Leg"}],
        )
        copa["id"] = "2"
        _sincronizar_evento(copa, "Copa Chile", Resolver(), self.stats)
        self.assertEqual(Partido.objects.count(), 2)
        p = Partido.objects.get(liga="Copa Chile")
        self.assertEqual(p.metricas_avanzadas["ronda"], "Semifinal · ida")
