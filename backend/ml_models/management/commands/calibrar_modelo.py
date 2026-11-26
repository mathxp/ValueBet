"""
Script de validación: compara las probabilidades que predijo el modelo
contra los resultados reales históricos, mercado por mercado -- no asume
que un modelo bien calibrado en 1X2 también lo está en líneas altas de
goles (ver prompt.md sección 8). Usa únicamente AnalisisPartido ya
resuelto (AnalisisPartido.reconciliar) -- nunca inventa un número si no
hay suficiente muestra (ver MIN_MUESTRA_CALIBRACION).

La línea OVER_UNDER_4.5 se incluye a propósito aunque ya no se recomiende
(ver LINEAS_OVER_UNDER_VALIDAS en data_ingestion/tasks.py) -- sirve
justamente para auditar, con números, por qué se sacó.
"""

from django.core.management.base import BaseCommand

from db_models.models import AnalisisPartido
from ml_models.pipelines.calibracion import calcular_reporte, pares_desde_analisis

MERCADOS_A_AUDITAR = [
    "1X2",
    "OVER_UNDER_0.5",
    "OVER_UNDER_1.5",
    "OVER_UNDER_2.5",
    "OVER_UNDER_3.5",
    "OVER_UNDER_4.5",
]


class Command(BaseCommand):
    help = "Calibración del modelo (Brier score, Log Loss, reliability) por mercado, usando resultados reales."

    def handle(self, *args, **options):
        for mercado in MERCADOS_A_AUDITAR:
            queryset = AnalisisPartido.objects.filter(
                mercado=mercado,
                prediccion_acertada__isnull=False,
                probabilidad_seleccion__isnull=False,
            )
            pares = pares_desde_analisis(queryset)
            reporte = calcular_reporte(mercado, pares)
            self._imprimir_reporte(reporte)

    def _imprimir_reporte(self, reporte):
        self.stdout.write(f"\n=== {reporte.mercado} ({reporte.n} casos resueltos) ===")
        if not reporte.datos_suficientes:
            self.stdout.write(
                f"  Datos insuficientes: {reporte.n} caso(s) resuelto(s), mínimo 20 -- no se calcula nada todavía."
            )
            return

        self.stdout.write(f"  Brier score: {reporte.brier_score}   (0 = perfecto, 0.25 = como tirar una moneda)")
        self.stdout.write(f"  Log loss:    {reporte.log_loss}")
        self.stdout.write("  Calibración (probabilidad predicha vs. frecuencia real):")
        for bucket in reporte.buckets:
            if bucket.n == 0:
                self.stdout.write(f"    {bucket.rango:>8}: sin casos")
                continue
            diferencia = abs(bucket.prob_promedio - bucket.frecuencia_real)
            alerta = "  <-- descalibrado" if diferencia > 0.15 else ""
            self.stdout.write(
                f"    {bucket.rango:>8}: n={bucket.n:<4} predicho={bucket.prob_promedio * 100:5.1f}%  real={bucket.frecuencia_real * 100:5.1f}%{alerta}"
            )
