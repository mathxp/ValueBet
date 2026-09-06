from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from db_models.models import Partido


class Command(BaseCommand):
    help = (
        "Genera un prompt listo para pegar en Claude.ai o Gemini (con búsqueda web) "
        "pidiendo goles esperados (xG) para los próximos partidos de la liga chilena. "
        "No llama a ninguna API -- es para uso manual, ya que no hay API key de pago "
        "configurada, solo las apps de chat (Claude Pro / Gemini Pro)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=10,
            help="Cuántos días hacia adelante incluir (default: 10, cubre la próxima fecha).",
        )

    def handle(self, *args, **options):
        horizonte = timezone.now() + timedelta(days=options["days_ahead"])
        partidos = Partido.objects.filter(
            estado=Partido.Estado.PROGRAMADO,
            fecha_hora__gte=timezone.now(),
            fecha_hora__lte=horizonte,
        ).select_related("equipo_local", "equipo_visitante").order_by("fecha_hora")

        if not partidos:
            self.stdout.write(
                self.style.WARNING(
                    "No hay partidos programados en ese rango. Corré primero "
                    "'python manage.py run_pipeline_once' para sincronizar fixtures."
                )
            )
            return

        lista_partidos = "\n".join(
            f"{i}. {p.equipo_local.nombre} vs {p.equipo_visitante.nombre} "
            f"-- {p.fecha_hora.strftime('%A %d/%m %H:%M')}"
            for i, p in enumerate(partidos, start=1)
        )

        prompt = f"""Sos un analista de fútbol especializado en la Primera División de Chile.
Para cada uno de estos partidos, buscá en la web información actualizada sobre:
- Bajas por lesión o suspensión de cada plantel
- Forma reciente (últimos 5 partidos: victorias/empates/derrotas y goles)
- Historial reciente entre ambos equipos
- Cualquier factor relevante (cambio de DT, carga de partidos, clima si aplica)

Partidos:
{lista_partidos}

Con esa información, estimá el xG (goles esperados) de cada equipo para cada
partido -- un número decimal razonable (ej. 1.4, no "alto" o "bajo"). Si hay
consenso público de xG (SofaScore, FotMob, Understat u otra fuente con datos
de esta liga), priorizalo por sobre tu propia estimación y citá la fuente.

Respondé en este formato exacto, una línea por partido, para que sea fácil de
copiar al sistema:

N. Equipo Local vs Equipo Visitante: xG_local=X.X xG_visitante=X.X
   Justificación: <1-2 frases con lo más relevante que encontraste>
"""

        self.stdout.write(prompt)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n({len(partidos)} partido(s). Pegá lo de arriba en Claude.ai o Gemini, "
                "y cargá los xG resultantes en /admin/ -> Partidos -> el partido correspondiente.)"
            )
        )
