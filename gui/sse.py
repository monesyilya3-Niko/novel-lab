"""SSE（Server-Sent Events）进度推送工具。

基于标准库 http.server 的分块写能力，向前端 EventSource 推送 progress 事件。
协议：``text/event-stream``，每条消息 ``data: <json>\\n\\n``。
"""
from __future__ import annotations

import json
import queue
import threading
from typing import Any, Dict, Optional


class SseBroker:
    """线程安全的事件分发器：服务层往队列塞事件，每个 SSE 连接各自消费。

    采用「每连接一个 queue」的广播模型：发布时向所有活跃连接投递；连接关闭时
    自动移除，避免订阅者泄漏。
    """

    def __init__(self) -> None:
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        """注册一个新订阅者，返回其专属队列。"""
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        """移除订阅者。"""
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: Dict[str, Any]) -> None:
        """向所有活跃订阅者广播一个事件（非阻塞投递）。"""
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                # 队列满（订阅者消费太慢），丢弃以避免阻塞服务层。
                continue


def format_event(event: Dict[str, Any]) -> str:
    """把一个事件 dict 序列化为 SSE 帧。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# 全局单例 broker（服务层与 server 共用）。
broker = SseBroker()
