<h1 align="center">AI Hub · One-stop Free AI Services</h1>
<p align="center">
  To allow you to experience various free AI services, this integration does not support any paid models or services. You may need to apply for an account or create an API Key.<br>
  <strong>Special Thanks:</strong> We stand on the shoulders of giants. Without <a href="https://github.com/knoop7" target="_blank">knoop7</a> and <a href="https://github.com/rany2/edge-tts" target="_blank">edge-tts</a>, this project would not exist!
</p>

<p align="center">
  <a href="https://github.com/ha-china/ai_hub/releases"><img src="https://img.shields.io/github/v/release/ha-china/ai_hub" alt="GitHub Version"></a>
  <a href="https://github.com/ha-china/ai_hub/issues"><img src="https://img.shields.io/github/issues/ha-china/ai_hub" alt="GitHub Issues"></a>
  <img src="https://img.shields.io/github/forks/ha-china/ai_hub?style=social" alt="GitHub Forks">
  <img src="https://img.shields.io/github/stars/ha-china/ai_hub?style=social" alt="GitHub Stars"> <a href="README.md">中文</a>
</p>

---

## 📋 Table of Contents

- [🔧 Prerequisites](#🔧-prerequisites)
- [🌟 Features](#🌟-features)
- [📦 Installation](#📦-installation)
- [🚀 Quick Start](#🚀-quick-start)
- [🔑 Account Registration & Token Acquisition](#🔑-account-registration--token-acquisition)
- [📖 Usage Guide](#📖-usage-guide)
- [🔧 Service Details](#🔧-service-details)
- [⚙️ Configuration Parameters](#⚙️-configuration-parameters)
- [⚠️ Notes](#⚠️-notes)
- [🛠️ Troubleshooting](#🛠️-troubleshooting)
- [🤝 Contributing](#🤝-contributing)
- [📄 License](#📄-license)
- [📱 Follow Me](#📱-follow-me)
- [☕ Support](#☕-support)

---

## 🔧 Prerequisites

- **Home Assistant**: 2025.8.0 or higher
- **Network Requirement**: This integration relies entirely on internet services; a stable network connection is required.

## 🌟 Features

AI Hub is a custom integration for Home Assistant, providing native connections to SiliconFlow and Bemfa.

If you don't need some entries, just leave the api key blank or delete it. You can add it back later when needed.

### Core Features

#### 🗣️ Conversation Assistant
- **Streaming Output**: Real-time display of model replies for a smooth conversational experience.
- **Home Control**: Integrates with Home Assistant LLM API to control/query devices.
- **Image Understanding**: Automatically switches to vision model (GLM-4.1V-9B-Thinking) if a message contains an image.
- **Context Memory**: Configurable number of history messages to balance effect and performance.

#### 🤖 AI Tasks
- **Structured Data Generation**: Specify JSON structure, with error prompts on failure.
- **Image Generation**: Generate images using Kolors and other models, supporting URL or base64 result.
- **Multimodal Support**: Reuses conversation message format for complex tasks.

#### 🔊 TTS (Text to Speech, Edge TTS)
- **High-Quality Voice**: Integrates Microsoft Edge TTS, supporting multiple languages and styles.
- **Rich Voice Library**: Supports 400+ voices including Xiaoxiao, Yun Jian, Aria, Jenny, and more.
- **Prosody Parameters**: Supports rate, volume, and pitch adjustments.
- **Streaming Output**: Supports streaming TTS output for LLM conversation scenarios.
- **Audio Format**: Outputs MP3 format audio.

#### 🎤 STT (Speech to Text, SiliconFlow)
- **High Accuracy Recognition**: Integrates SiliconFlow speech recognition service, supporting SenseVoice, TeleSpeechASR and more models.
- **Auto Language Detection**: Automatically detects Chinese, English, Japanese, Korean, and other languages without manual specification.
- **Format Compatibility**: Supports WAV/MP3/FLAC/M4A/OGG/WebM and other audio formats.
- **Real-Time Processing**: Suitable for voice control, Voice Assistant, and other scenarios.

#### 🌐 HACS Integration Localization
- **Auto Translation**: Use AI to automatically translate custom component English translation files to Chinese.
- **Batch Processing**: Supports batch localization for multiple components.
- **Intelligent Recognition**: Automatically detects components needing translation, skipping already localized ones.

#### 🏗️ Blueprint Localization
- **One-Click Localization**: Add "Blueprint Localization" button in the integration interface for one-click translation of all blueprints.
- **In-Place Translation**: Directly modify original blueprint files without creating additional translation files.
- **Smart Protection**: Automatically protect technical parameters and variables, only translating user interface text.
- **Recursive Scanning**: Automatically scan blueprints directory and its subdirectories for all YAML files.
- **Status Detection**: Intelligently detect already localized files to avoid duplicate processing.
- **Complete Support**: Support complex nested structures and Home Assistant special syntax.

#### 📱 WeChat Notification (Bemfa)
- **Real-Time Notifications**: Integrate Bemfa service to send device status notifications via WeChat.

---

## 📦 Installation

### Method 1: HACS Installation (Recommended)

1. **Open HACS**: In Home Assistant, go to HACS → Integrations.
2. **Search for Integration**: Click the upper right "Explore & Download Repositories", search for "ai_hub".
3. **Install Integration**: Find "AI Hub" and click Download.
4. **Restart**: Restart Home Assistant to activate.

### Method 2: Manual Installation

1. **Download Files**: Download the latest `ai_hub.zip` from [GitHub Releases](https://github.com/ha-china/ai_hub/releases).
2. **Extract Files**: Unzip to `<HA_CONFIG>/custom_components/ai_hub/`.
3. **Restart**: Restart Home Assistant.

> **Tip**: This integration depends on the new Conversation/AI Task/Entry framework; a newer Home Assistant version (>2025.8.0) is recommended.

---

## 🚀 Quick Start

### Configuration Wizard

1. **Add Integration**: Go to Settings → Devices & Services → Integrations → Add Integration, search "AI HUB (ai_hub)".
2. **Configure API Keys**: Follow the wizard to configure:
   - SiliconFlow API Key (for Conversation, AI Task, and STT).
   - Bemfa API Key (for WeChat messages).
3. **Verify**: System will verify your API Keys.
4. **Finish**: Integration will auto-create relevant services and entities.

### Sub-Entry Configuration

AI Hub supports sub-entry configuration for independent functionality:

- **AI Hub Conversation**: For Assist agents.
- **AI Hub AI Task**: For image generation and structured data.
- **AI Hub TTS**: For text-to-speech.
- **AI Hub STT**: For speech-to-text.
- **AI Hub WeChat Notification**: For WeChat messages.
- **AI Hub Localization**: For component translation.
- **AI Hub Blueprint Localization**: For blueprint translation.

---

## 🔑 Account Registration & Token Acquisition

### SiliconFlow
- **Usage**: Conversation, AI Tasks, STT
- **Register**: [Sign Up Here](https://cloud.siliconflow.cn/i/U3e0rmsr)
- **Get API Key**:
  1. Register and login.
  2. Go to the dashboard.
  3. Create new API Key in the [API Key Management](https://cloud.siliconflow.cn/account/ak) page.
  4. Copy your new API Key.

### Bemfa
- **Usage**: WeChat Notification
- **Register**: [Sign Up Here](http://www.cloud.bemfa.com/u_register.php)
- **Get Device Topic**:
  1. Register and login.
  2. Go to [TCP Device Management](https://cloud.bemfa.com/tcp/index.html)
  3. Create or use an existing device.
  4. Copy the device topic.

> **Note**: Edge TTS uses the official Microsoft free API; no API Key is required.

---

## 📖 Usage Guide

### A. Conversation Assistant

#### Basic Conversation
1. **Switch Agent**: In Assist, set agent to "AI Hub Conversation".
2. **Start Chat**: Input/speak questions such as:
   - "Turn on the living room light to 60%"
   - "Summarize my schedule for today"
   - "Set an alarm for 8 AM tomorrow"

#### Image Understanding
1. **Upload Image**: Upload images or use camera snapshots in a supported frontend.
2. **Describe Issue**: Input what you want to ask/analyze about the image.
3. **Get Analysis**: The model analyzes and responds automatically.

#### Tool Invocation
- **Enable Tools**: Enable "LLM Hass API" in the conversation sub-entry.
- **Control Devices**: The model can call Home Assistant APIs to control/query devices.

### B. AI Tasks

#### Image Generation
Generate images via automation or service invocation:

```yaml
automation:
  - alias: "Generate daily picture"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: ai_hub.generate_image
        data:
          prompt: "Beautiful sunrise landscape"
          size: "1024x1024"
          model: "Kwai-Kolors/Kolors"
```

#### Structured Data Generation
Generate formatted JSON data:

```yaml
# Call AI task to generate JSON data
service: ai_hub.ai_task
data:
  input: "Generate a JSON including name, age, and occupation"
  model: "Qwen/Qwen3-8B"
  temperature: 0.3
```

### C. TTS (Text to Speech)

#### As Entity
1. **Select TTS**: In a media player, select "AI Hub TTS".
2. **Input Text**: Enter your text.
3. **Play Voice**: It will be played automatically.

#### As Service
```yaml
service: ai_hub.tts_speech
data:
  text: "Welcome to AI Hub voice synthesis"
  voice: "zh-CN-XiaoxiaoNeural"
  pitch: "+0Hz"    # Pitch adjustment, e.g., "+5Hz" or "-5Hz"
  rate: "+0%"      # Speed adjustment, e.g., "+10%" or "-10%"
  volume: "+0%"    # Volume adjustment, e.g., "+10%" or "-10%"
  media_player_entity: media_player.living_room_speaker
```

### D. STT (Speech to Text)

#### As Entity
1. **Select STT**: In microphone settings, select "AI Hub STT".
2. **Record**: Start recording.
3. **Get Text**: Speech will be converted to text.

#### As Service
```yaml
service: ai_hub.stt_transcribe
data:
  file: "/config/tmp/recording.wav"
  model: "FunAudioLLM/SenseVoiceSmall"
```

### E. WeChat Notification

#### Push via Automation
```yaml
automation:
  - alias: "Notify if door/window opens"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: ai_hub.send_wechat_message
        data:
          device_entity: binary_sensor.front_door
          message: "Front door opened, please pay attention!"
```

### F. Localization

#### Manual Translation
```yaml
service: ai_hub.translate_components
data:
  custom_components_path: "custom_components"  # Optional, default path
  force_translation: false  # Force re-translate
```

### G. 🏗️ Blueprint Localization

#### One-Click Localization (Recommended)
1. **Add Blueprint Localization Sub-Entry**: In AI Hub integration details page, click "Add Sub-Entry" and select "AI Hub Blueprint Localization"
2. **One-Click Localization**: Click the "Blueprint Localization" button in the integration details page. The system will automatically:
   - Scan all YAML files in `/config/blueprints` directory and its subdirectories
   - Intelligently detect already localized files and skip duplicate processing
   - Protect technical parameters, variable names, and Home Assistant syntax
   - Perform localization directly on original files without creating additional files

#### Service-Based Localization
```yaml
# List all Blueprint files and their localization status
service: ai_hub.translate_blueprints
data:
  list_blueprints: true  # Only list status, do not perform localization
  target_blueprint: ""  # Leave empty to view all files
  force_translation: false  # Force re-localization

# Localize specific Blueprint file
service: ai_hub.translate_blueprints
data:
  list_blueprints: false  # Perform localization operation
  target_blueprint: "my_blueprint.yaml"  # Specify file name (without path)
  force_translation: false  # Force re-localization of already localized files

# Localize all Blueprint files
service: ai_hub.translate_blueprints
data:
  list_blueprints: false  # Perform localization operation
  target_blueprint: ""  # Leave empty to localize all files
  force_translation: false  # Force re-localization of already localized files
```

#### Localization Rules
**Smart Protection Mechanism:**
- **Technical Parameter Protection**: Automatically protects `input`, `variable`, `trigger` and other technical fields
- **Home Assistant Syntax**: Protects `!input`, `!secret`, `!include` and other special syntax
- **Variable Name Protection**: Does not translate YAML key names and variable references
- **Default Value Translation**: Only translates descriptive text such as `name`, `description`, default values, etc.

**Supported Translation Content:**
- Blueprint `name` and `description` fields
- `input` fields like `name`, `description`, `default` and other user interface text
- `name` and `state` attributes of entities like `binary_sensor`, `sensor`
- Descriptive text in conditions and actions

**Status Detection:**
- Automatically detects if files contain Chinese characters
- Files containing Chinese are considered localized and skipped by default
- Use `force_translation: true` to force re-localization

**Usage Example:**
Before localization:
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

After localization:
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

## 🔧 Service Details

AI Hub provides rich service APIs, which can be accessed via Developer Tools.

### Image Generation
```yaml
service: ai_hub.generate_image
data:
  prompt: "Image description"  # required
  size: "1024x1024"  # optional
  model: "cogview-3-flash"  # optional
```

### Image Analysis
```yaml
service: ai_hub.analyze_image
data:
  image_file: "/path/to/image.jpg"  # optional
  image_entity: "camera.front_door"  # optional
  message: "Analysis instruction"  # required
  model: "glm-4.1v-thinking-flash"  # optional
  temperature: 0.3  # optional
  max_tokens: 1000  # optional
```

### Text to Speech
```yaml
service: ai_hub.tts_speech
data:
  text: "Text to convert"  # required
  voice: "zh-CN-XiaoxiaoNeural"  # optional
  pitch: "+0Hz"  # optional: pitch adjustment
  rate: "+0%"  # optional: speed adjustment
  volume: "+0%"  # optional: volume adjustment
  media_player_entity: "media_player.speaker"  # optional
```

### Speech to Text
```yaml
service: ai_hub.stt_transcribe
data:
  file: "/path/to/audio.wav"  # required
  model: "FunAudioLLM/SenseVoiceSmall"  # optional
```

### Create Automation
```yaml
service: ai_hub.create_automation
data:
  description: "Automation description"  # required
  name: "Automation name"  # optional
  area_id: "living_room"  # optional
```

### WeChat Message
```yaml
service: ai_hub.send_wechat_message
data:
  device_entity: "sensor.door_sensor"  # required
  message: "Message content"  # required
  group: "Notification group"  # optional
  url: "https://example.com"  # optional
```

### Translate Components
```yaml
service: ai_hub.translate_components
data:
  custom_components_path: "custom_components"  # optional
  force_translation: false  # optional
  target_component: "custom_component_name"  # optional
  list_components: false  # optional
```

### Blueprint Localization
```yaml
service: ai_hub.translate_blueprints
data:
  list_blueprints: false  # optional: Only list blueprint files and their status
  target_blueprint: "my_blueprint.yaml"  # optional: Specify specific blueprint file name
  force_translation: false  # optional: Force re-localization of already localized files
```

---

## ⚙️ Configuration Parameters

### Recommended Configuration (Defaults)

#### Conversation
- **Model**: Qwen/Qwen3-8B
- **Temperature**: 0.3 (for randomness)
- **Top P**: 0.5 (controls candidate range)
- **Top K**: 1 (limits candidate count)
- **Max Tokens**: 250
- **History Messages**: 30 (context continuity)

#### AI Tasks
- **Text Model**: Qwen/Qwen3-8B
- **Image Model**: Kwai-Kolors/Kolors
- **Temperature**: 0.95 (creativity)
- **Top P**: 0.7
- **Max Tokens**: 2000

#### TTS
- **Default Voice**: zh-CN-XiaoxiaoNeural (Xiaoxiao)
- **Pitch**: +0Hz (default, adjustable e.g., +5Hz/-5Hz)
- **Rate**: +0% (default, adjustable e.g., +10%/-10%)
- **Volume**: +0% (default, adjustable e.g., +10%/-10%)
- **Stream Output**: Supported

#### STT
- **Default Model**: FunAudioLLM/SenseVoiceSmall
- **Language Detection**: Automatic (supports Chinese, English, Japanese, Korean, etc.)
- **Audio Formats**: WAV, MP3, FLAC, M4A, OGG, WebM
- **Max File Size**: 25MB

---

## ⚠️ Notes

### System Requirements
1. **Network**: This integration depends on the internet. Ensure stable connectivity.
2. **Performance**: Higher device performance provides better voice experience.
3. **Storage**: Voice files may require temporary local storage.

### Usage Limits
1. **Free Models**:
   - No streaming output, may be slower
   - Call frequency limits
   - Free quotas have limitations

2. **API Keys**:
   - Keep your keys safe; do not leak them
   - Check usage periodically
   - Verify keys if errors occur

3. **Feature Limits**:
   - Some features require newer Home Assistant
   - Image generation/recognition needs stable network
   - WeChat push requires following Bemfa public account

### Privacy & Security
1. **Data Transfer**: All data is sent over the internet to AI services.
2. **Local Storage**: Voice files may be temporarily stored locally.
3. **API Security**: Protect your API Keys.

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. Integration cannot be added
**Possible reasons**:
- Home Assistant version too low (needs 2025.8.0+)
- Network issues
- Invalid API Keys

**Solutions**:
- Check Home Assistant version
- Ensure the network is up
- Verify API Keys

#### 2. Conversation Assistant unresponsive
**Possible reasons**:
- SiliconFlow API Key invalid or expired
- Network issues
- Incorrect model selection

**Solutions**:
- Check SiliconFlow API Key
- Test network
- Make sure a free model is selected

#### 3. TTS not playing
**Possible reasons**:
- Edge TTS unavailable
- Wrong media player
- Network issues

**Solutions**:
- Check network access to Microsoft
- Confirm media player status
- Try another voice model

#### 4. STT recognition failure
**Possible reasons**:
- SiliconFlow API Key invalid
- Unsupported audio format
- File too large

**Solutions**:
- Check SiliconFlow Key
- Confirm audio format is supported
- Compress audio file

#### 5. WeChat push not working
**Possible reasons**:
- Bemfa device topic config error
- Not following Bemfa official account
- Network issues

**Solutions**:
- Check topic value
- Follow Bemfa public account
- Test network

### Log Debugging
If needed, check Home Assistant log:

1. **Check integration log**:
   ```
   Settings → System → Logs
   ```

2. **Enable Debug**
   Add in `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.ai_hub: debug
   ```

3. **Restart Home Assistant** and test again.

### Get Help
If above doesn't solve your issue:
1. **Check [Issues Page](https://github.com/ha-china/ai_hub/issues)** for known issues
2. **Open new Issue**, please provide:
   - Home Assistant version
   - AI Hub version
   - Detailed description
   - Related logs
   - Reproduce steps

---

## 🤝 Contributing

You're welcome to contribute — improve features and docs!

### Project Structure

```
custom_components/ai_hub/
├── __init__.py          # Integration entry point
├── config_flow.py       # Configuration flow
├── const.py             # Constants
├── conversation.py      # Conversation agent
├── ai_task.py           # AI Task
├── ai_automation.py     # AI Automation
├── tts.py               # TTS entity (Edge TTS)
├── stt.py               # STT entity
├── entity.py            # Entity base class
├── sensor.py            # Health check sensors
├── diagnostics.py       # Diagnostics module
├── helpers.py           # Helper functions
├── intents.py           # Intent processing entry
├── services.py          # Service registration
├── markdown_filter.py   # Markdown filter
├── voices.py            # Edge TTS voice list
├── button/              # Button entities
│   └── __init__.py
├── providers/           # API providers
│   ├── __init__.py
│   ├── base.py          # Base class
│   ├── edge_tts.py      # Edge TTS provider
│   ├── openai_compatible.py  # OpenAI compatible API
│   ├── siliconflow_stt.py    # SiliconFlow STT
│   ├── stt_base.py      # STT base
│   └── tts_base.py      # TTS base
├── services_lib/        # Service implementations
│   ├── __init__.py      # Module exports
│   ├── schemas.py       # Service validation
│   ├── image.py         # Image services
│   ├── tts.py           # TTS service
│   ├── stt.py           # STT service
│   ├── wechat.py        # WeChat notification
│   ├── translation.py   # Component translation
│   └── blueprints.py    # Blueprint translation
├── intents/             # Intent processing
│   ├── __init__.py      # Module entry
│   ├── loader.py        # Config loader
│   ├── handlers.py      # Intent handlers
│   ├── validator.py     # Config validator
│   ├── config_cache.py  # Config cache
│   └── config/          # Intent configs
│       ├── intents.yaml
│       ├── base.yaml
│       ├── lists.yaml
│       ├── expansion.yaml
│       └── local_control.yaml
├── utils/               # Utilities
│   ├── __init__.py
│   ├── retry.py         # Retry mechanism
│   └── tts_cache.py     # TTS cache
└── translations/        # Translations
    ├── en.json
    └── zh-Hans.json
```

### How to Contribute
1. **Report Bugs**: [Issues](https://github.com/ha-china/ai_hub/issues)
2. **Submit Code**: Fork, modify & PR
3. **Improve Docs**: Add/expand documentation and usage examples
4. **Feedback**: Test new features and feedback

## 📄 License

This project is released under the [LICENSE](LICENSE) in this repository.

### Project Links
- **Homepage**: [https://github.com/ha-china/ai_hub](https://github.com/ha-china/ai_hub)
- **Issue Tracker**: [https://github.com/ha-china/ai_hub/issues](https://github.com/ha-china/ai_hub/issues)
- **Releases**: [https://github.com/ha-china/ai_hub/releases](https://github.com/ha-china/ai_hub/releases)
- **HACS Page**: [HACS Integration Shop](https://hacs.xyz/docs/integration/setup)

### Thanks
- Thanks to [knoop7](https://github.com/knoop7) for project foundation
- Thanks to [hasscc/hass-edge-tts](https://github.com/hasscc/hass-edge-tts) for Edge TTS integration
- Thanks to all contributors and users for support and feedback

## 📱 Follow Me

📲 Scan the QR code below to follow me! Feel free to leave me a message:

<img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/WeChat_QRCode.png" width="50%" /> 

## ☕ Support

If you found my work helpful, please buy me a milk tea! Your support motivates continuous improvement!

<div style="display: flex; justify-content: space-between;">
  <img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/1_readme/Ali_Pay.jpg" height="350px" />
  <img src="https://gitee.com/desmond_GT/hassio-addons/raw/main/1_readme/WeChat_Pay.jpg" height="350px" />
</div> 💖

Thank you for your support!
