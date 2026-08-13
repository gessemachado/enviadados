const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');

const ROOT = __dirname;
const PORT = 8000;
const API_HOST = 'obsidian-envia.duckdns.org';
const LOG_FILE = path.join(__dirname, '.gupshup_log.json');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2':'font/woff2',
};

// ── Log local (JSON em disco) ────────────────────────────────────────
function loadLog() {
  try { return JSON.parse(fs.readFileSync(LOG_FILE, 'utf-8')); } catch { return []; }
}
function saveLog(entries) {
  try { fs.writeFileSync(LOG_FILE, JSON.stringify(entries, null, 2)); }
  catch (e) { console.error('log write err:', e.message); }
}
function appendLog(entry) {
  const log = loadLog();
  log.unshift({ id: Date.now() + Math.random(), enviado_em: new Date().toISOString(), ...entry });
  if (log.length > 5000) log.length = 5000;
  saveLog(log);
}

// ── Helpers ──────────────────────────────────────────────────────────
function normFone(v) {
  if (!v) return '';
  const d = String(v).replace(/\D/g, '');
  if (!d) return '';
  if (!d.startsWith('55') && (d.length === 10 || d.length === 11)) return '55' + d;
  return d;
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', c => raw += c);
    req.on('end', () => {
      try { resolve(raw ? JSON.parse(raw) : {}); }
      catch { reject(new Error('json inválido')); }
    });
  });
}

function jsonRes(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

function callGupshup(apikey, appname, source, destination, template_id, params, mediaUrl, mediaType, mediaId) {
  return new Promise(resolve => {
    const template = JSON.stringify({ id: template_id, params: params || [] });
    const fields = {
      channel: 'whatsapp',
      source, destination, template,
      'src.name': appname,
    };
    if (mediaId) {
      const t = (mediaType || 'image').toLowerCase();
      fields.message = JSON.stringify({ type: t, [t]: { id: mediaId } });
    } else if (mediaUrl) {
      const t = (mediaType || 'image').toLowerCase();
      fields.message = JSON.stringify({ type: t, [t]: { link: mediaUrl } });
    }
    const form = new URLSearchParams(fields).toString();
    const req = https.request({
      host: 'api.gupshup.io', port: 443,
      path: '/wa/api/v1/template/msg', method: 'POST',
      headers: {
        'apikey': apikey,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(form),
      },
    }, up => {
      let body = '';
      up.on('data', c => body += c);
      up.on('end', () => resolve({ status: up.statusCode, body }));
    });
    req.on('error', err => resolve({ status: 0, body: 'network error: ' + err.message }));
    req.end(form);
  });
}

// Envia mensagem de sessão (texto livre) — endpoint /wa/api/v1/msg
// Só funciona nas 24h após o destinatário mandar msg pro business.
function callGupshupText(apikey, appname, source, destination, texto) {
  return new Promise(resolve => {
    const fields = {
      channel: 'whatsapp',
      source, destination,
      'src.name': appname,
      message: JSON.stringify({ type: 'text', text: texto }),
    };
    const form = new URLSearchParams(fields).toString();
    const req = https.request({
      host: 'api.gupshup.io', port: 443,
      path: '/wa/api/v1/msg', method: 'POST',
      headers: {
        apikey,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(form),
      },
    }, up => {
      let body = '';
      up.on('data', c => body += c);
      up.on('end', () => resolve({ status: up.statusCode, body }));
    });
    req.on('error', err => resolve({ status: 0, body: 'network: ' + err.message }));
    req.end(form);
  });
}

async function apiGupshupSendText(req, res) {
  try {
    const b = await readJson(req);
    const source = String(b.source || '').replace(/\D/g, '');
    const dest = normFone(b.destination);
    if (!b.apikey || !b.appname || !source || !dest || !b.texto)
      return jsonRes(res, 400, { error: 'apikey/appname/source/destination/texto obrigatórios' });
    const { status, body } = await callGupshupText(b.apikey, b.appname, source, dest, b.texto);
    let msg_id = null, st = 'error';
    try {
      const j = JSON.parse(body);
      msg_id = j.messageId || null;
      if (status >= 200 && status < 300 && (j.status === 'submitted' || j.status === 'success')) st = 'submitted';
    } catch {}
    appendLog({
      destino: dest, id_cliente: null, cliente_nome: b.cliente_nome || null,
      appname: b.appname, source,
      template_id: null, template_nome: '[TEXTO-SESSAO]',
      params: [texto_len(b.texto)], status: st, http_status: status,
      message_id: msg_id, response_body: body, lote_id: null,
      usuario_nome: 'local-dev',
    });
    const aviso_sandbox = /^1555/.test(source)
      ? `⚠ TEST NUMBER: source ${source} só entrega para números na allowed list do Meta Business Suite.`
      : null;
    const aviso_sessao = st !== 'submitted' && /1002|no active session/i.test(body)
      ? `⚠ SEM SESSÃO ATIVA: o destinatário ${dest} precisa te mandar uma mensagem no WhatsApp primeiro (janela de 24h).`
      : null;
    jsonRes(res, 200, { ok: st === 'submitted', status: st, http_status: status, message_id: msg_id, response: body, aviso_sandbox, aviso_sessao });
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}
function texto_len(t) { return `${(t||'').length} chars`; }

function parseResp(status, body) {
  let msg_id = null, st = 'error';
  try {
    const j = JSON.parse(body);
    msg_id = j.messageId || null;
    if (status >= 200 && status < 300 && (j.status === 'submitted' || j.status === 'success')) st = 'submitted';
  } catch {}
  return { st, msg_id };
}

// ── Handlers ─────────────────────────────────────────────────────────

// Rota original (usada por marketing_teste.html) — mantida
function sendGupshup(req, res) {
  readJson(req).then(async body => {
    const source = String(body.source || '').replace(/\D/g, '');
    const destination = normFone(body.destination);
    const { status, body: respBody } = await callGupshup(
      body.apikey, body.appname, source, destination, body.template_id, body.params
    );
    res.writeHead(status || 502, { 'Content-Type': 'application/json' });
    res.end(respBody);
  }).catch(e => jsonRes(res, 400, { error: e.message }));
}

async function apiGupshupSend(req, res) {
  try {
    const b = await readJson(req);
    const source = String(b.source || '').replace(/\D/g, '');
    const dest = normFone(b.destination);
    if (!b.apikey || !b.appname || !source || !dest || !b.template_id)
      return jsonRes(res, 400, { error: 'apikey/appname/source/destination/template_id obrigatórios' });
    // Aviso: source sandbox (+1 555…) só entrega pra números opted-in no painel Gupshup
    if (/^1555/.test(source)) {
      console.warn(`[SANDBOX] source ${source} → ${dest}: só entrega se ${dest} estiver opted-in no painel.`);
    }
    const { status, body } = await callGupshup(b.apikey, b.appname, source, dest, b.template_id, b.params, b.media_url, b.media_type, b.media_id);
    const { st, msg_id } = parseResp(status, body);
    appendLog({
      destino: dest, id_cliente: b.id_cliente || null,
      cliente_nome: b.cliente_nome || null,
      appname: b.appname, source,
      template_id: b.template_id, template_nome: b.template_nome || null,
      params: b.params || [], status: st, http_status: status,
      message_id: msg_id, response_body: body, lote_id: null,
      usuario_nome: 'local-dev',
    });
    const aviso_sandbox = /^1555/.test(source)
      ? `⚠ TEST NUMBER (${source}): Marketing-Lite tem cota de ~1-2 mensagens/24h por destinatário. Se ${dest} recebeu recentemente, essa nova pode ser descartada silenciosamente até renovar. Registre um número real pra remover a limitação.`
      : null;
    jsonRes(res, 200, { ok: st === 'submitted', status: st, http_status: status, message_id: msg_id, response: body, aviso_sandbox });
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

async function apiGupshupBulk(req, res) {
  try {
    const b = await readJson(req);
    const source = String(b.source || '').replace(/\D/g, '');
    if (!b.apikey || !b.appname || !source || !b.template_id)
      return jsonRes(res, 400, { error: 'apikey/appname/source/template_id obrigatórios' });
    if (!Array.isArray(b.destinos) || !b.destinos.length)
      return jsonRes(res, 400, { error: 'destinos deve ser lista não vazia' });
    if (b.destinos.length > 250)
      return jsonRes(res, 400, { error: 'máximo 250 por lote (limite MM Lite)' });

    const lote_id = 'lot' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    const resultados = [];
    let ok = 0;

    for (let i = 0; i < b.destinos.length; i++) {
      const d = b.destinos[i];
      const dest = normFone(d.destination);
      if (!dest) { resultados.push({ destination: d.destination, ok: false, erro: 'telefone inválido' }); continue; }
      const { status, body } = await callGupshup(b.apikey, b.appname, source, dest, b.template_id, d.params || [], b.media_url, b.media_type, b.media_id);
      const { st, msg_id } = parseResp(status, body);
      appendLog({
        destino: dest, id_cliente: d.id_cliente || null,
        cliente_nome: d.cliente_nome || null,
        appname: b.appname, source,
        template_id: b.template_id, template_nome: b.template_nome || null,
        params: d.params || [], status: st, http_status: status,
        message_id: msg_id, response_body: body, lote_id,
        usuario_nome: 'local-dev',
      });
      if (st === 'submitted') ok++;
      resultados.push({ destination: dest, id_cliente: d.id_cliente || null, ok: st === 'submitted', status: st, http_status: status, message_id: msg_id });
      if (i < b.destinos.length - 1) await new Promise(r => setTimeout(r, 250));
    }
    jsonRes(res, 200, { lote_id, total: b.destinos.length, enviados: ok, falhas: b.destinos.length - ok, resultados });
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Upload de sample media pra criação de template (usa endpoint da Gupshup que
// gera o Meta handle — obrigatório pra templates com header IMAGE/VIDEO/DOCUMENT)
async function apiGupshupUploadSample(req, res) {
  try {
    const parsed = url.parse(req.url, true);
    const apikey = parsed.query.apikey;
    const appId = parsed.query.app_id;
    if (!apikey || !appId) return jsonRes(res, 400, { error: 'apikey e app_id na query obrigatórios' });
    const contentType = req.headers['content-type'] || '';
    if (!contentType.startsWith('multipart/form-data'))
      return jsonRes(res, 400, { error: 'Content-Type deve ser multipart/form-data' });

    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const rawBody = Buffer.concat(chunks);

    // Extrai o arquivo do multipart
    const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/);
    if (!boundaryMatch) return jsonRes(res, 400, { error: 'boundary não encontrado' });
    const boundary = '--' + (boundaryMatch[1] || boundaryMatch[2]);
    const boundaryBuf = Buffer.from(boundary);
    const parts = [];
    let start = 0;
    while (true) {
      const idx = rawBody.indexOf(boundaryBuf, start);
      if (idx < 0) break;
      if (start > 0) parts.push(rawBody.slice(start, idx));
      start = idx + boundaryBuf.length;
    }
    let fileBuf = null, fileName = 'sample.bin', fileMime = 'image/png';
    for (const part of parts) {
      const headerEnd = part.indexOf('\r\n\r\n');
      if (headerEnd < 0) continue;
      const headers = part.slice(2, headerEnd).toString();
      if (!/name="file"/.test(headers)) continue;
      const fn = headers.match(/filename="([^"]+)"/);
      if (fn) fileName = fn[1];
      const ct = headers.match(/Content-Type:\s*([^\r\n]+)/i);
      if (ct) fileMime = ct[1].trim();
      fileBuf = part.slice(headerEnd + 4, part.length - 2);
      break;
    }
    if (!fileBuf) return jsonRes(res, 400, { error: 'campo "file" não encontrado' });

    // Sanitiza nome
    let safeName = fileName.replace(/[^a-zA-Z0-9._-]/g, '_');
    if (safeName.length < 5) safeName = 'sample_' + Date.now().toString(36) + '.png';

    // Monta multipart pro endpoint /template/upload/media com file_type e file_length
    const b2 = '----g' + Math.random().toString(36).slice(2);
    const out = [];
    out.push(Buffer.from(`--${b2}\r\nContent-Disposition: form-data; name="file_type"\r\n\r\n${fileMime}\r\n`));
    out.push(Buffer.from(`--${b2}\r\nContent-Disposition: form-data; name="file_length"\r\n\r\n${fileBuf.length}\r\n`));
    out.push(Buffer.from(`--${b2}\r\nContent-Disposition: form-data; name="file"; filename="${safeName}"\r\nContent-Type: ${fileMime}\r\n\r\n`));
    out.push(fileBuf);
    out.push(Buffer.from(`\r\n--${b2}--\r\n`));
    const body = Buffer.concat(out);

    const options = {
      host: 'api.gupshup.io', port: 443,
      path: `/wa/app/${encodeURIComponent(appId)}/template/upload/media`,
      method: 'POST',
      headers: {
        apikey,
        'Content-Type': `multipart/form-data; boundary=${b2}`,
        'Content-Length': body.length,
      },
    };
    const up = https.request(options, r => {
      let bd = '';
      r.on('data', c => bd += c);
      r.on('end', () => {
        let j; try { j = JSON.parse(bd); } catch { j = null; }
        const handle = j?.handleId?.message;
        if (r.statusCode !== 200 || !handle) {
          return jsonRes(res, r.statusCode || 502, { error: 'Gupshup: ' + bd.substring(0, 300) });
        }
        jsonRes(res, 200, { handleId: handle, mediaType: fileMime.split('/')[0] });
      });
    });
    up.on('error', err => jsonRes(res, 502, { error: 'network: ' + err.message }));
    up.end(body);
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Cria um template novo na Gupshup (submete pra aprovação Meta)
async function apiGupshupCreateTemplate(req, res) {
  try {
    const b = await readJson(req);
    if (!b.apikey || !b.app_id || !b.element_name || !b.content) {
      return jsonRes(res, 400, { error: 'apikey, app_id, element_name e content obrigatórios' });
    }
    const fields = {
      elementName:  b.element_name,
      languageCode: b.language_code || 'pt_BR',
      category:     b.category      || 'MARKETING',
      templateType: b.template_type || 'TEXT',
      vertical:     b.vertical      || 'MARKETING',
      content:      b.content,
      example:      b.example       || b.content,
      enableSample: 'true',
      allowTemplateCategoryChange: 'true',
    };
    if (b.footer) fields.footer = b.footer;
    // Gupshup aceita URL público OU Meta handle no mesmo campo exampleMedia.
    // Handle (obtido via /template/upload/media) tem prioridade — é o que garante aprovação.
    if (b.example_media_id) fields.exampleMedia = b.example_media_id;
    else if (b.example_media) fields.exampleMedia = b.example_media;

    const form = new URLSearchParams(fields).toString();
    const options = {
      host: 'api.gupshup.io', port: 443,
      path: `/wa/app/${encodeURIComponent(b.app_id)}/template`,
      method: 'POST',
      headers: {
        apikey: b.apikey,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(form),
      },
    };
    const up = https.request(options, r => {
      let body = '';
      r.on('data', c => body += c);
      r.on('end', () => {
        res.writeHead(r.statusCode || 502, { 'Content-Type': 'application/json' });
        res.end(body);
      });
    });
    up.on('error', err => jsonRes(res, 502, { error: err.message }));
    up.end(form);
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Consulta o status/eventos de uma mensagem específica na Gupshup.
// GET /api/gupshup/msg-status?apikey=...&app_id=...&msg_id=...&app_name=...
// Chama /wa/app/{appId}/msg/{msgId} e, se vazio, faz fallback pra /wa/app/{appName}/msg-event/{msgId}
async function apiGupshupMsgStatus(req, res) {
  try {
    const parsed = url.parse(req.url, true);
    const { apikey, app_id, msg_id, app_name } = parsed.query;
    if (!apikey || !app_id || !msg_id)
      return jsonRes(res, 400, { error: 'apikey, app_id e msg_id obrigatórios' });

    const call = (path) => new Promise(resolve => {
      const up = https.request({
        host: 'api.gupshup.io', port: 443, path, method: 'GET',
        headers: { apikey },
      }, r => {
        let body = '';
        r.on('data', c => body += c);
        r.on('end', () => resolve({ status: r.statusCode, body, path }));
      });
      up.on('error', err => resolve({ status: 0, body: 'net: ' + err.message, path }));
      up.end();
    });

    const tries = [
      `/wa/app/${encodeURIComponent(app_id)}/msg/${encodeURIComponent(msg_id)}`,
      `/wa/app/${encodeURIComponent(app_id)}/msg-event/${encodeURIComponent(msg_id)}`,
    ];
    if (app_name) tries.push(`/wa/app/${encodeURIComponent(app_name)}/msg-event/${encodeURIComponent(msg_id)}`);

    const results = [];
    for (const p of tries) {
      const r = await call(p);
      results.push(r);
      if (r.status === 200 && r.body && r.body !== '[]' && r.body !== '{}') {
        let parsedBody; try { parsedBody = JSON.parse(r.body); } catch { parsedBody = r.body; }
        return jsonRes(res, 200, { endpoint: p, http_status: r.status, data: parsedBody, tried: results });
      }
    }
    jsonRes(res, 200, {
      warning: 'Nenhum endpoint retornou dados. Gupshup só entrega estado por callback webhook — se o webhook não estiver configurado, esses endpoints devolvem vazio.',
      tried: results,
    });
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Lista usuários opted-in na Gupshup.
// GET /api/gupshup/list-optin?apikey=...&app_name=...
async function apiGupshupListOptin(req, res) {
  try {
    const parsed = url.parse(req.url, true);
    const { apikey, app_name } = parsed.query;
    if (!apikey || !app_name) return jsonRes(res, 400, { error: 'apikey e app_name obrigatórios' });
    const path = `/sm/api/v1/users/${encodeURIComponent(app_name)}`;
    const up = https.request({
      host: 'api.gupshup.io', port: 443, path, method: 'GET',
      headers: { apikey },
    }, r => {
      let body = '';
      r.on('data', c => body += c);
      r.on('end', () => {
        let j; try { j = JSON.parse(body); } catch { j = body; }
        jsonRes(res, r.statusCode || 502, { http_status: r.statusCode, endpoint: path, data: j });
      });
    });
    up.on('error', err => jsonRes(res, 502, { error: err.message }));
    up.end();
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Marca um usuário como opted-in na Gupshup (necessário pra receber templates).
// POST /api/gupshup/optin  body: { apikey, app_id, phone, app_name? }
// Chama Gupshup /wa/app/{appId}/wallet/optin/{phone}
async function apiGupshupOptin(req, res) {
  try {
    const b = await readJson(req);
    const phone = normFone(b.phone);
    if (!b.apikey || !b.app_id || !phone)
      return jsonRes(res, 400, { error: 'apikey, app_id e phone obrigatórios' });

    const tryPost = (path) => new Promise(resolve => {
      const up = https.request({
        host: 'api.gupshup.io', port: 443, path, method: 'POST',
        headers: { apikey: b.apikey, 'Content-Length': 0 },
      }, r => {
        let body = '';
        r.on('data', c => body += c);
        r.on('end', () => resolve({ status: r.statusCode, body, path }));
      });
      up.on('error', err => resolve({ status: 0, body: 'net: ' + err.message, path }));
      up.end();
    });

    // Endpoint oficial confirmado: POST /sm/api/v1/app/opt/in/{appName}
    // O Gupshup aceita user tanto como form-urlencoded quanto JSON. Tento os dois.
    const tryOptin = (path, body, contentType) => new Promise(resolve => {
      const up = https.request({
        host: 'api.gupshup.io', port: 443, path, method: 'POST',
        headers: {
          apikey: b.apikey,
          'Content-Type': contentType,
          'Content-Length': Buffer.byteLength(body),
        },
      }, r => {
        let rb = '';
        r.on('data', c => rb += c);
        r.on('end', () => resolve({ status: r.statusCode, body: rb, path, sent: body, contentType }));
      });
      up.on('error', err => resolve({ status: 0, body: 'net: ' + err.message, path }));
      up.end(body);
    });

    const appName = b.app_name || 'sertaocomunic';
    const tries = [
      // 1) Oficial (SDK): /sm/api/v1/app/opt/in/{appName} + form user=phone
      { path: `/sm/api/v1/app/opt/in/${encodeURIComponent(appName)}`, body: `user=${encodeURIComponent(phone)}`, ct: 'application/x-www-form-urlencoded' },
      // 2) Oficial (SDK) formato JSON
      { path: `/sm/api/v1/app/opt/in/${encodeURIComponent(appName)}`, body: JSON.stringify({ user: phone }), ct: 'application/json' },
      // 3) Enterprise API: /wa/api/v1/app/opt/in/{phone}
      { path: `/wa/api/v1/app/opt/in/${encodeURIComponent(phone)}`, body: 'channel=whatsapp', ct: 'application/x-www-form-urlencoded' },
      // 4) Novo /wa/app/{appId}/optin
      { path: `/wa/app/${encodeURIComponent(b.app_id)}/optin`, body: `user=${encodeURIComponent(phone)}`, ct: 'application/x-www-form-urlencoded' },
      // 5) Legacy wallet
      { path: `/wa/app/${encodeURIComponent(b.app_id)}/wallet/optin/${encodeURIComponent(phone)}`, body: '', ct: 'application/x-www-form-urlencoded' },
    ];

    const results = [];
    for (const t of tries) {
      const r = await tryOptin(t.path, t.body, t.ct);
      results.push({ path: r.path, ct: r.contentType, status: r.status, body: r.body.substring(0, 250) });
      if (r.status >= 200 && r.status < 300) {
        let parsed; try { parsed = JSON.parse(r.body); } catch { parsed = r.body; }
        if (parsed?.status === 'error') continue;
        return jsonRes(res, 200, { ok: true, endpoint: r.path, http_status: r.status, data: parsed, tried: results });
      }
    }
    jsonRes(res, 200, { ok: false, tried: results, dica: 'Se falhou em todos, faça manualmente em https://www.gupshup.io/whatsappassistant/#/account/opt-in' });
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Consulta a wallet/saldo Gupshup — se estiver zerado, envios voltam submitted mas não entregam
async function apiGupshupWallet(req, res) {
  try {
    const parsed = url.parse(req.url, true);
    const { apikey } = parsed.query;
    if (!apikey) return jsonRes(res, 400, { error: 'apikey obrigatório' });
    const up = https.request({
      host: 'api.gupshup.io', port: 443,
      path: '/wa/api/v1/wallet/balance', method: 'GET',
      headers: { apikey },
    }, r => {
      let body = '';
      r.on('data', c => body += c);
      r.on('end', () => {
        let j; try { j = JSON.parse(body); } catch { j = body; }
        jsonRes(res, r.statusCode || 502, { http_status: r.statusCode, data: j });
      });
    });
    up.on('error', err => jsonRes(res, 502, { error: err.message }));
    up.end();
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

// Proxy autenticado pro endpoint de templates da Gupshup
async function apiGupshupTemplates(req, res) {
  try {
    const b = await readJson(req);
    if (!b.apikey || !b.app_id)
      return jsonRes(res, 400, { error: 'apikey e app_id obrigatórios' });
    const options = {
      host: 'api.gupshup.io', port: 443,
      path: `/wa/app/${encodeURIComponent(b.app_id)}/template`,
      method: 'GET',
      headers: { apikey: b.apikey },
    };
    const up = https.request(options, r => {
      let body = '';
      r.on('data', c => body += c);
      r.on('end', () => {
        res.writeHead(r.statusCode || 502, { 'Content-Type': 'application/json' });
        res.end(body);
      });
    });
    up.on('error', err => jsonRes(res, 502, { error: err.message }));
    up.end();
  } catch (e) { jsonRes(res, 500, { error: e.message }); }
}

function apiGupshupHist(req, res) {
  const parsed = url.parse(req.url, true);
  const lote = parsed.query.lote_id;
  const limite = Math.min(parseInt(parsed.query.limite || '200'), 1000);
  let log = loadLog();
  if (lote) log = log.filter(e => e.lote_id === lote);
  jsonRes(res, 200, log.slice(0, limite));
}

// Proxy pro VPS: adapta /api/clientes/inativos → formato de marketing
function apiGupshupClientes(req, res) {
  const parsed = url.parse(req.url, true);
  const busca = (parsed.query.busca || '').toLowerCase();
  const inativo = parsed.query.inativo_dias || '0';

  const options = {
    host: API_HOST, port: 443,
    path: '/api/clientes/inativos?dias=' + encodeURIComponent(inativo),
    method: 'GET',
    headers: { host: API_HOST, 'Authorization': req.headers.authorization || '' },
  };
  const upstream = https.request(options, up => {
    let body = '';
    up.on('data', c => body += c);
    up.on('end', () => {
      let arr;
      try { arr = JSON.parse(body); } catch { arr = []; }
      if (!Array.isArray(arr)) {
        return jsonRes(res, up.statusCode || 502, arr || { error: 'upstream sem lista' });
      }
      const out = arr
        .filter(c => c.contato && (!busca || (c.nome || '').toLowerCase().includes(busca)))
        .map(c => ({
          id_cliente: c.id_cliente,
          nome: c.nome,
          cgc_cpf: c.cgc_cpf,
          telefone: normFone(c.contato),
          cidade: '', uf: '',
          ultima_compra: c.ultima_compra,
        }));
      jsonRes(res, 200, out);
    });
  });
  upstream.on('error', err => jsonRes(res, 502, { error: 'proxy error: ' + err.message }));
  upstream.end();
}

function proxyApi(req, res) {
  const options = {
    host: API_HOST, port: 443,
    path: req.url, method: req.method,
    headers: { ...req.headers, host: API_HOST },
  };
  const upstream = https.request(options, up => {
    res.writeHead(up.statusCode, up.headers);
    up.pipe(res);
  });
  upstream.on('error', err => { res.writeHead(502); res.end('proxy error: ' + err.message); });
  req.pipe(upstream);
}

function serveStatic(req, res) {
  const parsed = url.parse(req.url);
  let pathname = decodeURIComponent(parsed.pathname);
  if (pathname === '/') pathname = '/index.html';
  const filePath = path.join(ROOT, pathname);
  if (!filePath.startsWith(ROOT)) { res.writeHead(403); return res.end('forbidden'); }
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) { res.writeHead(404); return res.end('not found: ' + pathname); }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

http.createServer((req, res) => {
  const p = req.url.split('?')[0];
  if (p === '/gupshup/send' && req.method === 'POST') return sendGupshup(req, res);
  if (p === '/api/gupshup/send' && req.method === 'POST') return apiGupshupSend(req, res);
  if (p === '/api/gupshup/send-text' && req.method === 'POST') return apiGupshupSendText(req, res);
  if (p === '/api/gupshup/enviar-lote' && req.method === 'POST') return apiGupshupBulk(req, res);
  if (p === '/api/gupshup/templates' && req.method === 'POST') return apiGupshupTemplates(req, res);
  // upload-media agora vai pra Flask (salva em /var/www/enviadados/media, URL permanente)
  if (p === '/api/gupshup/upload-sample-media' && req.method === 'POST') return apiGupshupUploadSample(req, res);
  if (p === '/api/gupshup/create-template' && req.method === 'POST') return apiGupshupCreateTemplate(req, res);
  if (p === '/api/gupshup/envios' && req.method === 'GET') return apiGupshupHist(req, res);
  if (p === '/api/gupshup/msg-status' && req.method === 'GET') return apiGupshupMsgStatus(req, res);
  if (p === '/api/gupshup/wallet' && req.method === 'GET') return apiGupshupWallet(req, res);
  if (p === '/api/gupshup/optin' && req.method === 'POST') return apiGupshupOptin(req, res);
  if (p === '/api/gupshup/list-optin' && req.method === 'GET') return apiGupshupListOptin(req, res);
  if (p === '/api/gupshup/clientes-marketing' && req.method === 'GET') return apiGupshupClientes(req, res);
  if (req.url.startsWith('/api/')) return proxyApi(req, res);
  serveStatic(req, res);
}).listen(PORT, () => {
  console.log(`serving ${ROOT} on http://localhost:${PORT}`);
  console.log(`/api/gupshup/*   → tratado localmente (log em ${LOG_FILE})`);
  console.log(`/api/*           → proxy pra https://${API_HOST}`);
  console.log(`POST /gupshup/send (legado) → api.gupshup.io direto`);
});
