"""
Backtesting con datos históricos, evitando data leakage: para cada partido
finalizado, calcula el rating de ataque/defensa y la proyección de xG
usando SOLO los partidos que ya habían terminado ANTES de esa fecha (ver
`hasta_fecha` en team_ratings.py) -- nunca información del futuro respecto
al partido que se está evaluando.

Compara el modelo de Poisson contra un baseline simple y honesto: el prior
neutro (45% local / 27% empate / 28% visitante) que describe prompt.md
sección 3.4 -- el que este mismo proyecto usaba antes de tener historial
real y decidió dejar de usar. No se inventa un baseline más sofisticado
porque no hace falta: si el modelo de Poisson no le gana ni a esto, no
vale la pena seguir.

El ROI simulado solo se calcula sobre partidos que además tienen una cuota
de mercado real capturada en HistorialCuotas de antes del partido -- la
inmensa mayoría del historial (datasets importados de Excel) no tiene
cuotas guardadas, así que ese número queda "datos insuficientes" la
mayor parte del tiempo. Eso es preferible a inventar una cuota.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from data_ingestion.tasks import LINEAS_OVER_UNDER_VALIDAS
from db_models.models import CalibracionMercado, HistorialCuotas, Partido
from ml_models.pipelines.calibracion import calcular_reporte, construir_curva_calibracion
from ml_models.predictor import distribucion_goles_totales, probabilidad_over, probabilidades_1x2_por_poisson
from ml_models.pipelines.team_ratings import proyectar_xg
from trading_engine.risk_manager import evaluar_apuesta

PRIOR_BASELINE = {"LOCAL": 0.45, "EMPATE": 0.27, "VISITANTE": 0.28}
LINEAS_OVER_UNDER_AUDITADAS = ["1.5", "2.5", "3.5", "4.5"]
BANKROLL_SIMULADO = Decimal("1000")


def _resultado_1x2(goles_local: int, goles_visita: int) -> str:
    if goles_local > goles_visita:
        return "LOCAL"
    if goles_local == goles_visita:
        return "EMPATE"
    return "VISITANTE"


class Command(BaseCommand):
    help = "Backtesting histórico del modelo de Poisson (accuracy, Brier, log loss, ROI simulado), sin data leakage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--guardar-calibracion",
            action="store_true",
            help=(
                "Además de imprimir el reporte, guarda la curva de calibración medida en "
                "CalibracionMercado para las líneas de Over/Under vigentes (ver "
                "LINEAS_OVER_UNDER_VALIDAS) -- ml_models.predictor la usa desde ese momento para "
                "corregir la probabilidad cruda antes de calcular edge/EV."
            ),
        )

    def handle(self, *args, **options):
        partidos = list(
            Partido.objects.filter(estado=Partido.Estado.FINALIZADO)
            .exclude(resultado={})
            .select_related("equipo_local", "equipo_visitante")
            .order_by("fecha_hora")
        )

        pares_modelo: list[tuple[float, int]] = []  # decomposición 3-way (prob por clase, ocurrió)
        pares_baseline: list[tuple[float, int]] = []
        pares_favorito_modelo: list[tuple[float, int]] = []
        aciertos_modelo = aciertos_baseline = 0
        pares_over_under: dict[str, list[tuple[float, int]]] = {linea: [] for linea in LINEAS_OVER_UNDER_AUDITADAS}

        evaluados = 0
        sin_historial_suficiente = 0
        pnl_total = Decimal("0")
        stake_total = Decimal("0")
        apuestas_simuladas = 0

        for partido in partidos:
            goles_local = partido.resultado.get("local")
            goles_visita = partido.resultado.get("visitante")
            if goles_local is None or goles_visita is None:
                continue

            proyeccion = proyectar_xg(
                partido.equipo_local.api_football_id,
                partido.equipo_visitante.api_football_id,
                partido.liga,
                hasta_fecha=partido.fecha_hora,
            )
            if proyeccion is None:
                sin_historial_suficiente += 1
                continue

            evaluados += 1
            xg_local, xg_visitante = proyeccion
            probs_modelo = probabilidades_1x2_por_poisson(xg_local, xg_visitante)
            resultado_real = _resultado_1x2(goles_local, goles_visita)

            for clase in ("LOCAL", "EMPATE", "VISITANTE"):
                ocurrio = int(clase == resultado_real)
                pares_modelo.append((probs_modelo[clase], ocurrio))
                pares_baseline.append((PRIOR_BASELINE[clase], ocurrio))

            favorito_modelo = max(probs_modelo, key=probs_modelo.get)
            favorito_baseline = max(PRIOR_BASELINE, key=PRIOR_BASELINE.get)
            aciertos_modelo += int(favorito_modelo == resultado_real)
            aciertos_baseline += int(favorito_baseline == resultado_real)
            pares_favorito_modelo.append((probs_modelo[favorito_modelo], int(favorito_modelo == resultado_real)))

            distribucion = distribucion_goles_totales(xg_local, xg_visitante)
            total_real = goles_local + goles_visita
            for linea in LINEAS_OVER_UNDER_AUDITADAS:
                prob_over_linea = probabilidad_over(distribucion, float(linea))
                ocurrio_over = int(total_real > float(linea))
                pares_over_under[linea].append((prob_over_linea, ocurrio_over))

            # ROI simulado: solo si hay una cuota real de mercado capturada
            # antes de este partido para el favorito del modelo en 1X2.
            cuota_previa = (
                HistorialCuotas.objects.filter(
                    partido=partido, mercado="1X2", seleccion=favorito_modelo, capturado_en__lt=partido.fecha_hora
                )
                .order_by("-capturado_en")
                .first()
            )
            if cuota_previa:
                evaluacion = evaluar_apuesta(
                    probabilidad_modelo=probs_modelo[favorito_modelo],
                    cuota_decimal=float(cuota_previa.cuota_back),
                    bankroll=BANKROLL_SIMULADO,
                )
                if evaluacion.es_apuesta_de_valor and evaluacion.stake_sugerido > 0:
                    apuestas_simuladas += 1
                    stake_total += evaluacion.stake_sugerido
                    if favorito_modelo == resultado_real:
                        pnl_total += evaluacion.stake_sugerido * (Decimal(str(cuota_previa.cuota_back)) - 1)
                    else:
                        pnl_total -= evaluacion.stake_sugerido

        self.stdout.write(f"Partidos evaluados: {evaluados} (sin historial suficiente todavía: {sin_historial_suficiente})")

        if evaluados == 0:
            self.stdout.write("No hay partidos evaluables -- no se calcula nada.")
            return

        self.stdout.write("\n=== Accuracy (favorito del modelo, 1X2) ===")
        self.stdout.write(f"  Modelo:   {aciertos_modelo}/{evaluados}  ({aciertos_modelo / evaluados:.1%})")
        self.stdout.write(f"  Baseline: {aciertos_baseline}/{evaluados}  ({aciertos_baseline / evaluados:.1%})  (siempre predice LOCAL, prior 45/27/28)")

        self.stdout.write("\n=== Brier score / Log loss (3-way, 1X2) ===")
        reporte_modelo = calcular_reporte("modelo", pares_modelo)
        reporte_baseline = calcular_reporte("baseline", pares_baseline)
        self.stdout.write(f"  Modelo:   brier={reporte_modelo.brier_score}  log_loss={reporte_modelo.log_loss}")
        self.stdout.write(f"  Baseline: brier={reporte_baseline.brier_score}  log_loss={reporte_baseline.log_loss}")

        self.stdout.write("\n=== Calibración del favorito del modelo (1X2) ===")
        reporte_favorito = calcular_reporte("favorito", pares_favorito_modelo)
        if not reporte_favorito.datos_suficientes:
            self.stdout.write(f"  Datos insuficientes: {reporte_favorito.n} casos, mínimo 20.")
        else:
            for bucket in reporte_favorito.buckets:
                if bucket.n == 0:
                    continue
                self.stdout.write(f"    {bucket.rango:>8}: n={bucket.n:<4} predicho={bucket.prob_promedio:.1%}  real={bucket.frecuencia_real:.1%}")

        self.stdout.write("\n=== Over/Under por línea (incluye 4.5 para auditar por qué se sacó) ===")
        for linea in LINEAS_OVER_UNDER_AUDITADAS:
            reporte_linea = calcular_reporte(f"OVER_UNDER_{linea}", pares_over_under[linea])
            if not reporte_linea.datos_suficientes:
                self.stdout.write(f"  Más de {linea}: datos insuficientes ({reporte_linea.n} casos).")
                continue
            self.stdout.write(f"  Más de {linea}: brier={reporte_linea.brier_score}  log_loss={reporte_linea.log_loss}  n={reporte_linea.n}")
            # Un Brier score bajo en un evento poco frecuente (ej. "más de 4.5
            # goles", raro dado que esta liga promedia ~2.7 goles/partido) no
            # prueba buena calibración por sí solo -- puede ser solo el
            # resultado de acertar casi siempre "no" por la base rate. La
            # tabla de calibración es la que de verdad lo confirma o lo
            # desmiente.
            for bucket in reporte_linea.buckets:
                if bucket.n == 0:
                    continue
                diferencia = abs(bucket.prob_promedio - bucket.frecuencia_real)
                alerta = "  <-- descalibrado" if diferencia > 0.15 else ""
                self.stdout.write(
                    f"      {bucket.rango:>8}: n={bucket.n:<5} predicho={bucket.prob_promedio:.1%}  real={bucket.frecuencia_real:.1%}{alerta}"
                )

        if options["guardar_calibracion"]:
            self._guardar_calibracion(pares_over_under)

        self.stdout.write("\n=== ROI simulado (solo partidos con cuota real capturada antes del partido) ===")
        MIN_APUESTAS_ROI = 20
        if apuestas_simuladas == 0:
            self.stdout.write("  Datos insuficientes: no hay cuotas históricas capturadas antes de los partidos evaluados.")
        elif apuestas_simuladas < MIN_APUESTAS_ROI:
            self.stdout.write(
                f"  Solo {apuestas_simuladas} apuesta(s) simulada(s) (mínimo {MIN_APUESTAS_ROI} para que el ROI signifique algo) "
                f"-- PNL={pnl_total}, stake={stake_total}, pero NO es una muestra representativa, no sacar conclusiones todavía."
            )
        else:
            roi = float(pnl_total / stake_total) if stake_total else None
            self.stdout.write(f"  Apuestas simuladas: {apuestas_simuladas}  stake total: {stake_total}  PNL: {pnl_total}  ROI: {roi:.1%}")

    def _guardar_calibracion(self, pares_over_under: dict[str, list[tuple[float, int]]]):
        """
        Guarda la curva de calibración medida para cada línea de Over/Under
        VIGENTE (nunca para 4.5 -- ya no se recomienda, no tiene sentido
        corregir una probabilidad que no se va a usar). Si la muestra no
        alcanza para armar una curva confiable, borra cualquier curva vieja
        para ese mercado en vez de dejar una desactualizada.
        """
        self.stdout.write("\n=== Guardando curva de calibración (Over/Under) ===")
        for linea in LINEAS_OVER_UNDER_VALIDAS:
            mercado = f"OVER_UNDER_{linea}"
            pares = pares_over_under.get(linea, [])
            curva = construir_curva_calibracion(pares)
            if curva is None:
                borrados, _ = CalibracionMercado.objects.filter(mercado=mercado).delete()
                self.stdout.write(f"  {mercado}: sin muestra confiable todavía -- {'se borró la curva vieja' if borrados else 'sin curva'}.")
                continue

            CalibracionMercado.objects.update_or_create(
                mercado=mercado, defaults={"puntos": curva, "n_total": len(pares)}
            )
            self.stdout.write(f"  {mercado}: curva guardada con {len(curva)} puntos (n={len(pares)}).")
