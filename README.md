
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_wakepro?name=astrbot_plugin_wakepro&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_wakepro

_✨ 唤醒增强插件 ✨_  

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

WakePro 是 AstrBot 的高阶唤醒插件，把「能否唤醒」拆成 5 个可独立开关的阶梯，每一级都只干一件事，顺序可锁定也可自定义。  
阶梯顺序 = 配置里的 `pipeline.steps`，默认自上而下执行：

| 阶梯 | 配置键名 | 一句话职责 | 可关闭 | 对管理员可豁免 |
| ---- | -------- | ---------------- | ------ | -------------- |
| ① 名单过滤 | `list` | 先决定「谁有资格说话」 | ✅ | ✅ |
| ② 阻塞判断 | `block` | 再决定「当下能不能唤醒」 | ✅ | ✅ |
| ③ 指令屏蔽 | `cmd` | 避免「误把内置指令当聊天」 | ✅ | ✅ |
| ④ 智能唤醒 | `wake` | 真正开始「判断要不要唤醒」 | ✅ | ❌ |
| ⑤ 沉默检测 | `silence` | 唤醒后「被骂就闭嘴」 | ✅ | ❌ |

&gt; 想改顺序？把 `pipeline.lock_order` 设成 `false`，然后按 UI 列表拖拽即可。  
&gt; 想让管理员无视某一步？在 `pipeline.admin_steps` 里勾选对应阶梯即可。

---

### ① 名单过滤（list）

“大门保安”——先过滤掉机器人自己、QQ 官方机器人、黑名单用户/群，或只允许白名单通过。  
检查顺序：屏蔽自身 → 屏蔽 QQ 机器人 → 用户白名单 → 群白名单 → 用户黑名单 → 群黑名单。  
（任何一步命中就直接放行或拦截，不再往下走。）

### ② 阻塞判断（block）

“红绿灯”——如果消息里含屏蔽词、在唤醒 CD 内、或是复读 Bot 上一条消息，则直接拒绝唤醒。  

- 唤醒 CD 默认 0.5 s，每人独立计时，优先级最高。  
- 屏蔽复读默认开启，可防止“复读机”把 Bot 无限叫起。

### ③ 指令屏蔽（cmd）

“防误触”——把可能跟 AstrBot 内置指令冲突的消息提前拦掉。  
支持三种模式：  

- 屏蔽内置指令（如 /llm /tts …）  
- 屏蔽前缀指令（如 !help 不再触发插件指令）  
- 屏蔽前缀 LLM（如 !聊天 不再唤醒大模型）

### ④ 智能唤醒（wake）

“大脑决策”——所有前置关卡通过后，才真正判断“这句消息值不值得回”。  
可叠加 7 种信号，全部独立开关、阈值可调：  

1. 提及唤醒（@昵称）  
2. 相关性唤醒（与 Bot 最近 5 条消息做语义相似度）  
3. 答疑唤醒（检测到专业问句）  
4. 兴趣唤醒（自定义关键词包）  
5. 无聊唤醒（群聊低活跃）  
6. 唤醒延长（被唤醒后 N 秒内持续在线）  
7. 概率兜底（上面都没命中时，按固定概率随缘回）

### ⑤ 沉默检测（silence）

“自我保护”——**仅在唤醒后生效**。  
检测到“闭嘴、辱骂、人机”三类负面信号时，Bot 对该用户/群进入一段沉默时间，期间不再响应任何唤醒。  
沉默时长 = 触发阈值 × 倍数，阈值越低“玻璃心”越重。

---

### 附：消息防抖与缓存（跨阶梯通用）

- 用户级防抖锁：同一用户 0.3 s 内多条消息自动合并，减少 Token。  
- Bot 消息缓存：始终保留最近 5 条 Bot 发言，用于相关性计算与复读屏蔽。  

以上能力已内嵌，无需额外开关，跟随阶梯流程自动生效。

## 📦 安装

在astrbot的插件市场搜索astrbot_plugin_wakepro，点击安装即可

## ⌨️ 配置

请前往插件配置面板进行配置

## 🤝 使用说明

正常发消息即可生效

### 效果图

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
