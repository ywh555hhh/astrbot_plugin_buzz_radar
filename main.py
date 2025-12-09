import os
import time

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain

try:
    from .logic import MessageFilter, ScoreEngine
    from .radar import RadarSystem
    from .sampler import ContentSampler
    from .persona import PersonaManager
except ImportError:
    from logic import MessageFilter, ScoreEngine
    from radar import RadarSystem
    from sampler import ContentSampler
    from persona import PersonaManager

@register("buzz_radar", "YourName", "智能群聊热度雷达", "2.0.0")
class BuzzRadarPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # Initialize Components
        self.msg_filter = MessageFilter(self.config)
        self.score_engine = ScoreEngine(self.config)
        
        # Use StarTools for correct data path
        plugin_data_dir = StarTools.get_data_dir("buzz_radar")
        persistence_file = os.path.join(plugin_data_dir, "persistence.json")
        self.radar = RadarSystem(self.config, persistence_path=persistence_file)
        
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

    async def _is_admin(self, event: AstrMessageEvent) -> bool:
        """
        Robust admin check using AstrBot's API and config.
        """
        try:
             # 1. Global Superuser Check (from global config)
             user_id = event.message_obj.sender.user_id
             if str(user_id) in self.context.get_config().get("admins_id", []):
                 return True

             # 2. Group Role Check (Owner/Admin)
             group_id = event.message_obj.group_id
             if not group_id: return False # Private chat?
             
             # Use bot.get_group_member_info for accurate role
             try:
                info = await event.bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(user_id), no_cache=True
                )
                role = info.get("role", "member")
                if role in ["admin", "owner"]:
                    return True
             except Exception as e:
                # Fallback to event object if API fails
                logger.warning(f"[BuzzRadar] Admin check API failed: {e}, falling back to event data.")
                role = event.get_sender_role()
                if role in ["admin", "owner"]: return True
                
             return False
        except Exception as e:
             logger.error(f"[BuzzRadar] Admin check error: {e}")
             return False

    @filter.command_group("radar")
    def radar_cmd(self):
        pass

    @radar_cmd.command("status", alias=["heat", "热度"])
    async def show_status(self, event: AstrMessageEvent):
        """显示当前群热度状态"""
        if not await self._is_admin(event):
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
        
        # Rich Status
        active_count = len(self.radar.get_group_state(group_id).active_users)
        msg_count = len(self.radar.get_group_state(group_id).message_buffer)
        
        msg = (
            f"📊 BuzzRadar 实时监控\n"
            f"-----------------------\n"
            f"🔥 当前热度: {score} 分\n"
            f"👥 活跃人数: {active_count} 人 (10min)\n"
            f"📝 缓存消息: {msg_count} 条 (10min)\n"
            f"-----------------------\n"
            f"[触发阈值]: {bar_trigger}\n"
            f"[热度封顶]: {bar_cap}\n"
            f"-----------------------\n"
            f"Status: {cooldown_text}\n"
            f"Persona: {current_persona['name']}"
        )
        yield event.plain_result(msg)

    @radar_cmd.command("calm", alias=["降温"])
    async def calm_down(self, event: AstrMessageEvent):
        """一键降温"""
        if not await self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return

        group_id = event.message_obj.group_id
        self.radar.force_reset(group_id)
        yield event.plain_result("🌊 已执行强制降温，热度归零。")

    @radar_cmd.command("test")
    async def debug_test(self, event: AstrMessageEvent, level: str = "1"):
        """调试触发: /radar test"""
        if not await self._is_admin(event):
             yield event.plain_result("🚫 权限不足")
             return
             
        group_id = event.message_obj.group_id
        state = self.radar.get_group_state(group_id)
        
        # v3.1: Use REAL data to reflect "Natural Intervention" logic
        real_history = state.message_buffer
        real_active_count = len(state.active_users)
        
        if not real_history:
            yield event.plain_result(f"⚠️ 当前群内无已缓存的消息记录，请先在群里聊几句。\n(当前缓存为空，无法提取话题)")
            return

        yield event.plain_result(f"🧪 正在基于真实数据模拟触发...\n📊 当前活跃人数: {real_active_count} 人\n📝 缓存消息数: {len(real_history)} 条")
        
        # Use real history
        async for result in self._generate_summary(group_id, real_history):
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
        
        final_prompt = prompt_tmpl.replace("{{context}}", context_str)
        
        logger.info(f"[BuzzRadar] 正在生成总结... Group: {group_id} | Persona: {persona['name']}")
        # News Ticker needs no "summoning" text, just silence or small log
        # yield MessageEventResult(chain=[Plain(f"🔥 检测到高热度！正在通灵 {persona['name']} 进行总结...")])

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
                # News Ticker Formatting
                # Get Config first
                config = self.config
                display_cfg = config.get("display_settings", {})
                max_len = display_cfg.get("max_keyword_length", 20)
                
                keyword = response.completion_text.strip().replace("关键词", "").replace(":", "").replace("：", "").replace("\"", "").replace("'", "")
                if len(keyword) > max_len: keyword = keyword[:max_len] + "..."
                if not keyword: keyword = "群内热聊"
                
                # Get real active count
                state = self.radar.get_group_state(group_id)
                # Rich Status Data
                active_count = len(state.active_users)
                if active_count == 0: active_count = 1
                msg_count = len(state.message_buffer)
                current_score = int(state.current_score)
                
                # Use Template
                tmpl = display_cfg.get("summary_template", "【{keyword}】 {active_count} 人正在热议 🔥")
                
                # Safe Format
                try:
                    final_msg = tmpl.format(
                        keyword=keyword, 
                        active_count=active_count,
                        msg_count=msg_count,
                        score=current_score
                    )
                except Exception:
                    # Fallback if user template is broken
                    final_msg = f"【{keyword}】 {active_count} 人正在热议 🔥"
                
                yield MessageEventResult(chain=[Plain(final_msg)])
            else:
                 yield MessageEventResult(chain=[Plain("⚠️ 总结生成失败：LLM 返回为空。")])
                 
        except Exception as e:
            logger.error(f"[BuzzRadar] LLM Error: {e}")
            yield MessageEventResult(chain=[Plain(f"⚠️ 总结生成出错: {str(e)}")])

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
        sender_name = event.message_obj.sender.nickname or event.message_obj.sender.card or "GroupMember"
        content = event.message_str
        
        # 1. Check Cleanup (Simplified scheduling: one check per 100 messages)
        import random
        if random.randint(1, 100) == 1:
            self.radar.cleanup_zombies()
        
        # 2. Filter Noise
        if self.msg_filter.is_noise(content, group_id):
            return 
            
        # 3. Calculate Score
        score = self.score_engine.calculate_score(event)
        
        # 4. Radar System Processing
        ts = getattr(event, 'timestamp', None) or time.time()
        is_triggered, context_msgs = await self.radar.on_message(group_id, score, user_id, sender_name, content, timestamp=ts)
        
        # 6. Trigger Action
        if is_triggered:
            # Circuit Breaker Check
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
