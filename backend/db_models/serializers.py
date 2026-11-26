from rest_framework import serializers

from .models import AnalisisPartido, Combinada, ConfiguracionRiesgo, Equipo, HistorialCuotas, Operacion, Partido


class EquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipo
        fields = "__all__"


class PartidoSerializer(serializers.ModelSerializer):
    equipo_local = EquipoSerializer(read_only=True)
    equipo_visitante = EquipoSerializer(read_only=True)
    equipo_local_id = serializers.PrimaryKeyRelatedField(
        queryset=Equipo.objects.all(), source="equipo_local", write_only=True
    )
    equipo_visitante_id = serializers.PrimaryKeyRelatedField(
        queryset=Equipo.objects.all(), source="equipo_visitante", write_only=True
    )

    class Meta:
        model = Partido
        fields = "__all__"


class HistorialCuotasSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorialCuotas
        fields = "__all__"


class OperacionSerializer(serializers.ModelSerializer):
    """
    `valor_esperado` (campo del modelo) es el EV proporcional: (prob*cuota)-1.
    `edge` acá es un campo DISTINTO, calculado al vuelo (no vive en la base
    porque se deriva de dos campos que ya están guardados) -- la diferencia
    en puntos de probabilidad entre el modelo y el mercado, que es lo que
    AnalisisPartido ya mostraba por separado. No son la misma unidad: EV es
    proporcional (>0 no tiene techo natural), edge son puntos porcentuales
    (-100 a +100 pp) -- mezclarlos fue la confusión que reportó el usuario.
    """

    partido = PartidoSerializer(read_only=True)
    partido_id = serializers.PrimaryKeyRelatedField(
        queryset=Partido.objects.all(), source="partido", write_only=True
    )
    probabilidad_implicita = serializers.SerializerMethodField()
    edge = serializers.SerializerMethodField()

    class Meta:
        model = Operacion
        fields = "__all__"

    def get_probabilidad_implicita(self, obj):
        return (1 / float(obj.cuota_apostada)) if obj.cuota_apostada else None

    def get_edge(self, obj):
        implicita = self.get_probabilidad_implicita(obj)
        return (obj.probabilidad_modelo - implicita) if implicita is not None else None


class AnalisisPartidoSerializer(serializers.ModelSerializer):
    partido = PartidoSerializer(read_only=True)

    class Meta:
        model = AnalisisPartido
        fields = "__all__"


class CombinadaSerializer(serializers.ModelSerializer):
    patas = AnalisisPartidoSerializer(many=True, read_only=True)

    class Meta:
        model = Combinada
        fields = "__all__"


class ConfiguracionRiesgoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionRiesgo
        fields = [
            "paper_bankroll",
            "kelly_fraction",
            "max_stake_per_bet",
            "min_edge_threshold",
            "probabilidad_minima_seleccion",
            "actualizado_en",
        ]
        read_only_fields = ["actualizado_en"]

    def validate_paper_bankroll(self, value):
        if value <= 0:
            raise serializers.ValidationError("El bankroll debe ser mayor a 0.")
        return value

    def validate_kelly_fraction(self, value):
        if not (0 < value <= 1):
            raise serializers.ValidationError("La fracción de Kelly debe estar entre 0 (exclusivo) y 1.")
        return value

    def validate_max_stake_per_bet(self, value):
        if value <= 0:
            raise serializers.ValidationError("El stake máximo debe ser mayor a 0.")
        return value

    def validate_min_edge_threshold(self, value):
        if not (0 <= value < 1):
            raise serializers.ValidationError("El edge mínimo debe estar entre 0 (inclusive) y 1.")
        return value

    def validate_probabilidad_minima_seleccion(self, value):
        if not (0 <= value < 1):
            raise serializers.ValidationError("La probabilidad mínima debe estar entre 0 (inclusive) y 1.")
        return value
