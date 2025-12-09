import json
import time
import asyncio
import os
import sys
import logging
import contextlib
import unittest
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MOCK ASTRBOT START ---
class MockFilter:
    def event_message_type(self, *args, **kwargs):
        def decorator(func): return func
        return decorator
    def command_group(self, name):
        class MockGroup:
            def command(self, subname):
                def decorator(func): return func
                return decorator
            def __call__(self, func): return self
        return MockGroup()
    class EventMessageType: GROUP_MESSAGE = "GROUP_MESSAGE"

class MockStar:
     def __init__(self, context): self.context = context
def mock_register(*args, **kwargs):
    def decorator(cls): return cls
    return decorator

mock_astrbot = MagicMock()
mock_astrbot.api.event.filter = MockFilter()
mock_astrbot.api.event.AstrMessageEvent = MagicMock()
mock_astrbot.api.event.MessageEventResult = MagicMock()
mock_astrbot.api.star.Context = MagicMock()
mock_astrbot.api.star.Star = MockStar
mock_astrbot.api.star.register = mock_register
mock_astrbot.api.logger = MagicMock()
mock_astrbot.core.config.astrbot_config.AstrBotConfig = dict

sys.modules['astrbot'] = mock_astrbot
sys.modules['astrbot.api'] = mock_astrbot.api
sys.modules['astrbot.api.event'] = mock_astrbot.api.event
sys.modules['astrbot.api.star'] = mock_astrbot.api.star
sys.modules['astrbot.core'] = mock_astrbot.core
sys.modules['astrbot.core.config'] = mock_astrbot.core.config
sys.modules['astrbot.core.config.astrbot_config'] = mock_astrbot.core.config.astrbot_config
# --- MOCK ASTRBOT END ---

from tests.mock_event import MockEvent, MockContext
from main import BuzzRadarPlugin

class ScenarioRunner:
    def __init__(self):
        self.context = MockContext()
        self.config = self._load_defaults_from_schema()
        # OVERRIDE for Testing
        if 'trigger_settings' in self.config:
            self.config['trigger_settings']['trigger_threshold'] = 1000 
            self.config['trigger_settings']['velocity_threshold'] = 2.0
            self.config['trigger_settings']['min_velocity_score'] = 5
            
        self.plugin = BuzzRadarPlugin(self.context, self.config)

    def _load_defaults_from_schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', '_conf_schema.json')
        config = {}
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
                for key, item in schema.items():
                    if 'default' in item: config[key] = item['default']
                    if item.get('type') == 'object' and 'items' in item:
                        sub_config = {}
                        for sub_key, sub_item in item['items'].items():
                            if 'default' in sub_item: sub_config[sub_key] = sub_item['default']
                        config[key] = sub_config
        return config

    @contextlib.contextmanager
    def mock_time(self, current_time):
         with unittest.mock.patch('time.time', return_value=current_time):
             yield

    async def run_scenario(self, log_file):
        if not os.path.exists(log_file):
            print(f"[Runner] Error: File {log_file} not found.")
            return

        with open(log_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        print(f"[Runner] Starting scenario: {log_file} with {len(events)} events.")
        events.sort(key=lambda x: x.get('time_offset', 0))
        
        start_time = time.time()

        for i, item in enumerate(events):
            offset = item.get('time_offset', 0)
            user_id = item.get('user', "unknown_user")
            content = item.get('content', "")
            group_id = item.get('group', "group_default")
            
            simulated_time = start_time + offset
            
            with self.mock_time(simulated_time):
                # Create Event INSIDE mocked context
                event = MockEvent(content, user_id, group_id)
                print(f"[Time {offset:.1f}s] Group:{group_id} User:{user_id} -> {content}")
                
                async for result in self.plugin.handle_message(event):
                    print(f"   >>> BOT RESPONSE: {result}")

        print("[Runner] Scenario completed.")

if __name__ == "__main__":
    runner = ScenarioRunner()
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    else:
        data_file = os.path.join(os.path.dirname(__file__), "data", "test_phase1.json")
    asyncio.run(runner.run_scenario(data_file))
