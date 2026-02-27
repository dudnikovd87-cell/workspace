#!/usr/bin/env python3
"""
Выгрузка статистики Ozon Performance API за вчера по товарам
"""
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import sys

# Конфигурация из ozon-pc-api.txt
CLIENT_ID = "1959914"
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
    if resp.status_code != 200:
        print(f"Ошибка получения токена: {resp.status_code} - {resp.text}")
        return None
    
    return resp.json().get("access_token")

def get_campaigns(token):
    """Получение списка кампаний"""
    url = f"{BASE_URL}/api/client/campaign"
    headers = {"Authorization": f"Bearer {token}", "Client-Id": CLIENT_ID}
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Ошибка получения кампаний: {resp.status_code}")
        return []
    
    return resp.json().get("list", [])

def request_report(token, campaign_ids, date_from, date_to):
    """Запрос отчёта"""
    url = f"{BASE_URL}/api/client/statistics/json"
    payload = {
        "campaigns": campaign_ids,
        "dateFrom": date_from,
        "dateTo": date_to
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": CLIENT_ID,
        "Content-Type": "application/json"
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        print(f"Ошибка запроса отчёта: {resp.status_code} - {resp.text[:200]}")
        return None
    
    return resp.json().get("UUID")

def wait_for_report(token, uuid, max_attempts=30):
    """Ожидание готовности отчёта"""
    url = f"{BASE_URL}/api/client/statistics/{uuid}"
    headers = {"Authorization": f"Bearer {token}", "Client-Id": CLIENT_ID}
    
    for i in range(max_attempts):
        resp = requests.get(url, headers=headers)
        data = resp.json()
        state = data.get("state")
        
        if state == "OK":
            return data.get("link")
        elif state == "FAIL":
            print(f"Отчёт не удался: {data}")
            return None
        
        time.sleep(2)
    
    return None

def download_report(token, link):
    """Скачивание отчёта"""
    url = f"{BASE_URL}{link}"
    headers = {"Authorization": f"Bearer {token}", "Client-Id": CLIENT_ID}
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Ошибка скачивания: {resp.status_code}")
        return None
    
    try:
        return resp.json()
    except:
        return None

def parse_report_data(report_json):
    """Парсинг данных отчёта"""
    rows = []
    
    for campaign_id, campaign_data in report_json.items():
        title = campaign_data.get("title", "")
        report = campaign_data.get("report", {})
        report_rows = report.get("rows", [])
        
        for row in report_rows:
            rows.append({
                "campaign_id": campaign_id,
                "campaign_name": title,
                "sku": row.get("sku", ""),
                "product_name": row.get("title", ""),
                "price": row.get("price", ""),
                "views": row.get("views", ""),
                "clicks": row.get("clicks", ""),
                "ctr": row.get("ctr", ""),
                "toCart": row.get("toCart", ""),
                "avgBid": row.get("avgBid", ""),
                "moneySpent": row.get("moneySpent", ""),
                "ordersMoney": row.get("ordersMoney", ""),
            })
    
    return rows

def main():
    print("=" * 60)
    print("Выгрузка статистики Ozon Performance (по товарам)")
    print("=" * 60)
    
    # 1. Получаем токен
    token = get_token()
    if not token:
        print("Не удалось получить токен!")
        return
    
    print("✓ Токен получен")
    
    # 2. Получаем кампании
    campaigns = get_campaigns(token)
    if not campaigns:
        print("Нет кампаний!")
        return
    
    campaign_ids = [c.get("id") for c in campaigns if c.get("id")]
    print(f"✓ Всего кампаний: {len(campaign_ids)}")
    
    # 3. Запрашиваем статистику батчами по 10
    all_rows = []
    batch_size = 10
    total_batches = (len(campaign_ids) + batch_size - 1) // batch_size
    
    for i in range(0, len(campaign_ids), batch_size):
        batch_num = i // batch_size + 1
        batch = campaign_ids[i:i+batch_size]
        print(f"\nБатч {batch_num}/{total_batches}: кампании {batch[:3]}... ({len(batch)} шт)")
        
        # Запрашиваем отчёт
        uuid = request_report(token, batch, yesterday, yesterday)
        if not uuid:
            print(f"  ✗ Ошибка запроса")
            continue
        
        # Ждём готовности
        link = wait_for_report(token, uuid)
        if not link:
            print(f"  ✗ Отчёт не готов")
            continue
        
        # Скачиваем
        report_data = download_report(token, link)
        if not report_data:
            print(f"  ✗ Ошибка скачивания")
            continue
        
        # Парсим
        rows = parse_report_data(report_data)
        all_rows.extend(rows)
        print(f"  ✓ Получено строк: {len(rows)}")
        
        # Пауза между батчами
        if i + batch_size < len(campaign_ids):
            time.sleep(1)
    
    print(f"\n{'=' * 60}")
    print(f"Итого собрано: {len(all_rows)} строк")
    
    # 4. Сохраняем в Excel
    if all_rows:
        df = pd.DataFrame(all_rows)
        
        # Реorden колонок
        cols = ["campaign_id", "campaign_name", "sku", "product_name", "price", 
                "views", "clicks", "ctr", "toCart", "avgBid", "moneySpent", "ordersMoney"]
        df = df[[c for c in cols if c in df.columns]]
        
        output_file = f"/root/.openclaw/workspace/ozon_stats_{yesterday}.xlsx"
        df.to_excel(output_file, index=False)
        print(f"✓ Сохранено в: {output_file}")
        print(f"\nПервые 5 строк:")
        print(df.head().to_string())
    else:
        print("Нет данных для сохранения!")

if __name__ == "__main__":
    main()