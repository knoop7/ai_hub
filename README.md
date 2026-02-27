<h1 align="center">AI Hub · 一站式免费AI服务</h1>
<h1 align="center">AI Hub · One-stop Free AI Services</h1>
<p align="center">
  为了让你体验各种免费的AI服务，本集成不支持任何收费模型及服务，当然你可能会需要申请账号或创建 API Key。<br>
  <strong>开篇致谢：</strong>前人栽树，后人乘凉。没有 <a href="https://github.com/knoop7" target="_blank">knoop7</a> 和 <a href="https://github.com/rany2/edge-tts" target="_blank">edge-tts</a> 这两个项目，就没有本集成，特此感谢！<br><br>
  To experience various free AI services, this integration does not support any paid models or services. You may need to register an account or create an API Key.<br>
  <strong>Special Thanks:</strong> We stand on the shoulders of giants. Without <a href="https://github.com/knoop7" target="_blank">knoop7</a> and <a href="https://github.com/rany2/edge-tts" target="_blank">edge-tts</a>, this project would not exist!
</p>

<p align="center">
  <a href="https://github.com/ha-china/ai_hub/releases"><img src="https://img.shields.io/github/v/release/ha-china/ai_hub" alt="GitHub Version"></a>
  <a href="https://github.com/ha-china/ai_hub/issues"><img src="https://img.shields.io/github/issues/ha-china/ai_hub" alt="GitHub Issues"></a>
  <img src="https://img.shields.io/github/forks/ha-china/ai_hub?style=social" alt="GitHub Forks">
  <img src="https://img.shields.io/github/stars/ha-china/ai_hub?style=social" alt="GitHub Stars">
</p>

---

## 📋 目录 / Table of Contents

- [🔧 前置条件 / Prerequisites](#🔧-前置条件--prerequisites)
- [🌟 功能介绍 / Features](#🌟-功能介绍--features)
- [📦 安装方法 / Installation](#📦-安装方法--installation)
- [🚀 快速开始 / Quick Start](#🚀-快速开始--quick-start)
- [🔑 账号注册与Token获取 / Account Registration & Token](#🔑-账号注册与token获取--account-registration--token)
- [📖 使用指南 / Usage Guide](#📖-使用指南--usage-guide)
- [🔧 服务调用详解 / Service Details](#🔧-服务调用详解--service-details)
- [⚙️ 参数配置 / Configuration](#⚙️-参数配置--configuration)
- [⚠️ 注意事项 / Notes](#⚠️-注意事项--notes)
- [🛠️ 故障排除 / Troubleshooting](#🛠️-故障排除--troubleshooting)
- [🤝 参与贡献 / Contributing](#🤝-参与贡献--contributing)
- [📄 许可协议 / License](#📄-许可协议--license)
- [📱 关注我 / Follow Me](#📱-关注我--follow-me)
- [☕ 赞助支持 / Support](#☕-赞助支持--support)

---

## 🔧 前置条件 / Prerequisites

- **Home Assistant**: 2025.8.0 或更高版本 / 2025.8.0 or higher
- **网络要求 / Network**: 本集成完全依赖互联网服务，稳定的网络连接是必需的 / This integration relies entirely on internet services; a stable network connection is required

---

## 🌟 功能介绍 / Features

AI Hub 是 Home Assistant 的自定义集成，提供与硅基流动、巴法云的原生对接。

AI Hub is a custom integration for Home Assistant, providing native connections to SiliconFlow and Bemfa.

> **提示**: 如果有些条目你不需要，只需不填 API Key 即可，或者直接删除，后续有需要可以再次添加。
> 
> **Tip**: If you don't need some entries, just leave the API key blank or delete it. You can add it back later when needed.

### 核心功能 / Core Features

#### 🗣️ 对话助手 / Conversation Assistant

| 中文 | English |
|------|---------|
| **流式输出**: 实时显示模型回复，提供流畅的对话体验 | **Streaming Output**: Real-time display of model replies for a smooth conversational experience |
| **家居控制**: 对接 Home Assistant LLM API，支持控制/查询设备 | **Home Control**: Integrates with Home Assistant LLM API to control/query devices |
| **图片理解**: 消息携带图片时自动切换到视觉模型（GLM-4.1V-9B-Thinking） | **Image Understanding**: Automatically switches to vision model (GLM-4.1V-9B-Thinking) when message contains an image |
| **上下文记忆**: 可配置历史消息条数，平衡效果与性能 | **Context Memory**: Configurable number of history messages to balance effect and performance |

#### 🤖 AI 任务 / AI Tasks

| 中文 | English |
|------|---------|
| **结构化数据生成**: 指定 JSON 结构，失败提供错误提示 | **Structured Data Generation**: Specify JSON structure, with error prompts on failure |
| **图片生成**: 使用 Kolors 等模型生成图片，支持 URL 或 base64 返回 | **Image Generation**: Generate images using Kolors and other models, supporting URL or base64 result |
| **多模态支持**: 复用对话消息格式，便于复杂任务处理 | **Multimodal Support**: Reuses conversation message format for complex tasks |

#### 🔊 语音合成 / TTS (Edge TTS)

| 中文 | English |
|------|---------|
| **高质量语音**: 集成微软 Edge TTS，支持多语言、多风格 | **High-Quality Voice**: Integrates Microsoft Edge TTS, supporting multiple languages and styles |
| **丰富语音库**: 支持晓晓、云健、Aria、Jenny 等 400+ 种语音模型 | **Rich Voice Library**: Supports 400+ voices including Xiaoxiao, Yun Jian, Aria, Jenny, and more |
| **Prosody 参数**: 支持语速(rate)、音量(volume)、音调(pitch)调节 | **Prosody Parameters**: Supports rate, volume, and pitch adjustments |
| **流式输出**: 支持流式 TTS 输出，适合 LLM 对话场景 | **Streaming Output**: Supports streaming TTS output for LLM conversation scenarios |
| **多种格式**: 输出 MP3 格式音频 | **Audio Format**: Outputs MP3 format audio |

#### 🎤 语音识别 / STT (SiliconFlow)

| 中文 | English |
|------|---------|
| **高精度识别**: 集成硅基流动语音识别服务，支持 SenseVoice、TeleSpeechASR 等模型 | **High Accuracy Recognition**: Integrates SiliconFlow speech recognition service, supporting SenseVoice, TeleSpeechASR and more models |
| **自动语言检测**: 自动识别中文、英文、日文、韩文等多种语言，无需手动指定 | **Auto Language Detection**: Automatically detects Chinese, English, Japanese, Korean, and other languages without manual specification |
| **格式兼容**: 支持 WAV/MP3/FLAC/M4A/OGG/WebM 等多种音频格式 | **Format Compatibility**: Supports WAV/MP3/FLAC/M4A/OGG/WebM and other audio formats |
| **实时处理**: 适合语音控制、Voice Assistant 等场景 | **Real-Time Processing**: Suitable for voice control, Voice Assistant, and other scenarios |

#### 🌐 HACS 集成汉化 / HACS Integration Localization

| 中文 | English |
|------|---------|
| **自动翻译**: 使用AI自动翻译自定义组件的英文翻译文件为中文 | **Auto Translation**: Use AI to automatically translate custom component English translation files to Chinese |
| **批量处理**: 支持批量处理多个组件的汉化工作 | **Batch Processing**: Supports batch localization for multiple components |
| **智能识别**: 自动识别需要翻译的组件，跳过已存在中文翻译的文件 | **Intelligent Recognition**: Automatically detects components needing translation, skipping already localized ones |

#### 🏗️ Blueprint 蓝图汉化 / Blueprint Localization

| 中文 | English |
|------|---------|
| **一键汉化**: 在集成界面中添加"蓝图汉化"按钮，一键完成所有blueprints的汉化 | **One-Click Localization**: Add "Blueprint Localization" button in the integration interface for one-click translation of all blueprints |
| **原位翻译**: 直接修改原始blueprint文件，不产生额外翻译文件 | **In-Place Translation**: Directly modify original blueprint files without creating additional translation files |
| **智能保护**: 自动保护技术参数和变量，只翻译用户界面文本 | **Smart Protection**: Automatically protect technical parameters and variables, only translating user interface text |
| **递归扫描**: 自动扫描blueprints目录及其子目录中的所有YAML文件 | **Recursive Scanning**: Automatically scan blueprints directory and its subdirectories for all YAML files |
| **状态检测**: 智能检测已汉化文件，避免重复翻译 | **Status Detection**: Intelligently detect already localized files to avoid duplicate processing |
| **完整支持**: 支持复杂的嵌套结构和Home Assistant特殊语法 | **Complete Support**: Support complex nested structures and Home Assistant special syntax |

#### 📱 微信消息推送 / WeChat Notification (Bemfa)

| 中文 | English |
|------|---------|
| **实时通知**: 集成巴法云服务，通过微信发送设备状态通知 | **Real-Time Notifications**: Integrate Bemfa service to send device status notifications via WeChat |

---

## 📦 安装方法 / Installation

### 方法一：HACS 安装（推荐） / Method 1: HACS Installation (Recommended)

1. **打开 HACS**: 在 Home Assistant 中进入 HACS → 集成 / In Home Assistant, go to HACS → Integrations
2. **搜索集成**: 点击右上角的"探索与下载 repositories"，搜索"ai_hub" / Click "Explore & Download Repositories" in the upper right, search for "ai_hub"
3. **安装集成**: 找到"AI Hub"并点击下载 / Find "AI Hub" and click Download
4. **重启系统**: 重启 Home Assistant 使集成生效 / Restart Home Assistant to activate

### 方法二：手动安装 / Method 2: Manual Installation

1. **下载文件**: 从 [GitHub Releases](https://github.com/ha-china/ai_hub/releases) 下载最新版本的 `ai_hub.zip` / Download the latest `ai_hub.zip` from GitHub Releases
2. **解压文件**: 将 zip 文件解压到 `<HA_CONFIG>/custom_components/ai_hub/` 目录 / Unzip to `<HA_CONFIG>/custom_components/ai_hub/`
3. **重启系统**: 重启 Home Assistant / Restart Home Assistant

> **提示**: 本集成依赖新版的 Conversation/AI Task/子条目框架，建议使用较新的 Home Assistant 版本（>2025.8.0）。
> 
> **Tip**: This integration depends on the new Conversation/AI Task/Entry framework; a newer Home Assistant version (>2025.8.0) is recommended.

---

## 🚀 快速开始 / Quick Start

### 配置向导 / Configuration Wizard

1. **添加集成**: 进入 设置 → 设备与服务 → 集成 → 添加集成，搜索"AI HUB（ai_hub）" / Go to Settings → Devices & Services → Integrations → Add Integration, search "AI HUB (ai_hub)"
2. **配置 API Keys**: 按照向导提示依次配置以下服务 / Follow the wizard to configure:
   - 硅基流动 API Key（用于对话、AI任务、STT）/ SiliconFlow API Key (for Conversation, AI Task, and STT)
   - 巴法云私钥UID（用于微信消息推送）/ Bemfa API Key (for WeChat messages)
3. **验证配置**: 系统会自动验证 API Keys 的有效性 / System will verify your API Keys
4. **完成设置**: 配置完成后，集成会自动创建相应的服务和实体 / Integration will auto-create relevant services and entities

### 子条目配置 / Sub-Entry Configuration

AI Hub 支持子条目配置，可以为不同功能创建独立的配置：

AI Hub supports sub-entry configuration for independent functionality:

| 中文 | English |
|------|---------|
| **AI Hub对话助手**: 用于 Assist 对话代理 | **AI Hub Conversation**: For Assist agents |
| **AI Hub AI任务**: 用于图片生成和结构化数据 | **AI Hub AI Task**: For image generation and structured data |
| **AI Hub TTS语音**: 用于文本转语音 | **AI Hub TTS**: For text-to-speech |
| **AI Hub STT语音**: 用于语音转文本 | **AI Hub STT**: For speech-to-text |
| **AI Hub 微信通知**: 用于微信消息推送 | **AI Hub WeChat Notification**: For WeChat messages |
| **AI Hub 集成汉化**: 用于集成汉化 | **AI Hub Localization**: For component translation |
| **AI Hub 蓝图汉化**: 用于蓝图汉化 | **AI Hub Blueprint Localization**: For blueprint translation |

---

## 🔑 账号注册与Token获取 / Account Registration & Token

### 硅基流动 / SiliconFlow

| 项目 | 内容 |
|------|------|
| **用途 / Usage** | 对话助手、AI任务、语音识别 / Conversation, AI Tasks, STT |
| **注册地址 / Register** | [点击注册 / Sign Up Here](https://cloud.siliconflow.cn/i/U3e0rmsr) |

**获取 API Key / Get API Key:**
1. 完成注册并登录 / Register and login
2. 进入控制台 / Go to the dashboard
3. 在 [API密钥管理](https://cloud.siliconflow.cn/account/ak) 页面创建新的 API Key / Create new API Key in the API Key Management page
4. 复制生成的 API Key / Copy your new API Key

### 巴法云 / Bemfa

| 项目 | 内容 |
|------|------|
| **用途 / Usage** | 微信消息推送 / WeChat Notification |
| **注册地址 / Register** | [点击注册 / Sign Up Here](http://www.cloud.bemfa.com/u_register.php) |

**获取设备主题 / Get Device Topic:**
1. 完成注册并登录 / Register and login
2. 进入 [TCP设备管理](https://cloud.bemfa.com/tcp/index.html) / Go to TCP Device Management
3. 复制巴法云私钥 / Copy the device topic

> **注意**: Edge TTS 使用微软官方免费接口，不需要单独的 API Key。
> 
> **Note**: Edge TTS uses the official Microsoft free API; no API Key is required.

---

## 📖 使用指南 / Usage Guide

### A. 对话助手使用 / Conversation Assistant

#### 基础对话 / Basic Conversation

1. **切换代理**: 在 Assist 对话页面，将当前代理切换为"AI Hub对话助手" / In Assist, set agent to "AI Hub Conversation"
2. **开始对话**: 直接输入或说出问题，如 / Input/speak questions such as:
   - "打开客厅灯到 60%" / "Turn on the living room light to 60%"
   - "帮我总结今天日程" / "Summarize my schedule for today"
   - "设置一个明早8点的闹钟" / "Set an alarm for 8 AM tomorrow"

#### 图片理解 / Image Understanding

1. **上传图片**: 在支持的前端上传图片或引用摄像头图片 / Upload images or use camera snapshots in a supported frontend
2. **描述问题**: 输入对图片的描述或问题 / Input what you want to ask/analyze about the image
3. **获取分析**: 模型会自动进行视觉分析并回答 / The model analyzes and responds automatically

#### 工具调用 / Tool Invocation

- **启用工具**: 在对话助手子条目中启用"LLM Hass API" / Enable "LLM Hass API" in the conversation sub-entry
- **控制设备**: 模型可以调用 Home Assistant 工具来控制设备或查询状态 / The model can call Home Assistant APIs to control/query devices

### B. AI 任务使用 / AI Tasks

#### 图片生成 / Image Generation

通过自动化或服务调用生成图片：

Generate images via automation or service invocation:

```yaml
automation:
  - alias: "生成每日图片 / Generate daily picture"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: ai_hub.generate_image
        data:
          prompt: "美丽的日出风景 / Beautiful sunrise landscape"
          size: "1024x1024"
          model: "Kwai-Kolors/Kolors"
```

#### 结构化数据生成 / Structured Data Generation

生成指定格式的结构化数据：

Generate formatted JSON data:

```yaml
# 调用AI任务生成JSON数据 / Call AI task to generate JSON data
service: ai_hub.ai_task
data:
  input: "帮我生成一个包含姓名、年龄、职业的JSON格式数据 / Generate a JSON including name, age, and occupation"
  model: "Qwen/Qwen3-8B"
  temperature: 0.3
```

### C. TTS 语音合成 / Text to Speech

#### 实体方式 / As Entity

1. **选择TTS**: 在媒体播放器中选择"AI Hub TTS语音"作为语音服务 / In a media player, select "AI Hub TTS"
2. **输入文本**: 输入要合成的文本内容 / Enter your text
3. **播放语音**: 系统会自动播放合成的语音 / It will be played automatically

#### 服务调用 / As Service

```yaml
service: ai_hub.tts_speech
data:
  text: "欢迎使用AI Hub语音合成服务 / Welcome to AI Hub voice synthesis"
  voice: "zh-CN-XiaoxiaoNeural"
  pitch: "+0Hz"    # 音调调节，如 "+5Hz" 或 "-5Hz" / Pitch adjustment
  rate: "+0%"      # 语速调节，如 "+10%" 或 "-10%" / Speed adjustment
  volume: "+0%"    # 音量调节，如 "+10%" 或 "-10%" / Volume adjustment
  media_player_entity: media_player.living_room_speaker
```

### D. STT 语音识别 / Speech to Text

#### 实体方式 / As Entity

1. **选择STT**: 在麦克风设置中选择"AI Hub STT语音" / In microphone settings, select "AI Hub STT"
2. **开始录音**: 点击录音按钮开始语音输入 / Start recording
3. **获取文本**: 系统会自动将语音转换为文本 / Speech will be converted to text

#### 服务调用 / As Service

```yaml
service: ai_hub.stt_transcribe
data:
  file: "/config/tmp/recording.wav"
  model: "FunAudioLLM/SenseVoiceSmall"
```

### E. 微信消息推送 / WeChat Notification

```yaml
automation:
  - alias: "门窗打开通知 / Notify if door/window opens"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: ai_hub.send_wechat_message
        data:
          device_entity: binary_sensor.front_door
          message: "前门已打开，请注意安全！ / Front door opened, please pay attention!"
```

### F. 集成汉化 / Localization

```yaml
service: ai_hub.translate_components
data:
  custom_components_path: "custom_components"  # 可选 / Optional, default path
  force_translation: false  # 是否强制重新翻译 / Force re-translate
```

### G. Blueprint 蓝图汉化 / Blueprint Localization

#### 一键汉化（推荐）/ One-Click Localization (Recommended)

1. **添加蓝图汉化子条目**: 在 AI Hub 集成详情页，点击"添加子条目"，选择"AI Hub 蓝图汉化" / In AI Hub integration details page, click "Add Sub-Entry" and select "AI Hub Blueprint Localization"
2. **一键汉化**: 在集成详情页点击"蓝图汉化"按钮 / Click the "Blueprint Localization" button in the integration details page

系统会自动 / The system will automatically:
- 扫描 `/config/blueprints` 目录及其子目录中的所有 YAML 文件
- 智能识别已汉化文件，跳过重复处理
- 保护技术参数、变量名和 Home Assistant 语法
- 直接在原文件上进行汉化，不产生额外文件

#### 服务调用汉化 / Service-Based Localization

```yaml
# 列出所有 Blueprint 文件及其汉化状态 / List all Blueprint files and their status
service: ai_hub.translate_blueprints
data:
  list_blueprints: true  # 仅列出状态，不执行汉化 / Only list status
  target_blueprint: ""  # 留空表示查看所有 / Leave empty to view all
  force_translation: false

# 汉化指定的 Blueprint 文件 / Localize specific Blueprint file
service: ai_hub.translate_blueprints
data:
  list_blueprints: false  # 执行汉化操作 / Perform localization
  target_blueprint: "my_blueprint.yaml"  # 指定文件名（不含路径）
  force_translation: false

# 汉化所有 Blueprint 文件 / Localize all Blueprint files
service: ai_hub.translate_blueprints
data:
  list_blueprints: false
  target_blueprint: ""  # 留空表示汉化所有 / Leave empty to localize all
  force_translation: false
```

#### 汉化规则说明 / Localization Rules

**智能保护机制 / Smart Protection Mechanism:**
- **技术参数保护**: 自动保护 `input`、`variable`、`trigger` 等技术字段
- **Home Assistant 语法**: 保护 `!input`、`!secret`、`!include` 等特殊语法
- **变量名保护**: 不翻译 YAML 键名和变量引用
- **默认值翻译**: 仅翻译描述性文本，如 `name`、`description`、默认值等

**使用示例 / Usage Example:**

汉化前 / Before:
```yaml
blueprint:
  name: "Motion Light Automation"
  description: "Turn on lights when motion is detected"
  input:
    motion_sensor:
      name: "Motion Sensor"
      description: "Select motion sensor entity"
      selector:
        entity:
          domain: binary_sensor
```

汉化后 / After:
```yaml
blueprint:
  name: "移动感应灯光自动化"
  description: "检测到移动时自动开启灯光"
  input:
    motion_sensor:
      name: "移动感应器"
      description: "选择移动感应器实体"
      selector:
        entity:
          domain: binary_sensor
```

---

## 🔧 服务调用详解 / Service Details

AI Hub 提供了丰富的服务接口，可以通过开发者工具的服务面板调用：

AI Hub provides rich service APIs, which can be accessed via Developer Tools.

### 图片生成服务 / Image Generation

```yaml
service: ai_hub.generate_image
data:
  prompt: "图片描述 / Image description"  # 必填 / required
  size: "1024x1024"  # 可选 / optional
  model: "cogview-3-flash"  # 可选 / optional
```

### 图片分析服务 / Image Analysis

```yaml
service: ai_hub.analyze_image
data:
  image_file: "/path/to/image.jpg"  # 可选 / optional
  image_entity: "camera.front_door"  # 可选 / optional
  message: "分析指令 / Analysis instruction"  # 必填 / required
  model: "glm-4.1v-thinking-flash"  # 可选 / optional
  temperature: 0.3  # 可选 / optional
  max_tokens: 1000  # 可选 / optional
```

### 文本转语音服务 / Text to Speech

```yaml
service: ai_hub.tts_speech
data:
  text: "要转换的文本 / Text to convert"  # 必填 / required
  voice: "zh-CN-XiaoxiaoNeural"  # 可选 / optional
  pitch: "+0Hz"  # 可选: 音调调节 / optional: pitch adjustment
  rate: "+0%"  # 可选: 语速调节 / optional: speed adjustment
  volume: "+0%"  # 可选: 音量调节 / optional: volume adjustment
  media_player_entity: "media_player.speaker"  # 可选 / optional
```

### 语音转文本服务 / Speech to Text

```yaml
service: ai_hub.stt_transcribe
data:
  file: "/path/to/audio.wav"  # 必填 / required
  model: "FunAudioLLM/SenseVoiceSmall"  # 可选 / optional
```

### 创建自动化服务 / Create Automation

```yaml
service: ai_hub.create_automation
data:
  description: "自动化描述 / Automation description"  # 必填 / required
  name: "自动化名称 / Automation name"  # 可选 / optional
  area_id: "living_room"  # 可选 / optional
```

### 发送微信消息服务 / WeChat Message

```yaml
service: ai_hub.send_wechat_message
data:
  device_entity: "sensor.door_sensor"  # 必填 / required
  message: "消息内容 / Message content"  # 必填 / required
  group: "通知分组 / Notification group"  # 可选 / optional
  url: "https://example.com"  # 可选 / optional
```

### 翻译组件服务 / Translate Components

```yaml
service: ai_hub.translate_components
data:
  custom_components_path: "custom_components"  # 可选 / optional
  force_translation: false  # 可选 / optional
  target_component: "custom_component_name"  # 可选 / optional
  list_components: false  # 可选 / optional
```

### 蓝图汉化服务 / Blueprint Localization

```yaml
service: ai_hub.translate_blueprints
data:
  list_blueprints: false  # 可选: 仅列出蓝图文件及状态 / optional: Only list status
  target_blueprint: "my_blueprint.yaml"  # 可选: 指定蓝图文件名 / optional: Specify file name
  force_translation: false  # 可选: 强制重新汉化 / optional: Force re-localization
```

---

## ⚙️ 参数配置 / Configuration Parameters

### 推荐配置（默认值）/ Recommended Configuration (Defaults)

#### 对话助手配置 / Conversation

| 参数 | 值 | 说明 / Description |
|------|-----|-------------------|
| 模型 / Model | Qwen/Qwen3-8B | - |
| 温度 / Temperature | 0.3 | 控制回答的随机性 / for randomness |
| Top P | 0.5 | 控制候选词的选择范围 / controls candidate range |
| Top K | 1 | 限制候选词数量 / limits candidate count |
| 最大令牌数 / Max Tokens | 250 | - |
| 历史消息数 / History Messages | 30 | 保持上下文的连续性 / context continuity |

#### AI任务配置 / AI Tasks

| 参数 | 值 | 说明 / Description |
|------|-----|-------------------|
| 文本模型 / Text Model | Qwen/Qwen3-8B | - |
| 图片模型 / Image Model | Kwai-Kolors/Kolors | - |
| 温度 / Temperature | 0.95 | 提高创造性 / creativity |
| Top P | 0.7 | - |
| 最大令牌数 / Max Tokens | 2000 | - |

#### TTS 配置

| 参数 | 值 | 说明 / Description |
|------|-----|-------------------|
| 默认语音 / Default Voice | zh-CN-XiaoxiaoNeural（晓晓 / Xiaoxiao）| - |
| 音调 / Pitch | +0Hz | 可调节如 +5Hz/-5Hz / adjustable |
| 语速 / Rate | +0% | 可调节如 +10%/-10% / adjustable |
| 音量 / Volume | +0% | 可调节如 +10%/-10% / adjustable |
| 流式输出 / Stream Output | 支持 / Supported | - |

#### STT 配置

| 参数 | 值 | 说明 / Description |
|------|-----|-------------------|
| 默认模型 / Default Model | FunAudioLLM/SenseVoiceSmall | - |
| 语言检测 / Language Detection | 自动检测 / Automatic | 支持中文、英文、日文、韩文等 |
| 音频格式 / Audio Formats | WAV, MP3, FLAC, M4A, OGG, WebM | - |
| 最大文件大小 / Max File Size | 25MB | - |

---

## ⚠️ 注意事项 / Notes

### 系统要求 / System Requirements

1. **网络依赖 / Network**: 本集成完全依赖互联网服务，请确保网络连接稳定 / This integration depends on the internet. Ensure stable connectivity.
2. **性能要求 / Performance**: 建议使用性能较好的设备以获得更好的语音处理体验 / Higher device performance provides better voice experience.
3. **存储空间 / Storage**: 语音文件可能需要临时存储空间 / Voice files may require temporary local storage.

### 使用限制 / Usage Limits

1. **免费模型 / Free Models**:
   - 不支持流式输出，响应速度可能较慢 / No streaming output, may be slower
   - 有调用频率限制 / Call frequency limits
   - 免费额度有限制 / Free quotas have limitations

2. **API Keys**:
   - 请妥善保管 API Keys，不要泄露 / Keep your keys safe; do not leak them
   - 定期检查 API 使用量，避免超额 / Check usage periodically
   - 如遇到 API 错误，请检查 Keys 是否有效 / Verify keys if errors occur

3. **功能限制 / Feature Limits**:
   - 部分高级功能可能需要较新的 Home Assistant 版本 / Some features require newer Home Assistant
   - 图片生成和识别需要稳定的网络连接 / Image generation/recognition needs stable network
   - 微信推送需要关注巴法云公众号 / WeChat push requires following Bemfa public account

### 隐私安全 / Privacy & Security

1. **数据传输**: 所有数据都会通过互联网传输到相应的AI服务 / All data is sent over the internet to AI services
2. **本地存储**: 语音文件可能会临时存储在本地 / Voice files may be temporarily stored locally
3. **API安全**: 请确保 API Keys 的安全性 / Protect your API Keys

---

## 🛠️ 故障排除 / Troubleshooting

### 常见问题 / Common Issues

#### 1. 集成无法添加 / Integration cannot be added

**可能原因 / Possible reasons:**
- Home Assistant 版本过低（需要 2025.8.0+）/ Home Assistant version too low (needs 2025.8.0+)
- 网络连接问题 / Network issues
- API Keys 无效 / Invalid API Keys

**解决方法 / Solutions:**
- 检查 Home Assistant 版本 / Check Home Assistant version
- 确认网络连接正常 / Ensure the network is up
- 验证 API Keys 是否正确 / Verify API Keys

#### 2. 对话助手无响应 / Conversation Assistant unresponsive

**可能原因 / Possible reasons:**
- 硅基流动 API Key 无效或过期 / SiliconFlow API Key invalid or expired
- 网络连接问题 / Network issues
- 模型选择错误 / Incorrect model selection

**解决方法 / Solutions:**
- 检查硅基流动 API Key / Check SiliconFlow API Key
- 测试网络连接 / Test network
- 确认使用的是免费模型 / Make sure a free model is selected

#### 3. TTS 无法播放 / TTS not playing

**可能原因 / Possible reasons:**
- Edge TTS 服务不可用 / Edge TTS unavailable
- 媒体播放器选择错误 / Wrong media player
- 网络连接问题 / Network issues

**解决方法 / Solutions:**
- 检查网络连接到微软服务 / Check network access to Microsoft
- 确认媒体播放器状态正常 / Confirm media player status
- 尝试不同的语音模型 / Try another voice model

#### 4. STT 识别失败 / STT recognition failure

**可能原因 / Possible reasons:**
- 硅基流动 API Key 无效 / SiliconFlow API Key invalid
- 音频文件格式不支持 / Unsupported audio format
- 文件过大 / File too large

**解决方法 / Solutions:**
- 检查硅基流动 API Key / Check SiliconFlow Key
- 确认音频格式为支持的类型 / Confirm audio format is supported
- 压缩音频文件大小 / Compress audio file

#### 5. 微信推送不工作 / WeChat push not working

**可能原因 / Possible reasons:**
- 巴法云设备主题配置错误 / Bemfa device topic config error
- 未关注巴法云公众号 / Not following Bemfa official account
- 网络连接问题 / Network issues

**解决方法 / Solutions:**
- 检查设备主题是否正确 / Check topic value
- 确认已关注巴法云公众号 / Follow Bemfa public account
- 测试网络连接 / Test network

### 日志调试 / Log Debugging

如果遇到问题，可以查看 Home Assistant 日志：

If needed, check Home Assistant log:

1. **查看集成日志 / Check integration log**:
   ```
   设置 → 系统 → 日志 / Settings → System → Logs
   ```

2. **启用调试模式 / Enable Debug**:
   在 `configuration.yaml` 中添加 / Add in `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.ai_hub: debug
   ```

3. **重启 Home Assistant** 并重新测试功能 / Restart Home Assistant and test again

### 获取帮助 / Get Help

如果以上方法无法解决问题 / If above doesn't solve your issue:

1. **查看 [Issues 页面](https://github.com/ha-china/ai_hub/issues)** 查看是否有类似问题 / Check Issues Page for known issues
2. **创建新的 Issue**，请提供 / Open new Issue, please provide:
   - Home Assistant 版本 / Home Assistant version
   - AI Hub 版本 / AI Hub version
   - 详细的错误描述 / Detailed description
   - 相关的日志信息 / Related logs
   - 重现步骤 / Reproduce steps

---

## 🤝 参与贡献 / Contributing

欢迎参与项目贡献，帮助完善功能与文档：

You're welcome to contribute — improve features and docs!

### 项目结构 / Project Structure

```
custom_components/ai_hub/
├── __init__.py          # 集成入口 / Integration entry point
├── config_flow.py       # 配置流程 / Configuration flow
├── const.py             # 常量定义 / Constants
├── conversation.py      # 对话助手 / Conversation agent
├── ai_task.py           # AI 任务 / AI Task
├── ai_automation.py     # AI 自动化 / AI Automation
├── tts.py               # TTS 实体 (Edge TTS) / TTS entity
├── stt.py               # STT 实体 / STT entity
├── entity.py            # 实体基类 / Entity base class
├── sensor.py            # 健康检查传感器 / Health check sensors
├── diagnostics.py       # 诊断模块 / Diagnostics module
├── helpers.py           # 辅助函数 / Helper functions
├── intents.py           # 意图处理入口 / Intent processing entry
├── services.py          # 服务注册入口 / Service registration
├── markdown_filter.py   # Markdown 过滤器 / Markdown filter
├── voices.py            # Edge TTS 语音列表 / Edge TTS voice list
├── button/              # 按钮实体 / Button entities
│   └── __init__.py
├── providers/           # API 提供商模块 / API providers
│   ├── __init__.py
│   ├── base.py          # 基类 / Base class
│   ├── edge_tts.py      # Edge TTS 提供商 / Edge TTS provider
│   ├── openai_compatible.py  # OpenAI 兼容 API / OpenAI compatible API
│   ├── siliconflow_stt.py    # 硅基流动 STT / SiliconFlow STT
│   ├── stt_base.py      # STT 基类 / STT base
│   └── tts_base.py      # TTS 基类 / TTS base
├── services_lib/        # 服务实现模块 / Service implementations
│   ├── __init__.py      # 模块导出 / Module exports
│   ├── schemas.py       # 服务数据验证 / Service validation
│   ├── image.py         # 图像服务 / Image services
│   ├── tts.py           # TTS 服务 / TTS service
│   ├── stt.py           # STT 服务 / STT service
│   ├── wechat.py        # 微信通知 / WeChat notification
│   ├── translation.py   # 组件翻译 / Component translation
│   └── blueprints.py    # 蓝图翻译 / Blueprint translation
├── intents/             # 意图处理模块 / Intent processing
│   ├── __init__.py      # 模块入口 / Module entry
│   ├── loader.py        # 配置加载器 / Config loader
│   ├── handlers.py      # 意图处理器 / Intent handlers
│   ├── validator.py     # 配置验证器 / Config validator
│   ├── config_cache.py  # 配置缓存 / Config cache
│   └── config/          # 意图配置文件 / Intent configs
│       ├── intents.yaml
│       ├── base.yaml
│       ├── lists.yaml
│       ├── expansion.yaml
│       └── local_control.yaml
├── utils/               # 工具模块 / Utilities
│   ├── __init__.py
│   ├── retry.py         # 重试机制 / Retry mechanism
│   └── tts_cache.py     # TTS 缓存 / TTS cache
└── translations/        # 多语言翻译 / Translations
    ├── en.json
    └── zh-Hans.json
```

### 贡献方式 / How to Contribute

1. **报告问题**: 在 [Issues](https://github.com/ha-china/ai_hub/issues) 中报告 bug 或提出功能建议 / Report Bugs
2. **提交代码**: Fork 项目，修改代码后提交 Pull Request / Fork, modify & PR
3. **完善文档**: 帮助改进文档内容，增加使用示例 / Improve Docs
4. **测试反馈**: 测试新功能并提供反馈 / Feedback

---

## 📄 许可协议 / License

本项目遵循仓库内 [LICENSE](LICENSE) 协议发布。

This project is released under the [LICENSE](LICENSE) in this repository.

### 项目链接 / Project Links

- **项目主页 / Homepage**: [https://github.com/ha-china/ai_hub](https://github.com/ha-china/ai_hub)
- **问题反馈 / Issue Tracker**: [https://github.com/ha-china/ai_hub/issues](https://github.com/ha-china/ai_hub/issues)
- **发布版本 / Releases**: [https://github.com/ha-china/ai_hub/releases](https://github.com/ha-china/ai_hub/releases)
- **HACS 页面 / HACS Page**: [HACS 集成商店 / HACS Integration Shop](https://hacs.xyz/docs/integration/setup)

### 致谢 / Thanks

- 感谢 [knoop7](https://github.com/knoop7) 项目的基础架构 / Thanks to knoop7 for project foundation
- 感谢 [hasscc/hass-edge-tts](https://github.com/hasscc/hass-edge-tts) 项目的 Edge TTS 集成 / Thanks to hass-edge-tts for Edge TTS integration
- 感谢所有贡献者和用户的支持与反馈 / Thanks to all contributors and users for support and feedback

---

## 📱 关注我 / Follow Me

📲 扫描下面二维码，关注我。有需要可以随时给我留言：

Scan the QR code below to follow me! Feel free to leave me a message:

<img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/WeChat_QRCode.png" width="50%" />

---

## ☕ 赞助支持 / Support

如果您觉得我花费大量时间维护这个库对您有帮助，欢迎请我喝杯奶茶，您的支持将是我持续改进的动力！

If you found my work helpful, please buy me a milk tea! Your support motivates continuous improvement!

<div style="display: flex; justify-content: space-between;">
  <img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/1_readme/Ali_Pay.jpg" height="350px" />
  <img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/1_readme/WeChat_Pay.jpg" height="350px" />
</div>

💖 感谢您的支持与鼓励！/ Thank you for your support! 💖