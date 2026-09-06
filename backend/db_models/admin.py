from django import forms
from django.contrib import admin

from .models import Equipo, HistorialCuotas, Operacion, Partido


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "pais", "liga", "api_football_id")
    search_fields = ("nombre", "liga")


class PartidoAdminForm(forms.ModelForm):
    """
    Agrega dos campos para cargar a mano el xG investigado con Claude/Gemini
    (chat, no API) sin tener que editar el JSON de metricas_avanzadas a mano.
    Un valor cargado acá queda marcado como "manual" y project_xg_for_upcoming_matches
    (ml_models/tasks.py) nunca lo pisa con el proxy estadístico automático.
    """

    xg_local_manual = forms.FloatField(
        required=False,
        label="xG local (investigación manual)",
        help_text="Pegá acá el xG que te haya estimado Claude/Gemini para el equipo local.",
    )
    xg_visitante_manual = forms.FloatField(
        required=False,
        label="xG visitante (investigación manual)",
        help_text="Ídem para el equipo visitante.",
    )

    class Meta:
        model = Partido
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["xg_local_manual"].initial = self.instance.metricas_avanzadas.get("xg_local")
            self.fields["xg_visitante_manual"].initial = self.instance.metricas_avanzadas.get(
                "xg_visitante"
            )

    def save(self, commit=True):
        partido = super().save(commit=False)
        metricas = dict(partido.metricas_avanzadas)
        xg_local = self.cleaned_data.get("xg_local_manual")
        xg_visitante = self.cleaned_data.get("xg_visitante_manual")

        if xg_local is not None and xg_visitante is not None:
            metricas["xg_local"] = xg_local
            metricas["xg_visitante"] = xg_visitante
            metricas["xg_fuente"] = "manual"

        partido.metricas_avanzadas = metricas
        if commit:
            partido.save()
        return partido


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    form = PartidoAdminForm
    list_display = ("equipo_local", "equipo_visitante", "fecha_hora", "estado", "xg_proyectado")
    list_filter = ("estado", "liga")
    search_fields = ("equipo_local__nombre", "equipo_visitante__nombre")
    fields = (
        "equipo_local",
        "equipo_visitante",
        "liga",
        "temporada",
        "fecha_hora",
        "estado",
        "api_football_id",
        "resultado",
        "xg_local_manual",
        "xg_visitante_manual",
        "metricas_avanzadas",
    )

    @admin.display(description="xG proyectado")
    def xg_proyectado(self, obj):
        xg_local = obj.metricas_avanzadas.get("xg_local")
        xg_visitante = obj.metricas_avanzadas.get("xg_visitante")
        if xg_local is None:
            return "—"
        fuente = obj.metricas_avanzadas.get("xg_fuente", "?")
        return f"{xg_local} – {xg_visitante} ({fuente})"


@admin.register(HistorialCuotas)
class HistorialCuotasAdmin(admin.ModelAdmin):
    list_display = ("partido", "origen", "mercado", "seleccion", "cuota_back", "capturado_en")
    list_filter = ("origen", "mercado")


@admin.register(Operacion)
class OperacionAdmin(admin.ModelAdmin):
    """
    El flujo esperado: una recomendación nace en RECOMENDADA (la generó el
    escaneo automático). Vos decidís -- acá con las acciones de abajo -- si
    la aceptaste (la apostaste en tu casa/exchange) o la descartaste; y una
    vez jugado el partido, la marcás Ganada/Perdida para llevar el PNL real.
    """

    list_display = (
        "partido",
        "mercado",
        "seleccion",
        "cuota_apostada",
        "valor_esperado",
        "stake",
        "estado",
        "pnl",
        "creado_en",
    )
    list_filter = ("estado", "mercado")
    actions = ["marcar_aceptada", "marcar_descartada", "marcar_ganada", "marcar_perdida"]

    @admin.action(description="Marcar como aceptada (la aposté)")
    def marcar_aceptada(self, request, queryset):
        actualizadas = queryset.filter(estado=Operacion.Estado.RECOMENDADA).update(
            estado=Operacion.Estado.ACEPTADA
        )
        self.message_user(request, f"{actualizadas} recomendación(es) marcada(s) como aceptada(s).")

    @admin.action(description="Marcar como descartada (no la tomé)")
    def marcar_descartada(self, request, queryset):
        actualizadas = queryset.filter(estado=Operacion.Estado.RECOMENDADA).update(
            estado=Operacion.Estado.DESCARTADA
        )
        self.message_user(request, f"{actualizadas} recomendación(es) marcada(s) como descartada(s).")

    @admin.action(description="Marcar como ganada (calcula el PNL)")
    def marcar_ganada(self, request, queryset):
        actualizadas = 0
        for operacion in queryset.filter(estado=Operacion.Estado.ACEPTADA):
            operacion.marcar_ganada()
            actualizadas += 1
        self.message_user(request, f"{actualizadas} recomendación(es) marcada(s) como ganada(s).")

    @admin.action(description="Marcar como perdida (calcula el PNL)")
    def marcar_perdida(self, request, queryset):
        actualizadas = 0
        for operacion in queryset.filter(estado=Operacion.Estado.ACEPTADA):
            operacion.marcar_perdida()
            actualizadas += 1
        self.message_user(request, f"{actualizadas} recomendación(es) marcada(s) como perdida(s).")
