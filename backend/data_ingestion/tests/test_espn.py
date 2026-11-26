from datetime import datetime, timezone

from django.test import TestCase

from data_ingestion.equipos import Resolver
from data_ingestion.espn import _sincronizar_evento
from db_models.models import Equipo, Partido


def _evento(home, away, score_home, score_away, estado="post"):
    return {
        "id": "1",
        "date": "2026-11-28T21:00Z",
        "season": {"year": 2026},
        "status": {"type": {"name": "STATUS_FULL_TIME", "state": estado, "completed": estado == "post"}},
        "competitions": [
            {
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
        self.stats = {"creados": 0, "actualizados": 0, "sin_equipo": set()}

    def test_actualiza_partido_existente_con_alias_de_nombre(self):
        partido = Partido.objects.create(
            equipo_local=self.colo,
            equipo_visitante=self.serena,
            temporada="2026",
            fecha_hora=datetime(2026, 11, 28, 21, tzinfo=timezone.utc),
        )
        _sincronizar_evento(_evento("Colo-Colo", "La Serena", "3", "1"), Resolver(), self.stats)

        partido.refresh_from_db()
        self.assertEqual(partido.estado, Partido.Estado.FINALIZADO)
        self.assertEqual(partido.resultado, {"local": 3, "visitante": 1})
        self.assertEqual(self.stats["actualizados"], 1)
        self.assertEqual(Partido.objects.count(), 1)

    def test_crea_partido_programado_sin_resultado(self):
        _sincronizar_evento(_evento("Colo Colo", "La Serena", "0", "0", estado="pre"), Resolver(), self.stats)

        partido = Partido.objects.get()
        self.assertEqual(partido.estado, Partido.Estado.PROGRAMADO)
        self.assertEqual(partido.resultado, {})
        self.assertEqual(self.stats["creados"], 1)

    def test_equipo_desconocido_no_crea_nada(self):
        _sincronizar_evento(_evento("Equipo Fantasma", "La Serena", "1", "0"), Resolver(), self.stats)

        self.assertEqual(Partido.objects.count(), 0)
        self.assertEqual(self.stats["sin_equipo"], {"Equipo Fantasma"})
