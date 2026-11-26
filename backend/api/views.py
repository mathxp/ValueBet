from decimal import Decimal

from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from db_models.models import (
    AnalisisPartido,
    Combinada,
    ConfiguracionRiesgo,
    Equipo,
    HistorialCuotas,
    Operacion,
    Partido,
    ResultadoBacktest,
)
from db_models.serializers import (
    AnalisisPartidoSerializer,
    CombinadaSerializer,
    ConfiguracionRiesgoSerializer,
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
    filterset_fields = {
        "mercado": ["exact"],
        # "in" además de "exact" -- el dashboard lo usa para pedir "todo
        # menos descartadas" por defecto (?estado__in=a,b,c) sin tener que
        # listar cada estado como filtro exact aparte.
        "estado": ["exact", "in"],
        "partido__temporada": ["exact"],
    }

    def _requiere_estado(self, operacion, estado_esperado):
        if operacion.estado != estado_esperado:
            return Response(
                {"detail": f"La recomendación está en estado {operacion.estado}, se esperaba {estado_esperado}."},
                status=409,
            )
        return None

    def _requiere_estado_en(self, operacion, estados_esperados):
        if operacion.estado not in estados_esperados:
            return Response(
                {
                    "detail": (
                        f"La recomendación está en estado {operacion.estado}, se esperaba uno de "
                        f"{', '.join(estados_esperados)}."
                    )
                },
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

    @action(detail=True, methods=["post"], url_path="marcar-anulada")
    def marcar_anulada(self, request, pk=None):
        """NULA/PUSH: se devuelve el stake, sin efecto en el PNL."""
        operacion = self.get_object()
        error = self._requiere_estado(operacion, Operacion.Estado.ACEPTADA)
        if error:
            return error
        operacion.marcar_anulada()
        return Response(self.get_serializer(operacion).data)

    @action(detail=True, methods=["post"])
    def revertir(self, request, pk=None):
        """Deshace un Ganó/Perdió/Anulada marcado por error -- vuelve a Aceptada sin PNL."""
        operacion = self.get_object()
        error = self._requiere_estado_en(
            operacion, [Operacion.Estado.GANADA, Operacion.Estado.PERDIDA, Operacion.Estado.ANULADA]
        )
        if error:
            return error
        operacion.revertir_a_aceptada()
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
        # Con pocas apuestas resueltas, el win rate es ruido, no una señal --
        # no tiene sentido estadístico "confiar" en un 50% que sale de 2
        # casos. Mismo mínimo que usa AnalisisPartidoViewSet.rendimiento().
        minimo_para_comparar = 20
        agregados["win_rate"] = (ganadas / finalizadas) if finalizadas else None
        agregados["finalizadas"] = finalizadas
        agregados["minimo_requerido"] = minimo_para_comparar
        agregados["muestra_suficiente"] = finalizadas >= minimo_para_comparar
        return Response(agregados)


class CombinadaViewSet(viewsets.ModelViewSet):
    """
    Mismas acciones que OperacionViewSet (aceptar/descartar/marcar_*/revertir)
    y misma razón de ser -- ver trading_engine/combinador.py para cómo se
    arma cada combinada.
    """

    queryset = Combinada.objects.prefetch_related("patas__partido__equipo_local", "patas__partido__equipo_visitante").all()
    serializer_class = CombinadaSerializer
    filterset_fields = {"estado": ["exact"]}

    def _requiere_estado(self, combinada, estado_esperado):
        if combinada.estado != estado_esperado:
            return Response(
                {"detail": f"La combinada está en estado {combinada.estado}, se esperaba {estado_esperado}."},
                status=409,
            )
        return None

    def _requiere_estado_en(self, combinada, estados_esperados):
        if combinada.estado not in estados_esperados:
            return Response(
                {
                    "detail": (
                        f"La combinada está en estado {combinada.estado}, se esperaba uno de "
                        f"{', '.join(estados_esperados)}."
                    )
                },
                status=409,
            )
        return None

    @action(detail=True, methods=["post"])
    def aceptar(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado(combinada, Combinada.Estado.RECOMENDADA)
        if error:
            return error
        combinada.aceptar()
        return Response(self.get_serializer(combinada).data)

    @action(detail=True, methods=["post"])
    def descartar(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado(combinada, Combinada.Estado.RECOMENDADA)
        if error:
            return error
        combinada.descartar()
        return Response(self.get_serializer(combinada).data)

    @action(detail=True, methods=["post"], url_path="marcar-ganada")
    def marcar_ganada(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado(combinada, Combinada.Estado.ACEPTADA)
        if error:
            return error
        combinada.marcar_ganada()
        return Response(self.get_serializer(combinada).data)

    @action(detail=True, methods=["post"], url_path="marcar-perdida")
    def marcar_perdida(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado(combinada, Combinada.Estado.ACEPTADA)
        if error:
            return error
        combinada.marcar_perdida()
        return Response(self.get_serializer(combinada).data)

    @action(detail=True, methods=["post"], url_path="marcar-anulada")
    def marcar_anulada(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado(combinada, Combinada.Estado.ACEPTADA)
        if error:
            return error
        combinada.marcar_anulada()
        return Response(self.get_serializer(combinada).data)

    @action(detail=True, methods=["post"])
    def revertir(self, request, pk=None):
        combinada = self.get_object()
        error = self._requiere_estado_en(
            combinada, [Combinada.Estado.GANADA, Combinada.Estado.PERDIDA, Combinada.Estado.ANULADA]
        )
        if error:
            return error
        combinada.revertir_a_aceptada()
        return Response(self.get_serializer(combinada).data)


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
    filterset_fields = {
        "recomendacion": ["exact"],
        "mercado": ["exact"],
        "partido__fecha_hora": ["gte", "lte"],
        "partido__temporada": ["exact"],
    }

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

        for fila in resueltos:
            ocurrio = 1 if fila.prediccion_acertada else 0
            aciertos_modelo += ocurrio
            brier_modelo += (fila.probabilidad_seleccion - ocurrio) ** 2

            baseline_predice_ocurre = fila.probabilidad_implicita >= 0.5
            aciertos_baseline += int(baseline_predice_ocurre == bool(ocurrio))
            brier_baseline += (fila.probabilidad_implicita - ocurrio) ** 2

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
            }
        )

    @action(detail=False, methods=["get"], url_path="rendimiento-value-bets")
    def rendimiento_value_bets(self, request):
        """
        Rendimiento de TODAS las value bets que generó el sistema
        (recomendacion=VALUE_BET) -- las haya aceptado el usuario o no. Es
        DISTINTO de:
        - `rendimiento()` (arriba): todas las predicciones, haya o no
          recomendación -- mide si el modelo en general predice bien.
        - `OperacionViewSet.resumen()`: solo las que el usuario aceptó de
          verdad -- plata real, no teórica.
        Mezclar estos tres números fue justo la confusión que reportó el
        usuario ("no separar las estadísticas").
        """
        from django.db.models import Avg, Sum

        minimo_para_comparar = 20

        value_bets = self.get_queryset().filter(recomendacion=AnalisisPartido.Recomendacion.VALUE_BET)
        total_value_bets = value_bets.count()

        promedios = value_bets.aggregate(ev_promedio=Avg("ev"), edge_promedio=Avg("edge"))

        resueltas_qs = value_bets.filter(recomendacion_acertada__isnull=False)
        resueltas = resueltas_qs.count()

        base = {
            "total_value_bets": total_value_bets,
            "resueltas": resueltas,
            "minimo_requerido": minimo_para_comparar,
            "ev_promedio": promedios["ev_promedio"],
            "edge_promedio": promedios["edge_promedio"],
        }

        if resueltas < minimo_para_comparar:
            return Response(
                {
                    **base,
                    "datos_suficientes": False,
                    "motivo": (
                        "Todavía no hay suficientes value bets resueltas para un win rate/ROI "
                        "estadísticamente significativo."
                    ),
                }
            )

        aciertos = resueltas_qs.filter(recomendacion_acertada=True).count()
        agregados = resueltas_qs.aggregate(pnl_total=Sum("pnl_teorico"), stake_total=Sum("stake_sugerido"))
        stake_total = agregados["stake_total"] or Decimal("0")

        return Response(
            {
                **base,
                "datos_suficientes": True,
                "win_rate": aciertos / resueltas,
                "roi_teorico": float(agregados["pnl_total"] / stake_total) if stake_total else None,
                "pnl_teorico_total": agregados["pnl_total"],
                "stake_teorico_total": stake_total,
            }
        )

    @action(detail=False, methods=["get"], url_path="rendimiento-por-mercado")
    def rendimiento_por_mercado(self, request):
        """
        Igual que `rendimiento()`, pero desglosado por mercado en vez de un
        solo número mezclado -- el modelo puede estar bien calibrado en 1X2
        y mal en una línea de Over/Under (de hecho, así fue: ver prompt.md
        sección 8/10, es exactamente por qué se sacó la línea 4.5). Cada
        mercado se audita con su propio mínimo de muestra -- "GENERAL" se
        excluye porque no es un mercado real, es el registro de "no se pudo
        evaluar nada" (ver scanner.py:_registrar_no_bet_general).
        """
        from django.db.models import Sum

        minimo_para_comparar = 20

        resueltos_base = (
            self.get_queryset()
            .filter(
                prediccion_acertada__isnull=False,
                probabilidad_seleccion__isnull=False,
                probabilidad_implicita__isnull=False,
            )
            .exclude(mercado="GENERAL")
        )
        # .order_by() (sin argumentos) limpia el ordering default del modelo
        # (-fecha_analisis) -- si no, Django lo suma al SELECT DISTINCT por
        # abajo y "distinct" deja de deduplicar de verdad (cada fecha_analisis
        # sigue siendo única, así que cada mercado aparecía una vez por fila).
        mercados = resueltos_base.order_by().values_list("mercado", flat=True).distinct()

        resultados = []
        for mercado in sorted(mercados):
            resueltos = resueltos_base.filter(mercado=mercado)
            total = resueltos.count()

            if total < minimo_para_comparar:
                resultados.append(
                    {
                        "mercado": mercado,
                        "datos_suficientes": False,
                        "predicciones_resueltas": total,
                        "minimo_requerido": minimo_para_comparar,
                    }
                )
                continue

            aciertos = 0
            brier = 0.0
            for fila in resueltos:
                ocurrio = 1 if fila.prediccion_acertada else 0
                aciertos += ocurrio
                brier += (fila.probabilidad_seleccion - ocurrio) ** 2

            value_bets = resueltos.filter(
                recomendacion=AnalisisPartido.Recomendacion.VALUE_BET, pnl_teorico__isnull=False
            )
            agregados = value_bets.aggregate(pnl_total=Sum("pnl_teorico"), stake_total=Sum("stake_sugerido"))
            stake_total = agregados["stake_total"] or Decimal("0")

            resultados.append(
                {
                    "mercado": mercado,
                    "datos_suficientes": True,
                    "predicciones_resueltas": total,
                    "accuracy": aciertos / total,
                    "brier_score": round(brier / total, 4),
                    "value_bets_resueltas": value_bets.count(),
                    "roi_teorico": float(agregados["pnl_total"] / stake_total) if stake_total else None,
                }
            )

        return Response(resultados)

    @action(detail=False, methods=["get"])
    def backtest(self, request):
        """
        Última foto del backtest walk-forward guardada por `manage.py
        backtest_modelo --guardar-calibracion` (ver ResultadoBacktest) --
        correr el backtest completo tarda ~66s (recalcula ratings para cada
        partido evaluado, sin data leakage), así que este endpoint sirve la
        foto ya calculada en vez de recalcular en cada request. Con una
        muestra de ~1000 partidos históricos, esto es lo que da evidencia real
        de accuracy/calibración -- muy por encima de lo que alcanzan los
        análisis en vivo todavía (ver rendimiento(), gated a un mínimo de 20).
        """
        resultados = ResultadoBacktest.objects.all()
        if not resultados.exists():
            return Response(
                {
                    "datos_disponibles": False,
                    "motivo": (
                        "Todavía no se corrió manage.py backtest_modelo --guardar-calibracion "
                        "en este entorno."
                    ),
                }
            )

        return Response(
            {
                "datos_disponibles": True,
                "actualizado_en": max(r.actualizado_en for r in resultados),
                "mercados": [
                    {
                        "mercado": r.mercado,
                        "n": r.n,
                        "brier_score": r.brier_score,
                        "log_loss": r.log_loss,
                        "accuracy": r.accuracy,
                        "brier_score_baseline": r.brier_score_baseline,
                        "log_loss_baseline": r.log_loss_baseline,
                        "accuracy_baseline": r.accuracy_baseline,
                        "buckets": r.buckets,
                    }
                    for r in resultados
                ],
            }
        )


class ConfiguracionView(APIView):
    """
    GET: configuración actual -- riesgo (editable, ver abajo) + estado de las
    fuentes de datos/exchange (solo lectura, sin credenciales).
    PATCH: actualiza los parámetros de gestión de riesgo (bankroll de
    referencia, fracción de Kelly, stake máximo, edge mínimo). OddsScanner y
    PaperExchangeClient leen estos valores en cada escaneo (cada 30s), así
    que un cambio acá aplica sin reiniciar nada.
    """

    def get(self, request):
        return Response(self._serializar(ConfiguracionRiesgo.actual()))

    def patch(self, request):
        config = ConfiguracionRiesgo.actual()
        serializer = ConfiguracionRiesgoSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._serializar(config))

    def _serializar(self, config):
        return {
            "paper_bankroll": config.paper_bankroll,
            "kelly_fraction": config.kelly_fraction,
            "max_stake_per_bet": config.max_stake_per_bet,
            "min_edge_threshold": config.min_edge_threshold,
            "probabilidad_minima_seleccion": config.probabilidad_minima_seleccion,
            "actualizado_en": config.actualizado_en,
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


# --- Tablas de posiciones (Liga / Copa Chile / Copa de la Liga) ----------------
def _normalizar_equipo(nombre: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = s.replace("-", " ").replace(".", "").replace("'", "")
    return " ".join(s.split())


# Nombre en ESPN/Wikipedia -> nombre normalizado de Equipo en la base.
_ALIAS_EQUIPOS = {
    "audax italiano": "a italiano",
    "universidad catolica": "u catolica",
    "everton": "everton de vina",
    "everton cd": "everton de vina",
    "la serena": "d la serena",
    "deportes la serena": "d la serena",
    "deportes concepcion": "concepcion",
}


class TablasView(APIView):
    """GET: tablas de posiciones y llaves de las competiciones (ver data_ingestion/tablas.py)."""

    def get(self, request):
        from db_models.models import Equipo, TablaCompeticion

        logos = {
            _normalizar_equipo(e.nombre): e.logo_url
            for e in Equipo.objects.exclude(logo_url="").only("nombre", "logo_url")
        }

        def logo(nombre):
            n = _normalizar_equipo(nombre)
            return logos.get(_ALIAS_EQUIPOS.get(n, n), "")

        resultado = []
        for tabla in TablaCompeticion.objects.all():
            datos = tabla.datos
            for grupo in datos.get("grupos", []):
                for fila in grupo.get("filas", []):
                    fila["logo_url"] = logo(fila["equipo"])
            resultado.append(
                {
                    "slug": tabla.slug,
                    "nombre": tabla.nombre,
                    "temporada": tabla.temporada,
                    "fuente": tabla.fuente,
                    "actualizado_en": tabla.actualizado_en,
                    **datos,
                }
            )
        return Response(resultado)
