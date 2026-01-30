# const.py 变量重复分析

> 分析日期: 2026-01-30
> 问题: 大量 "Legacy" 常量只是字典值的重复引用

---

## 重复模式分析

### 模式：字典 + Legacy 常量双重定义

const.py 中大量使用了这种模式：

```python
# 1. 定义字典
TIMEOUTS: Final = {
    "default": 30.0,
    "chat_api": 60.0,
    ...
}

# 2. 再定义单独常量引用（Legacy）
TIMEOUT_DEFAULT: Final = TIMEOUTS["default"]
TIMEOUT_CHAT_API: Final = TIMEOUTS["chat_api"]
TIMEOUT_IMAGE_API: Final = TIMEOUTS["image_api"]
...
```

---

## 具体统计

| 字典 | Legacy 常量数量 | 额外行数 |
|------|----------------|----------|
| `TIMEOUTS` | 8 | ~8 行 |
| `RETRY_CONFIG` | 4 | ~4 行 |
| `CACHE_CONFIG` | 2 | ~2 行 |
| `AUDIO_LIMITS` | 4 | ~4 行 |
| `ERRORS` | 3 | ~3 行 |
| `SERVICES` | 8 | ~8 行 |
| `RECOMMENDED` | 14 | ~14 行 |
| `API_URLS` | 5 | ~5 行 |
| `DEFAULT_NAMES` | 13 | ~13 行 |
| **总计** | **61** | **~61 行** |

---

## 问题分析

### 1. 维护负担

每次添加新值需要更新两个地方：

```python
# 添加新的 timeout
TIMEOUTS: Final = {
    ...
    "new_api": 45.0,  # ← 需要在这里添加
}

# 还要添加 legacy 常量
TIMEOUT_NEW_API: Final = TIMEOUTS["new_api"]  # ← 还要在这里添加
```

### 2. 代码冗长

61 行 Legacy 常量只是简单引用，没有实际逻辑：

```python
# 这 61 行代码只是重复:
SOME_CONSTANT: Final = SOME_DICT["key"]
```

### 3. 实际使用情况

需要检查这些 Legacy 常量是否真的被使用。如果直接使用字典值会更清晰：

```python
# 当前方式
from .const import TIMEOUT_CHAT_API

# 更清晰的方式
from .const import TIMEOUTS
timeout = TIMEOUTS["chat_api"]
```

---

## 优化方案

### 方案 A：渐进式移除（推荐）

1. **保留字典定义** - 这是好的设计
2. **标记 Legacy 常量为废弃** - 添加 `_DEPRECATED` 后缀
3. **逐步迁移使用方** - 从 `TIMEOUT_CHAT_API` 迁移到 `TIMEOUTS["chat_api"]`

```python
# 新的命名约定
TIMEOUT_DEFAULT: Final = TIMEOUTS["default"]  # _DEPRECATED: Use TIMEOUTS["default"]
TIMEOUT_CHAT_API: Final = TIMEOUTS["chat_api"]  # _DEPRECATED: Use TIMEOUTS["chat_api"]
```

### 方案 B：统一访问函数

创建访问函数替代常量：

```python
def get_timeout(key: str) -> float:
    """Get timeout value by key. Returns default if key not found."""
    return TIMEOUTS.get(key, TIMEOUTS["default"])

# 使用
timeout = get_timeout("chat_api")
```

### 方案 C：直接导出字典项（最简洁）

在 `__init__.py` 中直接导出：

```python
# const.py
TIMEOUTS: Final = {...}

# 在 __init__.py 中
from .const import TIMEOUTS

# 导出常用值作为快捷方式
TIMEOUT_DEFAULT = TIMEOUTS["default"]
TIMEOUT_CHAT_API = TIMEOUTS["chat_api"]
```

---

## 建议

**最小改动方案**：

1. 保留所有字典定义（这是好的设计）
2. 对于真正被频繁使用的 Legacy 常量（如 `TIMEOUT_HEALTH_CHECK`），保留它们
3. 对于很少使用的 Legacy 常量，可以考虑：
   - 删除未使用的
   - 或添加注释说明 "Legacy constant, consider using TIMEOUTS[key] instead"

**如果要我清理**，可以：

1. 搜索每个 Legacy 常量的使用情况
2. 删除未使用的 Legacy 常量（预计可以减少 30-50 行）
3. 添加 deprecation 警告

需要我帮你分析哪些 Legacy 常量实际被使用了吗？

---

*分析时间: 2026-01-30*
