from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from db_models.models import Equipo, Partido
from ml_models.pipelines.team_ratings import (
    MIN_PARTIDOS_PARA_RATING,
    calcular_ratings,
    proyectar_xg,
)


def _crear_finalizado(local, visitante, dias_atras, gl, gv, proxy_xg=None):
    metricas = {"proxy_xg": proxy_xg} if proxy_xg else {}
    return Partido.objects.create(
        equipo_local=local,
        equipo_visitante=visitante,
        fecha_hora=timezone.now() - timedelta(days=dias_atras),
        estado=Partido.Estado.FINALIZADO,
        resultado={"local": gl, "visitante": gv},
        metricas_avanzadas=metricas,
    )


class CalcularRatingsTests(TestCase):
    def setUp(self):
        self.fuerte = Equipo.objects.create(nombre="Fuerte", api_football_id=92001)
        self.debil = Equipo.objects.create(nombre="Debil", api_football_id=92002)
        self.medio = Equipo.objects.create(nombre="Medio", api_football_id=92003)
        for i in range(5):
            _crear_finalizado(self.fuerte, self.medio, dias_atras=i + 1, gl=3, gv=1)
            _crear_finalizado(self.debil, self.medio, dias_atras=i + 1, gl=0, gv=2)

    def test_equipo_fuerte_tiene_mejor_ataque_que_el_debil(self):
        ratings = calcular_ratings()
        self.assertGreater(
            ratings[self.fuerte.api_football_id].ataque,
            ratings[self.debil.api_football_id].ataque,
        )

    def test_partidos_no_finalizados_no_cuentan(self):
        Partido.objects.create(
            equipo_local=self.fuerte,
            equipo_visitante=self.medio,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.PROGRAMADO,
        )
        ratings_despues = calcular_ratings()[self.fuerte.api_football_id].partidos
        # El partido programado (sin resultado) no debería sumar al conteo.
        self.assertEqual(ratings_despues, 5)

    def test_equipo_con_pocos_partidos_no_llega_al_minimo(self):
        nuevo = Equipo.objects.create(nombre="Nuevo", api_football_id=92004)
        _crear_finalizado(nuevo, self.medio, dias_atras=1, gl=1, gv=1)
        ratings = calcular_ratings()
        self.assertLess(ratings[nuevo.api_football_id].partidos, MIN_PARTIDOS_PARA_RATING)

    def test_shrinkage_acerca_al_promedio_de_liga_con_pocos_partidos(self):
        nuevo = Equipo.objects.create(nombre="Nuevo2", api_football_id=92005)
        # Una sola goleada -- sin shrinkage, el ataque crudo sería 5.0.
        _crear_finalizado(nuevo, self.medio, dias_atras=1, gl=5, gv=0)
        ratings = calcular_ratings()
        self.assertLess(ratings[nuevo.api_football_id].ataque, 5.0)

    def test_proxy_xg_atenua_un_resultado_perdido_por_varianza(self):
        """Un equipo que domina por xG pero pierde 0-1 no debería registrar
        el mismo ataque "real" (0) que un equipo que de verdad no generó
        nada -- el proxy de xG (cuando está disponible) mezcla la señal."""
        dominante = Equipo.objects.create(nombre="Dominante", api_football_id=92006)
        rival = Equipo.objects.create(nombre="Rival", api_football_id=92007)
        for i in range(5):
            _crear_finalizado(
                dominante, rival, dias_atras=i + 1, gl=0, gv=1,
                proxy_xg={"92006": 2.4, "92007": 0.3},
            )
        ratings_con_proxy = calcular_ratings()

        sin_proxy = Equipo.objects.create(nombre="SinProxy", api_football_id=92008)
        for i in range(5):
            _crear_finalizado(sin_proxy, rival, dias_atras=i + 1, gl=0, gv=1)
        ratings_sin_proxy = calcular_ratings()

        self.assertGreater(
            ratings_con_proxy[dominante.api_football_id].ataque,
            ratings_sin_proxy[sin_proxy.api_football_id].ataque,
        )


class ProyectarXgTests(TestCase):
    def setUp(self):
        self.a = Equipo.objects.create(nombre="Equipo A", api_football_id=93001)
        self.b = Equipo.objects.create(nombre="Equipo B", api_football_id=93002)

    def test_sin_historial_retorna_none(self):
        self.assertIsNone(proyectar_xg(self.a.api_football_id, self.b.api_football_id))

    def test_con_historial_retorna_proyeccion_valida(self):
        for i in range(5):
            _crear_finalizado(self.a, self.b, dias_atras=i + 1, gl=2, gv=1)
            _crear_finalizado(self.b, self.a, dias_atras=i + 6, gl=1, gv=1)

        proyeccion = proyectar_xg(self.a.api_football_id, self.b.api_football_id)
        self.assertIsNotNone(proyeccion)
        xg_local, xg_visitante = proyeccion
        self.assertGreater(xg_local, 0)
        self.assertGreater(xg_visitante, 0)

    def test_jugar_de_local_aumenta_la_proyeccion_del_mismo_equipo(self):
        """Valida la ventaja de localía: el mismo equipo debería proyectar más
        goles jugando de local que de visita contra el mismo rival. Para que
        factor_localia() (que mide la ventaja global, no por equipo) detecte
        algo, los datos fabricados necesitan una asimetría real entre local y
        visita -- acá el local siempre anota más que el visitante, sea quien sea."""
        for i in range(10):
            _crear_finalizado(self.a, self.b, dias_atras=i + 1, gl=3, gv=1)
            _crear_finalizado(self.b, self.a, dias_atras=i + 11, gl=2, gv=1)

        xg_a_local, _ = proyectar_xg(self.a.api_football_id, self.b.api_football_id)
        _, xg_a_visita = proyectar_xg(self.b.api_football_id, self.a.api_football_id)
        self.assertGreater(xg_a_local, xg_a_visita)
