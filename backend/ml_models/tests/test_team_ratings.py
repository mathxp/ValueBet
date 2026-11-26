from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from db_models.models import Equipo, Partido
from ml_models.pipelines.team_ratings import (
    MIN_PARTIDOS_PARA_RATING,
    _historial_finalizados,
    calcular_ratings,
    factor_localia,
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
            ratings[self.fuerte.pk].ataque,
            ratings[self.debil.pk].ataque,
        )

    def test_partidos_no_finalizados_no_cuentan(self):
        Partido.objects.create(
            equipo_local=self.fuerte,
            equipo_visitante=self.medio,
            fecha_hora=timezone.now(),
            estado=Partido.Estado.PROGRAMADO,
        )
        ratings_despues = calcular_ratings()[self.fuerte.pk].partidos
        # El partido programado (sin resultado) no debería sumar al conteo.
        self.assertEqual(ratings_despues, 5)

    def test_equipo_con_pocos_partidos_no_llega_al_minimo(self):
        nuevo = Equipo.objects.create(nombre="Nuevo", api_football_id=92004)
        _crear_finalizado(nuevo, self.medio, dias_atras=1, gl=1, gv=1)
        ratings = calcular_ratings()
        self.assertLess(ratings[nuevo.pk].partidos, MIN_PARTIDOS_PARA_RATING)

    def test_shrinkage_acerca_al_promedio_de_liga_con_pocos_partidos(self):
        nuevo = Equipo.objects.create(nombre="Nuevo2", api_football_id=92005)
        # Una sola goleada -- sin shrinkage, el ataque crudo sería 5.0.
        _crear_finalizado(nuevo, self.medio, dias_atras=1, gl=5, gv=0)
        ratings = calcular_ratings()
        self.assertLess(ratings[nuevo.pk].ataque, 5.0)

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
            ratings_con_proxy[dominante.pk].ataque,
            ratings_sin_proxy[sin_proxy.pk].ataque,
        )


class ProyectarXgTests(TestCase):
    def setUp(self):
        self.a = Equipo.objects.create(nombre="Equipo A", api_football_id=93001)
        self.b = Equipo.objects.create(nombre="Equipo B", api_football_id=93002)

    def test_sin_historial_retorna_none(self):
        self.assertIsNone(proyectar_xg(self.a.pk, self.b.pk))

    def test_con_historial_retorna_proyeccion_valida(self):
        for i in range(5):
            _crear_finalizado(self.a, self.b, dias_atras=i + 1, gl=2, gv=1)
            _crear_finalizado(self.b, self.a, dias_atras=i + 6, gl=1, gv=1)

        proyeccion = proyectar_xg(self.a.pk, self.b.pk)
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

        xg_a_local, _ = proyectar_xg(self.a.pk, self.b.pk)
        _, xg_a_visita = proyectar_xg(self.b.pk, self.a.pk)
        self.assertGreater(xg_a_local, xg_a_visita)


class FactorLocaliaTests(TestCase):
    def test_favorece_al_local_cuando_los_locales_anotan_mas(self):
        local = Equipo.objects.create(nombre="FL Local", api_football_id=93011)
        visita = Equipo.objects.create(nombre="FL Visita", api_football_id=93012)
        for i in range(10):
            _crear_finalizado(local, visita, dias_atras=i + 1, gl=2, gv=1)

        factor_local, factor_visita = factor_localia()
        self.assertGreater(factor_local, 1.0)
        self.assertLess(factor_visita, 1.0)

    def test_sin_historial_retorna_neutro(self):
        self.assertEqual(factor_localia(liga="Liga Sin Partidos"), (1.0, 1.0))


class HistorialFinalizadosTests(TestCase):
    def test_no_trunca_el_historial_aunque_haya_mas_de_1000_partidos(self):
        """Bug real: esta función cortaba en los 1000 partidos finalizados más
        recientes sin avisar -- ni el propio docstring lo mencionaba (decía
        "en producción se usa todo el historial disponible"). calcular_ratings()
        no lo sufría (se autolimita por equipo con MAX_PARTIDOS_POR_EQUIPO), pero
        factor_localia() promedia sobre TODO lo que devuelva esta función, así que
        el tope le cortaba en silencio las temporadas más viejas a medida que la
        liga acumulaba historial (ver HANDOFF_dataset_contexto.md sección 2.1).
        Con más de 1000 partidos cargados, tienen que volver todos."""
        local = Equipo.objects.create(nombre="Historico Local", api_football_id=93021)
        visita = Equipo.objects.create(nombre="Historico Visita", api_football_id=93022)
        cantidad = 1005
        Partido.objects.bulk_create(
            [
                Partido(
                    equipo_local=local,
                    equipo_visitante=visita,
                    fecha_hora=timezone.now() - timedelta(days=i + 1),
                    estado=Partido.Estado.FINALIZADO,
                    resultado={"local": 1, "visitante": 0},
                )
                for i in range(cantidad)
            ]
        )

        self.assertEqual(len(_historial_finalizados()), cantidad)


class DixonColesTests(TestCase):
    def test_equipos_sin_api_football_id_no_se_mezclan(self):
        # Regresión: los ratings usaban api_football_id como clave y todos los
        # equipos sin id compartían la clave None.
        goleador = Equipo.objects.create(nombre="SinId A")
        flojo = Equipo.objects.create(nombre="SinId B")
        rival = Equipo.objects.create(nombre="Rival", api_football_id=93001)
        for i in range(6):
            _crear_finalizado(goleador, rival, dias_atras=i + 1, gl=4, gv=0)
            _crear_finalizado(flojo, rival, dias_atras=i + 1, gl=0, gv=3)
        ratings = calcular_ratings()
        self.assertGreater(ratings[goleador.pk].ataque, ratings[flojo.pk].ataque)

    def test_ganarle_a_un_rival_fuerte_vale_mas_que_a_uno_debil(self):
        fuerte = Equipo.objects.create(nombre="Fuerte DC", api_football_id=93101)
        debil = Equipo.objects.create(nombre="Debil DC", api_football_id=93102)
        a = Equipo.objects.create(nombre="A DC", api_football_id=93103)
        b = Equipo.objects.create(nombre="B DC", api_football_id=93104)
        for i in range(6):
            _crear_finalizado(fuerte, debil, dias_atras=40 + i, gl=3, gv=0)
            _crear_finalizado(debil, fuerte, dias_atras=50 + i, gl=0, gv=3)
        for i in range(4):
            _crear_finalizado(a, fuerte, dias_atras=i + 1, gl=2, gv=1)  # A le gana al fuerte
            _crear_finalizado(b, debil, dias_atras=i + 1, gl=2, gv=1)  # B le gana al débil
        xg_a, _ = proyectar_xg(a.pk, b.pk)
        xg_b, _ = proyectar_xg(b.pk, a.pk)
        self.assertGreater(xg_a, xg_b)

    def test_cache_se_invalida_si_cambia_un_resultado(self):
        local = Equipo.objects.create(nombre="Cache L", api_football_id=93201)
        visita = Equipo.objects.create(nombre="Cache V", api_football_id=93202)
        partidos = [_crear_finalizado(local, visita, dias_atras=i + 1, gl=1, gv=1) for i in range(8)]
        antes = proyectar_xg(local.pk, visita.pk)
        for p in partidos:
            p.resultado = {"local": 4, "visitante": 0}
            p.save()
        despues = proyectar_xg(local.pk, visita.pk)
        self.assertGreater(despues[0], antes[0])


class SimulacionMonteCarloTests(TestCase):
    def test_simulacion_coincide_con_el_calculo_exacto(self):
        from ml_models.predictor import probabilidades_1x2_por_poisson, simular_partido

        sim = simular_partido(1.6, 1.1, rho=-0.05, n=20000, semilla=7)
        exacto = probabilidades_1x2_por_poisson(1.6, 1.1, rho=-0.05)
        total = sim["victorias_local"] + sim["empates"] + sim["victorias_visitante"]
        self.assertEqual(total, 20000)
        self.assertAlmostEqual(sim["victorias_local"] / total, exacto["LOCAL"], delta=0.015)
        self.assertAlmostEqual(sim["empates"] / total, exacto["EMPATE"], delta=0.015)
        self.assertEqual(len(sim["marcadores_frecuentes"]), 6)

    def test_misma_semilla_mismo_resultado(self):
        from ml_models.predictor import simular_partido

        self.assertEqual(simular_partido(1.2, 1.0, semilla=3), simular_partido(1.2, 1.0, semilla=3))

    def test_rho_cero_es_poisson_independiente(self):
        from ml_models.predictor import probabilidades_1x2_por_poisson

        p = probabilidades_1x2_por_poisson(1.4, 1.2)
        self.assertAlmostEqual(sum(p.values()), 1.0, places=6)
