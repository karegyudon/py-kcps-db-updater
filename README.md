# py-kcps-db-updater

KC 舰队数据库自动更新工具，从 api_start2.json 同步 Ship、Equipment、Slot Fitting 数据到 GameConstants.sqlite3。

## 功能

- **Ship 同步**：自动检测 api_start2.json 中的新增舰船，同步到 SQLite 数据库
- **Equipment 同步**：新增装备自动写入 Equipment 表
- **Slot Fitting 自动生成**：
  - 新增舰船的 ExclusiveFitting（Slot4）
  - 新增舰船的 InclusiveFitting（Slot6，继承自母舰链）
  - 继承规则：子舰的 Slot6 InclusiveFitting = 父舰的 Slot6 InclusiveFitting + 父舰的 Slot4 ExclusiveFitting

## 快速开始

### 环境要求

- Python 3.8+
- SQLite 3.0+

### 使用方法

```bash
# 运行主程序
python update_db_from_json.py
```

Windows 用户可运行 `02-update_database.cmd`。

## 文件说明

| 文件 | 说明 |
|------|------|
| `update_db_from_json.py` | 主程序，执行数据库同步 |
| `update_mappings.py` | JSON 映射更新脚本 |
| `ship_mappings.json` | 舰船 ID 映射（自动生成） |
| `item_mappings.json` | 装备 ID 映射（自动生成） |
| `api_start2.json` | 游戏 API 数据源（需手动获取） |
| `data/GameConstants.sqlite3` | 目标 SQLite 数据库 |

## 工作流程

```
api_start2.json
    ↓
update_mappings.py  →  ship_mappings.json / item_mappings.json
    ↓
update_db_from_json.py  →  GameConstants.sqlite3
```

### 更新步骤

1. 获取最新 api_start2.json（游戏 API 数据）
2. 运行 `01-update_data.cmd` 生成映射文件
3. 运行 `02-update_database.cmd` 更新数据库

## 技术细节

### Slot Fitting 规则

- **ExclusiveFitting**：新舰船自动创建 Slot4 排除列表（基于 api_mst_equip_exslot_types）
- **InclusiveFitting**：新舰船继承母舰链的 Slot6 排除列表
- **继承链**：通过 `api_aftershipid` 反向搜索找到母舰，逐级向上遍历

### 母舰查找

程序通过反向搜索 `api_aftershipid`（谁指向当前舰）来找到母舰，而非使用 `api_beforeshipid`（该字段在 API 中未填充）。

## 许可证

MIT
