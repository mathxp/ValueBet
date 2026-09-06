from decimal import Decimal

from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from db_models.models import AnalisisPartido, Equipo, HistorialCuotas, Operacion, Partido
from db_models.serializers import (
    AnalisisPartidoSerializer,
    EquipoSerializer,
    HistorialCuotasSerializer,
    OperacionSerializer,
    PartidoSerializer,
)


class EquipoViewSet(viewsets.ModelViewSet):
    queryset = Equipo.objects.all()
    serializer_class = EquipoSerializer

    @action(detail=False, methods=["get"])
    def ratings(self, request):
        """
        Rating de ataque/defensa de cada equipo (goles a favor/en contra
        promedio, con regularización estadística) -- ver
        ml_models/pipelines/team_ratings.py para la metodología completa.
        """
        from ml_models.pipelines.team_ratings import MIN_PARTIDOS_PARA_RATING, calcular_ratings

        ratings = calcular_ratings()
        equipos_por_id = {e.api_football_id: e for e in Equipo.objects.all()}

        resultados = []
        for api_football_id, rating in ratings.items():
            equipo = equipos_por_id.get(api_football_id)
            if not equipo:
                continue
            resultados.append(
                {
                    "equipo": EquipoSerializer(equipo).data,
                    "ataque": round(rating.ataque, 2),
                    "defensa": round(rating.defensa, 2),
                    "partidos": rating.partidos,
                    "confiable": rating.partidos >= MIN_PARTIDOS_PARA_RATING,
                }
            )

        resultados.sort(key=lambda r: r["ataque"] - r["defensa"], reverse=True)
        return Response(resultados)


class PartidoViewSet(viewsets.ModelViewSet):
    queryset = Partido.objects.select_related("equipo_local", "equipo_visitante").all()
    serializer_class = PartidoSerializer
    filterset_fields = ["estado", "liga"]

    @action(detail=True, methods=["get"])
    def cuotas(self, request, pk=None):
        partido = self.get_object()
        historial = partido.historial_cuotas.all()[:100]
        serializer = HistorialCuotasSerializer(historial, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def prediccion(self, request, pk=None):
        """
        Goles esperados (xG proyectado) y probabilidades 1X2 derivadas.
        Si el equipo todavía no tiene suficiente historial jugado, no hay
        señal real y se retorna `disponible: false` en vez de inventar un
        número -- ver ml_models/predictor.py.
        """
        from ml_models.predictor import MatchPredictor

        partido = self.get_object()
        predictor = MatchPredictor()
        goles = predictor.predecir_goles(partido)

        if goles is None:
            return Response({"disponible": False, "motivo": "Sin historial suficiente aún"})

        return Response(
            {
                "disponible": True,
                "xg_local": goles[0],
                "xg_visitante": goles[1],
                "fuente": partido.metricas_avanzadas.get("xg_fuente", "desconocida"),
                "probabilidades": predictor.predecir(partido),
            }
        )


class HistorialCuotasViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistorialCuotas.objects.select_related("partido").all()
    serializer_class = HistorialCuotasSerializer


class OperacionViewSet(viewsets.ModelViewSet):
    """
    Los endpoints de abajo (aceptar/descartar/marcar_*) existen para que el
    dashboard pueda gestionar el ciclo de vida de una recomendación con un
    botón, sin tener que pasar por /admin/. Hacen lo mismo que las acciones
    del admin (ver db_models/admin.py) -- misma lógica, dos entradas.
    """

    queryset = Operacion.objects.select_related("partido").all()
    serializer_class = OperacionSerializer

    def _requiere_estado(self, operacion, estado_esperado):
        if operacion.estado != estado_esperado:
            return Response(
                {"detail": f"La recomendación está en estado {operacion.estado}, se esperaba {estado_esperado}."},
                status=409,
            )
        return None

    @action(detail=True, methods=["post"])
    def aceptar(self, request, pk=None):
        operacion = self.get_object()
        error = self._requiere_estado(operacion, Operacion.Estado.RECOMENDADA)
        if error:
            return error
        operacion.aceptar()
        return Response(self.get_serializer(operacion).data)

    @action(detail=True, methods=["post"])
    def descartar(self, request, pk=None):
        operacion = self.get_object()
        error = self._requiere_estado(operacion, Operacion.Estado.RECOMENDADA)
        if error:
            return error
        operacion.descartar()
        return Response(self.get_serializer(operacion).data)

    @action(detail=True, methods=["post"], url_path="marcar-ganada")
    def marcar_ganada(self, request, pk=None):
        operacion = self.get_object()
        error = self._requiere_estado(operacion, Operacion.Estado.ACEPTADA)
        if error:
            return error
        operacion.marcar_ganada()
        return Response(self.get_serializer(operacion).data)

    @action(detail=True, methods=["post"], url_path="marcar-perdida")
    def marcar_perdida(self, request, pk=None):
        operacion = self.get_object()
        error = self._requiere_estado(operacion, Operacion.Estado.ACEPTADA)
        if error:
            return error
        operacion.marcar_perdida()
        return Response(self.get_serializer(operacion).data)

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """PNL agregado y estadísticas rápidas para el dashboard."""
        from django.db.models import Count, Sum

        qs = self.get_queryset()
        agregados = qs.aggregate(
            pnl_total=Sum("pnl"),
            total_operaciones=Count("id"),
        )
        ganadas = qs.filter(estado=Operacion.Estado.GANADA).count()
        finalizadas = qs.filter(
            estado__in=[Operacion.Estado.GANADA, Operacion.Estado.PERDIDA]
        ).count()
        agregados["win_rate"] = (ganadas / finalizadas) if finalizadas else None
        return Response(agregados)


class AnalisisPartidoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Historial de CADA análisis (haya o no recomendación) -- ver
    db_models.models.AnalisisPartido. Sirve para auditar el modelo con el
    tiempo, no solo mirar las recomendaciones que se terminaron sugiriendo.
    """

    queryset = AnalisisPartido.objects.select_related(
        "partido__equipo_local", "partido__equipo_visitante"
    ).all()
    serializer_class = AnalisisPartidoSerializer
    filterset_fields = ["recomendacion", "mercado"]

    @action(detail=False, methods=["get"])
    def rendimiento(self, request):
        """
        Compara el modelo contra un baseline ingenuo (confiar directamente en
        la probabilidad implícita del mercado) -- solo con análisis ya
        resueltos (partido terminado). No inventa números: si no hay
        suficientes casos resueltos todavía, lo dice explícitamente en vez de
        mostrar una métrica poco confiable con pocos datos.
        """
        minimo_para_comparar = 20

        resueltos = self.get_queryset().filter(
            prediccion_acertada__isnull=False,
            probabilidad_seleccion__isnull=False,
            probabilidad_implicita__isnull=False,
        )
        total = resueltos.count()

        if total < minimo_para_comparar:
            return Response(
                {
                    "datos_suficientes": False,
                    "predicciones_resueltas": total,
                    "minimo_requerido": minimo_para_comparar,
                    "motivo": (
                        "Todavía no hay suficientes análisis con resultado real para una "
                        "comparación estadísticamente significativa."
                    ),
                }
            )

        aciertos_modelo = 0
        aciertos_baseline = 0
        brier_modelo = 0.0
        brier_baseline = 0.0
        pnl_total = Decimal("0")
        stake_total = Decimal("0")

        for fila in resueltos:
            ocurrio = 1 if fila.prediccion_acertada else 0
            aciertos_modelo += ocurrio
            brier_modelo += (fila.probabilidad_seleccion - ocurrio) ** 2

            baseline_predice_ocurre = fila.probabilidad_implicita >= 0.5
            aciertos_baseline += int(baseline_predice_ocurre == bool(ocurrio))
            brier_baseline += (fila.probabilidad_implicita - ocurrio) ** 2

            if fila.recomendacion == AnalisisPartido.Recomendacion.VALUE_BET and fila.pnl_teorico is not None:
                pnl_total += fila.pnl_teorico
                stake_total += fila.stake_sugerido or Decimal("0")

        return Response(
            {
                "datos_suficientes": True,
                "predicciones_resueltas": total,
                "modelo": {
                    "accuracy": aciertos_modelo / total,
                    "brier_score": round(brier_modelo / total, 4),
                },
                "baseline_mercado": {
                    "accuracy": aciertos_baseline / total,
                    "brier_score": round(brier_baseline / total, 4),
                },
                "roi_value_bets": float(pnl_total / stake_total) if stake_total else None,
                "stake_total_teorico": stake_total,
                "pnl_total_teorico": pnl_total,
            }
        )


class ConfiguracionView(APIView):
    """Configuración de riesgo/ingesta actual (solo lectura, sin credenciales)."""

    def get(self, request):
        return Response(
            {
                "paper_bankroll": settings.PAPER_BANKROLL,
                "kelly_fraction": settings.KELLY_FRACTION,
                "max_stake_per_bet": settings.MAX_STAKE_PER_BET,
                "min_edge_threshold": settings.MIN_EDGE_THRESHOLD,
                "watched_leagues": list(settings.WATCHED_LEAGUES),
                "api_football_configurado": bool(settings.API_FOOTBALL_KEY),
                "betfair_configurado": bool(
                    settings.BETFAIR_APP_KEY
                    and settings.BETFAIR_USERNAME
                    and settings.BETFAIR_PASSWORD
                    and settings.BETFAIR_CERT_PATH
                ),
                "modo_exchange": "BETFAIR"
                if (
                    settings.BETFAIR_APP_KEY
                    and settings.BETFAIR_USERNAME
                    and settings.BETFAIR_PASSWORD
                    and settings.BETFAIR_CERT_PATH
                )
                else "PAPER",
            }
        )
