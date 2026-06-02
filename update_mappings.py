#!/usr/bin/env python3
"""
根据 https://github.com/kcwikizh/get_kaisou_data 项目自动更新映射数据
"""

import json
import requests
import os
from pathlib import Path


def download_api_start2():
    """下载最新的api_start2.json文件"""
    print("正在下载最新的api_start2.json...")
    url = "https://api.kcwiki.moe/start2"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        with open("api_start2.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("api_start2.json 下载完成")
        return data
    except Exception as e:
        print(f"下载api_start2.json失败: {e}")
        return None


def extract_ship_mappings(api_start2_data):
    """从api_start2数据中提取舰船ID映射"""
    if not api_start2_data or "api_mst_ship" not in api_start2_data:
        print("api_start2.json中没有找到舰船数据")
        return {}

    ships = {}
    for ship in api_start2_data["api_mst_ship"]:
        if "api_id" in ship and "api_name" in ship:
            ships[str(ship["api_id"])] = ship["api_name"]

    print(f"提取到 {len(ships)} 个舰船映射")
    return ships


def extract_item_mappings(api_start2_data):
    """从api_start2数据中提取装备ID映射"""
    if not api_start2_data or "api_mst_slotitem" not in api_start2_data:
        print("api_start2.json中没有找到装备数据")
        return {}

    items = {}
    for item in api_start2_data["api_mst_slotitem"]:
        if "api_id" in item and "api_name" in item:
            items[int(item["api_id"])] = item["api_name"]

    print(f"提取到 {len(items)} 个装备映射")
    return items


def save_ship_mappings(ships):
    """保存舰船映射到JSON文件"""
    with open("ship_mappings.json", "w", encoding="utf-8") as f:
        json.dump(ships, f, ensure_ascii=False, indent=2)
    print("舰船映射已保存到 ship_mappings.json")


def save_item_mappings(items):
    """保存装备映射到JSON文件"""
    with open("item_mappings.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("装备映射已保存到 item_mappings.json")


def main():
    print("开始更新映射数据...")

    # 下载最新的api_start2.json
    api_start2_data = download_api_start2()

    if api_start2_data:
        # 提取并保存舰船映射
        ship_mappings = extract_ship_mappings(api_start2_data)
        save_ship_mappings(ship_mappings)

        # 提取并保存装备映射
        item_mappings = extract_item_mappings(api_start2_data)
        save_item_mappings(item_mappings)

        print("所有映射数据已更新完成！")
    else:
        print("无法获取最新数据，保持原有数据不变")


if __name__ == "__main__":
    main()
