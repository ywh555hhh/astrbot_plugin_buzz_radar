import time
from typing import List, Any
from dataclasses import dataclass, field

# Mock AstrBot Components
@dataclass
class MockContext:
    config: dict = field(default_factory=dict)
    
    def get_config(self):
        return self.config

@dataclass
class MockSender:
    user_id: str
    nickname: str

@dataclass
class MockMessageObj:
    message_id: str
    group_id: str
    sender: MockSender
    raw_message: Any = None

@dataclass
class MockPlain:
    text: str
    
    def __str__(self):
        return self.text

class MockEvent:
    """
    Mock class mimicking AstrBot's AstrMessageEvent for testing.
    """
    def __init__(self, message_str: str, user_id: str, group_id: str, nickname: str = None):
        if nickname is None:
            nickname = f"User{user_id}"
            
        self.message_str = message_str
        self.sender = MockSender(user_id=user_id, nickname=nickname)
        self.message_obj = MockMessageObj(
            message_id=f"msg_{int(time.time()*1000)}",
            group_id=group_id,
            sender=self.sender
        )
        # Construct a simple message chain with one Plain component
        self.message_chain = [MockPlain(text=message_str)]
        
        # KEY FIELD: timestamp
        self.timestamp = time.time()
    
    def get_sender_role(self):
        return "member"

    def get_sender_name(self):
        return self.sender.nickname
        
    def get_messages(self):
        return self.message_chain
        
    def plain_result(self, text: str):
        # Mock yield result
        return f"[MockResponse] {text}"

# Helper to generate events quickly
def create_event(content: str, user="1001", group="group_1"):
    return MockEvent(content, user, group)
