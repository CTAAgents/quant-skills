#!/usr/bin/env node
/**
 * Polymarket Router CLI — 双模引擎 (优化版)
 *
 * 策略：
 *   - 首选：Python SmartRouter（多源路由 + 故障转移 + 缓存）
 *   - 降级：Direct API（纯Node.js零依赖，直连Gamma/CLOB）
 *
 * 优化内容：
 *   - 增强错误处理和用户友好的错误信息
 *   - 添加代理支持（环境变量和命令行参数）
 *   - 添加诊断命令（网络检查、代理测试）
 *   - 改进帮助文本和使用示例
 *
 * 用法：
 *   node wrapper.js search <query>
 *   node wrapper.js events --tag=crypto --limit=10
 *   node wrapper.js market <slug>
 *   node wrapper.js sports
 *   node wrapper.js tags
 *   node wrapper.js price <token_id> [buy|sell]
 *   node wrapper.js book <token_id>
 *   node wrapper.js alt-search <query>
 *   node wrapper.js alt <asset>
 *   node wrapper.js router status|test|stats|config
 *   node wrapper.js diagnose
 *   node wrapper.js test-proxy [proxy_url]
 *
 * 短别名：s=search, e=events, m=market, t=tags, p=price, b=book
 */

import { spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ─── 常量 ────────────────────────────────────────────
const GAMMA_API = 'https://gamma-api.polymarket.com';
const CLOB_API  = 'https://clob.polymarket.com';

const SHORT_ALIAS = {
  s: 'search', e: 'events', m: 'market', t: 'tags', p: 'price', b: 'book'
};

// ─── 代理配置 ─────────────────────────────────────────
const PROXY_CONFIG = {
  enabled: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.https_proxy || process.env.http_proxy,
  url: process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.https_proxy || process.env.http_proxy
};

// ─── 错误处理类 ───────────────────────────────────────
class ErrorHandler {
  static handle(error, context = '未知操作') {
    const errorInfo = {
      timestamp: new Date().toISOString(),
      context: context,
      error: error.message || String(error),
      suggestion: this.getSuggestion(error)
    };

    // 格式化错误信息
    console.error(`\n❌ 错误: ${error.message || String(error)}`);
    console.error(`   上下文: ${context}`);
    console.error(`   建议: ${errorInfo.suggestion}`);

    // 提供调试信息
    if (process.env.DEBUG) {
      console.error(`   详细信息: ${JSON.stringify(errorInfo, null, 2)}`);
    }

    return errorInfo;
  }

  static getSuggestion(error) {
    const message = error.message || String(error);

    if (message.includes('fetch failed') || message.includes('ECONNREFUSED')) {
      return '网络连接失败，请检查：\n     1. 网络连接是否正常\n     2. 是否需要配置代理（设置HTTPS_PROXY环境变量）\n     3. 防火墙是否阻止了连接';
    } else if (message.includes('timeout') || message.includes('ETIMEDOUT')) {
      return '请求超时，请：\n     1. 稍后重试\n     2. 增加超时时间（当前默认10秒）\n     3. 检查网络连接质量';
    } else if (message.includes('HTTP 429')) {
      return '请求过于频繁，请：\n     1. 等待1-2分钟后重试\n     2. 减少请求频率\n     3. 使用缓存机制';
    } else if (message.includes('HTTP 403')) {
      return '访问被拒绝，请：\n     1. 检查是否需要认证\n     2. 尝试使用代理\n     3. 联系数据源管理员';
    } else if (message.includes('HTTP 404')) {
      return '资源不存在，请：\n     1. 检查查询参数是否正确\n     2. 使用search命令搜索可用市场\n     3. 查看tags命令获取可用分类';
    } else if (message.includes('JSON')) {
      return '数据解析失败，请：\n     1. 稍后重试（可能是临时问题）\n     2. 使用diagnoze命令检查数据源状态\n     3. 尝试其他数据源';
    } else if (message.includes('Python') || message.includes('python')) {
      return 'Python环境问题，请：\n     1. 确保Python已安装并在PATH中\n     2. 安装依赖：pip install -r requirements.txt\n     3. 使用Direct API模式（自动降级）';
    }

    return '请查看详细错误信息，或使用diagnoze命令进行诊断';
  }

  static formatSuccess(message, details = null) {
    console.log(`✅ ${message}`);
    if (details) {
      console.log(`   ${details}`);
    }
  }

  static formatWarning(message, details = null) {
    console.log(`⚠️  ${message}`);
    if (details) {
      console.log(`   ${details}`);
    }
  }

  static formatInfo(message, details = null) {
    console.log(`ℹ️  ${message}`);
    if (details) {
      console.log(`   ${details}`);
    }
  }
}

// ─── 诊断工具类 ───────────────────────────────────────
class Diagnostics {
  static async checkNetworkConnectivity() {
    console.log('🔍 检查网络连接...\n');

    const tests = [
      { name: 'Polymarket Gamma API', url: GAMMA_API },
      { name: 'Polymarket CLOB API', url: CLOB_API },
      { name: '公共DNS (8.8.8.8)', url: 'https://dns.google/resolve?name=google.com' }
    ];

    const results = [];

    for (const test of tests) {
      try {
        const start = Date.now();
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(test.url, {
          method: 'HEAD',
          signal: controller.signal
        });

        clearTimeout(timeout);
        const duration = Date.now() - start;

        results.push({
          name: test.name,
          status: response.ok ? '✅' : '❌',
          code: response.status,
          time: `${duration}ms`
        });

        console.log(`   ${test.name}: ${response.ok ? '✅' : '❌'} (${response.status}, ${duration}ms)`);
      } catch (error) {
        results.push({
          name: test.name,
          status: '❌',
          error: error.message
        });
        console.log(`   ${test.name}: ❌ (${error.message})`);
      }
    }

    return results;
  }

  static async checkProxySettings() {
    console.log('\n🔍 检查代理设置...\n');

    const proxyVars = ['HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy', 'ALL_PROXY', 'all_proxy'];
    let proxyFound = false;

    for (const varName of proxyVars) {
      if (process.env[varName]) {
        console.log(`   ${varName}: ${process.env[varName]}`);
        proxyFound = true;
      }
    }

    if (!proxyFound) {
      console.log('   ⚠️  未检测到代理环境变量');
      console.log('   💡 提示: 如果需要代理，请设置环境变量：');
      console.log('      export HTTPS_PROXY=http://proxy:port');
      console.log('      或 export HTTP_PROXY=http://proxy:port');
    } else {
      console.log('\n   ✅ 代理已配置');
    }

    return proxyFound;
  }

  static async checkPythonEnvironment() {
    console.log('\n🔍 检查Python环境...\n');

    return new Promise((resolve) => {
      const proc = spawn('python', ['--version'], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => stdout += data.toString());
      proc.stderr.on('data', (data) => stderr += data.toString());

      proc.on('close', (code) => {
        if (code === 0) {
          console.log(`   Python版本: ${stdout.trim()}`);
          console.log('   ✅ Python环境正常');
          resolve(true);
        } else {
          console.log('   ❌ Python环境异常');
          console.log(`   错误: ${stderr.trim()}`);
          resolve(false);
        }
      });

      proc.on('error', (error) => {
        console.log('   ❌ Python未找到或无法执行');
        console.log(`   错误: ${error.message}`);
        resolve(false);
      });
    });
  }

  static async runFullDiagnostics() {
    console.log('═══════════════════════════════════════════════════════════════');
    console.log('           Polymarket Router 诊断工具');
    console.log('═══════════════════════════════════════════════════════════════\n');

    const results = {
      network: await this.checkNetworkConnectivity(),
      proxy: await this.checkProxySettings(),
      python: await this.checkPythonEnvironment(),
      timestamp: new Date().toISOString()
    };

    console.log('\n═══════════════════════════════════════════════════════════════');
    console.log('                         诊断总结');
    console.log('═══════════════════════════════════════════════════════════════');

    const networkOk = results.network.some(r => r.status === '✅');
    const pythonOk = results.python;

    if (networkOk && pythonOk) {
      console.log('✅ 环境检查通过，可以正常使用Polymarket Router');
    } else {
      console.log('⚠️  环境检查发现问题，建议：');
      if (!networkOk) {
        console.log('   1. 检查网络连接或配置代理');
      }
      if (!pythonOk) {
        console.log('   2. 安装或配置Python环境');
      }
    }

    console.log('\n═══════════════════════════════════════════════════════════════\n');

    return results;
  }
}

// ─── 帮助文本 ─────────────────────────────────────────
const HELP_TEXT = `
═══════════════════════════════════════════════════════════════
           Polymarket Router CLI — 多源数据集成路由
═══════════════════════════════════════════════════════════════

【基本命令】
  search  <query>       关键词搜索市场
  events  [options]     列出活跃事件
    --tag=<slug>        按分类筛选 (crypto, sports, politics等)
    --limit=<n>         最大结果数 (默认20)
  market  <slug>        获取市场详情及当前赔率
  sports                列出体育联赛
  tags                  列出可用分类
  price   <token_id>    获取代币当前价格 [buy|sell]
  book    <token_id>    获取订单簿深度

【备选数据源】
  alt-search <query>    备选数据源搜索
  alt     <asset>       备选资产查询 (crude-oil|gold|silver)

【路由器管理】
  router  status        查看路由器状态
  router  test [query]  测试路由器功能
  router  stats         查看性能统计
  router  config        查看配置信息

【诊断工具】
  diagnose              运行完整诊断（网络、代理、Python环境）
  test-proxy [url]      测试代理连接

【短别名】
  s=search, e=events, m=market, t=tags, p=price, b=book

【代理设置】
  支持通过环境变量配置代理：
    export HTTPS_PROXY=http://proxy:port
    export HTTP_PROXY=http://proxy:port

【示例】
  node wrapper.js search "super bowl"
  node wrapper.js events --tag=crypto --limit=10
  node wrapper.js market will-bitcoin-reach-100k
  node wrapper.js alt crude-oil
  node wrapper.js router status
  node wrapper.js diagnose
  node wrapper.js test-proxy http://proxy:port

【错误处理】
  如果遇到问题，请：
  1. 运行 diagnose 命令检查环境
  2. 检查网络连接和代理设置
  3. 查看详细错误信息和建议

═══════════════════════════════════════════════════════════════`;

// ─── 通用工具 ─────────────────────────────────────────
async function fetchJSON(url, options = {}) {
  const startTime = Date.now();

  try {
    // 添加代理支持
    const fetchOptions = { ...options };

    if (PROXY_CONFIG.enabled && PROXY_CONFIG.url) {
      try {
        const { ProxyAgent } = await import('undici');
        fetchOptions.dispatcher = new ProxyAgent(PROXY_CONFIG.url);
      } catch (e) {
        // undici不可用，使用默认fetch
      }
    }

    const res = await fetch(url, fetchOptions);
    const duration = Date.now() - startTime;

    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}: ${res.statusText}`);
      error.status = res.status;
      error.url = url;
      error.duration = duration;
      throw error;
    }

    const data = await res.json();
    return data;
  } catch (error) {
    const duration = Date.now() - startTime;

    // 增强错误信息
    if (error.name === 'AbortError') {
      const timeoutError = new Error(`请求超时 (${duration}ms)`);
      timeoutError.url = url;
      timeoutError.duration = duration;
      throw timeoutError;
    }

    error.url = url;
    error.duration = duration;
    throw error;
  }
}

function parsePriceArr(pricesStr) {
  try {
    return JSON.parse(pricesStr).map(p => (parseFloat(p) * 100).toFixed(1) + '%');
  } catch { return []; }
}

function parseOutcomes(outStr) {
  try { return JSON.parse(outStr); } catch { return []; }
}

// ─── 格式化 ──────────────────────────────────────────
function formatMarket(market, verbose = false) {
  const outcomes = parseOutcomes(market.outcomes);
  const prices   = parsePriceArr(market.outcomePrices);
  const odds = outcomes.map((o, i) => `${o}: ${prices[i] || '?'}`).join(' | ');

  let out = `📊 ${market.question}\n`;
  out += `   ${odds}\n`;
  out += `   Volume: $${(market.volumeNum || 0).toLocaleString()}`;
  if (market.liquidity) out += ` | Liquidity: $${parseFloat(market.liquidity).toLocaleString()}`;
  if (verbose) {
    out += `\n   Slug: ${market.slug}`;
    if (market.endDate) out += `\n   Ends: ${market.endDate.split('T')[0]}`;
  }
  return out;
}

function formatEvent(event, verbose = false) {
  let out = `\n🎯 ${event.title}\n`;
  if (event.description && verbose) {
    out += `   ${event.description.slice(0, 200)}${event.description.length > 200 ? '...' : ''}\n`;
  }
  out += `   Volume: $${(event.volume || 0).toLocaleString()}`;
  if (event.liquidity) out += ` | Liquidity: $${parseFloat(event.liquidity).toLocaleString()}`;
  out += '\n';

  if (event.markets && event.markets.length > 0) {
    for (const m of event.markets.slice(0, 5)) {
      if (m.active && !m.closed) out += formatMarket(m, verbose) + '\n';
    }
    if (event.markets.length > 5) out += `   ... and ${event.markets.length - 5} more markets\n`;
  }
  return out;
}

// ─── Python 路由器模式 ───────────────────────────────
class RouterWrapper {
  constructor(configPath = null) {
    this.configPath  = configPath || join(__dirname, '..', 'config', 'config.yaml');
    this.pythonScript = join(__dirname, 'router_client.py');
  }

  async _exec(request) {
    return new Promise((resolve) => {
      try {
        const proc = spawn('python', [this.pythonScript, JSON.stringify(request)], {
          cwd: __dirname, stdio: ['pipe', 'pipe', 'pipe']
        });
        let stdout = '', stderr = '';
        proc.stdout.on('data', d => stdout += d.toString());
        proc.stderr.on('data', d => stderr += d.toString());
        proc.on('close', code => {
          if (code !== 0) {
            console.error(`Python脚本执行失败 (退出码: ${code})`);
            if (stderr) console.error(`错误输出: ${stderr}`);
            resolve(null);
            return;
          }
          try { resolve(JSON.parse(stdout)); } catch {
            console.error('Python输出解析失败');
            resolve(null);
          }
        });
        proc.on('error', (error) => {
          console.error(`Python进程启动失败: ${error.message}`);
          resolve(null);
        });
      } catch (error) {
        console.error(`执行Python脚本时出错: ${error.message}`);
        resolve(null);
      }
    });
  }

  async search(query, limit = 10)       { return this._exec({ type: 'search', query, limit, timeout: 10000 }); }
  async getMarket(slug)                 { return this._exec({ type: 'market', slug, timeout: 10000 }); }
  async listEvents(options = {})        { return this._exec({ type: 'events', options, timeout: 10000 }); }
  async getStats()                      { return this._exec({ type: 'stats', timeout: 5000 }); }
  async getStatus()                     { return this._exec({ type: 'status', timeout: 5000 }); }
  async testRouter(query)               { return this._exec({ type: 'test', query, timeout: 10000 }); }
}

// ─── Direct API 降级模式 (零依赖) ─────────────────────
class DirectAPI {
  async search(query, limit = 10) {
    const url = `${GAMMA_API}/public-search?q=${encodeURIComponent(query)}&limit=50`;
    const data = await fetchJSON(url);
    if (!data.events?.length) {
      ErrorHandler.formatWarning(`没有找到匹配 "${query}" 的市场`);
      ErrorHandler.formatInfo('提示', '尝试使用更通用的关键词，或使用tags命令查看可用分类');
      return;
    }
    const matches = data.events.filter(e => e.active && !e.closed).slice(0, limit);
    if (!matches.length) {
      ErrorHandler.formatWarning(`没有找到匹配 "${query}" 的活跃市场`);
      ErrorHandler.formatInfo('提示', '市场可能已关闭或即将结算，尝试其他关键词');
      return;
    }
    console.log(`找到 ${matches.length} 个活跃事件匹配 "${query}":\n`);
    for (const e of matches) console.log(formatEvent(e, true));
  }

  async listEvents(options = {}) {
    const params = new URLSearchParams();
    params.set('active', 'true'); params.set('closed', 'false');
    params.set('limit', options.limit || '20');
    if (options.tag) params.set('tag_slug', options.tag);
    if (options.series) params.set('series_id', options.series);
    const events = await fetchJSON(`${GAMMA_API}/events?${params}`);
    console.log(`活跃事件 (${events.length}):\n`);
    for (const e of events) console.log(formatEvent(e));
  }

  async getMarket(slug) {
    const markets = await fetchJSON(`${GAMMA_API}/markets?slug=${encodeURIComponent(slug)}`);
    if (!markets?.length) {
      ErrorHandler.formatWarning(`市场未找到: ${slug}`);
      ErrorHandler.formatInfo('提示', '检查slug是否正确，或使用search命令搜索市场');
      return;
    }
    for (const m of markets) { console.log(formatMarket(m, true)); console.log(); }
  }

  async listSports() {
    try {
      const sports = await fetchJSON(`${GAMMA_API}/sports`);
      console.log('体育联赛:\n');
      for (const s of (sports || []).slice(0, 30)) console.log(`  ${s.label || s.title} (series_id: ${s.id})`);
    } catch (error) {
      ErrorHandler.formatWarning('Sports端点不可用或为空', error.message);
    }
  }

  async listTags(limit = 50) {
    const tags = await fetchJSON(`${GAMMA_API}/tags?limit=${limit}`);
    console.log('可用分类:\n');
    for (const t of tags) console.log(`  ${t.label} (slug: ${t.slug})`);
  }

  async getPrice(tokenId, side = 'buy') {
    try {
      const data = await fetchJSON(`${CLOB_API}/price?token_id=${tokenId}&side=${side}`);
      console.log(`Price (${side}): ${(parseFloat(data.price) * 100).toFixed(1)}%`);
    } catch (error) {
      ErrorHandler.handle(error, `获取价格 (token: ${tokenId})`);
    }
  }

  async getOrderbook(tokenId) {
    try {
      const data = await fetchJSON(`${CLOB_API}/book?token_id=${tokenId}`);
      console.log('Orderbook:');
      const fmt = arr => (arr || []).slice(0, 5).map(x => `${(parseFloat(x.price)*100).toFixed(1)}% x $${x.size}`).join(', ');
      console.log('  Bids:', fmt(data.bids) || 'none');
      console.log('  Asks:', fmt(data.asks) || 'none');
    } catch (error) {
      ErrorHandler.handle(error, `获取订单簿 (token: ${tokenId})`);
    }
  }
}

// ─── CLI 入口 (双模自动切换) ──────────────────────────
async function main() {
  const args = process.argv.slice(2);
  let cmd  = args[0];
  if (!cmd) { console.log(HELP_TEXT); process.exit(0); }

  // 短别名解析
  if (SHORT_ALIAS[cmd]) cmd = SHORT_ALIAS[cmd];

  // 诊断命令
  if (cmd === 'diagnose') {
    await Diagnostics.runFullDiagnostics();
    return;
  }

  // 代理测试命令
  if (cmd === 'test-proxy') {
    const proxyUrl = args[1] || PROXY_CONFIG.url;
    if (!proxyUrl) {
      ErrorHandler.formatWarning('未指定代理地址');
      ErrorHandler.formatInfo('用法', 'node wrapper.js test-proxy http://proxy:port');
      ErrorHandler.formatInfo('或设置环境变量', 'export HTTPS_PROXY=http://proxy:port');
    } else {
      console.log(`\n🔍 测试代理连接: ${proxyUrl}\n`);
      try {
        const { ProxyAgent } = await import('undici');
        const agent = new ProxyAgent(proxyUrl);

        const start = Date.now();
        const res = await fetch(GAMMA_API, {
          method: 'HEAD',
          dispatcher: agent,
          signal: AbortSignal.timeout(10000)
        });
        const duration = Date.now() - start;

        if (res.ok) {
          ErrorHandler.formatSuccess(`代理连接成功`, `响应时间: ${duration}ms`);
        } else {
          ErrorHandler.formatWarning(`代理连接失败`, `HTTP ${res.status}`);
        }
      } catch (error) {
        ErrorHandler.handle(error, '代理测试');
      }
    }
    return;
  }

  // Router 管理命令 → 仅 Python 模式
  if (cmd === 'router') {
    const router = new RouterWrapper();
    const sub = args[1];
    if (sub === 'status') {
      const r = await router.getStatus();
      console.log(r ? JSON.stringify(r, null, 2) : 'Router 不可用');
    } else if (sub === 'test') {
      const r = await router.testRouter(args[2] || 'Bitcoin');
      console.log(r ? JSON.stringify(r, null, 2) : 'Router 测试失败');
    } else if (sub === 'stats') {
      const r = await router.getStats();
      console.log(r ? JSON.stringify(r, null, 2) : 'Router 统计不可用');
    } else if (sub === 'config') {
      const path = join(__dirname, '..', 'config', 'config.yaml');
      const fs = await import('fs'); console.log(fs.readFileSync(path, 'utf8'));
    } else {
      console.log('用法: router status|test|stats|config');
    }
    return;
  }

  // alt-search / alt → Python 路由模式
  if (cmd === 'alt-search' || cmd === 'alt') {
    const router = new RouterWrapper();
    const query = args.slice(1).join(' ');
    const r = cmd === 'alt-search' ? await router.search(query) : await router.getMarket(args[1]);
    if (r) {
      console.log(JSON.stringify(r, null, 2));
    } else {
      ErrorHandler.formatWarning('备选数据源不可用');
      ErrorHandler.formatInfo('建议', '使用diagnose命令检查网络连接和Python环境');
    }
    return;
  }

  // 首选 Python Router
  const router = new RouterWrapper();
  let result = null;

  // 参数提取
  const rest = args.slice(1);
  switch (cmd) {
    case 'search':  result = await router.search(rest.join(' ')); break;
    case 'events': {
      const opts = {};
      for (const a of rest) {
        if (a.startsWith('--tag='))    opts.tag    = a.split('=')[1];
        if (a.startsWith('--series=')) opts.series  = a.split('=')[1];
        if (a.startsWith('--limit='))  opts.limit   = a.split('=')[1];
      }
      result = await router.listEvents(opts);
      break;
    }
    case 'market':  result = await router.getMarket(rest[0]); break;
    default: result = null;
  }

  if (result) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  // ─── 降级: Direct API ──────────────────────────────
  ErrorHandler.formatWarning('Python Router 不可用，降级为 Direct API 模式');
  console.log('');

  const api = new DirectAPI();

  try {
    switch (cmd) {
      case 'search':
        if (!rest[0]) {
          ErrorHandler.formatWarning('请指定搜索关键词');
          ErrorHandler.formatInfo('用法', 'node wrapper.js search <query>');
          ErrorHandler.formatInfo('示例', 'node wrapper.js search "Bitcoin"');
          process.exit(1);
        }
        await api.search(rest.join(' '));
        break;
      case 'events': {
        const opts = {};
        for (const a of rest) {
          if (a.startsWith('--tag='))    opts.tag    = a.split('=')[1];
          if (a.startsWith('--series=')) opts.series  = a.split('=')[1];
          if (a.startsWith('--limit='))  opts.limit   = a.split('=')[1];
        }
        await api.listEvents(opts);
        break;
      }
      case 'market':
        if (!rest[0]) {
          ErrorHandler.formatWarning('请指定市场slug');
          ErrorHandler.formatInfo('用法', 'node wrapper.js market <slug>');
          ErrorHandler.formatInfo('示例', 'node wrapper.js market will-bitcoin-reach-100k');
          process.exit(1);
        }
        await api.getMarket(rest[0]);
        break;
      case 'sports':
        await api.listSports();
        break;
      case 'tags':
        await api.listTags(parseInt(rest[0]) || 50);
        break;
      case 'price':
        if (!rest[0]) {
          ErrorHandler.formatWarning('请指定token_id');
          ErrorHandler.formatInfo('用法', 'node wrapper.js price <token_id> [buy|sell]');
          process.exit(1);
        }
        await api.getPrice(rest[0], rest[1] || 'buy');
        break;
      case 'book':
        if (!rest[0]) {
          ErrorHandler.formatWarning('请指定token_id');
          ErrorHandler.formatInfo('用法', 'node wrapper.js book <token_id>');
          process.exit(1);
        }
        await api.getOrderbook(rest[0]);
        break;
      default:
        ErrorHandler.formatWarning(`未知命令: ${cmd}`);
        console.log(HELP_TEXT);
    }
  } catch (error) {
    ErrorHandler.handle(error, `执行命令: ${cmd}`);
    process.exit(1);
  }
}

main();