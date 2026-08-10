from __future__ import annotations

import unittest

from kwancode_harness.mcp_server import TOOLS


class MCPSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = {tool["name"]: tool for tool in TOOLS}

    def field_type(self, control_id: str, field: str) -> str:
        return self.tools[f"kch.control.{control_id}"]["inputSchema"]["properties"][field]["type"]

    def test_r05_deliverables_is_array(self):
        self.assertEqual(self.field_type("R05", "deliverables"), "array")

    def test_r05_cost_receipt_is_object(self):
        self.assertEqual(self.field_type("R05", "cost_receipt"), "object")

    def test_r16_genealogy_is_array(self):
        self.assertEqual(self.field_type("R16", "genealogy"), "array")


if __name__ == "__main__":
    unittest.main()
