
import logging
from typing import Dict, Any

logger = logging.getLogger("astrbot")

class PersonaManager:
    def __init__(self, config: dict):
        self.config = config
        # v3.1 Strict Few-Shot Prompt (Hardcoded for stability)
        self.strict_prompt = (
            "你是一个精准的群聊热点提取器。你的任务是从杂乱的聊天记录中，提取出一个最具吸引力的“热搜标题”。\n\n"
            "### 聊天记录：\n{{context}}\n\n"
            "### 提取规则：\n"
            "1. **核心目标**：提取“实体 + 事件”或“核心冲突点”。\n"
            "2. **风格要求**：像微博热搜或B站热门标签。具体、紧凑、有信息量。\n"
            "3. **字数限制**：严格控制在 10-20 个汉字之间。\n"
            "4. **格式禁忌**：\n"
            "   - ❌ 严禁使用任何标点符号。\n"
            "   - ❌ 严禁包含“大家”、“讨论”、“关于”、“正在”等无意义的废话。\n"
            "   - ❌ 严禁输出完整句子，只要短语。\n"
            "   - ❌ 严禁使用引号（\"\" 或 ‘’）。\n\n"
            "### 优质示例（Few-Shot）：\n"
            "Input: (一群人在聊饿了、想吃火锅、谁去订位、海底捞还要排队吗)\n"
            "Output: 深夜海底捞组局计划\n\n"
            "Input: (詹姆斯今天太铁了、确实不如库里、数据刷子、历史地位不行)\n"
            "Output: NBA詹库历史地位激辩\n\n"
            "Input: (报错了、Python环境不对、重装试试、版本不兼容)\n"
            "Output: Bot启动环境报错排查\n\n"
            "Input: (无职转生这一集神了、鲁迪做得不对、作画太强了)\n"
            "Output: 无职转生最新集剧情争议\n\n"
            "对话历史：\n{{context}}\n\n"
            "Keyword:"
        )
        
    def _get_settings(self) -> dict:
        return self.config.get("persona_settings", {})

    def get_persona(self) -> Dict[str, str]:
        """
        Get the News Ticker persona.
        Priority:
        1. Config 'custom_prompt' (if set by user)
        2. Built-in Strict Few-Shot Prompt
        """
        settings = self._get_settings()
        # Prefer config (which now defaults to the strict prompt via schema)
        custom_prompt = settings.get("summary_prompt", "").strip()
        prompt_to_use = custom_prompt if custom_prompt else self.strict_prompt
        
        return {
            "id": "strict_ticker",
            "name": "BuzzRadar",
            "prompt": prompt_to_use
        }
