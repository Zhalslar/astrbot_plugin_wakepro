import re
from functools import lru_cache

import jieba


class Interest:
    def __init__(
        self, interest_words, cache_size=2048, min_msg_len=3, noise_pattern=r"^[\W_]+$"
    ):
        """
        interest_words: list[list[str]]
        """
        self.topics = [list(t) for t in interest_words]
        self.min_msg_len = min_msg_len
        self.noise_re = re.compile(noise_pattern)
        self._install_token_cache(cache_size)

    # --------------------------------------
    # Tokenizer + LRU Cache
    # --------------------------------------
    def _install_token_cache(self, size):
        @lru_cache(maxsize=size)
        def cached(msg: str):
            msg = msg.lower()
            return [t for t in jieba.lcut(msg) if t.strip()]

        self._cached_tokenize = cached

    def tokenize(self, msg: str):
        return self._cached_tokenize(msg)

    # --------------------------------------
    # Noise filtering
    # --------------------------------------
    def _is_noise(self, msg: str) -> bool:
        msg = msg.strip()

        # 太短的消息直接视为噪声
        if len(msg) < self.min_msg_len:
            return True

        # 纯符号 / 纯emoji / 纯空白
        if self.noise_re.match(msg):
            return True

        # 常见噪声片段
        noise_words = {"嗯", "啊", "哦", "哈", "哈哈", "嘿嘿", "哎", "欸"}
        if msg in noise_words:
            return True

        return False

    # --------------------------------------
    # Interest Calculation（高精度）
    # --------------------------------------
    def calc_interest(self, msg: str) -> float:
        """
        返回兴趣值 0~1
        """
        if self._is_noise(msg):
            return 0.0

        tokens = self.tokenize(msg)
        best = 0.0

        for topic in self.topics:
            score = self._score_topic(msg, tokens, topic)
            best = max(best, score)

        return min(1.0, best)

    # --------------------------------------
    # Topic scoring（更智能的打分）
    # --------------------------------------
    def _score_topic(self, msg: str, tokens, topic_keywords):
        total_weight = 0.0
        gained = 0.0

        for kw in topic_keywords:
            w = self._keyword_weight(kw)
            total_weight += w

            gained += w * self._match_strength(kw, msg, tokens)

        if total_weight == 0:
            return 0.0

        # 非线性拉伸：强命中更突出 + 弱命中更弱化
        base = gained / total_weight
        return base**0.8  # γ < 1 → 强化强关联

    # --------------------------------------
    # 关键词权重（长度越长权重越高）
    # --------------------------------------
    @staticmethod
    def _keyword_weight(kw: str):
        L = len(kw)
        if L <= 1:
            return 0.8
        elif L == 2:
            return 1.2
        elif L == 3:
            return 1.5
        return 1.8  # 更长的关键词权重大

    # --------------------------------------
    # 关键词命中强度（0~1）
    # --------------------------------------
    def _match_strength(self, kw, msg, tokens):
        # 完整命中（tokens）
        if kw in tokens:
            return 1.0

        # 原文命中（子串）
        pos = msg.find(kw)
        if pos != -1:
            # 位置权重：句首更强，越后越弱
            pos_factor = max(0.5, 1.0 - pos / max(1, len(msg)))
            return 0.7 * pos_factor

        # 半命中（关键词部分被切开，例如 "排" + "位"）
        chars_hit = sum(1 for c in kw if c in msg)
        if chars_hit >= len(kw) / 2:
            return 0.35

        return 0.0
