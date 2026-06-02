#!/usr/bin/env python3
"""从 api_start2.json 更新 GameConstants.sqlite3 数据库的 slot fitting 关系."""
import sqlite3
import json
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _new_guid():
    return str(uuid.uuid4()).upper()


def load_api(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_lookups(api):
    ships = {s["api_id"]: s for s in api["api_mst_ship"]}
    items = {i["api_id"]: i for i in api["api_mst_slotitem"]}
    stypes = {s["api_id"]: s["api_name"] for s in api["api_mst_stype"]}
    eqtypes = {e["api_id"]: e["api_name"] for e in api["api_mst_slotitem_equiptype"]}
    exslot_ship = api.get("api_mst_equip_exslot_ship", {})
    exslot_types = set(api.get("api_mst_equip_exslot", []))
    return ships, items, stypes, eqtypes, exslot_ship, exslot_types


def _get_type_map(cursor, table, type_col="TypeInGame", id_col="Id"):
    cursor.execute(f"SELECT {id_col}, {type_col} FROM {table}")
    return {r[1]: r[0] for r in cursor.fetchall()}


def _get_existing_ids(cursor, table, id_col="Id"):
    cursor.execute(f"SELECT {id_col} FROM {table}")
    return {r[0] for r in cursor.fetchall()}


def _find_parent_ship_id(api, ship_id):
    """通过反向查找 aftershipid 找到母舰（改造前形态）。"""
    for s in api["api_mst_ship"]:
        a = s.get("api_aftershipid", 0)
        if a and int(a) == ship_id:
            return s["api_id"]
    return None


def _get_ship_type_if_types(cursor, api_stype):
    """Look up ShipType InclusiveFitting (TypeInGame values) from DB for a ship type."""
    cursor.execute("""
        SELECT et.TypeInGame FROM ShipTypes st
        JOIN _ShipType_InclusiveFitting sti ON st.Id = sti.RelatedShipTypesId
        JOIN _InclusiveFitting_EquipmentType x ON sti.InclusiveFittingsId = x.RelatedInclusiveFittingsId
        JOIN EquipmentTypes et ON x.AcceptedEquipmentTypesId = et.Id
        WHERE st.TypeInGame = ?
    """, (api_stype,))
    return {r["TypeInGame"] for r in cursor.fetchall()}


def _has_slot_exclusive_fitting(cursor, ship_id, slot):
    cursor.execute("SELECT 1 FROM SlotExclusiveFittings WHERE ShipId=? AND Slot=?", (ship_id, slot))
    return cursor.fetchone() is not None


def _has_slot6_fitting(cursor, ship_id):
    cursor.execute("SELECT 1 FROM SlotInclusiveFittings WHERE ShipId=? AND Slot=6", (ship_id,))
    return cursor.fetchone() is not None


def _get_slots_needing_fitting(conn, api, ship_id):
    """
    返回舰船需要生成 ExclusiveFitting 的槽位列表。
    Slots 1-3 默认无限制，Slot 4/5 可能需要限制。
    Slot 6 是所有船都支持的，通过 InclusiveFitting 处理。
    返回 (需要限制的槽位列表, 母舰ID)。
    """
    c = conn.cursor()
    ships = {s["api_id"]: s for s in api["api_mst_ship"]}
    ship = ships.get(ship_id)
    if not ship:
        return [], None
    parent_id = _find_parent_ship_id(api, ship_id)
    if not parent_id or parent_id not in ships:
        return [], None
    parent = ships[parent_id]
    if ship["api_slot_num"] <= parent["api_slot_num"]:
        return [], None

    slots_needing_fitting = []
    for slot in [4, 5]:
        if slot <= ship["api_slot_num"] and not _has_slot_exclusive_fitting(c, ship_id, slot):
            slots_needing_fitting.append(slot)

    return slots_needing_fitting, parent_id


def sync_ships(conn, api, ship_type_map, dry_run=False):
    c = conn.cursor()
    existing = _get_existing_ids(c, "Ships")
    ships_data = {s["api_id"]: s for s in api["api_mst_ship"]}
    new_ids = []
    for api_id, ship in sorted(ships_data.items()):
        if api_id in existing or api_id >= 1500:
            continue
        type_guid = ship_type_map.get(ship["api_stype"])
        if not type_guid:
            print(f"  ?  ShipId={api_id} ({ship['api_name']}): unknown stype={ship['api_stype']}")
            continue
        ts = _now()
        if not dry_run:
            c.execute("""
                INSERT INTO Ships (Id, CreatedAt, ModifiedAt, Comment, IsRuntimeGenerated,
                                   TypeId, ClassId, SpecializationId)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (api_id, ts, ts, None, 0, type_guid, None, None))
        print(f"  + Ship {api_id:4d}: {ship['api_name']} (stype={ship['api_stype']}, slot_num={ship['api_slot_num']})")
        new_ids.append(api_id)
    if not dry_run:
        conn.commit()
    return new_ids


def sync_equipments(conn, api, equip_type_map, exslot_types, dry_run=False):
    c = conn.cursor()
    existing = _get_existing_ids(c, "Equipments")
    items_data = {i["api_id"]: i for i in api["api_mst_slotitem"]}
    new_ids = []
    for api_id, item in sorted(items_data.items()):
        if api_id in existing or api_id >= 1500:
            continue
        main_type = item["api_type"][0]
        type_guid = equip_type_map.get(main_type)
        if not type_guid:
            print(f"  ?  EquipId={api_id} ({item['api_name']}): unknown type={main_type}")
            continue
        extra_slot = 1 if main_type in exslot_types else 0
        ts = _now()
        if not dry_run:
            c.execute("""
                INSERT INTO Equipments (Id, CreatedAt, ModifiedAt, Comment, IsRuntimeGenerated,
                                        TypeId, ExtraSlotEquipable)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (api_id, ts, ts, None, 0, type_guid, extra_slot))
        print(f"  + Equip {api_id:4d}: {item['api_name']} (type={main_type})")
        new_ids.append(api_id)
    if not dry_run:
        conn.commit()
    return new_ids


def _compute_extra_slot_rejected_types(ship_type_if_types, exslot_types, ship_if_types):
    """
    新增正常槽位的拒绝类型:
    = ShipType IF 中不在 exslot_types 内的类型 + Ship IF 类型.
    """
    base_rejected = (ship_type_if_types - exslot_types) | (set(ship_if_types or []))
    return sorted(base_rejected)


def _generate_extra_slot_fitting(conn, ship_id, ship_name, slot, ship_type_if_types,
                                  exslot_types, ship_if_types, dry_run=False):
    c = conn.cursor()
    excl_id = _new_guid()
    ts = _now()
    comment = f"[{ship_id}]{ship_name}:Slot{slot}"
    if not dry_run:
        c.execute("""
            INSERT INTO ExclusiveFittings (Id, CreatedAt, ModifiedAt, Comment, IsRuntimeGenerated)
            VALUES (?, ?, ?, ?, 1)
        """, (excl_id, ts, ts, comment))

    rejected_types = _compute_extra_slot_rejected_types(ship_type_if_types, exslot_types, ship_if_types)
    equip_type_guid_map = _get_type_map(c, "EquipmentTypes")

    if not dry_run:
        for tid in rejected_types:
            eq_type_guid = equip_type_guid_map.get(tid)
            if eq_type_guid:
                c.execute("""
                    INSERT INTO _ExclusiveFitting_EquipmentType (RelatedExclusiveFittingsId, UnacceptedEquipmentTypesId)
                    VALUES (?, ?)
                """, (excl_id, eq_type_guid))

    if not dry_run:
        c.execute("""
            INSERT INTO SlotExclusiveFittings (Slot, ExclusiveFittingId, CreatedAt, ModifiedAt, Comment, ShipId)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (slot, excl_id, ts, ts, comment, ship_id))

    kept = sorted(ship_type_if_types - set(rejected_types))
    print(f"    Slot{slot} ExclusiveFitting: {excl_id[:12]}... rejects {len(rejected_types)} types, "
          f"keeps {kept}")
    return excl_id


def _generate_slot6_fitting(conn, ship_id, ship_name, api_ctype, exslot_ship, dry_run=False):
    """
    用 api_mst_equip_exslot_ship 的 ctypes(舰级) + ship_ids(特定舰) 推导 Slot 6 可装备列表.
    stypes(舰种) 暂不使用, 因为会波及同种所有舰船.
    """
    c = conn.cursor()
    if _has_slot6_fitting(c, ship_id):
        return None
    allowed_equips = {}
    for eq_id_str, info in exslot_ship.items():
        equip_id = int(eq_id_str)
        c.execute("SELECT Id FROM Equipments WHERE Id=?", (equip_id,))
        if not c.fetchone():
            continue
        level_req = info.get("api_req_level", 0)
        ship_ids = info.get("api_ship_ids") or {}
        ctypes = info.get("api_ctypes") or {}
        can_equip = str(api_ctype) in ctypes or str(ship_id) in ship_ids
        if can_equip:
            allowed_equips[equip_id] = level_req
    if not allowed_equips:
        return None
    incl_id = _new_guid()
    ts = _now()
    comment = f"[{ship_id}]{ship_name}:SlotEx"
    if not dry_run:
        c.execute("""
            INSERT INTO InclusiveFittings (Id, CreatedAt, ModifiedAt, Comment, IsRuntimeGenerated)
            VALUES (?, ?, ?, ?, 1)
        """, (incl_id, ts, ts, comment))
    for equip_id, level_req in sorted(allowed_equips.items()):
        c.execute("SELECT Id FROM AcceptedEquipments WHERE EquipmentId=? AND LevelRequirement=?", (equip_id, level_req))
        existing = c.fetchone()
        if existing:
            ae_id = existing["Id"]
        else:
            ae_id = _new_guid()
            if not dry_run:
                c.execute("""
                    INSERT INTO AcceptedEquipments (Id, CreatedAt, ModifiedAt, EquipmentId, LevelRequirement)
                    VALUES (?, ?, ?, ?, ?)
                """, (ae_id, ts, ts, equip_id, level_req))
        if not dry_run:
            c.execute("""
                INSERT INTO _InclusiveFitting_AcceptedEquipment (AcceptedEquipmentsId, RelatedInclusiveFittingsId)
                VALUES (?, ?)
            """, (ae_id, incl_id))
    if not dry_run:
        c.execute("""
            INSERT INTO SlotInclusiveFittings (Slot, InclusiveFittingId, CreatedAt, ModifiedAt, Comment, ShipId)
            VALUES (6, ?, ?, ?, ?, ?)
        """, (incl_id, ts, ts, comment, ship_id))
    print(f"    Slot6 InclusiveFitting: {incl_id[:12]}... accepts {len(allowed_equips)} equipment items")
    for eid, lvl in sorted(allowed_equips.items()):
        print(f"      EquipId={eid} Level={lvl}")
    return incl_id


def _find_nearest_ship_if(cursor, api, ship_id):
    """Walk up ancestry chain to find nearest Ship-level InclusiveFitting."""
    visited = set()
    sid = ship_id
    while sid and sid not in visited:
        visited.add(sid)
        cursor.execute("SELECT InclusiveFittingsId FROM _Ship_InclusiveFitting WHERE RelatedShipsId=?", (sid,))
        r = cursor.fetchone()
        if r:
            cursor.execute("""
                SELECT et.TypeInGame FROM _InclusiveFitting_EquipmentType x
                JOIN EquipmentTypes et ON x.AcceptedEquipmentTypesId = et.Id
                WHERE x.RelatedInclusiveFittingsId = ?
            """, (r["InclusiveFittingsId"],))
            types = [t["TypeInGame"] for t in cursor.fetchall()]
            return types
        sid = _find_parent_ship_id(api, sid)
    return None


def _generate_ship_inclusive_fitting(conn, api, ship_id, ship_name, dry_run=False):
    """查找母舰链上最近的 Ship-level InclusiveFitting 并继承类型约束."""
    c = conn.cursor()
    c.execute("SELECT InclusiveFittingsId FROM _Ship_InclusiveFitting WHERE RelatedShipsId=?", (ship_id,))
    if c.fetchone():
        return None
    parent_types = _find_nearest_ship_if(c, api, ship_id)
    if parent_types is None:
        return None
    incl_id = _new_guid()
    ts = _now()
    comment = f"[{ship_id}]{ship_name}"
    equip_type_guid_map = _get_type_map(c, "EquipmentTypes")
    if not dry_run:
        c.execute("""
            INSERT INTO InclusiveFittings (Id, CreatedAt, ModifiedAt, Comment, IsRuntimeGenerated)
            VALUES (?, ?, ?, ?, 1)
        """, (incl_id, ts, ts, comment))
        for tid in parent_types:
            type_guid = equip_type_guid_map.get(tid)
            if type_guid:
                c.execute("""
                    INSERT INTO _InclusiveFitting_EquipmentType (AcceptedEquipmentTypesId, RelatedInclusiveFittingsId)
                    VALUES (?, ?)
                """, (type_guid, incl_id))
        c.execute("""
            INSERT INTO _Ship_InclusiveFitting (InclusiveFittingsId, RelatedShipsId)
            VALUES (?, ?)
        """, (incl_id, ship_id))
    print(f"    Ship-level InclusiveFitting: {incl_id[:12]}... types={parent_types}")
    return incl_id


def _process_new_ship(conn, api, ships_map, c, ship_id, exslot_ship, exslot_types, dry_run=False):
    """为一条新船生成所有 fittings 并打印详情."""
    ship = ships_map[ship_id]
    ship_name = ship["api_name"]
    api_stype = ship["api_stype"]
    api_ctype = ship.get("api_ctype", 0)

    print(f"\n  [{ship_id}] {ship_name} (stype={api_stype}, ctype={api_ctype}, slots={ship['api_slot_num']})")

    ship_type_if_types = _get_ship_type_if_types(c, api_stype)
    if ship_type_if_types:
        print(f"    ShipType IF ({api_stype}): {sorted(ship_type_if_types)}")
    else:
        print(f"    ShipType IF ({api_stype}): (none)")

    slots_needing_fitting, parent_id = _get_slots_needing_fitting(conn, api, ship_id)
    if slots_needing_fitting:
        ship_if_types = _find_nearest_ship_if(c, api, ship_id)
        print(f"    -> slot increase (parent={parent_id}), ExclusiveFitting for slots: {slots_needing_fitting}")
        for slot in slots_needing_fitting:
            _generate_extra_slot_fitting(conn, ship_id, ship_name, slot,
                                          ship_type_if_types, exslot_types, ship_if_types, dry_run)

    slot6_id = _generate_slot6_fitting(conn, ship_id, ship_name, api_ctype, exslot_ship, dry_run)
    if slot6_id:
        print(f"    -> Slot6 InclusiveFitting derived")

    ship_if_id = _generate_ship_inclusive_fitting(conn, api, ship_id, ship_name, dry_run)
    if ship_if_id:
        print(f"    -> Ship-level InclusiveFitting inherited")


def update_database(db_path, api_path, dry_run=False):
    print(f"Updating: {db_path}\nAPI: {api_path}")

    api = load_api(api_path)
    ships_map, items_map, stypes, eqtypes, exslot_ship, exslot_types = build_lookups(api)

    print(f"\nAPI: {len(ships_map)} ships, {len(items_map)} equipment, "
          f"{len(stypes)} stypes, {len(eqtypes)} eqtypes, {len(exslot_ship)} exslot rules, "
          f"exslot_types={sorted(exslot_types)}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    ship_type_map = _get_type_map(c, "ShipTypes")
    equip_type_map = _get_type_map(c, "EquipmentTypes")

    print(f"\nDB: {len(_get_existing_ids(c, 'Ships'))} ships, {len(_get_existing_ids(c, 'Equipments'))} equipment")

    print(f"\n--- Step 1: Sync Ships ---")
    new_ships = sync_ships(conn, api, ship_type_map, dry_run)
    print(f"  -> {len(new_ships)} new ships")

    print(f"\n--- Step 2: Sync Equipments ---")
    new_equips = sync_equipments(conn, api, equip_type_map, exslot_types, dry_run)
    print(f"  -> {len(new_equips)} new equipment")

    print(f"\n--- Step 3: Generate Slot fittings for new ships ---")
    for ship_id in sorted(new_ships):
        _process_new_ship(conn, api, ships_map, c, ship_id, exslot_ship, exslot_types, dry_run=dry_run)

    if not dry_run:
        conn.commit()
    conn.close()

    conn2 = sqlite3.connect(db_path)
    c2 = conn2.cursor()
    final_ships = len(_get_existing_ids(c2, "Ships", "Id"))
    final_equips = len(_get_existing_ids(c2, "Equipments", "Id"))
    c2.execute("SELECT COUNT(*) FROM SlotExclusiveFittings")
    slot_ex = c2.fetchone()[0]
    c2.execute("SELECT COUNT(*) FROM SlotInclusiveFittings")
    slot_in = c2.fetchone()[0]
    c2.execute("SELECT COUNT(*) FROM ExclusiveFittings")
    excl = c2.fetchone()[0]
    c2.execute("SELECT COUNT(*) FROM InclusiveFittings")
    incl = c2.fetchone()[0]
    conn2.close()

    print(f"\n{'='*50}")
    print(f"Complete: Ships={final_ships}, Equip={final_equips}, "
          f"SlotEx={slot_ex}, SlotIn={slot_in}, Excl={excl}, Incl={incl}")
    print(f"{'='*50}")
    return new_ships, new_equips


def compare_databases(db_a, db_b, label_a="A", label_b="B"):
    def _stats(path):
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [t[0] for t in c.fetchall()]
        s = {}
        for t in tables:
            c.execute(f'SELECT COUNT(*) FROM "{t}"')
            s[t] = c.fetchone()[0]
        conn.close()
        return s

    sa, sb = _stats(db_a), _stats(db_b)
    print(f"\nDiff {label_a} vs {label_b}:")
    any_diff = False
    for t in sorted(set(list(sa.keys()) + list(sb.keys()))):
        a, b = sa.get(t, 0), sb.get(t, 0)
        if a != b:
            any_diff = True
            print(f"  {t:45s} {a:5d} -> {b:5d} ({'+' if b>a else ''}{b-a})")
    if not any_diff:
        print("  (all tables match)")
    return sa, sb


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Update GameConstants.sqlite3 slot fitting from api_start2.json")
    parser.add_argument("--db", default="data/GameConstants.sqlite3")
    parser.add_argument("--api", default="api_start2.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--compare", metavar="DB", help="Compare with another DB after update")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    db_path = base_dir / args.db
    api_path = base_dir / args.api

    if not db_path.exists():
        print(f"Error: DB not found: {db_path}")
        sys.exit(1)
    if not api_path.exists():
        print(f"Error: API not found: {api_path}")
        sys.exit(1)

    update_database(str(db_path), str(api_path), dry_run=args.dry_run)
    if args.compare:
        compare_databases(str(db_path), args.compare, "target", args.compare)
