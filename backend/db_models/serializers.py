from rest_framework import serializers

from .models import AnalisisPartido, Equipo, HistorialCuotas, Operacion, Partido


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
    partido = PartidoSerializer(read_only=True)
    partido_id = serializers.PrimaryKeyRelatedField(
        queryset=Partido.objects.all(), source="partido", write_only=True
    )

    class Meta:
        model = Operacion
        fields = "__all__"


class AnalisisPartidoSerializer(serializers.ModelSerializer):
    partido = PartidoSerializer(read_only=True)

    class Meta:
        model = AnalisisPartido
        fields = "__all__"
