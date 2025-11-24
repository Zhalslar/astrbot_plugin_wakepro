
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_wakepro?name=astrbot_plugin_wakepro&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_wakepro

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot)唤醒增强插件 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

# ❗❗更新到v1.1.4+的用户请注意，v1.1.4重构了相关度的算法，相关性唤醒的阈值变化会更平缓，请重新根据bot发言频率调整阈值

## 🤝 介绍

WakePro 是一款针对 Astrbot 的 **高级唤醒增强插件**，通过引入多源信号判断、情绪识别、消息合并与防误触机制，让 Bot 的唤醒更聪明、更稳定、更不容易被干扰。

插件提供了以下扩展能力：

### 🎯 更智能的触发判定

- ⏳ **唤醒 CD**：为每个群成员独立维护冷却时间，避免连续触发  
- 📢 **提及唤醒**：当用户提到 bot 的昵称或关键词时主动唤醒  
- ⏰ **唤醒延长**：在被激活后的一段时间内持续保持活跃  
- 🧩 **相关性唤醒**：根据用户消息与 bot 最近 5 条回复的语义相关度智能判断唤醒  
- ❓ **答疑唤醒**：识别问句或强疑问情绪时主动回应  
- 😐 **无聊唤醒**：在群聊低互动时提供轻度回应  
- 🎲 **概率唤醒**：支持按概率触发，增加轻量互动性  

### 🛡️ 更稳态的抗噪机制

- 🚫 **唤醒屏蔽词**：包含指定词语时直接忽略唤醒  
- 🤐 **闭嘴机制**：收到“闭嘴”类内容时可进入群级静默期  
- 😡 **辱骂沉默**：检测到辱骂性内容时自动对发送者静默一定时间  
- 👤 **人机屏蔽**：检测人机句式，防止因 AI 或自动回复导致误唤醒  
- 🛑 **内置指令屏蔽**：避免触发 Astrbot 内置命令时错误唤醒
- 🛑 **前缀屏蔽**：支持屏蔽以特定前缀开头的指令或非指令消息（LLM）

### 📬 更实用的消息管控

- 📨 **消息合并防抖**：短时间内多条消息会自动合并一次性提交给 LLM，减少 token 消耗与重复触发  
- 🔒 **用户级防抖锁**：每个用户有独立锁，确保高并发下行为正确  
- 📚 **Bot 消息缓存**：自动维护最近 5 条 bot 消息用于相关性判断  
- 🚷 **复读屏蔽**：复读 bot 自己的消息时不会触发唤醒  

## 📦 安装

- 直接在astrbot的插件市场搜索astrbot_plugin_wakepro，点击安装，等待完成即可

- 也可以克隆源码到插件文件夹：

```bash
# 克隆仓库到插件目录
cd /AstrBot/data/plugins
git clone https://github.com/Zhalslar/astrbot_plugin_wakepro

# 控制台重启AstrBot
```

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
