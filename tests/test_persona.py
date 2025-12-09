import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.persona import PersonaManager

class TestPersonaManager(unittest.TestCase):
    def setUp(self):
        self.mock_config = {
            "persona_settings": {
                "selection_mode": "manual",
                "active_preset": "test_id",
                "presets": {
                    "p1": {"id": "test_id", "name": "Test Persona", "prompt": "Prompt A"},
                    "p2": {"id": "other_id", "name": "Other Persona", "prompt": "Prompt B"}
                }
            }
        }
        self.manager = PersonaManager(self.mock_config)

    def test_manual_selection(self):
        persona = self.manager.get_persona()
        self.assertEqual(persona['id'], "test_id")
        self.assertEqual(persona['name'], "Test Persona")
        self.assertEqual(persona['prompt'], "Prompt A")

    def test_random_selection(self):
        self.mock_config["persona_settings"]["selection_mode"] = "random"
        # Monkey patch random
        import random
        random.seed(42) # Should resolve consistently if choice is deterministic-ish with seed
        
        # Test multiple times to ensure we get valid keys
        seen = set()
        for _ in range(20):
             p = self.manager.get_persona()
             self.assertTrue(p['prompt'] in ["Prompt A", "Prompt B"])
             seen.add(p['name'])
        
        self.assertTrue(len(seen) > 0) # At least one

    def test_fallback(self):
        self.mock_config["persona_settings"]["active_preset"] = "missing_id"
        self.mock_config["persona_settings"]["presets"] = {
             "preset_1": {"id": "default", "name": "Default", "prompt": "Default Prompt"}
        }
        persona = self.manager.get_persona()
        self.assertEqual(persona['prompt'], "Default Prompt")

if __name__ == '__main__':
    unittest.main()
