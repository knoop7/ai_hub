# 意图配置说明

本目录包含 AI Hub 的意图配置文件，采用 OHF-Voice 风格的模块化架构。

## 文件结构

```
config/
├── _common.yaml        # 共享配置（语言、列表、扩展规则、响应、跳过词、设备操作）
├── auto_lists.yaml     # 自动生成的列表（HA 区域和实体名，勿手动编辑）
├── local_control.yaml  # 本地控制配置（全局设备控制）
├── sentences/          # 意图句式定义（每个意图一个文件）
│   ├── climate_HassClimateSetTemperature.yaml
│   ├── light_HassLightSet.yaml
│   ├── media_player_HassMediaPlayerMute.yaml
│   └── ...
└── responses/          # 响应模板（每个意图一个文件）
    ├── climate_HassClimateSetTemperature.yaml
    ├── light_HassLightSet.yaml
    └── ...
```

## 配置说明

### _common.yaml
- `language`: 语言设置
- `lists`: 设备类型名称列表（light_names、climate_names、area_names 等）
- `expansion_rules`: 扩展规则（礼貌用语、动词、参数等）
- `responses`: 通用响应消息模板
- `skip_words`: 跳过词列表
- `device_operations`: 设备操作配置（控制操作、验证、默认值）

### sentences/*.yaml
- 每个文件定义一个或多个意图的句式模板
- 文件名格式：`<domain>_<intent>.yaml`
- 同一意图可由多个文件贡献句子（`data` 数组自动合并）

### responses/*.yaml
- 每个文件定义意图的响应模板
- 文件名格式：`<domain>_<intent>.yaml`
- 响应键名需与意图名完全匹配

### local_control.yaml
- `GlobalDeviceControl`: 全局设备控制配置
  - `global_keywords`: 全局关键词（所有、全部等）
  - `on_keywords`: 开启关键词
  - `off_keywords`: 关闭关键词
  - `domain_services`: 设备域到服务的映射
  - `responses`: 响应消息模板

## 加载顺序

1. `_common.yaml` → 基础配置
2. `auto_lists.yaml` → 补充列表（HA 实体名）
3. `sentences/*.yaml` → 意图句式（按文件名字母序）
4. `responses/*.yaml` → 响应模板（按文件名字母序）
5. `local_control.yaml` → 本地控制

## 添加新意图

1. 在 `sentences/` 下创建 `<domain>_<intent>.yaml`，定义意图和句式
2. 如需自定义响应，在 `responses/` 下创建对应文件
3. 如需新的设备类型列表，在 `_common.yaml` 的 `lists` 中添加
4. 如需新的扩展规则，在 `_common.yaml` 的 `expansion_rules` 中添加

## 注意事项

- 修改配置后需要重启 Home Assistant
- 配置会在启动时自动验证
- `auto_lists.yaml` 由系统自动生成，勿手动编辑
- 查看日志了解配置加载状态