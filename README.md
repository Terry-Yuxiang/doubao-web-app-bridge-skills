# doubao-web-app-bridge-skills

让 AI 智能体（AI Agent）通过浏览器自动化直接操控**豆包（doubao.com）网页版**，实现消息发送、回复读取、对话持久化与继续对话。

适用于 Claude Code、OpenClaw、Cursor Agent、任何支持 bash 工具调用的 AI Agent 框架，以及自定义的 Agentic Workflow。

---

## 解决什么问题

AI Agent 在执行长任务时经常需要：
- 把某个子问题转发给外部 AI（豆包）获取第二意见
- 在不同 AI 之间路由问题，节省主模型 token
- 将与豆包的完整对话持久化，供后续 Agent 会话复用

这个 skill 通过 **Chrome DevTools Protocol（CDP）** 直接操控浏览器，无需 API Key，无需破解任何接口，就像人类操作网页一样。

---

## 核心能力

| 能力 | 说明 |
|---|---|
| **probe** | 检查浏览器是否连接、页面状态 |
| **ask** | 向豆包发送一条消息 |
| **read** | 读取当前页面末尾内容（获取回复） |
| **navigate** | 跳转到已保存的对话继续追问 |
| **store** | 将完整对话保存为 JSONL + Markdown |
| **路由模式** | 开启后所有 Agent 消息自动转发给豆包 |

---

## 前置条件

- macOS + Google Chrome
- Chrome 以 CDP 模式启动：
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/doubao-cdp-profile
  ```
- 在该浏览器中打开 `https://www.doubao.com/chat/` 并登录
- Python 3 + `pip install websockets`

---

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# 验证连接
python scripts/doubao_web_probe.py probe

# 发送消息
python scripts/doubao_web_probe.py ask --question "你好，豆包"
sleep 8
python scripts/doubao_web_probe.py read

# 保存对话
python scripts/doubao_conversation_store.py --export-md --project my-project
```

完整验证流程见 `references/install.md`。

---

## 在 AI Agent 中集成

### Claude Code / OpenClaw / Cursor Agent

项目根目录包含 `SKILL.md`（skill 定义）和 `.claude/commands/doubao.md`（slash command），支持直接作为 skill 加载。

使用 `/doubao` slash command：

```
/doubao +用一句话解释什么是大语言模型
/doubao conversation list
/doubao conversation 大语言模型 +继续上次的话题
/doubao start   ← 开启路由模式，后续所有消息转发豆包
/doubao end
```

### 通用 Agentic Workflow

直接调用脚本，无框架依赖：

```bash
# Agent 决定转发问题给豆包
python scripts/doubao_web_probe.py ask --question "$QUESTION"
sleep 8
REPLY=$(python scripts/doubao_web_probe.py read)

# 保存，供下一个 Agent 会话复用
python scripts/doubao_conversation_store.py --export-md
```

---

## 对话管理

```bash
# 列出所有已保存对话
python scripts/doubao_conversation_store.py --list

# 模糊搜索
python scripts/doubao_conversation_store.py --find "大语言模型"

# 加标签（方便缩写搜索）
python scripts/doubao_conversation_store.py --tag 38418062 LLM AI

# 导航继续对话
python scripts/doubao_web_probe.py navigate --chat-id 38418062256168706
sleep 4
python scripts/doubao_web_probe.py ask --question "继续上次的话题"
```

---

## 技术实现要点

### 输入触发

豆包使用字节跳动 semi-design 组件库，输入框是 React 托管的 `<textarea>`。普通 DOM 事件无法触发 React 状态更新。

解法：通过 `element.__reactProps.onChange()` 调用 React 内部事件处理器，确保 send 按钮正常激活。此方案已在实际测试中验证稳定。

### DOM 提取

不调用任何后端 API，直接读取渲染好的 DOM：

| 元素 | 选择器 |
|---|---|
| 输入框 | `[data-testid="chat_input_input"]` |
| 发送按钮 | `[data-testid="chat_input_send_button"]` |
| 用户消息 | `[data-testid="send_message"]` |
| AI 回复 | `[data-testid="receive_message"]` |
| 对话 URL | `https://www.doubao.com/chat/{数字ID}` |

### navigate 等待

导航到已保存对话后需等待约 4 秒让页面完全渲染，脚本和 slash command 均已内置此逻辑。navigate 到具体对话 URL 需要已登录豆包账号。

### 对话存储

所有对话存储在 **skills 目录之外**，升级或删除 skills 不会丢失数据：

```
~/.ai-bridge/doubao-bridge/conversations/
  {标题slug}--{chatId}/
    meta.json           ← chatId、标题、URL、保存时间、标签
    conversation.jsonl  ← 每条消息一行 JSON
    conversation.md     ← LLM 可读的 Markdown（Round/User/Assistant 层级）
```

重复保存安全，自动去重，只追加新轮次。

---

## 已验证工作流

以下完整流程已实测通过：

1. ✅ probe — 正确识别豆包页面和输入框
2. ✅ ask × 3 轮 — React state 正确更新，消息稳定发送
3. ✅ store 增量保存 — 去重逻辑正常，只追加新轮次
4. ✅ navigate + continue — 登录后跳转恢复对话正常
5. ✅ Markdown 导出 — Round/User/Assistant 层级结构正确

---

## 与其他 Bridge Skills 的关系

本项目是 `~/.ai-bridge/` 多 AI 桥接体系的一部分：

```
~/.ai-bridge/
  claude-bridge/conversations/    ← claude-code-web-app-bridge-skills
  chatgpt-bridge/conversations/   ← chatgpt-web-app-bridge-skills
  doubao-bridge/conversations/    ← 本项目
  gemini-bridge/conversations/    ← (计划中)
```

各 bridge skill 使用相同的存储格式和 slash command 风格，可以跨 AI 对比回答、路由问题。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Terry-Yuxiang/doubao-web-app-bridge-skills&type=Date)](https://star-history.com/#Terry-Yuxiang/doubao-web-app-bridge-skills&Date)

---

## 注意事项

- 需要登录豆包账号才能 navigate 到已保存对话
- navigate 后必须等待 4 秒再调用 ask
- Chrome 必须以 `--remote-debugging-port=9222` 启动
- Agent 执行时直接调用 bash 脚本，不要通过 Skill tool 间接调用 `/doubao`
