"""
auto_repeater - 关键字回复 + 复读机
================================
收到消息后：
  1. 命中预设关键词 → 自动回复
  2. 与上一条相同、发送者不同 → 复读

所有配置通过 AstrBot 后台插件设置面板管理。
"""

import json
from difflib import SequenceMatcher

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig


@register("auto_repeater", "Kita", "关键字回复 + 复读机", "0.1.0")
class AutoRepeater(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self._chain_text = None  # 当前连续相同文本
        self._chain_senders = set()  # 已发言的不同发送者

    # ===== 消息入口 =====

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """消息入口：先关键字匹配，再复读检测。异常不抛出，仅记录日志。"""
        try:
            text = event.get_message_str().strip()
            if not text:
                return

            sender = event.get_sender_id()

            # ① 关键字回复（精确子串优先，未命中则模糊匹配兜底）
            if self.config.get("keyword_enabled", True):
                reply = self._match(text)
                if reply:
                    yield event.chain_result([Plain(reply)])
                    return

            # ② 复读检测（连续 N 个不同人说相同内容时触发）
            if self.config.get("repeater_enabled", True):
                threshold = self.config.get("repeat_count", 2)
                if text == self._chain_text:
                    self._chain_senders.add(sender)
                    if len(self._chain_senders) >= threshold:
                        yield event.chain_result([Plain(text)])
                        self._chain_text = None
                        self._chain_senders.clear()
                else:
                    self._chain_text = text
                    self._chain_senders = {sender}
        except Exception:
            # 任何异常静默吞掉，不影响 Bot 运行
            pass

    # ===== 内部逻辑 =====

    def _match(self, text: str):
        """先精确子串匹配，未命中则模糊匹配兜底"""
        raw = self.config.get("keywords", "{}")
        try:
            items = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return None

        best = None
        best_score = self.config.get("fuzzy_threshold", 0.6)

        for name, item in items.items():
            kws = item.get("keywords", [])
            reply = item.get("reply", f"请查看 {name}")

            for kw in kws:
                # 精确子串
                if kw in text:
                    return reply
                # 模糊匹配
                score = SequenceMatcher(None, kw, text).ratio()
                if score > best_score:
                    best_score = score
                    best = reply

        return best
