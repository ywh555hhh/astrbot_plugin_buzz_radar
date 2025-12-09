import random
import logging
from typing import Dict, Any

logger = logging.getLogger("astrbot")

class PersonaManager:
    def __init__(self, config: dict):
        self.config = config
        self.default_prompt = "你是一个群聊话题总结助手。{{context}}"
        
    def _get_settings(self) -> dict:
        return self.config.get("persona_settings", {})

    def get_persona(self) -> Dict[str, str]:
        """
        Select a persona based on configuration (Manual vs Random).
        Returns dict with 'id', 'name', 'prompt'.
        """
        settings = self._get_settings()
        mode = settings.get("selection_mode", "manual")
        presets = settings.get("presets", {})
        
        selected_key = None
        
        if mode == "random":
            # Filter out empty presets
            valid_keys = [k for k, v in presets.items() if v.get("prompt")]
            if valid_keys:
                selected_key = random.choice(valid_keys)
        else:
            # Manual mode: find preset by ID match or directly by key??
            # Schema uses "active_preset" which stores the ID (e.g. "gossip").
            # But presets are keyed by "preset_1", "preset_2"... 
            # We need to find which preset slot has that ID.
            target_id = settings.get("active_preset", "gossip")
            for k, v in presets.items():
                if v.get("id") == target_id:
                    selected_key = k
                    break
        
        # Fallback to preset_1 if not found
        if not selected_key:
             selected_key = "preset_1"
        
        preset_data = presets.get(selected_key, {})
        
        return {
            "id": preset_data.get("id", "default"),
            "name": preset_data.get("name", "Default"),
            "prompt": preset_data.get("prompt", self.default_prompt)
        }
