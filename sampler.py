from typing import List, Tuple

class ContentSampler:
    def __init__(self, max_length: int = 1500):
        self.max_length = max_length

    def sample(self, messages: List[str]) -> List[str]:
        """
        Intelligently sample messages to fit within token limits while preserving context.
        Strategy: Head + Middle (Weighted) + Tail
        """
        total_msgs = len(messages)
        if total_msgs <= 10:
            return messages
        
        # Simple Logic for now:
        # Keep first 3 (Context start)
        # Keep last 15 (Recent context)
        # Sample middle if space allows? 
        # For Phase 2, let's implement a simple Head + Tail strategy.
        
        head = messages[:3]
        tail = messages[-15:]
        
        # Check simple length constraints (approx chars)
        result = head + ["... (skipped) ..."] + tail
        
        # Calculate roughly
        current_len = sum(len(m) for m in result)
        
        if current_len > self.max_length:
             # Truncate further from tail's start if needed
             while current_len > self.max_length and len(tail) > 1:
                 tail.pop(0)
                 result = head + ["... (skipped) ..."] + tail
                 current_len = sum(len(m) for m in result)
                 
        return result
