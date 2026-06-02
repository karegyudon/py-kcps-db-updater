# py-kcps-db-updater

KC 舰队数据库自动更新工具，从 api_start2.json 同步 Ship、Equipment、Slot Fitting 数据到 GameConstants.sqlite3。

## 功能

- **Ship 同步**：自动检测 api_start2.json 中的新增舰船，同步到 SQLite 数据库
- **Equipment 同步**：新增装备自动写入 Equipment 表
- **Slot 数量变化检测**：自动检测已存在舰船的 slot 数量变化（如時雨改三 3→4），重建 fitting
- **Slot Fitting 自动生成**：
  - 新增/变化舰船的 ExclusiveFitting（Slot 4/5）
  - 新增/变化舰船的 InclusiveFitting（Slot6，继承自母舰链）
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

- **Slots 1-3**：默认无限制，不需要 ExclusiveFitting
- **Slots 4/5**：可能有限制，需要生成 ExclusiveFitting（基于 api_mst_equip_exslot_types）
- **Slot 6**：所有船都支持，通过 InclusiveFitting 处理（api_mst_equip_exslot_ship）
- **继承链**：通过 `api_aftershipid` 反向搜索找到母舰，逐级向上遍历

### 母舰查找

程序通过反向搜索 `api_aftershipid`（谁指向当前舰）来找到母舰，而非使用 `api_beforeshipid`（该字段在 API 中未填充）。

### Slot 数量变化检测

数据库首次运行时会自动添加 `Ships.ApiSlotCount` 列（迁移），并填入当前 API 的 `api_slot_num` 作为基线。后续运行会对比该列与最新 API：

- **API > DB**：检测到 slot 增加，删除旧 fitting 并重建（视为新船处理）
- **API < DB**：slot 减少，仅打印警告不修改（避免破坏手工添加的 fitting）
- **API = DB**：无变化，跳过

示例：2026-05-28 更新后時雨改三从 3 slots 改为 4 slots，运行程序会自动检测并重建其 Slot4 ExclusiveFitting 和 Slot6 InclusiveFitting。

## 许可证

MIT
