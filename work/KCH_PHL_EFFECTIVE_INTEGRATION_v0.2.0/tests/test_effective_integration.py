from __future__ import annotations

import sqlite3
import urllib.error
import urllib.request
from contextlib import closing

import effective_integration_cases as cases


class EffectiveIntegrationTests(cases.EffectiveIntegrationTests):
    def test_event_tampering_is_detected(self):
        self.write(self.service.register_decision, "tamper-event", cases.decision())
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE events SET payload_json='{}' WHERE sequence=1")
            connection.commit()
        self.assertEqual(self.service.verify()["gate"], "FAIL")

    def test_projection_tampering_is_detected(self):
        self.write(self.service.register_decision, "tamper-projection", cases.decision())
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE decisions SET record_json='{}' WHERE decision_id='decision-001'")
            connection.commit()
        self.assertEqual(self.service.verify()["gate"], "FAIL")


class HTTPBoundaryTests(cases.HTTPBoundaryTests):
    def test_http_rejects_unauthorized_client(self):
        request = urllib.request.Request(self.url + "/v1/projection", headers={"Authorization": "Bearer invalid"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 401)
        context.exception.close()
