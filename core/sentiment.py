# \astrbot\core\sentiment.py

import math
import re

import jieba

# 扩充jieba词典, 后续补充
jieba.add_word("傻逼")

class Sentiment:
    """
    高精度语义检测器 - 优化版词表
    """

    # 精简停用词表
    STOP = {
        "的",
        "了",
        "在",
        "是",
        "都",
        "就",
        "也",
        "和",
        "把",
        "我",
        "你",
        "他",
        "她",
        "它",
        "啊",
        "吧",
        "吗",
        "嘛",
    }

    # 闭嘴类关键词 - 按强度分级
    SHUT_WORDS = {
        # 强命令 (权重1.0, 强度1.8-2.0)
        "闭嘴": (1.0, 2.0),
        "住口": (1.0, 1.9),
        "安静": (1.0, 1.8),
        "shut up": (1.0, 2.0),
        "别说话": (1.0, 1.8),
        "别吵": (1.0, 1.8),
        "别出声": (1.0, 1.7),
        "别嚷嚷": (1.0, 1.7),
        # 中度命令 (权重0.9, 强度1.4-1.6)
        "安静点": (0.9, 1.5),
        "小点声": (0.9, 1.4),
        "别吵了": (0.9, 1.6),
        "别闹了": (0.8, 1.4),
        "别烦我": (0.8, 1.5),
        "别打扰": (0.8, 1.4),
        "别插嘴": (0.8, 1.5),
        # 弱表达 (权重0.7, 强度1.2-1.3)
        "太吵了": (0.7, 1.3),
        "吵死了": (0.7, 1.3),
        "好吵": (0.6, 1.2),
        "话多": (0.6, 1.2),
        "话痨": (0.6, 1.2),
        "少说点": (0.5, 1.1),
        "少说话": (0.5, 1.1),
    }

    # 侮辱类关键词 - 按严重程度分级
    INSULT_WORDS = {
        # 严重侮辱 (权重1.0, 强度1.9-2.0)
        "傻逼": (1.0, 2.0),
        "sb": (1.0, 1.9),
        "nmsl": (1.0, 2.0),
        "去死": (1.0, 2.0),
        "草泥马": (1.0, 1.9),
        "cnm": (1.0, 1.9),
        "废物": (1.0, 1.8),
        "垃圾": (1.0, 1.8),
        "脑残": (1.0, 1.8),
        "弱智": (1.0, 1.7),
        "智障": (1.0, 1.7),
        # 中度侮辱 (权重0.9, 强度1.5-1.6)
        "有病": (0.9, 1.6),
        "神经病": (0.9, 1.6),
        "白痴": (0.9, 1.6),
        "蠢货": (0.9, 1.5),
        "滚": (0.9, 1.7),
        "滚开": (0.9, 1.6),
        "滚蛋": (0.9, 1.7),
        "nt": (0.9, 1.6),
        "fw": (0.9, 1.6),
        "菜鸡": (0.8, 1.5),
        # 轻度侮辱 (权重0.7, 强度1.3-1.4)
        "憨憨": (0.7, 1.3),
        "笨": (0.6, 1.2),
        "呆": (0.6, 1.2),
        "猪": (0.7, 1.3),
        "没脑子": (0.8, 1.4),
        "没出息": (0.7, 1.3),
        "low": (0.7, 1.4),
    }

    # 无聊类关键词 - 按表达强度分级
    BORED_WORDS = {
        # 强烈表达 (权重1.0, 强度1.7-1.8)
        "无聊死了": (1.0, 1.8),
        "好无聊": (1.0, 1.7),
        "太无聊": (1.0, 1.7),
        "闷死了": (1.0, 1.7),
        "好没劲": (1.0, 1.6),
        "真没意思": (1.0, 1.6),
        "闲得慌": (1.0, 1.6),
        # 中度表达 (权重0.8, 强度1.4-1.5)
        "无聊": (0.8, 1.5),
        "好闲": (0.8, 1.4),
        "寂寞": (0.8, 1.4),
        "冷清": (0.8, 1.4),
        "空虚": (0.7, 1.3),
        "没人": (0.7, 1.3),
        "冷场": (0.8, 1.5),
        "死群": (0.8, 1.5),
        # 轻度表达 (权重0.6, 强度1.1-1.2)
        "有点闷": (0.6, 1.2),
        "没事做": (0.6, 1.1),
        "打发时间": (0.6, 1.1),
        "求聊天": (0.7, 1.3),
        "有人吗": (0.7, 1.4),
        "在吗": (0.5, 1.0),
        "滴滴": (0.5, 1.0),
    }

    # 提问类关键词 - 按提问明确度分级
    ASK_WORDS = {
        # 明确提问 (权重1.0, 强度1.7-1.8)
        "请问": (1.0, 1.8),
        "求解": (1.0, 1.8),
        "求教": (1.0, 1.7),
        "请教": (1.0, 1.7),
        "如何解决": (1.0, 1.8),
        "怎么处理": (1.0, 1.7),
        "怎么办": (1.0, 1.7),
        "为什么": (1.0, 1.6),
        "什么原因": (1.0, 1.6),
        "怎么回事": (1.0, 1.7),
        "谁能帮": (1.0, 1.7),
        # 一般提问 (权重0.9, 强度1.4-1.5)
        "怎么": (0.9, 1.5),
        "如何": (0.9, 1.5),
        "啥意思": (0.9, 1.5),
        "怎么做": (0.9, 1.6),
        "哪里": (0.8, 1.4),
        "哪个": (0.8, 1.4),
        "哪能": (0.8, 1.4),
        "有什么": (0.8, 1.4),
        "有没有": (0.8, 1.4),
        "会不会": (0.8, 1.4),
        "能不能": (0.8, 1.5),
        "可不可以": (0.8, 1.5),
        # 模糊提问 (权重0.7, 强度1.2-1.3)
        "什么": (0.7, 1.3),
        "啥": (0.7, 1.2),
        "呢": (0.5, 1.1),
        "吗": (0.5, 1.0),
        "谁懂": (0.8, 1.4),
        "谁知道": (0.8, 1.4),
        "有人会": (0.7, 1.3),
    }

    # 人机检测关键词 - 常见AI口癖
    AI_WORDS = {
        # 明显AI用语 (权重1.0, 强度1.8-2.0)
        "一个ai": (1.0, 2.0),
        "人工智能": (1.0, 2.0),
        "我是ai": (1.0, 1.9),
        "ai助手": (1.0, 1.8),
        "智能助手": (1.0, 1.8),
        # 常见AI口癖 (权重0.8-0.9, 强度1.4-1.6)
        "作为一个": (0.9, 1.5),
        "根据你的描述": (0.9, 1.5),
        "上下文": (0.8, 1.4),
        "抱歉": (0.8, 1.4),
        "模型": (0.9, 1.5),
        "不能保证": (0.8, 1.5),
        "无法提供": (0.8, 1.5),
        "无法回答": (0.8, 1.5),
        # 可疑AI特征 (权重0.6-0.7, 强度1.1-1.3)
        "理解": (0.7, 1.2),
        "希望": (0.7, 1.2),
        "请注意": (0.7, 1.2),
        "参考": (0.6, 1.1),
    }

    # 否定词表 - 用于降低可信度
    NEGATION_WORDS = {
        "不",
        "没",
        "无",
        "非",
        "否",
        "别",
        "不要",
        "不太",
        "不太想",
        "不想",
        "不至于",
        "算不上",
        "才不",
        "才不会",
    }

    # 反问词表 - 可能改变语义
    RHETORICAL_WORDS = {"难道", "何必", "怎么可以", "怎么可能", "哪能", "岂能", "谁还"}

    @classmethod
    def _seg(cls, text: str) -> list:
        """分词并保留位置信息"""
        text = re.sub(r"[^\w\s\u4e00-\u9fa5]", "", text.lower())
        words = []
        for word in jieba.lcut(text):
            if word.strip() and word not in cls.STOP:
                words.append(word)
        return words

    @classmethod
    def _calculate_confidence(cls, words: list, keyword_dict: dict) -> float:
        """计算语义可信度"""
        # 1. 基础匹配分数
        base_score = 0
        matched_keywords = []

        # 检查反问表达
        has_rhetorical = any(r_word in words for r_word in cls.RHETORICAL_WORDS)

        for i, word in enumerate(words):
            if word in keyword_dict:
                weight, intensity = keyword_dict[word]

                # 检查否定词
                has_negation = any(
                    neg_word in words[max(0, i - 3) : i]
                    for neg_word in cls.NEGATION_WORDS
                )

                # 否定词降低权重
                if has_negation:
                    weight *= 0.3
                    intensity *= 0.5
                # 反问句可能反转语义
                elif has_rhetorical:
                    weight *= 0.7
                    intensity *= 0.8

                base_score += weight * intensity
                matched_keywords.append(word)

        # 2. 上下文增强分数
        context_score = 0
        if matched_keywords:
            # 关键词密度增强
            density = len(matched_keywords) / len(words) if words else 0
            context_score += min(1.0, density * 5) * 0.5

            # 关键词组合增强
            if len(matched_keywords) > 1:
                context_score += min(1.0, (len(matched_keywords) - 1) * 0.4)

        # 3. 总分数计算
        total_score = base_score + context_score

        # 4. 应用Sigmoid函数转换为概率值
        confidence = 1 / (1 + math.exp(-4 * (total_score - 1.5)))

        # 5. 上限控制
        return min(0.99, confidence)

    # 对外接口
    @classmethod
    def shut(cls, text: str) -> float:
        """判断是否要闭嘴"""
        words = cls._seg(text)
        return cls._calculate_confidence(words, cls.SHUT_WORDS)

    @classmethod
    def insult(cls, text: str) -> float:
        """判断是否辱骂"""
        words = cls._seg(text)
        return cls._calculate_confidence(words, cls.INSULT_WORDS)

    @classmethod
    def bored(cls, text: str) -> float:
        """判断是否无聊"""
        words = cls._seg(text)
        return cls._calculate_confidence(words, cls.BORED_WORDS)

    @classmethod
    def ask(cls, text: str) -> float:
        """判断是否疑惑"""
        words = cls._seg(text)
        return cls._calculate_confidence(words, cls.ASK_WORDS)

    @classmethod
    def is_ai(cls, text: str) -> float:
        """
        判断是否为AI口吻
        """
        words = cls._seg(text)
        return cls._calculate_confidence(words, cls.AI_WORDS)
