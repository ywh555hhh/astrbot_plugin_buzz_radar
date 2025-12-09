import re
import logging

logger = logging.getLogger("astrbot")

class MessageFilter:
    def __init__(self, config: dict):
        self.config = config
        self.last_content = {} # group_id -> content string (for deduplication)
        self.dedup_counter = {} # group_id -> count of consecutive dupes

    def is_noise(self, content: str, group_id: str) -> bool:
        """
        判断消息是否为噪音。
        返回 True 表示是噪音（应被忽略），False 表示是有效信号。
        """
        cleaning_conf = self.config.get("cleaning_settings", {})
        
        # 1. 长度过滤
        min_len = cleaning_conf.get("min_text_length", 2)
        if len(content.strip()) < min_len:
            logger.debug(f"[BuzzRadar] 过滤短文本: {content}")
            return True

        # 2. 正则过滤 (指令等)
        ignore_regex = cleaning_conf.get("ignore_regex", "^[#/!]")
        if re.search(ignore_regex, content):
            logger.debug(f"[BuzzRadar] 过滤正则匹配: {content}")
            return True

        # 3. 复读机过滤
        dedup_limit = cleaning_conf.get("deduplicate_threshold", 3)
        last = self.last_content.get(group_id, "")
        if content == last:
            self.dedup_counter[group_id] = self.dedup_counter.get(group_id, 0) + 1
            if self.dedup_counter[group_id] >= dedup_limit:
                logger.debug(f"[BuzzRadar] 过滤复读机: {content} (x{self.dedup_counter[group_id]})")
                return True
        else:
            self.last_content[group_id] = content
            self.dedup_counter[group_id] = 1
            
        return False

class ScoreEngine:
    def __init__(self, config: dict):
        self.config = config
    
    def calculate_score(self, event) -> int:
        """
        计算单条消息的热度分。
        """
        score_conf = self.config.get("score_weights", {})
        base_score = score_conf.get("base_score", 1)
        score = base_score
        
        # 获取消息链和纯文本
        message_chain = event.get_messages()
        text_content = event.message_str or ""
        
        # 1. 图片/表情包加分
        has_image = False
        for component in message_chain:
            # 简单判断: 如果是图片组件 (实际需根据 AstrBot 组件类型判断，这里假设 type name)
            # Adapt to actual AstrBot component types later
            if type(component).__name__ in ["Image", "Face", "Record", "Video"]:
                has_image = True
                break
        
        if has_image:
            score = max(score, score_conf.get("image_score", 2))

        # 2. 长文本加分
        if len(text_content) > 15:
            score += score_conf.get("long_text_bonus", 1)

        # 3. 回复/引用加分 (Need to check event structure for reply)
        # 暂时留空，待确认 AstrBot 回复判断逻辑
        # if event.is_reply:
            # score += score_conf.get("reply_bonus", 2)
            
        return score
