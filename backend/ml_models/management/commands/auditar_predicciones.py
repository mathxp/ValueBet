"""
Script de diagnóstico: para cada partido programado (o uno puntual con
--partido-id) muestra los números crudos detrás de la proyección de xG --
rating de ataque/defensa de cada equipo, factor de localía, xG local/
visitante/total -- y la distribución de goles totales que produce el
modelo de Poisson a partir de esos números, agrupada en 0/1/2/3/4/5+ goles.

Sirve para detectar a simple vista si algún número base (ej. un xG total
por encima de 4) se ve poco creíble ANTES de que llegue a convertirse en
una recomendación -- ver también trading_engine/scanner.py y
prompt.md sección 8 (auditoría de calibración).
"""

from django.core.management.base import BaseCommand

from db_models.models import Partido
from ml_models.predictor import MatchPredictor, distribucion_goles_totales
from ml_models.pipelines.team_ratings import calcular_ratings, factor_localia


def agrupar_distribucion(distribucion: dict[int, float], corte: int = 4) -> dict[str, float]:
    """{"0": p, "1": p, ..., f"{corte}": p, f"{corte+1}+": p_acumulada}"""
    agrupado = {str(k): 0.0 for k in range(corte + 1)}
    agrupado[f"{corte + 1}+"] = 0.0
    for total, prob in distribucion.items():
        clave = str(total) if total <= corte else f"{corte + 1}+"
        agrupado[clave] += prob
    return agrupado


class Command(BaseCommand):
    help = "Audita los ratings, la proyección de xG y la distribución de Poisson detrás de cada partido programado."

    def add_arguments(self, parser):
        parser.add_argument("--partido-id", type=int, default=None, help="Auditar un solo partido por id.")

    def handle(self, *args, **options):
        qs = Partido.objects.filter(estado=Partido.Estado.PROGRAMADO)
        if options["partido_id"]:
            qs = Partido.objects.filter(pk=options["partido_id"])
        qs = qs.select_related("equipo_local", "equipo_visitante").order_by("fecha_hora")

        if not qs.exists():
            self.stdout.write("No hay partidos que auditar.")
            return

        predictor = MatchPredictor()
        for partido in qs:
            self._auditar_partido(partido, predictor)

    def _auditar_partido(self, partido: Partido, predictor: MatchPredictor):
        encabezado = f"{partido.equipo_local.nombre} vs {partido.equipo_visitante.nombre} ({partido.fecha_hora:%Y-%m-%d %H:%M})"
        self.stdout.write(f"\n=== {encabezado} ===")

        ratings = calcular_ratings(partido.liga)
        local = ratings.get(partido.equipo_local.api_football_id)
        visitante = ratings.get(partido.equipo_visitante.api_football_id)
        if not local or not visitante:
            self.stdout.write("  Sin rating suficiente para alguno de los dos equipos -- se omite.")
            return

        factor_local, factor_visita = factor_localia(partido.liga)
        self.stdout.write(f"  Rating ataque/defensa local:      {local.ataque:.3f} / {local.defensa:.3f}  ({local.partidos} partidos)")
        self.stdout.write(f"  Rating ataque/defensa visitante:  {visitante.ataque:.3f} / {visitante.defensa:.3f}  ({visitante.partidos} partidos)")
        self.stdout.write(f"  Factor de localía:                local x{factor_local:.3f} / visita x{factor_visita:.3f}")

        goles = predictor.predecir_goles(partido)
        if goles is None:
            self.stdout.write("  xG: sin proyección disponible todavía (falta correr project_xg_for_upcoming_matches).")
            return

        xg_local, xg_visitante = goles
        total = xg_local + xg_visitante
        alerta = "  <-- alto para el promedio de la liga" if total > 4.0 else ""
        self.stdout.write(f"  xG local:      {xg_local:.3f}")
        self.stdout.write(f"  xG visitante:  {xg_visitante:.3f}")
        self.stdout.write(f"  xG total:      {total:.3f}{alerta}")

        distribucion = distribucion_goles_totales(xg_local, xg_visitante)
        agrupado = agrupar_distribucion(distribucion, corte=4)
        self.stdout.write("  Distribución de goles totales (Poisson):")
        for clave in ["0", "1", "2", "3", "4", "5+"]:
            self.stdout.write(f"    {clave} goles: {agrupado[clave] * 100:5.1f}%")
