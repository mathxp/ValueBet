from decimal import Decimal

from django.db import models


class Equipo(models.Model):
    """Un equipo de fútbol."""

    nombre = models.CharField(max_length=150)
    pais = models.CharField(max_length=100, blank=True)
    liga = models.CharField(max_length=150, blank=True)
    api_football_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    logo_url = models.URLField(blank=True)
    # Métricas variables por temporada: xG promedio, forma reciente, etc.
    metadata = models.JSONField(default=dict, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Partido(models.Model):
    """Un partido entre dos equipos, con sus métricas avanzadas."""

    class Estado(models.TextChoices):
        PROGRAMADO = "SCHEDULED", "Programado"
        EN_VIVO = "LIVE", "En vivo"
        FINALIZADO = "FINISHED", "Finalizado"
        POSPUESTO = "POSTPONED", "Pospuesto"
        CANCELADO = "CANCELLED", "Cancelado"

    equipo_local = models.ForeignKey(
        Equipo, on_delete=models.PROTECT, related_name="partidos_local"
    )
    equipo_visitante = models.ForeignKey(
        Equipo, on_delete=models.PROTECT, related_name="partidos_visitante"
    )
    liga = models.CharField(max_length=150, blank=True)
    temporada = models.CharField(max_length=20, blank=True)
    fecha_hora = models.DateTimeField()
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PROGRAMADO
    )
    api_football_id = models.PositiveIntegerField(unique=True, null=True, blank=True)

    # Resultado final: {"local": 2, "visitante": 1, "goles_1t": {...}, ...}
    resultado = models.JSONField(default=dict, blank=True)

    # El "edge" real: xG, lesiones, clima, minutos jugados en la semana, etc.
    # Ej: {"xg_local": 1.8, "xg_visitante": 0.9, "clima": "lluvia",
    #      "bajas_local": [...], "carga_fisica_visitante_dias": 3}
    metricas_avanzadas = models.JSONField(default=dict, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_hora"]
        indexes = [models.Index(fields=["fecha_hora", "estado"])]

    def __str__(self):
        return f"{self.equipo_local} vs {self.equipo_visitante} ({self.fecha_hora:%Y-%m-%d})"


class HistorialCuotas(models.Model):
    """Snapshot de una cuota de mercado en un instante dado (para backtesting y detección de valor)."""

    partido = models.ForeignKey(
        Partido, on_delete=models.CASCADE, related_name="historial_cuotas"
    )
    origen = models.CharField(
        max_length=100, help_text="Ej: Betfair, Pinnacle, api-football"
    )
    mercado = models.CharField(max_length=100, help_text="Ej: 1X2, OVER_UNDER_2.5")
    seleccion = models.CharField(max_length=100, help_text="Ej: LOCAL, EMPATE, OVER")

    cuota_back = models.DecimalField(max_digits=7, decimal_places=3)
    cuota_lay = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    volumen_disponible = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    capturado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-capturado_en"]
        indexes = [models.Index(fields=["partido", "mercado", "seleccion"])]

    def __str__(self):
        return f"{self.partido_id} | {self.mercado}/{self.seleccion} @ {self.cuota_back}"


class Operacion(models.Model):
    """
    Una recomendación de apuesta de valor detectada por el sistema.

    El sistema NO ejecuta nada por vos -- es una herramienta de apoyo a la
    decisión, no un bot autónomo. Cada fila nace en RECOMENDADA (el sistema
    encontró un edge y sugiere un stake vía Kelly); vos decidís si la tomás
    (ACEPTADA) o no (DESCARTADA), y una vez jugado el partido la marcás
    GANADA/PERDIDA para llevar el registro de resultados reales.
    """

    class Estado(models.TextChoices):
        RECOMENDADA = "RECOMMENDED", "Recomendada"
        ACEPTADA = "ACCEPTED", "Aceptada"
        DESCARTADA = "DISCARDED", "Descartada"
        GANADA = "WON", "Ganada"
        PERDIDA = "LOST", "Perdida"
        ANULADA = "VOID", "Anulada"

    partido = models.ForeignKey(
        Partido, on_delete=models.PROTECT, related_name="operaciones"
    )
    mercado = models.CharField(max_length=100)
    seleccion = models.CharField(max_length=100)

    probabilidad_modelo = models.FloatField(
        help_text="Probabilidad estimada por el modelo de ML (0-1)"
    )
    cuota_apostada = models.DecimalField(
        max_digits=7, decimal_places=3, help_text="Cuota de mercado vista al momento del escaneo"
    )
    valor_esperado = models.FloatField(
        help_text=(
            "EV (valor esperado) por unidad apostada: (prob_modelo * cuota) - 1. "
            "No confundir con el edge (diferencia en puntos de probabilidad, ver "
            "OperacionSerializer.edge) -- son dos números distintos con distinta unidad."
        )
    )

    kelly_fraccion_usada = models.FloatField(
        help_text="Fracción de Kelly aplicada, ej. 0.25 para quarter-Kelly"
    )
    stake = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Stake sugerido por Kelly fraccional"
    )

    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.RECOMENDADA
    )
    pnl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Se completa a mano una vez que aceptás la recomendación y el partido termina",
    )

    exchange_bet_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID de la apuesta en el exchange, solo si en el futuro se ejecuta automáticamente",
    )
    metadata = models.JSONField(default=dict, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.partido_id} | {self.mercado}/{self.seleccion} | stake={self.stake}"

    def aceptar(self):
        self.estado = self.Estado.ACEPTADA
        self.save(update_fields=["estado", "actualizado_en"])

    def descartar(self):
        self.estado = self.Estado.DESCARTADA
        self.save(update_fields=["estado", "actualizado_en"])

    def marcar_ganada(self):
        self.pnl = self.stake * (self.cuota_apostada - 1)
        self.estado = self.Estado.GANADA
        self.save(update_fields=["pnl", "estado", "actualizado_en"])

    def marcar_perdida(self):
        self.pnl = -self.stake
        self.estado = self.Estado.PERDIDA
        self.save(update_fields=["pnl", "estado", "actualizado_en"])

    def marcar_anulada(self):
        """
        NULA/PUSH: se devuelve el stake exacto, sin ganancia ni pérdida.
        Aplica cuando el mercado queda sin efecto (ej. partido suspendido
        después de aceptar la recomendación, o un mercado tipo "hándicap
        asiático"/"empate no acción" que la casa/exchange anula).
        """
        self.pnl = Decimal("0")
        self.estado = self.Estado.ANULADA
        self.save(update_fields=["pnl", "estado", "actualizado_en"])


class AnalisisPartido(models.Model):
    """
    Historial de CADA análisis que hace el escáner, exista o no una
    recomendación -- a diferencia de Operacion (que solo nace cuando hay
    valor real), esto incluye también los "NO BET" explícitos. El objetivo es
    poder responder objetivamente "¿qué tan bueno es el modelo?" con datos
    propios, no solo mirar las apuestas que se terminaron sugiriendo.

    Un mismo (partido, mercado) puede tener varias filas a lo largo del
    tiempo si la cuota de mercado se mueve entre un escaneo y otro -- eso es
    intencional: permite reconstruir el historial de cuotas visto por el
    sistema y calcular CLV (closing line value) más adelante.
    """

    class Recomendacion(models.TextChoices):
        VALUE_BET = "VALUE_BET", "Value bet"
        NO_BET = "NO_BET", "No bet"
        # Distinto de un NO_BET común (edge insuficiente): acá SÍ había edge
        # aparente, pero se bloqueó por una razón estructural -- edge
        # estadísticamente inverosímil, o el mercado todavía no tiene curva
        # de calibración medida contra resultados reales (ver
        # trading_engine/scanner.py). Separarlo de NO_BET evita que se lea
        # como "no hay nada interesante acá" cuando en realidad es "hay algo
        # que mirar, pero no se puede confiar en el número todavía".
        ANOMALIA = "ANOMALIA", "Anomalía detectada"

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name="analisis")
    mercado = models.CharField(
        max_length=50,
        help_text='Mercado específico analizado: "1X2", "OVER_UNDER_2.5", o "GENERAL" si no hubo cuotas que evaluar',
    )
    seleccion_evaluada = models.CharField(
        max_length=20, blank=True, help_text="La selección de mejor edge dentro de esa familia (si la hubo)"
    )

    xg_local = models.FloatField(null=True, blank=True)
    xg_visitante = models.FloatField(null=True, blank=True)
    probabilidad_local = models.FloatField(null=True, blank=True)
    probabilidad_empate = models.FloatField(null=True, blank=True)
    probabilidad_visitante = models.FloatField(null=True, blank=True)
    probabilidad_seleccion = models.FloatField(
        null=True, blank=True, help_text="Probabilidad del modelo para seleccion_evaluada específicamente"
    )

    cuota_mercado = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    cuota_justa = models.DecimalField(
        max_digits=7, decimal_places=3, null=True, blank=True, help_text="1 / probabilidad_seleccion"
    )
    probabilidad_implicita = models.FloatField(null=True, blank=True, help_text="1 / cuota_mercado")
    edge = models.FloatField(
        null=True, blank=True,
        help_text="Diferencia en puntos de probabilidad: probabilidad_seleccion - probabilidad_implicita",
    )
    ev = models.FloatField(
        null=True, blank=True,
        help_text="Valor esperado por unidad apostada: probabilidad_seleccion * cuota_mercado - 1",
    )

    data_quality_score = models.PositiveSmallIntegerField(default=0)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    value_score = models.PositiveSmallIntegerField(default=0)

    recomendacion = models.CharField(max_length=10, choices=Recomendacion.choices)
    motivo_no_bet = models.CharField(max_length=200, blank=True)

    kelly_fraccion_usada = models.FloatField(null=True, blank=True)
    stake_sugerido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    modelo_utilizado = models.CharField(max_length=50, default="poisson_ratings_v1")
    fecha_analisis = models.DateTimeField(auto_now_add=True)

    # Se completan cuando el partido termina -- ver AnalisisPartido.reconciliar()
    # y ml_models.tasks.reconciliar_analisis (tarea periódica).
    prediccion_acertada = models.BooleanField(
        null=True, blank=True, help_text="¿La dirección implícita en probabilidad_seleccion ocurrió?"
    )
    recomendacion_acertada = models.BooleanField(
        null=True, blank=True, help_text="Solo aplica si recomendacion=VALUE_BET"
    )
    pnl_teorico = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="PNL si se hubiera apostado stake_sugerido -- independiente de si el usuario la aceptó de verdad",
    )
    cuota_cierre = models.DecimalField(
        max_digits=7, decimal_places=3, null=True, blank=True,
        help_text="Última cuota vista antes del inicio del partido, para calcular CLV",
    )
    clv = models.FloatField(
        null=True, blank=True,
        help_text="Closing Line Value: (cuota_mercado / cuota_cierre) - 1. Positivo = se apostó a mejor precio que el de cierre.",
    )
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_analisis"]
        indexes = [models.Index(fields=["partido", "mercado"])]

    def __str__(self):
        return f"{self.partido_id} | {self.mercado} | {self.recomendacion}"

    def reconciliar(self):
        """
        Completa el resultado real una vez que el partido terminó. Se llama
        desde la tarea periódica reconciliar_analisis -- ver ml_models/tasks.py.
        """
        from django.utils import timezone

        from db_models.models import HistorialCuotas

        partido = self.partido
        goles_local = partido.resultado.get("local")
        goles_visitante = partido.resultado.get("visitante")

        if goles_local is not None and goles_visitante is not None and self.seleccion_evaluada:
            if self.mercado == "1X2":
                if goles_local > goles_visitante:
                    resultado_real = "LOCAL"
                elif goles_local == goles_visitante:
                    resultado_real = "EMPATE"
                else:
                    resultado_real = "VISITANTE"
                self.prediccion_acertada = self.seleccion_evaluada == resultado_real
            elif self.mercado.startswith("OVER_UNDER_"):
                linea = float(self.mercado.removeprefix("OVER_UNDER_"))
                total_real = goles_local + goles_visitante
                resultado_real = "OVER" if total_real > linea else "UNDER"
                self.prediccion_acertada = self.seleccion_evaluada == resultado_real

            if self.recomendacion == self.Recomendacion.VALUE_BET:
                self.recomendacion_acertada = self.prediccion_acertada
                if self.stake_sugerido and self.cuota_mercado:
                    if self.recomendacion_acertada:
                        self.pnl_teorico = self.stake_sugerido * (self.cuota_mercado - 1)
                    else:
                        self.pnl_teorico = -self.stake_sugerido

        # Cuota de cierre y CLV: la última cuota capturada antes del inicio del partido.
        cierre = (
            HistorialCuotas.objects.filter(
                partido=partido,
                mercado=self.mercado,
                seleccion=self.seleccion_evaluada,
                capturado_en__lte=partido.fecha_hora,
            )
            .order_by("-capturado_en")
            .first()
        )
        if cierre and self.cuota_mercado:
            self.cuota_cierre = cierre.cuota_back
            if self.cuota_cierre:
                self.clv = float(self.cuota_mercado / self.cuota_cierre) - 1

        self.resuelto_en = timezone.now()
        self.save()


class ConfiguracionRiesgo(models.Model):
    """
    Parámetros de gestión de riesgo, editables desde el dashboard (pestaña
    Configuración) sin tener que tocar backend/.env ni reiniciar ningún
    proceso -- OddsScanner y PaperExchangeClient leen esta fila en cada
    escaneo. Singleton: siempre existe una única fila (pk=1);
    ConfiguracionRiesgo.actual() la crea con los valores de settings.py
    (o sea, los de backend/.env) la primera vez que se pide.
    """

    paper_bankroll = models.DecimalField(max_digits=12, decimal_places=2)
    kelly_fraction = models.FloatField()
    max_stake_per_bet = models.DecimalField(max_digits=10, decimal_places=2)
    min_edge_threshold = models.FloatField()

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de riesgo"
        verbose_name_plural = "Configuración de riesgo"

    def __str__(self):
        return "Configuración de riesgo"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def actual(cls) -> "ConfiguracionRiesgo":
        from django.conf import settings

        instancia, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "paper_bankroll": settings.PAPER_BANKROLL,
                "kelly_fraction": settings.KELLY_FRACTION,
                "max_stake_per_bet": settings.MAX_STAKE_PER_BET,
                "min_edge_threshold": settings.MIN_EDGE_THRESHOLD,
            },
        )
        return instancia


class CalibracionMercado(models.Model):
    """
    Curva de calibración por mercado: puntos (probabilidad predicha por el
    modelo, frecuencia real medida) obtenidos con backtesting walk-forward
    sobre el historial real, sin data leakage -- ver
    ml_models/management/commands/backtest_modelo.py (--guardar-calibracion)
    y ml_models/pipelines/calibracion.py.

    ml_models.predictor.MatchPredictor la usa para corregir la probabilidad
    cruda del modelo de Poisson antes de que el escáner calcule edge/EV --
    ej. si el historial real muestra que "40-60% predicho" en realidad
    ocurrió solo 32% de las veces, una nueva predicción de 50% para ese
    mercado se ajusta hacia abajo en esa misma proporción medida, en vez de
    usarse tal cual. Si no hay fila para un mercado, no se ajusta nada --
    nunca se inventa una corrección sin evidencia real detrás.
    """

    mercado = models.CharField(max_length=50, unique=True)
    puntos = models.JSONField(
        help_text="Lista de [probabilidad_predicha, frecuencia_real], un punto por bucket con muestra suficiente."
    )
    n_total = models.PositiveIntegerField(help_text="Cantidad total de casos históricos usados para esta curva.")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibración de mercado"
        verbose_name_plural = "Calibraciones de mercado"

    def __str__(self):
        return f"Calibración {self.mercado} (n={self.n_total})"
