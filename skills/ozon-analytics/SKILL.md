---
name: ozon-analytics
description: Выгрузка и анализ данных Ozon. Используй когда нужно: (1) получить финансовый отчёт Ozon, (2) получить аналитику по товарам с Premium метриками (показы, конверсии, выкуп), (3) объединить финансы, аналитику и рекламу в один Excel. Триггеры: "выгрузи аналитику Ozon", "отчёт Ozon", "финансы Ozon", "продажи Ozon".
---

# Ozon Analytics

Выгрузка отчётов с маркетплейса Ozon и создание объединённого отчёта.

## Быстрый старт

### 1. Выгрузить аналитику

```bash
# Запрос к API аналитики (нужна Premium Plus подписка)
curl -s -X POST "https://api-seller.ozon.ru/v1/analytics/data" \
  -H "Client-Id: 1959914" \
  -H "Api-Key: 3d9d2d17-a9f6-4fe5-8f3b-0aa12ad6acce" \
  -H "Content-Type: application/json" \
  -d '{
    "date_from": "2026-02-01",
    "date_to": "2026-02-28",
    "metrics": ["revenue", "ordered_units", "hits_view", "hits_tocart", "session_view", "delivered_units", "returns", "cancellations"],
    "dimensions": ["sku"],
    "limit": 1000
  }'
```

### 2. Метрики

**Базовые (для всех):**
- `revenue` — выручка
- `ordered_units` — заказано единиц

**Premium Plus:**
- `hits_view` — показы
- `hits_tocart` — добавлено в корзину
- `session_view` — сессии
- `delivered_units` — доставлено
- `returns` — возвращено
- `cancellations` — отменено

### 3. Финансы

```bash
curl -s -X POST "https://api-seller.ozon.ru/v1/finance/balance" \
  -H "Client-Id: 1959914" \
  -H "Api-Key: 3d9d2d17-a9f6-4fe5-8f3b-0aa12ad6acce" \
  -H "Content-Type: application/json" \
  -d '{"date_from": "2026-02-01", "date_to": "2026-02-28"}'
```

### 4. Реклама

Рекламный отчёт хранится в: `/root/.openclaw/workspace/reports/ozon_ads_feb2026_raw.csv`

## Создание объединённого отчёта

1. Выгрузить аналитику → сохранить raw JSON
2. Выгрузить финансы → сохранить raw JSON  
3. Прочитать рекламный CSV
4. Объединить по Ozon SKU
5. Создать Excel

Пример данных в CSV рекламы:
```csv
seller_article,ozon_sku,impr,clicks,ctr_pct,spend,cpc,orders,sales,drr_pct
2650v2-rx580-32-1024-SL190,3275517737,198109.0,12379.0,6.25,300149.18,24.25,31.0,3899707.0,7.7
```

## Файл с ключами

Ключи хранятся в: `/root/.openclaw/workspace/secrets/ozon_keys.txt`

```
Client ID: 1959914
API Key: 3d9d2d17-a9f6-4fe5-8f3b-0aa12ad6acce
Performance ID: 50792585-1751269039661@advertising.performance.ozon.ru
```

## Важные правила

1. **Сначала raw данные** — всегда сохраняй JSON с ответом API перед обработкой
2. **Помесячно** — выгружай данные помесячно (не более 1 месяца для finance/balance)
3. **Premium метрики** — только с Premium Plus подпиской доступны: hits_view, hits_tocart, session_view и др.
4. **Ограничение** — /v1/analytics/data можно использовать не чаще 1 раза в минуту
