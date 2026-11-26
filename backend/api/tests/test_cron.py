import threading
from unittest import mock

from django.test import TestCase, override_settings


class CronPipelineTests(TestCase):
    @override_settings(PROXY_SECRET="s3cret", PROXY_SECRET_REQUIRED=True)
    def test_exige_secreto(self):
        resp = self.client.get("/api/cron/pipeline/")
        self.assertEqual(resp.status_code, 403)

    @override_settings(PROXY_SECRET="s3cret", PROXY_SECRET_REQUIRED=True)
    def test_dispara_el_pipeline_en_segundo_plano(self):
        terminado = threading.Event()

        def falso_pipeline(*args, **kwargs):
            terminado.set()

        with mock.patch("django.core.management.call_command", side_effect=falso_pipeline) as cmd, mock.patch(
            "django.db.connection.close"
        ):
            resp = self.client.get("/api/cron/pipeline/", HTTP_X_PROXY_SECRET="s3cret")
            self.assertEqual(resp.status_code, 202)
            self.assertTrue(terminado.wait(5))
        cmd.assert_called_once_with("run_pipeline_once")
