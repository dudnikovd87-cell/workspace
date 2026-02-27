#!/usr/bin/env python3
"""
Выгрузка статистики Ozon Performance API за вчера
"""
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os

# Конфигурация из ozon-pc-api.txt
CLIENT_ID = "1959914"
API_KEY = "3d9d2d17-a9f6-4fe5-8f3b-0aa12ad6acce"
PERFORMANCE_ID = "50792585-1751269039661@advertising.performance.ozon.ru"
CLIENT_SECRET = "cWgUPyd1hbsq3bzuf-9-roYbZ72d6vDO3A3dwxf46nz2NEdutctgIRaJ0A91FGvbt_MXbBd7WZKhFVBPEg"

BASE_URL = "https://api-performance.ozon.ru"

# Вчерашняя дата
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"Выгружаем статистику за: {yesterday}")

def get_token():
    """Получение токена доступа"""
    url = f"{BASE_URL}/api/client/token"
    payload = {
        "client_id": PERFORMANCE_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    headers = {"Content-Type": "application/json"}
    
    resp = requests.post(url, json=payload, headers=headers)
    print(f"Token response status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return None
    
    data = resp.json()
    return data.get("access_token")

def get_campaigns(token):
    """Получение списка кампаний"""
    url = f"{BASE_URL}/api/client/campaign"
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": CLIENT_ID
    }
    
    resp = requests.get(url, headers=headers)
    print(f"Campaigns response status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
        return []
    
    data = resp.json()
    campaigns = data.get("list", [])
    print(f"Найдено кампаний: {len(campaigns)}")
    return campaigns

def get_campaign_statistics(token, campaign_ids, date_from, date_to):
    """Получение статистики по кампаниям батчами"""
    all_stats = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": CLIENT_ID,
        "Content-Type": "application/json"
    }
    
    # Батчи по 10 кампаний
    for i in range(0, len(campaign_ids), 10):
        batch = campaign_ids[i:i+10]
        print(f"Обрабатываю батч {i//10 + 1}: кампании {batch[:3]}... ({len(batch)} шт)")
        
        url = f"{BASE_URL}/api/client/statistics/daily"
        payload = {
            "campaigns": batch,
            "date_from": date_from,
            "date_to": date_to
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                all_stats.extend(items)
                print(f"  Получено записей: {len(items)}")
            else:
                print(f"  Ошибка: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"  Exception: {e}")
        
    return all_stats

def main():
    print("=" * 50)
    print("Начинаю выгрузку статистики Ozon PC")
    print("=" * 50)
    
    # 1. Получаем токен
    token = get_token()
    if not token:
        print("Не удалось получить токен!")
        return
    
    print(f"Токен получен: {token[:20]}...")
    
    # 2. Получаем кампании
    campaigns = get_campaigns(token)
    if not campaigns:
        print("Нет кампаний!")
        return
    
    # Выводим список кампаний
    print("\nСписок кампаний:")
    for c in campaigns:
        print(f"  ID: {c.get('id')} - {c.get('name', 'N/A')} ({c.get('state', 'N/A')})")
    
    campaign_ids = [c.get("id") for c in campaigns if c.get("id")]
    print(f"\nВсего ID кампаний: {len(campaign_ids)}")
    
    # 3. Получаем статистику
    stats = get_campaign_statistics(token, campaign_ids, yesterday, yesterday)
    print(f"\nВсего записей статистики: {len(stats)}")
    
    # 4. Сохраняем в Excel
    if stats:
        # Парсим данные
        rows = []
        for item in stats:
            campaign_id = item.get("campaign_id")
            date = item.get("date")
            for product in item.get("products", []):
                rows.append({
                    "campaign_id": campaign_id,
                    "date": date,
                    "sku": product.get("sku"),
                    "name": product.get("product_name", ""),
                    "views": product.get("views", 0),
                    "clicks": product.get("clicks", 0),
                    "ctr": product.get("ctr", 0),
                    "cost": product.get("cost", 0),
                    "orders": product.get("orders", 0),
                    "revenue": product.get("revenue", 0),
                    " acos": product.get("acos", 0),
                })
        
        df = pd.DataFrame(rows)
        
        output_file = f"/root/.openclaw/workspace/ozon_stats_{yesterday}.xlsx"
        df.to_excel(output_file, index=False)
        print(f"\nСохранено в: {output_file}")
        print(f"Всего строк: {len(df)}")
        print("\nПервые строки:")
        print(df.head(10).to_string())
    else:
        print("Нет данных для сохранения!")

if __name__ == "__main__":
    main()