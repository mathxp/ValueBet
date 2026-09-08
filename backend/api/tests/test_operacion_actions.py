from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from db_models.models import Equipo, Operacion, Partido


class OperacionActionsApiTests(TestCase):
    def setUp(self):
        local = Equipo.objects.create(nombre="Local", api_football_id=96001)
        visita = Equipo.objects.create(nombre="Visita", api_football_id=96002)
        partido = Partido.objects.create(
            equipo_local=local, equipo_visitante=visita, fecha_hora=timezone.now()
        )
        self.operacion = Operacion.objects.create(
            partido=partido,
            mercado="1X2",
            seleccion="LOCAL",
            probabilidad_modelo=0.6,
            cuota_apostada=Decimal("2.00"),
            valor_esperado=0.2,
            kelly_fraccion_usada=0.25,
            stake=Decimal("100.00"),
        )

    def test_aceptar_cambia_estado(self):
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["estado"], "ACCEPTED")

    def test_aceptar_dos_veces_da_conflicto(self):
        self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        self.assertEqual(resp.status_code, 409)

    def test_marcar_ganada_sin_aceptar_antes_da_conflicto(self):
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-ganada/")
        self.assertEqual(resp.status_code, 409)

    def test_flujo_completo_aceptar_y_ganar(self):
        self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-ganada/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()["pnl"]), Decimal("100.00"))

    def test_flujo_completo_aceptar_y_perder(self):
        self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-perdida/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()["pnl"]), Decimal("-100.00"))

    def test_flujo_completo_aceptar_y_anular(self):
        self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-anulada/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["estado"], "VOID")
        self.assertEqual(Decimal(resp.json()["pnl"]), Decimal("0"))

    def test_marcar_anulada_sin_aceptar_antes_da_conflicto(self):
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-anulada/")
        self.assertEqual(resp.status_code, 409)

    def test_revertir_deshace_un_ganada_marcado_por_error(self):
        self.client.post(f"/api/operaciones/{self.operacion.id}/aceptar/")
        self.client.post(f"/api/operaciones/{self.operacion.id}/marcar-ganada/")
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/revertir/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["estado"], "ACCEPTED")
        self.assertIsNone(resp.json()["pnl"])

    def test_revertir_sobre_una_recomendada_da_conflicto(self):
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/revertir/")
        self.assertEqual(resp.status_code, 409)

    def test_descartar_una_recomendada(self):
        resp = self.client.post(f"/api/operaciones/{self.operacion.id}/descartar/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["estado"], "DISCARDED")


class OperacionFiltrosApiTests(TestCase):
    """Filtros de historial (mercado/estado/temporada) -- ver pestaña Recomendaciones."""

    def setUp(self):
        local = Equipo.objects.create(nombre="Local Filtros", api_football_id=96003)
        visita = Equipo.objects.create(nombre="Visita Filtros", api_football_id=96004)
        partido_2025 = Partido.objects.create(
            equipo_local=local, equipo_visitante=visita, fecha_hora=timezone.now(), temporada="2025"
        )
        partido_2026 = Partido.objects.create(
            equipo_local=local, equipo_visitante=visita, fecha_hora=timezone.now(), temporada="2026"
        )
        self.op_1x2_2025 = Operacion.objects.create(
            partido=partido_2025, mercado="1X2", seleccion="LOCAL", probabilidad_modelo=0.6,
            cuota_apostada=Decimal("2.00"), valor_esperado=0.2, kelly_fraccion_usada=0.25,
            stake=Decimal("100.00"), estado=Operacion.Estado.ACEPTADA,
        )
        self.op_over_2026 = Operacion.objects.create(
            partido=partido_2026, mercado="OVER_UNDER_2.5", seleccion="OVER", probabilidad_modelo=0.6,
            cuota_apostada=Decimal("2.00"), valor_esperado=0.2, kelly_fraccion_usada=0.25,
            stake=Decimal("100.00"), estado=Operacion.Estado.RECOMENDADA,
        )

    def test_filtra_por_mercado(self):
        resp = self.client.get("/api/operaciones/", {"mercado": "1X2"})
        ids = [r["id"] for r in resp.json()["results"]]
        self.assertEqual(ids, [self.op_1x2_2025.id])

    def test_filtra_por_estado(self):
        resp = self.client.get("/api/operaciones/", {"estado": "ACCEPTED"})
        ids = [r["id"] for r in resp.json()["results"]]
        self.assertEqual(ids, [self.op_1x2_2025.id])

    def test_filtra_por_temporada(self):
        resp = self.client.get("/api/operaciones/", {"partido__temporada": "2026"})
        ids = [r["id"] for r in resp.json()["results"]]
        self.assertEqual(ids, [self.op_over_2026.id])
