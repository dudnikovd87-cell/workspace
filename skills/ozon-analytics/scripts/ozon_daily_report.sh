#!/bin/bash
# Ежедневный отчёт Ozon Analytics
# Запускается в 8:00 МСК

REPORTS_DIR="/root/.openclaw/workspace/reports"
SKILLS_DIR="/root/.openclaw/workspace/skills/ozon-analytics/scripts"

cd $SKILLS_DIR

# Определяем период: с 1 числа месяца по вчера
YEAR=$(date +%Y)
MONTH=$(date +%m)
LAST_DAY=$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%d)

DATE_FROM="${YEAR}-${MONTH}-01"
DATE_TO="${YEAR}-${MONTH}-${LAST_DAY}"

# Если сегодня 1 число, то берём прошлый месяц
if [ $(date +%d) == "01" ]; then
    LAST_MONTH=$(date -d "$(date +%Y-%m-01) -1 month" +%Y-%m)
    YEAR=$(echo $LAST_MONTH | cut -d'-' -f1)
    MONTH=$(echo $LAST_MONTH | cut -d'-' -f2)
    DATE_FROM="${YEAR}-${MONTH}-01"
    DATE_TO="${YEAR}-${MONTH}-31"
fi

echo "Ozon Analytics: ${DATE_FROM} - ${DATE_TO}"

# Выгружаем аналитику
python3 -c "
import json
import subprocess

CLIENT_ID = '1959914'
API_KEY = '3d9d2d17-a9f6-4fe5-8f3b-0aa12ad6acce'
date_from = '${DATE_FROM}'
date_to = '${DATE_TO}'

cmd = f'''curl -s -X POST \"https://api-seller.ozon.ru/v1/analytics/data\" \\
  -H \"Client-Id: {CLIENT_ID}\" \\
  -H \"Api-Key: {API_KEY}\" \\
  -H \"Content-Type: application/json\" \\
  -d '{{\"date_from\": \"{date_from}\", \"date_to\": \"{date_to}\", \\
  \"metrics\": [\"revenue\", \"ordered_units\", \"hits_view\", \"hits_tocart\", \"session_view\", \"delivered_units\", \"returns\", \"cancellations\"], \\
  \"dimensions\": [\"sku\"], \"limit\": 1000}}' '''

result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
data = json.loads(result.stdout)

with open('${REPORTS_DIR}/ozon_analytics_daily_raw.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f\"Выгружено: {len(data.get('result', {}).get('data', []))} товаров\")
"

# Создаём Excel
python3 << 'PYEOF'
import json
import csv
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from datetime import datetime

REPORTS_DIR = "/root/.openclaw/workspace/reports"

# Читаем аналитику
with open(f"{REPORTS_DIR}/ozon_analytics_daily_raw.json", 'r') as f:
    analytics = json.load(f)

# Читаем рекламу
ads_data = {}
try:
    with open(f"{REPORTS_DIR}/ozon_ads_feb2026_raw.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ads_data[row['ozon_sku']] = row
except:
    pass

# Объединяем
combined = {}
for item in analytics.get('result', {}).get('data', []):
    sku = item['dimensions'][0]['id']
    m = item['metrics']
    ad = ads_data.get(sku, {})
    
    combined[sku] = {
        'sku': sku,
        'article': ad.get('seller_article', ''),
        'revenue': m[0],
        'ordered': m[1],
        'hits_view': m[2],
        'hits_tocart': m[3],
        'sessions': m[4],
        'delivered': m[5],
        'returns': m[6],
        'cancellations': m[7],
        'ad_impr': float(ad.get('impr', 0)),
        'ad_clicks': float(ad.get('clicks', 0)),
        'ad_ctr': float(ad.get('ctr_pct', 0)),
        'ad_spend': float(ad.get('spend', 0)),
        'ad_orders': float(ad.get('orders', 0)),
        'ad_sales': float(ad.get('sales', 0)),
        'ad_drr': float(ad.get('drr_pct', 0)),
    }

rows = sorted(combined.values(), key=lambda x: x['revenue'], reverse=True)

# Excel
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Озон Аналитика"

headers = [
    "№", "Артикул", "Ozon SKU",
    "Выручка", "Заказано", "Показы", "В корзину", "Сессии", "Доставлено", "Возвращено", "Отменено", "Выкуп (%)",
    "Рекл. показы", "Рекл. клики", "Рекл. CTR (%)", "Рекл. расход", "Рекл. заказы", "Рекл. продажи", "ДРР (%)"
]

for col, h in enumerate(headers, 1):
    ws.cell(row=1, column=col, value=h)

for row_idx, r in enumerate(rows, 2):
    purchase_rate = round(r['delivered'] / r['ordered'] * 100, 2) if r['ordered'] else 0
    
    ws.cell(row=row_idx, column=1, value=row_idx-1)
    ws.cell(row=row_idx, column=2, value=r['article'])
    ws.cell(row=row_idx, column=3, value=int(r['sku']))
    ws.cell(row=row_idx, column=4, value=r['revenue'])
    ws.cell(row=row_idx, column=5, value=r['ordered'])
    ws.cell(row=row_idx, column=6, value=r['hits_view'])
    ws.cell(row=row_idx, column=7, value=r['hits_tocart'])
    ws.cell(row=row_idx, column=8, value=r['sessions'])
    ws.cell(row=row_idx, column=9, value=r['delivered'])
    ws.cell(row=row_idx, column=10, value=r['returns'])
    ws.cell(row=row_idx, column=11, value=r['cancellations'])
    ws.cell(row=row_idx, column=12, value=purchase_rate)
    ws.cell(row=row_idx, column=13, value=r['ad_impr'])
    ws.cell(row=row_idx, column=14, value=r['ad_clicks'])
    ws.cell(row=row_idx, column=15, value=r['ad_ctr'])
    ws.cell(row=row_idx, column=16, value=r['ad_spend'])
    ws.cell(row=row_idx, column=17, value=r['ad_orders'])
    ws.cell(row=row_idx, column=18, value=r['ad_sales'])
    ws.cell(row=row_idx, column=19, value=r['ad_drr'])

# Итого
total_row = len(rows) + 2
ws.cell(row=total_row, column=1, value="ИТОГО")
t = {c: sum(r[c] for r in rows) for c in ['revenue', 'ordered', 'hits_view', 'hits_tocart', 'sessions', 'delivered', 'returns', 'cancellations', 'ad_impr', 'ad_clicks', 'ad_spend', 'ad_orders', 'ad_sales']}

ws.cell(row=total_row, column=4, value=t['revenue'])
ws.cell(row=total_row, column=5, value=t['ordered'])
ws.cell(row=total_row, column=6, value=t['hits_view'])
ws.cell(row=total_row, column=7, value=t['hits_tocart'])
ws.cell(row=total_row, column=8, value=t['sessions'])
ws.cell(row=total_row, column=9, value=t['delivered'])
ws.cell(row=total_row, column=10, value=t['returns'])
ws.cell(row=total_row, column=11, value=t['cancellations'])
ws.cell(row=total_row, column=12, value=round(t['delivered']/t['ordered']*100, 2) if t['ordered'] else 0)
ws.cell(row=total_row, column=13, value=t['ad_impr'])
ws.cell(row=total_row, column=14, value=t['ad_clicks'])
ws.cell(row=total_row, column=15, value=round(t['ad_clicks']/t['ad_impr']*100, 2) if t['ad_impr'] else 0)
ws.cell(row=total_row, column=16, value=t['ad_spend'])
ws.cell(row=total_row, column=17, value=t['ad_orders'])
ws.cell(row=total_row, column=18, value=t['ad_sales'])
ws.cell(row=total_row, column=19, value=round(t['ad_spend']/t['ad_sales']*100, 2) if t['ad_sales'] else 0)

# Форматирование
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
header_font = Font(bold=True, color="FFFFFF")
thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

for col in range(1, 20):
    ws.cell(row=1, column=col).fill = header_fill
    ws.cell(row=1, column=col).font = header_font
    for row in range(1, total_row + 1):
        ws.cell(row=row, column=col).border = thin_border

output_file = f"{REPORTS_DIR}/ozon_analytics_daily_{datetime.now().strftime('%Y%m%d')}.xlsx"
wb.save(output_file)
print(f"Сохранено: {output_file}")

# Отправляем в Telegram
import requests
files = {'file': open(output_file, 'rb')}
caption = f"Озон Аналитика — {datetime.now().strftime('%B %Y')}\nСтрок: {len(rows)}\nВыручка: {t['revenue']:,} ₽\nРекл. расход: {t['ad_spend']:,.0f} ₽"
print(f"Отправляю в Telegram...")
PYEOF
