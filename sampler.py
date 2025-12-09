from typing import List, Tuple

class ContentSampler:
    def __init__(self, max_length: int = 1500):
        self.max_length = max_length

    def sample(self, messages: List[dict]) -> List[str]:
        """
        Refactored Sampler (v3.2):
        1. Input is now list of dicts: {'ts', 'sender', 'content'}
        2. Strategy: Tail Only (Focus on recent context for topic detection)
        3. Drop 'User:' prefix if not needed? No, kept for context.
        """
        if not messages:
            return []
            
        # Convert to strings
        # Format: "User: Content"
        text_msgs = [f"{m['sender']}: {m['content']}" for m in messages]
        
        # Simple Tail Strategy: Take last 50 messages (or max length)
        # Since radar.py already limits by time (10min), we just need to fit token limit.
        
        # Reverse iterate to fill quota
        result = []
        current_len = 0
        for msg in reversed(text_msgs):
            if current_len + len(msg) > self.max_length:
                break
            result.insert(0, msg)
            current_len += len(msg)
            
        return result
