from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"equipos", views.EquipoViewSet)
router.register(r"partidos", views.PartidoViewSet)
router.register(r"historial-cuotas", views.HistorialCuotasViewSet)
router.register(r"operaciones", views.OperacionViewSet)
router.register(r"analisis", views.AnalisisPartidoViewSet)
router.register(r"combinadas", views.CombinadaViewSet)

urlpatterns = [
    path("config/", views.ConfiguracionView.as_view(), name="configuracion"),
    path("", include(router.urls)),
]
