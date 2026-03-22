# doubao-web-app-bridge-skills

一个 **Claude Code Skill**，通过 Chrome DevTools Protocol（CDP）操控浏览器里的豆包网页版，让 Claude Code 智能体能够向豆包发送消息、读取回复、保存对话，并在未来继续已保存的对话。

## 功能

- 在 Claude Code 会话中向豆包发送消息
- 将豆包的回复读回智能体上下文
- 将完整对话保存为 JSONL + Markdown（含代码块）
- 导航到已保存的对话继续追问
- 路由模式：通过 `/doubao start` / `/doubao end` 将所有消息转发给豆包

## 工作原理

### 消息发送

豆包使用字节跳动内部的 semi-design 组件库，输入框是 React 托管的 `<textarea>`。直接设置 `.value` 不会触发 React 状态更新，send 按钮不会出现。

解决方案：通过 `element.__reactProps.onChange()` 直接调用 React 的内部事件处理器，确保 React state 正确更新，send 按钮正常激活。

### 消息提取

直接读取渲染好的 DOM，不依赖任何后端 API：

| 元素 | 选择器 |
|---|---|
| 输入框 | `[data-testid="chat_input_input"]` |
| 发送按钮 | `[data-testid="chat_input_send_button"]` |
| 用户消息 | `[data-testid="send_message"]` |
| AI 回复 | `[data-testid="receive_message"]` |
| 消息正文 | `[data-testid="message_text_content"]` |
| 对话 URL | `https://www.doubao.com/chat/{纯数字ID}` |

### navigate 注意事项

导航到已保存对话后，豆包页面需要约 4 秒完成渲染才能正常使用输入框。脚本和 slash command 均已内置此等待时间。导航到具体对话 URL 需要已登录豆包账号。

## 前置条件

- macOS + Google Chrome
- 启动带 CDP 的 Chrome：
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/doubao-cdp-profile
  ```
- 在该浏览器中打开 `https://www.doubao.com/chat/` 并登录
- Python 3

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 目录结构

```
.claude/commands/
  doubao.md              ← /doubao slash command 定义
references/
  install.md             ← 完整安装与验证步骤
  bridge-patterns.md     ← context packet 模板和 prompt 模式
  conversation-continuation.md  ← 恢复已保存对话的完整流程
scripts/
  doubao_web_probe.py    ← CDP 底层操作：probe / ask / read / navigate
  doubao_conversation_store.py  ← 对话持久化：JSONL + meta + MD
  bridge_config.py       ← 读取配置文件
config.example.json      ← 配置模板
state.json               ← 当前路由模式和活跃对话
SKILL.md                 ← Claude Code skill 定义文件
```

## Slash Command 用法

| 命令 | 效果 |
|---|---|
| `/doubao start` | 开启路由模式，后续所有消息转发给豆包 |
| `/doubao end` | 关闭路由模式 |
| `/doubao +<消息>` | 单条消息转发给豆包 |
| `/doubao conversation list` | 列出所有已保存的对话 |
| `/doubao conversation <名称> +<消息>` | 导航到指定对话并发消息 |

`<名称>` 支持模糊匹配：关键词、缩写均可。

## 脚本说明

### `doubao_web_probe.py`

CDP 底层操作：

```bash
. .venv/bin/activate

# 检查页面状态
python scripts/doubao_web_probe.py probe

# 发送消息
python scripts/doubao_web_probe.py ask --question "你的问题"

# 读取页面末尾内容
python scripts/doubao_web_probe.py read

# 导航到已保存对话
python scripts/doubao_web_probe.py navigate --chat-id <chatId>
python scripts/doubao_web_probe.py navigate --url https://www.doubao.com/chat/<chatId>
```

### `doubao_conversation_store.py`

将当前豆包对话保存到 `~/.ai-bridge/doubao-bridge/conversations/`（存储在 skills 目录之外，升级或删除 skills 不会丢失）：

```bash
python scripts/doubao_conversation_store.py --export-md --project my-project
```

输出：`~/.ai-bridge/doubao-bridge/conversations/{slug}--{chatId}/conversation.jsonl`、`meta.json`、`conversation.md`

重复运行安全——只追加新轮次，已有消息自动去重。

搜索和管理：

```bash
python scripts/doubao_conversation_store.py --list
python scripts/doubao_conversation_store.py --find "关键词"
python scripts/doubao_conversation_store.py --tag <chatId前缀> 标签1 标签2
```

## 快速验证

```bash
. .venv/bin/activate
python scripts/doubao_web_probe.py probe
python scripts/doubao_web_probe.py ask --question "回复：DOUBAO_BRIDGE_OK"
sleep 8
python scripts/doubao_web_probe.py read
python scripts/doubao_conversation_store.py --export-md --project bridge-testing
```

完整验证步骤见 `references/install.md`。

## 对话 Markdown 格式

```markdown
# 对话标题

| Field | Value |
|---|---|
| Chat ID | `38418062256168706` |
| Turns | 3 |

---
# Round 1

## User

用一句话解释什么是大语言模型

## Assistant

大语言模型是基于海量文本数据训练……
```

## config.json 配置项

```json
{
  "doubaoBridge": {
    "enabled": true,
    "autoBridgeAllowed": false,
    "defaultMode": "diagnosis",
    "useDoubaoWeb": true,
    "requireRealResponse": true,
    "conversationsDir": "~/.ai-bridge/doubao-bridge/conversations"
  }
}
```

- `autoBridgeAllowed` — 为 `true` 时智能体可自动调用豆包处理长任务
- `requireRealResponse` — 不允许将本地猜测伪装成豆包的回复
- `conversationsDir` — 自定义对话存储路径

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Terry-Yuxiang/doubao-web-app-bridge-skills&type=Date)](https://star-history.com/#Terry-Yuxiang/doubao-web-app-bridge-skills&Date)

## 注意事项

- 需要登录豆包账号才能 navigate 到已保存的对话 URL
- navigate 后必须等待 4 秒页面渲染完毕再调用 ask
- Chrome 必须以 `--remote-debugging-port=9222` 启动
- 作为 AI 智能体运行时：直接执行 bash 命令，不要通过 Skill tool 调用 `/doubao`
