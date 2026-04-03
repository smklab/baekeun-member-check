const SHEET_NAME = '주소제출';
const SECRET_TOKEN = 'CHANGE_ME_TO_RANDOM_SECRET';

const HEADERS = [
  '제출시각',
  '수정시각',
  '입력성명',
  '입력연락처',
  '명부성명',
  '세대',
  '우편번호',
  '주소',
  '상세주소',
  '개인정보동의',
  'IP',
  'User-Agent',
];

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (!body || body.secret !== SECRET_TOKEN) {
      return jsonResponse({ ok: false, error: '인증에 실패했습니다.' });
    }

    const action = body.action;
    const payload = body.payload || {};

    ensureHeader_();

    if (action === 'findEntry') {
      return jsonResponse({ ok: true, data: findEntry_(payload) });
    }
    if (action === 'upsertEntry') {
      return jsonResponse({ ok: true, data: upsertEntry_(payload) });
    }
    if (action === 'listEntries') {
      return jsonResponse({ ok: true, data: listEntries_(payload) });
    }
    if (action === 'adminUpdateEntry') {
      return jsonResponse({ ok: true, data: adminUpdateEntry_(payload) });
    }

    return jsonResponse({ ok: false, error: '알 수 없는 action입니다.' });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error && error.message || error) });
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  return sheet;
}

function ensureHeader_() {
  const sheet = getSheet_();
  const firstRow = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  const same = HEADERS.every((h, idx) => firstRow[idx] === h);
  if (!same) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  }
}

function normalizePhone_(value) {
  return String(value || '').replace(/\D+/g, '');
}

function normalizeName_(value) {
  return String(value || '').replace(/\s+/g, '').trim();
}

function rowToObject_(row, rowNumber) {
  return {
    row_number: rowNumber,
    submitted_at: row[0] || '',
    updated_at: row[1] || '',
    input_name: row[2] || '',
    input_phone: row[3] || '',
    member_name: row[4] || '',
    generation: row[5] || '',
    zipcode: row[6] || '',
    address: row[7] || '',
    detail_address: row[8] || '',
    consent: row[9] || '',
    ip: row[10] || '',
    user_agent: row[11] || '',
  };
}

function findMatchRowNumber_(inputName, inputPhone) {
  const sheet = getSheet_();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return 0;

  const values = sheet.getRange(2, 1, lastRow - 1, HEADERS.length).getValues();
  const targetName = normalizeName_(inputName);
  const targetPhone = normalizePhone_(inputPhone);

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];
    if (normalizePhone_(row[3]) === targetPhone && normalizeName_(row[2]) === targetName) {
      return i + 2;
    }
  }
  return 0;
}

function findEntry_(payload) {
  const rowNumber = findMatchRowNumber_(payload.input_name, payload.input_phone);
  if (!rowNumber) return {};
  const row = getSheet_().getRange(rowNumber, 1, 1, HEADERS.length).getValues()[0];
  return rowToObject_(row, rowNumber);
}

function upsertEntry_(payload) {
  const sheet = getSheet_();
  let rowNumber = findMatchRowNumber_(payload.input_name, payload.input_phone);
  const row = [
    payload.submitted_at || '',
    payload.updated_at || '',
    payload.input_name || '',
    payload.input_phone || '',
    payload.member_name || '',
    payload.generation || '',
    payload.zipcode || '',
    payload.address || '',
    payload.detail_address || '',
    payload.consent || '',
    payload.ip || '',
    payload.user_agent || '',
  ];

  if (rowNumber) {
    const existingSubmittedAt = sheet.getRange(rowNumber, 1).getValue();
    row[0] = existingSubmittedAt || payload.submitted_at || '';
    sheet.getRange(rowNumber, 1, 1, HEADERS.length).setValues([row]);
  } else {
    rowNumber = sheet.getLastRow() + 1;
    sheet.getRange(rowNumber, 1, 1, HEADERS.length).setValues([row]);
  }
  return { row_number: rowNumber };
}

function listEntries_(payload) {
  const sheet = getSheet_();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return { rows: [] };

  const query = String(payload.query || '').trim().toLowerCase();
  const values = sheet.getRange(2, 1, lastRow - 1, HEADERS.length).getValues();
  let rows = values.map((row, idx) => rowToObject_(row, idx + 2));

  if (query) {
    rows = rows.filter((row) => {
      const text = [
        row.input_name,
        row.input_phone,
        row.member_name,
        row.generation,
        row.zipcode,
        row.address,
        row.detail_address,
      ].join(' ').toLowerCase();
      return text.indexOf(query) >= 0;
    });
  }

  rows.sort((a, b) => Number(b.row_number) - Number(a.row_number));
  return { rows };
}

function adminUpdateEntry_(payload) {
  const rowNumber = Number(payload.row_number || 0);
  if (!rowNumber || rowNumber < 2) {
    throw new Error('유효한 행 번호가 아닙니다.');
  }

  const sheet = getSheet_();
  const row = sheet.getRange(rowNumber, 1, 1, HEADERS.length).getValues()[0];
  row[1] = payload.updated_at || '';
  row[6] = payload.zipcode || '';
  row[7] = payload.address || '';
  row[8] = payload.detail_address || '';
  sheet.getRange(rowNumber, 1, 1, HEADERS.length).setValues([row]);
  return { row_number: rowNumber };
}
