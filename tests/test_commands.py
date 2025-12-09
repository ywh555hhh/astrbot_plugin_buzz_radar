import asyncio
import os
import sys
from unittest.mock import MagicMock

# Setup Mocks (Same as scenario_runner)
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

# Inject Mocks
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
sys.modules['astrbot.core.config'] = mock_astrbot.core.config
sys.modules['astrbot.core.config.astrbot_config'] = mock_astrbot.core.config.astrbot_config

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import logic
from main import BuzzRadarPlugin
from tests.mock_event import MockEvent, MockContext

async def test_dashboard():
    print("--- Testing /radar status ---")
    plugin = BuzzRadarPlugin(MockContext(), {"enable_plugin": True})
    
    # 1. Simulate some activity
    msg_event = MockEvent("test msg", "u1", "g1")
    await list(plugin.handle_message(msg_event))[0] if hasattr(plugin.handle_message, '__iter__') else None
    # Wait, handle_message is async generator
    async for _ in plugin.handle_message(msg_event): pass
    
    # Manually pump score
    plugin.radar.groups["g1"].current_score = 50
    plugin.radar.groups["g1"].trigger_threshold = 100
    
    # 2. Call Status Command
    # Mock Admin Event
    cmd_event = MockEvent("/radar status", "admin_user", "g1")
    cmd_event.get_sender_role = MagicMock(return_value="admin")
    
    print("Invoking show_status...")
    async for result in plugin.show_status(cmd_event):
        print(f"Result:\n{result}")

async def test_calm():
    print("\n--- Testing /radar calm ---")
    plugin = BuzzRadarPlugin(MockContext(), {"enable_plugin": True})
    plugin.radar.get_group_state("g1").current_score = 999
    
    cmd_event = MockEvent("/radar calm", "admin_user", "g1")
    cmd_event.get_sender_role = MagicMock(return_value="admin")
    
    async for result in plugin.calm_down(cmd_event):
        print(f"Result: {result}")
        
    print(f"Score after calm: {plugin.radar.get_group_state('g1').current_score}")

if __name__ == "__main__":
    asyncio.run(test_dashboard())
    asyncio.run(test_calm())
