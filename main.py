from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from src.logic import MessageFilter, ScoreEngine
from src.radar import RadarSystem
from src.sampler import ContentSampler
from src.persona import PersonaManager

@register("buzz_radar", "YourName", "智能群聊热度雷达", "2.0.0")
class BuzzRadarPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # Initialize Components
        self.msg_filter = MessageFilter(self.config)
        self.score_engine = ScoreEngine(self.config)
        self.radar = RadarSystem(self.config, persistence_path="data/buzz_radar/persistence.json")
        self.sampler = ContentSampler()
        self.persona_manager = PersonaManager(self.config)
        
        # Circuit Breaker state
        self.last_llm_call = 0
        self.llm_call_count = 0 
        
        logger.info("[BuzzRadar] 插件已加载。智能热度监控启动。")

    def _draw_progress_bar(self, current: float, total: int, length: int = 10) -> str:
        """Helper to draw ASCII progress bar"""
        if total <= 0: return "[]"
        percent = min(1.0, current / total)
        filled = int(length * percent)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}] {current}/{total}"

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """Simple admin check"""
        try:
             role = event.get_sender_role()
             return role in ["admin", "owner"]
        except:
             return False

    @filter.command_group("radar")
    def radar_cmd(self):
        pass

    @radar_cmd.command("status")
    @radar_cmd.command("热度")
    async def show_status(self, event: AstrMessageEvent):
        """显示当前群热度状态"""
        if not self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return

        group_id = event.message_obj.group_id
        state = self.radar.get_group_state_snapshot(group_id)
        
        if not state:
            yield event.plain_result("❄️ 本群暂无热度记录。")
            return

        # Visual Dashboard
        score = state['score']
        threshold = state['threshold']
        cap = state['max_score']
        cooldown = state['remaining_cooldown']
        
        bar_trigger = self._draw_progress_bar(score, threshold, 10)
        bar_cap = self._draw_progress_bar(score, cap, 10)
        
        cooldown_text = f"❄️ 冷却中 ({int(cooldown)}s)" if cooldown > 0 else "✅ 监控中"
        
        current_persona = self.persona_manager.get_persona()
        
        msg = (
            f"📊 BuzzRadar 实时监控\n"
            f"-----------------------\n"
            f"🔥 当前热度: {score} 分\n"
            f"-----------------------\n"
            f"[触发阈值]: {bar_trigger}\n"
            f"[热度封顶]: {bar_cap}\n"
            f"-----------------------\n"
            f"Status: {cooldown_text}\n"
            f"Persona: {current_persona['name']}"
        )
        yield event.plain_result(msg)

    @radar_cmd.command("calm")
    @radar_cmd.command("降温")
    async def calm_down(self, event: AstrMessageEvent):
        """一键降温"""
        if not self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return

        group_id = event.message_obj.group_id
        self.radar.force_reset(group_id)
        yield event.plain_result("🌊 已执行强制降温，热度归零。")

    @radar_cmd.command("test")
    async def debug_test(self, event: AstrMessageEvent, level: str = "1"):
        """调试触发: /radar test [level]"""
        if not self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return
             
        yield event.plain_result(f"🧪 正在模拟 Level {level} 触发流程...(功能开发中)")
    
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_message(self, event: AstrMessageEvent):
        """
        核心消息处理逻辑
        """
        if not self.config.get("enable_plugin", True):
            return

        if not hasattr(event, "message_obj"):
            return
            
        group_id = event.message_obj.group_id
        user_id = event.message_obj.sender.user_id
        content = event.message_str
        
        # 2. Filter Noise
        if self.msg_filter.is_noise(content, group_id):
            return 
            
        # 3. Calculate Score
        score = self.score_engine.calculate_score(event)
        
        # 4. Radar System Processing
        import time
        ts = getattr(event, 'timestamp', None) or time.time()
        is_triggered, context_msgs = await self.radar.on_message(group_id, score, user_id, content, timestamp=ts)
        
        # 6. Trigger Action
        if is_triggered:
            # Circuit Breaker Check
            import time
            now = time.time()
            if now - self.last_llm_call < 60: # 1 minute window
                if self.llm_call_count >= 5: # Max 5 calls per minute global
                    logger.warning("[BuzzRadar] 熔断保护: LLM 调用频率过高，跳过此次总结。")
                    return
                self.llm_call_count += 1
            else:
                self.llm_call_count = 1
                self.last_llm_call = now

            # Random Delay (Debounce/Humanization)
            import random
            import asyncio
            delay = random.uniform(5, 15)
            logger.info(f"[BuzzRadar] 拟人化延迟: {delay:.1f}s")
            await asyncio.sleep(delay)
            
            # Sampling
            sampled_context = self.sampler.sample(context_msgs)
            context_str = "\n".join(sampled_context)
            
            # Generate Prompt via Persona Manager
            persona = self.persona_manager.get_persona()
            prompt_tmpl = persona['prompt']
            system_prompt = prompt_tmpl.replace("{{context}}", context_str)
            
            logger.info(f"[BuzzRadar] 正在生成总结... Group: {group_id} | Persona: {persona['name']}")
            
            result_text = f"🔥 ({persona['name']}视角) 群里好热闹！大家在聊：\n{context_str}\n(AI 总结生成中...)"
            
            yield event.plain_result(result_text)

    async def terminate(self):
        """Plugin shutdown cleanup."""
        self.radar.persistence.save()
        logger.info("[BuzzRadar] 数据已保存，插件卸载。")
