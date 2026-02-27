/** 
 * Ozon Performance Ads → Daily statistics by SKU (articles)
 * Запуск: exportOzonAdsBySku(1) // вчера
 *         exportOzonAdsBySku(7) // последние 7 дней
 */
const OZON_BASE = 'https://api-performance.ozon.ru';
const SHEET_NAME = 'reklama_test';
const DAYSBACK = 1;
const BATCH_SIZE = 10;

function exportOzonAdsBySku() {
  const daysBack = DAYSBACK;
  if (!daysBack || daysBack < 1) throw new Error('DAYSBACK >= 1');
  
  const sheet = getOrCreateSheet_(SHEET_NAME);
  const tz = Session.getScriptTimeZone() || 'Europe/Moscow';
  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const start = new Date(end.getFullYear(), end.getMonth(), end.getDate() - (daysBack - 1));
  
  const token = getPerfAccessToken_();
  
  // 1) Получаем список кампаний
  const campaigns = getCampaigns_(token);
  if (!campaigns.length) {
    Logger.log('Нет кампаний - проверь логи!');
    return;
  }
  Logger.log('Найдено кампаний: ' + campaigns.length);
  
  // 2) Разбиваем на батчи
  const results = [];
  for (let i = 0; i < campaigns.length; i += BATCH_SIZE) {
    const batch = campaigns.slice(i, i + BATCH_SIZE);
    const campaignIds = batch.map(function(c) { return c.id; });
    
    const stats = getProductStats_(token, campaignIds, start, end, tz);
    results.push.apply(results, stats);
    
    Utilities.sleep(500);
  }
  
  // 3) Пишем в таблицу
  const lastRow = sheet.getLastRow();
  if (lastRow === 0) {
    const header = ['date', 'sku', 'campaign_id', 'campaign_name', 'views', 'clicks', 'ctr', 'cost', 'orders', 'revenue', 'acos'];
    sheet.getRange(1, 1, 1, header.length).setValues([header]);
  }
  
  const dataRows = results.map(function(r) {
    return [
      r.date, r.sku, r.campaign_id, r.campaign_name, 
      r.views, r.clicks, r.ctr, r.cost, r.orders, r.revenue, r.acos
    ];
  });
  
  if (dataRows.length) {
    sheet.getRange(lastRow + 1, 1, dataRows.length, dataRows[0].length).setValues(dataRows);
  }
  Logger.log('Записано строк: ' + dataRows.length);
}

/** Тест получения кампаний - запусти эту функцию и посмотри логи */
function testGetCampaigns_() {
  var token = getPerfAccessToken_();
  var result = getCampaigns_(token);
  Logger.log(JSON.stringify(result, null, 2));
}

/** Получить список кампаний - пробуем разные варианты */
function getCampaigns_(token) {
  // Вариант 1: базовый
  var url = OZON_BASE + '/api/client/campaign';
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Authorization: 'Bearer ' + token }
  });
  
  var code = resp.getResponseCode();
  var body = resp.getContentText();
  Logger.log('Campaigns response code: ' + code);
  Logger.log('Campaigns response body: ' + body.substring(0, 2000));
  
  if (code === 200) {
    try {
      var json = JSON.parse(body);
      // Разные варианты структуры
      if (json.list) return json.list;
      if (json.items) return json.items;
      if (json.result) return json.result;
      if (json.campaigns) return json.campaigns;
      if (Array.isArray(json)) return json;
      Logger.log('Unknown JSON structure: ' + JSON.stringify(json));
    } catch (e) {
      Logger.log('JSON parse error: ' + e);
    }
  }
  
  // Вариант 2: с параметрами
  if (code !== 200) {
    var url2 = OZON_BASE + '/api/client/campaign?limit=100&offset=0';
    resp = UrlFetchApp.fetch(url2, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { Authorization: 'Bearer ' + token }
    });
    code = resp.getResponseCode();
    body = resp.getContentText();
    Logger.log('Campaigns v2 response: ' + code);
    
    if (code === 200) {
      var json = JSON.parse(body);
      if (json.list) return json.list;
      if (json.items) return json.items;
      if (json.result) return json.result;
    }
  }
  
  // Вариант 3: POST
  if (code !== 200) {
    var url3 = OZON_BASE + '/api/client/campaign/list';
    resp = UrlFetchApp.fetch(url3, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      headers: { Authorization: 'Bearer ' + token },
      payload: JSON.stringify({ limit: 100, offset: 0 })
    });
    code = resp.getResponseCode();
    body = resp.getContentText();
    Logger.log('Campaigns v3 (POST) response: ' + code);
    Logger.log(body.substring(0, 2000));
    
    if (code === 200) {
      var json = JSON.parse(body);
      if (json.list) return json.list;
      if (json.items) return json.items;
      if (json.result) return json.result;
    }
  }
  
  return [];
}

/** Получить статистику по товарам для списка кампаний (батчами) */
function getProductStats_(token, campaignIds, start, end, tz) {
  var dateFrom = formatDate_(start, tz);
  var dateTo = formatDate_(end, tz);
  var results = [];
  
  // Разбиваем на батчи по 10 кампаний
  for (var i = 0; i < campaignIds.length; i += BATCH_SIZE) {
    var batchIds = campaignIds.slice(i, i + BATCH_SIZE);
    
    // Пробуем CSV с campaign_id - может вернуть разбивку по товарам
    var url = OZON_BASE + '/api/client/statistics/daily?dateFrom=' + dateFrom + '&dateTo=' + dateTo + '&campaign_id=' + batchIds.join(',');
    
    var resp = UrlFetchApp.fetch(url, { 
      method: 'get', 
      muteHttpExceptions: true, 
      headers: { Authorization: 'Bearer ' + token }
    });
    
    var code = resp.getResponseCode();
    var body = resp.getContentText();
    
    if (code === 200) {
      var rows = parseCsv_(body);
      if (rows.length > 1) {
        var mapped = mapCsvItems_(rows, dateFrom);
        results.push.apply(results, mapped);
      }
    } else {
      Logger.log('Batch ' + i + ' error ' + code + ': ' + body.substring(0, 200));
    }
    
    // Пауза между батчами
    Utilities.sleep(300);
  }
  
  Logger.log('Total stats rows: ' + results.length);
  return results;
}

function mapCsvItems_(rows, defaultDate) {
  if (!rows || rows.length < 2) return [];
  var header = rows[0].map(function(h) { return h.toLowerCase().trim(); });
  Logger.log('CSV header: ' + header.join(', '));
  
  var dataRows = rows.slice(1);
  return dataRows.map(function(row) {
    var obj = {};
    header.forEach(function(h, i) { obj[h] = row[i] || ''; });
    
    return {
      date: obj.date || defaultDate,
      sku: obj.sku || obj['sku/id'] || obj.articul || obj['product id'] || '',
      campaign_id: obj['campaign id'] || obj.campaign_id || '',
      campaign_name: obj['campaign name'] || obj.campaign_name || '',
      views: parseInt(obj.views || obj.shows || 0),
      clicks: parseInt(obj.clicks || 0),
      ctr: parseFloat(obj.ctr || 0),
      cost: parseFloat(obj.cost || obj.spend || 0),
      orders: parseInt(obj.orders || obj.purchases || 0),
      revenue: parseFloat(obj.revenue || obj.sales || 0),
      acos: '0%'
    };
  });
}

function parseCsv_(csvText) {
  var text = csvText.replace(/^\uFEFF/, '');
  var delim = text.indexOf(';') > text.indexOf(',') ? ';' : ',';
  var rows = [];
  var row = [];
  var field = '';
  var inQuotes = false;
  
  for (var i = 0; i < text.length; i++) {
    var c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else { inQuotes = false; }
      } else { field += c; }
      continue;
    }
    if (c === '"') { inQuotes = true; continue; }
    if (c === delim) { row.push(field); field = ''; continue; }
    if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field);
      field = '';
      if (row.length > 1 || (row.length === 1 && row[0] !== '')) rows.push(row);
      row = [];
      continue;
    }
    field += c;
  }
  row.push(field);
  if (row.length > 1 || (row.length === 1 && row[0] !== '')) rows.push(row);
  return rows;
}

function mapItems_(items, defaultDate) {
  if (!items) return [];
  return items.map(function(item) {
    var revenue = item.revenue || 0;
    var cost = item.cost || 0;
    return {
      date: item.date || defaultDate,
      sku: item.sku || item.product_id || item.item_id || '',
      campaign_id: item.campaign_id,
      campaign_name: item.campaign_name || '',
      views: item.views || 0,
      clicks: item.clicks || 0,
      ctr: item.ctr || 0,
      cost: cost,
      orders: item.orders || 0,
      revenue: revenue,
      acos: revenue > 0 ? (cost / revenue * 100).toFixed(2) + '%' : '0%'
    };
  });
}

/** === Auth === */
function getPerfAccessToken_() {
  var props = PropertiesService.getScriptProperties();
  var clientId = props.getProperty('OZON_PERF_CLIENT_ID');
  var clientSecret = props.getProperty('OZON_PERF_CLIENT_SECRET');
  
  if (!clientId || !clientSecret) {
    throw new Error('Не заданы Script Properties: OZON_PERF_CLIENT_ID и OZON_PERF_CLIENT_SECRET');
  }
  
  var cachedToken = props.getProperty('OZON_PERF_ACCESS_TOKEN');
  var cachedExp = Number(props.getProperty('OZON_PERF_ACCESS_TOKEN_EXP') || '0');
  var nowSec = Math.floor(Date.now() / 1000);
  
  if (cachedToken && cachedExp && (cachedExp - 60) > nowSec) {
    return cachedToken;
  }
  
  var url = OZON_BASE + '/api/client/token';
  var payload = { 
    client_id: clientId, 
    client_secret: clientSecret, 
    grant_type: 'client_credentials' 
  };
  var resp = UrlFetchApp.fetch(url, {
    method: 'post', 
    contentType: 'application/json', 
    muteHttpExceptions: true,
    payload: JSON.stringify(payload)
  });
  
  var json = JSON.parse(resp.getContentText());
  var accessToken = json.access_token;
  var expiresIn = Number(json.expires_in || 3600);
  var expSec = nowSec + expiresIn;
  
  props.setProperty('OZON_PERF_ACCESS_TOKEN', accessToken);
  props.setProperty('OZON_PERF_ACCESS_TOKEN_EXP', String(expSec));
  return accessToken;
}

function getOrCreateSheet_(name) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  return sh;
}

function formatDate_(d, tz) {
  return Utilities.formatDate(d, tz, 'yyyy-MM-dd');
}