"""
Importa `liga_chile_contexto_2022_2026.xlsx` (ver HANDOFF_dataset_contexto.md en la
raíz del repo): sede/altitud por club y features de contexto por partido (distancia de
viaje, derbi, altitud, descanso) para las cinco temporadas 2022-2026.

Es CONTEXTO INFORMATIVO, mismo criterio que ya usa Equipo.metadata["fotmob"] (ver
ml_models/pipelines/fotmob_stats.py): se guarda para poder auditarlo con
backtest_modelo más adelante, pero calcular_ratings()/proyectar_xg() no lo tocan
todavía -- ninguno de los hallazgos del handoff pasó por esa validación.

Las columnas "targets calculados del marcador" (total_goles, resultado, over_X, etc.)
del Excel NO se importan: son derivables al toque de Partido.resultado, que ya
tenemos, y guardarlas de nuevo sería duplicar dato en vez de agregar información.

Idempotente: correrlo de nuevo pisa la sede/contexto guardado, no duplica nada.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand

from db_models.models import Equipo, Partido

RUTA_POR_DEFECTO = str(
    Path(__file__).resolve().parents[2] / "historical_datasets" / "liga_chile_contexto_2022_2026.xlsx"
)

# Nombre tal como aparece en el Excel -> id del Equipo ya existente en nuestra base
# (confirmado a mano contra Equipo.objects.all(), ver HANDOFF_dataset_contexto.md).
# Cubre los 23 clubes que jugaron Primera entre 2022 y 2026, incluidos los ya
# descendidos -- sin esto, import_historical_dataset-style get_or_create crearía un
# Equipo duplicado por cada nombre que no calce letra por letra.
EXCEL_A_EQUIPO_ID = {
    "Audax Italiano": 10,
    "Cobreloa": 17,
    "Cobresal": 12,
    "Colo-Colo": 4,
    "Coquimbo Unido": 5,
    "Curico Unido": 21,
    "Deportes Antofagasta": 22,
    "Deportes Concepcion": 8,
    "Deportes Copiapo": 18,
    "Deportes Iquique": 19,
    "Deportes La Serena": 6,
    "Deportes Limache": 7,
    "Everton": 15,
    "Huachipato": 13,
    "Magallanes": 23,
    "Nublense": 14,
    "O'Higgins": 16,
    "Palestino": 11,
    "Union Espanola": 20,
    "Union La Calera": 9,
    "Universidad Catolica": 2,
    "Universidad de Chile": 1,
    "Universidad de Concepcion": 3,
}

# Dos filas que el propio handoff marca como no jugadas -- no tienen marcador real
# con qué cruzar contra nuestro Partido.resultado.
ESTADOS_A_OMITIR = {"No disputado", "Suspendido"}

CAMPOS_CONTEXTO = [
    "jornada",
    "fecha",
    "estadio",
    "ciudad_local",
    "ciudad_visita",
    "distancia_viaje_km",
    "viaje_largo_700km",
    "derbi_misma_ciudad",
    "altitud_local_m",
    "altitud_sede_visita_m",
    "delta_altitud_m",
    "altura_2000m",
    "dias_descanso_local",
    "dias_descanso_visita",
]


class Command(BaseCommand):
    help = "Importa sede/altitud por club y contexto por partido desde liga_chile_contexto_2022_2026.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("--ruta", default=RUTA_POR_DEFECTO, help="Ruta al .xlsx.")

    def handle(self, *args, **options):
        wb = openpyxl.load_workbook(options["ruta"], read_only=True, data_only=True)

        equipos_actualizados = self._importar_sedes(wb["Sedes"])
        self.stdout.write(self.style.SUCCESS(f"Sedes guardadas en Equipo.metadata: {equipos_actualizados}/23"))

        resumen = self._importar_partidos(wb["Partidos"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Partidos actualizados: {resumen['actualizados']}  "
                f"omitidos (no jugados): {resumen['omitidos']}  "
                f"sin match en la base: {resumen['sin_match']}  "
                f"marcador no coincide (no se tocó): {resumen['marcador_distinto']}"
            )
        )
        if resumen["sin_match_detalle"]:
            self.stdout.write("\nSin match (revisar nombre/temporada):")
            for detalle in resumen["sin_match_detalle"][:20]:
                self.stdout.write(f"  {detalle}")
            if len(resumen["sin_match_detalle"]) > 20:
                self.stdout.write(f"  ... y {len(resumen['sin_match_detalle']) - 20} más.")
        if resumen["marcador_distinto_detalle"]:
            self.stdout.write("\nMarcador no coincide (posible cruce erróneo, no se tocó):")
            for detalle in resumen["marcador_distinto_detalle"]:
                self.stdout.write(f"  {detalle}")

    def _importar_sedes(self, hoja) -> int:
        filas = hoja.iter_rows(values_only=True)
        encabezado = next(filas)
        actualizados = 0
        for fila in filas:
            d = dict(zip(encabezado, fila))
            equipo_id = EXCEL_A_EQUIPO_ID.get(d["equipo"])
            if equipo_id is None:
                self.stderr.write(f"Sede sin Equipo mapeado, se ignora: {d['equipo']!r}")
                continue
            equipo = Equipo.objects.get(pk=equipo_id)
            equipo.metadata["sede"] = {
                "ciudad": d["ciudad"],
                "estadio": d["estadio"],
                "lat": d["lat"],
                "lon": d["lon"],
                "altitud_m": d["altitud_m"],
            }
            equipo.save(update_fields=["metadata"])
            actualizados += 1
        return actualizados

    def _importar_partidos(self, hoja) -> dict:
        filas = hoja.iter_rows(values_only=True)
        encabezado = next(filas)

        resumen = {
            "actualizados": 0,
            "omitidos": 0,
            "sin_match": 0,
            "sin_match_detalle": [],
            "marcador_distinto": 0,
            "marcador_distinto_detalle": [],
        }

        for fila in filas:
            d = dict(zip(encabezado, fila))
            if d["estado"] in ESTADOS_A_OMITIR:
                resumen["omitidos"] += 1
                continue

            id_local = EXCEL_A_EQUIPO_ID.get(d["local"])
            id_visita = EXCEL_A_EQUIPO_ID.get(d["visita"])
            if id_local is None or id_visita is None:
                resumen["sin_match"] += 1
                resumen["sin_match_detalle"].append(
                    f"partido_id {d['partido_id']}: equipo sin mapear ({d['local']!r} / {d['visita']!r})"
                )
                continue

            partido = Partido.objects.filter(
                temporada=str(d["temporada"]),
                equipo_local_id=id_local,
                equipo_visitante_id=id_visita,
            ).first()
            if partido is None:
                resumen["sin_match"] += 1
                resumen["sin_match_detalle"].append(
                    f"partido_id {d['partido_id']}: {d['local']} vs {d['visita']} ({d['temporada']}) no está en la base"
                )
                continue

            goles_local_real = partido.resultado.get("local")
            goles_visita_real = partido.resultado.get("visitante")
            if goles_local_real != d["goles_local"] or goles_visita_real != d["goles_visita"]:
                resumen["marcador_distinto"] += 1
                resumen["marcador_distinto_detalle"].append(
                    f"partido_id {d['partido_id']}: Excel {d['goles_local']}-{d['goles_visita']} "
                    f"vs base {goles_local_real}-{goles_visita_real} ({d['local']} vs {d['visita']}, {d['temporada']})"
                )
                continue

            contexto = {campo: d.get(campo) for campo in CAMPOS_CONTEXTO}
            if contexto.get("fecha") is not None:
                contexto["fecha"] = str(contexto["fecha"])
            partido.metricas_avanzadas["contexto_2022_2026"] = contexto
            partido.save(update_fields=["metricas_avanzadas"])
            resumen["actualizados"] += 1

        return resumen
