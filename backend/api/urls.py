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
    path("tablas/", views.TablasView.as_view(), name="tablas"),
    path("pronosticos/", views.PronosticosView.as_view(), name="pronosticos"),
    path("notificaciones/", views.NotificacionesView.as_view(), name="notificaciones"),
    path("push/", views.PushView.as_view(), name="push"),
    path("push/prueba/", views.PushPruebaView.as_view(), name="push-prueba"),
    path("contenido/", views.ContenidoView.as_view(), name="contenido"),
    path("contenido/imagen/", views.ContenidoImagenView.as_view(), name="contenido-imagen"),
    path("cron/pipeline/", views.CronPipelineView.as_view(), name="cron-pipeline"),
    path("pronosticos/historial/", views.HistorialPronosticosView.as_view(), name="pronosticos-historial"),
    path("", include(router.urls)),
]
