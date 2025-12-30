# \astrbot\core\similarity.py

import math
import re
from collections import defaultdict, deque

import jieba


class Similarity:
    """
    最终稳定版话题相关性检测
    - 群号隔离
    - TF-IDF 稳定无膨胀
    - 内置 bot 消息预处理（去噪、去重、过滤模板）
    """

    def __init__(
        self,
        history_limit: int = 120,
        stopwords=None,
        bot_template_threshold: int = 2,
        early_stop: float = 0.92,
    ):
        """
        :param history_limit: 每个群最大历史窗口
        :param stopwords: 停用词
        :param bot_template_threshold: bot token 数 ≤ N 时视为模板句
        :param early_stop: 若相似度超该值，提前返回
        """
        self._GROUP_DATA = defaultdict(
            lambda: {
                "history": deque(maxlen=history_limit),
                "idf": defaultdict(int),
                "total_docs": 0,
            }
        )

        self.stopwords = stopwords or {
            "的",
            "了",
            "吗",
            "吧",
            "啊",
            "哦",
            "嗯",
            "恩",
            "你",
            "我",
            "他",
            "她",
            "它",
            "这",
            "那",
            "就",
            "都",
            "又",
        }

        self.bot_template_threshold = bot_template_threshold
        self.early_stop = early_stop

    # ---------------------------------------------------------
    # 分词
    # ---------------------------------------------------------
    def _tokenize(self, text: str):
        text = re.sub(r"[^\w\u4e00-\u9fa5]", " ", text)
        tokens = jieba.lcut(text)
        return [t for t in tokens if t not in self.stopwords and t.strip()]

    # ---------------------------------------------------------
    # 噪音检测（表情、纯符号、纯引用等）
    # ---------------------------------------------------------
    def _is_noise_msg(self, text: str) -> bool:
        s = text.strip()

        # 空消息
        if not s:
            return True

        # 纯 CQ 码，如 [CQ:reply,id=xxx]
        if re.fullmatch(r"\[CQ:[^\]]+]", s):
            return True

        # 纯 emoji / 符号
        if re.fullmatch(r"[\W_]+", s):
            return True

        # 纯数字和标点（如“123。。。!!”）
        if re.fullmatch(r"[\d\W_]+", s):
            return True

        return False

    # ---------------------------------------------------------
    # bot 消息预处理
    # ---------------------------------------------------------
    def _preprocess_bot_msgs(self, msgs: list[str]) -> list[str]:
        cleaned = []
        seen = set()

        for m in msgs:
            if not m:
                continue

            # 去重
            if m in seen:
                continue
            seen.add(m)

            # 噪音过滤
            if self._is_noise_msg(m):
                continue

            # token 数过滤（模板句过滤）
            tokens = self._tokenize(m)
            if len(tokens) <= self.bot_template_threshold:
                continue

            cleaned.append(m)

        return cleaned

    # ---------------------------------------------------------
    # TF-IDF 构建
    # ---------------------------------------------------------
    def _update_idf(self, group_id: str, tokens: set):
        data = self._GROUP_DATA[group_id]
        for t in tokens:
            data["idf"][t] += 1 # type: ignore
        data["total_docs"] += 1  # type: ignore

    def _tfidf_vector(self, group_id: str, tokens: list):
        data = self._GROUP_DATA[group_id]
        total_docs = data["total_docs"] or 1

        tf = defaultdict(int)
        for t in tokens:
            tf[t] += 1

        vec = {}
        for t, c in tf.items():
            idf = math.log((total_docs + 1) / (data["idf"][t] + 1)) + 1  # type: ignore
            vec[t] = c * idf

        return vec

    # ---------------------------------------------------------
    # Cosine
    # ---------------------------------------------------------
    def _cosine(self, v1, v2):
        if not v1 or not v2:
            return 0.0

        dot = sum(v * v2.get(k, 0) for k, v in v1.items())
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    # ---------------------------------------------------------
    # 主接口
    # ---------------------------------------------------------
    def similarity(
        self,
        group_id: str,
        user_msg: str,
        bot_msgs: list[str],
        update_history: bool = True,
    ) -> float:
        # 分词
        user_tokens = self._tokenize(user_msg)
        if not user_tokens:
            return 0.0

        # 更新历史（可关闭）
        if update_history:
            entry = " ".join(user_tokens)
            self._GROUP_DATA[group_id]["history"].append(entry)  # type: ignore
            self._update_idf(group_id, set(user_tokens))

        # 用户向量
        user_vec = self._tfidf_vector(group_id, user_tokens)

        # bot 消息预处理 + 最近优先
        bot_list = self._preprocess_bot_msgs(bot_msgs)[::-1]

        best = 0.0
        for bm in bot_list:
            bm_tokens = self._tokenize(bm)
            if not bm_tokens:
                continue

            bm_vec = self._tfidf_vector(group_id, bm_tokens)

            sim = self._cosine(user_vec, bm_vec)
            if sim > best:
                best = sim

            # 提前返回
            if sim >= self.early_stop:
                return sim

        return best
