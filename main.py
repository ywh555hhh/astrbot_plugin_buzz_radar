import sys
import os
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain

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
             # Proactive Chat Plugin has a robust role check, let's allow "owner" and "admin"
             # 1. Try helper
             role = event.get_sender_role()
             if role in ["admin", "owner"]: return True
             
             # 2. Try raw object attributes
             if hasattr(event, "message_obj") and event.message_obj.sender:
                 sender = event.message_obj.sender
                 if hasattr(sender, "role") and sender.role in ["admin", "owner"]:
                     return True
                     
             return False
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
import sys
import os
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)

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
        """调试触发: /radar test"""
        if not self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return
             
        group_id = event.message_obj.group_id
        yield event.plain_result(f"🧪 正在模拟触发 (Level {level})...")
        
        # Mock context for testing
        mock_context = [
            "UserA: 哇，今天 AstrBot 更新真的好快！",
            "UserB: 是啊，新功能太强了。",
            "UserC: 这个热度雷达插件有点意思。",
            "UserA: 确实，还能自动总结。",
            "UserD: 这个测试命令好用吗？"
        ]
        
        # Reuse the summary generation logic
        async for result in self._generate_summary(group_id, mock_context):
            yield result
    
    async def _generate_summary(self, group_id: str, context_msgs: list):
        """Shared summary generation logic"""
        # Sampling
        sampled_context = self.sampler.sample(context_msgs)
        context_str = "\n".join(sampled_context)
        
        # Generate Prompt via Persona Manager
        persona = self.persona_manager.get_persona()
        prompt_tmpl = persona['prompt']
        final_prompt = prompt_tmpl.replace("{{context}}", context_str)
        
        logger.info(f"[BuzzRadar] 正在生成总结... Group: {group_id} | Persona: {persona['name']}")
        yield MessageEventResult(event=None, message_chain=[Plain(f"🔥 检测到高热度！正在通灵 {persona['name']} 进行总结...")])

        # Call LLM
        try:
            # Try to get provider ID (AstrBot v4.5.7+)
            if hasattr(self.context, 'get_current_chat_provider_id'):
                provider_id = await self.context.get_current_chat_provider_id(group_id)
                response = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=final_prompt
                )
            else:
                # Fallback for older versions
                provider = self.context.get_using_provider(umo=group_id)
                if provider:
                    response = await provider.text_chat(prompt=final_prompt)
                else:
                    raise Exception("No LLM Provider found")
            
            if response and response.completion_text:
                result_text = f"🔥 ({persona['name']}视角) 热度总结：\n{response.completion_text}"
                yield MessageEventResult(event=None, message_chain=[Plain(result_text)])
            else:
                 yield MessageEventResult(event=None, message_chain=[Plain("⚠️ 总结生成失败：LLM 返回为空。")])
                 
        except Exception as e:
            logger.error(f"[BuzzRadar] LLM Error: {e}")
            yield MessageEventResult(event=None, message_chain=[Plain(f"⚠️ 总结生成出错: {str(e)}")])

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
            
            # Use shared logic
            async for result in self._generate_summary(group_id, context_msgs):
                yield result

    async def terminate(self):
        """Plugin shutdown cleanup."""
        self.radar.persistence.save()
        logger.info("[BuzzRadar] 数据已保存，插件卸载。")
