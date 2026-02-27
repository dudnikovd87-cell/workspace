#!/usr/bin/env python3
import requests
from collections import defaultdict

API_HOST = "https://api-seller.ozon.ru"


def load_creds(path="secrets/ozon-nb-api.txt"):
    client_id = None
    api_key = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Client ID="):
                client_id = line.split("=", 1)[1].strip()
            if line.startswith("API Key="):
                api_key = line.split("=", 1)[1].strip()
    if not client_id or not api_key:
        raise RuntimeError("Client ID / API Key не найдены в файле")
    return client_id, api_key


def headers(client_id, api_key):
    return {
        "Client-Id": client_id,
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }


def get_clusters(client_id, api_key):
    url = f"{API_HOST}/v1/cluster/list"
    payload = {"cluster_type": "CLUSTER_TYPE_OZON"}
    r = requests.post(url, json=payload, headers=headers(client_id, api_key), timeout=60)
    r.raise_for_status()
    data = r.json()
    wh_to_cluster = {}
    clusters = data.get("clusters", [])
    for c in clusters:
        cid = c.get("id")
        cname = c.get("name")
        for lc in c.get("logistic_clusters", []):
            for w in lc.get("warehouses", []):
                wid = w.get("warehouse_id")
                if wid is not None:
                    wh_to_cluster[wid] = (cid, cname)
    return wh_to_cluster


def list_products_v3_filter(client_id, api_key, limit=1000):
    """POST /v3/product/list с filter"""
    url = f"{API_HOST}/v3/product/list"
    offset = 0
    products = []
    while True:
        # filter с visibility = ALL должен работать
        payload = {
            "limit": limit,
            "offset": offset,
            "filter": {"visibility": "ALL"}
        }
        r = requests.post(url, json=payload, headers=headers(client_id, api_key), timeout=60)
        r.raise_for_status()
        data = r.json()
        batch = data.get("products", [])
        products.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return products


def get_skus_from_product_ids(client_id, api_key, product_ids):
    url = f"{API_HOST}/v3/product/info/list"
    skus = []
    for i in range(0, len(product_ids), 1000):
        chunk = product_ids[i : i + 1000]
        payload = {"product_id": [str(x) for x in chunk]}
        r = requests.post(url, json=payload, headers=headers(client_id, api_key), timeout=60)
        r.raise_for_status()
        data = r.json()
        for it in data.get("items", []):
            sku = it.get("sku")
            if sku is not None:
                skus.append(str(sku))
    return skus


def get_fbo_stocks(client_id, api_key, warehouse_ids, skus, limit=1000):
    url = f"{API_HOST}/v1/analytics/stocks"
    offset = 0
    items = []
    while True:
        payload = {
            "filter": {
                "stock_types": ["STOCK_TYPE_VALID"],
                "warehouse_ids": warehouse_ids,
                "skus": skus[:100],
            },
            "limit": limit,
            "offset": offset,
        }
        r = requests.post(url, json=payload, headers=headers(client_id, api_key), timeout=60)
        r.raise_for_status()
        data = r.json()
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return items


def main():
    client_id, api_key = load_creds()

    wh_to_cluster = get_clusters(client_id, api_key)
    warehouse_ids = list(wh_to_cluster.keys())
    if not warehouse_ids:
        print("Склады не найдены.")
        return

    print("Получаем список товаров...")
    products = list_products_v3_filter(client_id, api_key)
    product_ids = []
    for p in products:
        pid = p.get("product_id") or p.get("id")
        if pid is not None:
            product_ids.append(pid)

    if not product_ids:
        print("Товары не найдены.")
        return

    print(f"Найдено товаров: {len(product_ids)}")

    print("Получаем SKU...")
    skus = get_skus_from_product_ids(client_id, api_key, product_ids)
    if not skus:
        print("SKU не найдены.")
        return

    print(f"Найдено SKU: {len(skus)}")

    agg = defaultdict(lambda: {"valid": 0, "defect": 0, "expiring": 0, "waitingdocs": 0})

    print("Получаем остатки FBO...")
    for i in range(0, len(skus), 100):
        chunk = skus[i : i + 100]
        try:
            items = get_fbo_stocks(client_id, api_key, warehouse_ids, chunk)
        except Exception as e:
            print(f"Ошибка при получении остатков: {e}")
            continue
        for it in items:
            wid = it.get("warehouse_id") or it.get("warehouseId")
            if wid in wh_to_cluster:
                _, cname = wh_to_cluster[wid]
            else:
                cname = "unknown"

            agg[cname]["valid"] += it.get("valid_stock_count", 0)
            agg[cname]["defect"] += it.get("defect_stock_count", 0)
            agg[cname]["expiring"] += it.get("expiring_stock_count", 0)
            agg[cname]["waitingdocs"] += it.get("waitingdocs_stock_count", 0)

    print("\n" + "="*50)
    print("FBO остатки по кластерам:")
    print("="*50)
    for cname, v in sorted(agg.items()):
        print(
            f"- {cname}: valid={v['valid']}, defect={v['defect']}, expiring={v['expiring']}, waitingdocs={v['waitingdocs']}"
        )


if __name__ == "__main__":
    main()