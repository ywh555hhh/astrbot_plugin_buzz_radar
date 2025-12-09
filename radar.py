import time
import json
import os
import logging
import asyncio

logger = logging.getLogger("astrbot")

class GroupState:
    def __init__(self, group_id: str, max_score_cap: int = 1000, trigger_threshold: int = 80):
        self.group_id = group_id
        self.current_score = 0
        self.max_score_cap = max_score_cap
        self.trigger_threshold = trigger_threshold
        
        # State
        self.last_update_time = time.time()
        self.last_trigger_time = 0
        self.message_buffer = [] # Store short history for context: list of (sender, content)
        
        # Velocity Tracking
        self.window_size = 60 # 1 minute windows
        self.current_window_start = time.time()
        self.current_window_score = 0
        self.prev_window_score = 0
        
        # Crowd Tracking (v3.0)
        self.active_users = {} # {user_id: last_speak_timestamp}
        self.active_window = 600 # 10 minutes

    def _clean_active_users(self, now: float):
        """Remove users who haven't spoken in active_window"""
        dead_users = [uid for uid, ts in self.active_users.items() if now - ts > self.active_window]
        for uid in dead_users:
            del self.active_users[uid]

    def add_score(self, base_score: int, sender_id: str, timestamp: float = None):
        """
        v3.0 Score Logic:
        1. New Face Bonus: +20 if not active recently.
        2. Crowd Multiplier: Base + (ActiveCount * Weight).
        """
        now = timestamp or time.time()
        self._clean_active_users(now)
        
        final_score = base_score
        
        # 1. New Face Bonus
        if sender_id not in self.active_users:
            final_score += 20
            logger.debug(f"[BuzzRadar] New Face Bonus! User {sender_id} +20")
            
        # Update user activity
        self.active_users[sender_id] = now
        
        # 2. Crowd Multiplier
        active_count = len(self.active_users)
        crowd_weight = 2 # Configurable? Hardcoded for now
        crowd_bonus = active_count * crowd_weight
        final_score += crowd_bonus
        
        # Check window rotation
        diff = now - self.current_window_start
        if diff > self.window_size:
            logger.debug(f"[BuzzRadar] Rotating Window! Diff={diff}")
            self.prev_window_score = self.current_window_score
            self.current_window_score = 0
            self.current_window_start = now
            
        self.current_window_score += final_score
        
        self.decay(timestamp=now) # Update decay before adding to total
        self.current_score += final_score
        if self.current_score > self.max_score_cap:
             self.current_score = self.max_score_cap
        
        logger.debug(f"[BuzzRadar] Group {self.group_id} Score: {self.current_score:.2f} (+{final_score}) | Active: {active_count}")

    def decay(self, rate_per_minute: int = 5, timestamp: float = None):
        now = timestamp or time.time()
        minutes_passed = (now - self.last_update_time) / 60.0
        
        if minutes_passed > 0:
            decay_amount = minutes_passed * rate_per_minute
            self.current_score = max(0, self.current_score - decay_amount)
            self.last_update_time = now

    def add_message(self, sender: str, content: str, timestamp: float = None):
        """
        Store message with timestamp.
        """
        now = timestamp or time.time()
        self.message_buffer.append({
            "ts": now,
            "sender": sender,
            "content": content
        })
        
        # Cleanup old messages (keep only those within active_window)
        # We use the same window as active_users for consistency (default 10 mins)
        cutoff = now - self.active_window
        while self.message_buffer and self.message_buffer[0]["ts"] < cutoff:
            self.message_buffer.pop(0)

    def get_history_text(self) -> str:
        """Format buffer for LLM"""
        return "\n".join([f"{m['sender']}: {m['content']}" for m in self.message_buffer])

class PersistenceLayer:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = {}
        self.load()
        
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"[BuzzRadar] 加载持久化数据失败: {e}")
                self.data = {}
    
    def save(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[BuzzRadar] 保存持久化数据失败: {e}")

    def update_trigger_time(self, group_id: str, timestamp: float):
        self.data[group_id] = {"last_trigger_time": timestamp}


class RadarSystem:
    def __init__(self, config: dict, persistence_path: str = "data/buzz_radar/persistence.json", start_loop=True):
        self.config = config
        self.groups = {} # group_id -> GroupState
        self.persistence = PersistenceLayer(persistence_path)
        
        # Restore last trigger times if needed (logic to be refined)
        
        # Start periodic tasks
        if start_loop:
            # Note: In actual plugin, use scheduler or asyncio.create_task
            pass

    def get_group_state(self, group_id: str) -> GroupState:
        if group_id not in self.groups:
            trigger_settings = self.config.get("trigger_settings", {})
            self.groups[group_id] = GroupState(
                group_id, 
                max_score_cap=trigger_settings.get("max_score_cap", 1000),
                trigger_threshold=trigger_settings.get("trigger_threshold", 80)
            )
            # Restore trigger time
            if group_id in self.persistence.data:
                 self.groups[group_id].last_trigger_time = self.persistence.data[group_id].get("last_trigger_time", 0)
        return self.groups[group_id]

    async def on_message(self, group_id: str, score: int, user_id: str, sender_name: str, content: str, timestamp: float = None):
        state = self.get_group_state(group_id)
        
        # 1. Update Score
        state.add_score(score, user_id, timestamp=timestamp)
        state.add_message(sender_name, content)
        
        # 2. Check Trigger
        trigger_conf = self.config.get("trigger_settings", {})
        cooldown = trigger_conf.get("cooldown_minutes", 10) * 60
        now = timestamp or time.time()
        
        is_triggered = False
        trigger_reason = ""
        
        # A. Velocity Trigger (Acceleration)
        velocity_threshold = trigger_conf.get("velocity_threshold", 2.0)
        min_velocity_score = trigger_conf.get("min_velocity_score", 30)
        
        # Ensure we have a previous window to compare against and enough volume
        if state.prev_window_score > 0 and state.current_window_score > min_velocity_score:
            current_velocity = state.current_window_score / state.prev_window_score
            if current_velocity >= velocity_threshold:
                 logger.info(f"[BuzzRadar] 🚀 Group {group_id} 加速触发! Velocity: {current_velocity:.2f}x (Curr: {state.current_window_score}, Prev: {state.prev_window_score})")
                 is_triggered = True
                 trigger_reason = "velocity"

        # B. Standard Threshold Trigger
        if not is_triggered and state.current_score >= state.trigger_threshold:
             is_triggered = True
             trigger_reason = "threshold"

        if is_triggered:
            logger.debug(f"[DEBUG] Check Trigger ({trigger_reason}): Now={now}, Last={state.last_trigger_time}, Diff={now - state.last_trigger_time}, Cooldown={cooldown}")
            if now - state.last_trigger_time > cooldown:
                # TRIGGER!
                logger.info(f"[BuzzRadar] 🚀 Group {group_id} 触发总结 ({trigger_reason})! Score: {state.current_score}")
                state.last_trigger_time = now
                self.persistence.update_trigger_time(group_id, now)
                self.persistence.save() # Immediate save on trigger is okay (low freq)
                return True, state.message_buffer
            else:
                 logger.debug(f"[BuzzRadar] Group {group_id} 冷却中... (Score: {state.current_score})")

        return False, None
    
    def get_group_state_snapshot(self, group_id: str) -> dict:
        """
        Get a snapshot of the group state for admin display.
        """
        if group_id not in self.groups:
            return None
        
        state = self.groups[group_id]
        state.decay() # Update decay for fresh view
        
        trigger_conf = self.config.get("trigger_settings", {})
        cooldown_minutes = trigger_conf.get("cooldown_minutes", 10)
        cooldown_seconds = cooldown_minutes * 60
        
        now = time.time()
        time_since_last_trigger = now - state.last_trigger_time
        remaining_cooldown = max(0, cooldown_seconds - time_since_last_trigger)
        
        return {
            "score": round(state.current_score, 1),
            "max_score": state.max_score_cap,
            "threshold": state.trigger_threshold,
            "remaining_cooldown": remaining_cooldown
        }

    def force_reset(self, group_id: str):
        """
        Force reset group score and trigger time.
        """
        if group_id in self.groups:
            state = self.groups[group_id]
            state.current_score = 0
            # Optional: Reset trigger time or set to now to force cooldown? 
            # User requirement: "Force reset score". "Optional: Force cooldown".
            # Let's just reset score for "Calm". 
            logger.info(f"[BuzzRadar] Manually reset score for group {group_id}")

    def cleanup_zombies(self, max_idle_days=7):
        """
        清理僵尸群状态 (Lazy Cleanup)
        """
        now = time.time()
        limit = max_idle_days * 86400
        zombies = []
        for gid, state in self.groups.items():
            if now - state.last_update_time > limit:
                zombies.append(gid)
        
        for gid in zombies:
            del self.groups[gid]
            logger.info(f"[BuzzRadar] 清理僵尸群状态: {gid}")
