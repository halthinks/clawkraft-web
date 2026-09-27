import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright-core'));
} catch {
  ({ chromium } = require(process.env.PLAYWRIGHT_CORE || '/home/clawkraft-runner-1/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core'));
}

const BASE = process.env.QUALIFY_BASE || 'http://127.0.0.1:8765';
const OUT = path.resolve('output/qualification/SURF-003');
const EXECUTABLE = process.env.CHROMIUM_PATH ||
  '/home/clawkraft-runner-1/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';

const PAGES = [
  { id: 'home', path: '/' },
  { id: 'product', path: '/product/' },
  { id: 'how-it-works', path: '/how-it-works/' },
  { id: 'use-cases', path: '/use-cases/' },
  { id: 'security', path: '/security/' },
  { id: 'get-started', path: '/get-started/' },
  { id: 'docs', path: '/docs/' },
  { id: 'status', path: '/status/' },
];

const VIEWPORTS = [
  { id: 'desktop', width: 1440, height: 900, isMobile: false },
  { id: 'mobile', width: 390, height: 844, isMobile: true },
];

const GET_STARTED_PREFIX = 'https://setup.clawkraft.dev';
const LOGIN_PREFIX = 'https://app.clawkraft.dev';

function classifyHref(href) {
  if (typeof href !== 'string') return 'other';
  if (href.startsWith(GET_STARTED_PREFIX)) return 'get_started';
  if (href.startsWith(LOGIN_PREFIX)) return 'login';
  return 'other';
}

const results = {
  schema: 'clawkraft/qualification-evidence/v1',
  work_id: 'SURF-003',
  gate_id: 'SURF-003-GATE',
  requirement_id: 'SURF-003-EV-01',
  evidence_type: 'qualification',
  qualification_profile: 'product-surfaces',
  base_url: BASE,
  source_binding: {
    repository: 'halthinks/clawkraft-web',
    ref: 'main',
    base_sha: '6d0cd8610dbf48fc0003057dbb3070776c75fc69',
    binding_id: 'SURF-003-SRC-1',
  },
  work_packet_hash: 'sha256:8b1be96df61a1522667b70fb174736c0a4fcc88460718e9e90bb2fb86b8312bc',
  generated_at: new Date().toISOString(),
  viewports: VIEWPORTS.map(v => ({ id: v.id, width: v.width, height: v.height, isMobile: v.isMobile })),
  pages: [],
  routing: { get_started: [], login: [] },
  checks: [],
  outcome: 'PASS',
};

function fail(msg) {
  results.outcome = 'FAIL';
  results.checks.push({ id: 'runtime', status: 'FAIL', detail: msg });
}

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch({
  executablePath: EXECUTABLE,
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-crashpad',
    '--disable-crash-reporter',
    '--disable-gpu',
  ],
});

try {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.isMobile,
      hasTouch: viewport.isMobile,
      deviceScaleFactor: viewport.isMobile ? 2 : 1,
    });
    const page = await context.newPage();

    for (const target of PAGES) {
      const url = BASE + target.path;
      const response = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      const status = response ? response.status() : 0;
      const title = await page.title();
      const overflow = await page.evaluate(() => {
        const doc = document.documentElement;
        return {
          scrollWidth: doc.scrollWidth,
          clientWidth: doc.clientWidth,
          horizontalOverflow: doc.scrollWidth > doc.clientWidth + 1,
        };
      });

      const links = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('a[href]')).map(a => ({
          text: (a.textContent || '').trim().replace(/\s+/g, ' '),
          href: a.getAttribute('href') || '',
          visible: !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length),
        }));
      });

      const getStarted = links.filter(l => classifyHref(l.href) === 'get_started');
      const login = links.filter(l => classifyHref(l.href) === 'login');
      const privilegedMarkers = await page.evaluate(() => {
        const ids = ['hardStop','enableAll','disableAll','workerToggle','authorityEnvelope','pauseProgram','resumeProgram'];
        return ids.filter(id => document.getElementById(id));
      });

      const shot = path.join(OUT, `${target.id}-${viewport.id}.png`);
      await page.screenshot({ path: shot, fullPage: true });

      const pageResult = {
        id: target.id,
        path: target.path,
        viewport: viewport.id,
        url,
        http_status: status,
        title,
        screenshot: path.relative(process.cwd(), shot),
        horizontal_overflow: overflow.horizontalOverflow,
        scroll_width: overflow.scrollWidth,
        client_width: overflow.clientWidth,
        get_started_links: getStarted,
        login_links: login,
        privileged_control_ids: privilegedMarkers,
        nav_visible_links: links.filter(l => l.visible).slice(0, 20),
      };
      results.pages.push(pageResult);

      results.routing.get_started.push({
        page: target.id,
        viewport: viewport.id,
        count: getStarted.length,
        hrefs: [...new Set(getStarted.map(l => l.href))],
      });
      results.routing.login.push({
        page: target.id,
        viewport: viewport.id,
        count: login.length,
        hrefs: [...new Set(login.map(l => l.href))],
      });

      const checks = [];
      checks.push({
        id: `http-${target.id}-${viewport.id}`,
        status: status === 200 ? 'PASS' : 'FAIL',
        detail: `HTTP ${status}`,
      });
      checks.push({
        id: `responsive-${target.id}-${viewport.id}`,
        status: overflow.horizontalOverflow ? 'FAIL' : 'PASS',
        detail: overflow.horizontalOverflow
          ? `horizontal overflow ${overflow.scrollWidth}>${overflow.clientWidth}`
          : `no horizontal overflow (${overflow.clientWidth}px)`,
      });
      checks.push({
        id: `get-started-${target.id}-${viewport.id}`,
        status: getStarted.length > 0 && getStarted.every(l => classifyHref(l.href) === 'get_started')
          ? 'PASS' : 'FAIL',
        detail: `Get Started links: ${[...new Set(getStarted.map(l => l.href))].join(', ') || 'none'}`,
      });
      checks.push({
        id: `login-${target.id}-${viewport.id}`,
        status: login.length > 0 ? 'PASS' : 'FAIL',
        detail: `Login links: ${[...new Set(login.map(l => l.href))].join(', ') || 'none'}`,
      });
      checks.push({
        id: `privileged-${target.id}-${viewport.id}`,
        status: privilegedMarkers.length === 0 ? 'PASS' : 'FAIL',
        detail: privilegedMarkers.length === 0
          ? 'no privileged control element ids'
          : `privileged control ids present: ${privilegedMarkers.join(', ')}`,
      });

      for (const c of checks) {
        results.checks.push({ ...c, page: target.id, viewport: viewport.id });
        if (c.status !== 'PASS') results.outcome = 'FAIL';
      }
    }

    await context.close();
  }
} catch (err) {
  fail(String(err && err.stack || err));
} finally {
  await browser.close();
}

const summary = {
  outcome: results.outcome,
  generated_at: results.generated_at,
  pages_captured: results.pages.length,
  screenshots: results.pages.map(p => p.screenshot),
  checks_total: results.checks.length,
  checks_failed: results.checks.filter(c => c.status !== 'PASS').length,
  get_started_destinations: [...new Set(results.routing.get_started.flatMap(r => r.hrefs))],
  login_destinations: [...new Set(results.routing.login.flatMap(r => r.hrefs))],
};
results.summary = summary;

await writeFile(path.join(OUT, 'qualification.json'), JSON.stringify(results, null, 2));
await writeFile(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2));

const failed = results.checks.filter(c => c.status !== 'PASS');
const md = [
  '# SURF-003 Qualification Evidence',
  '',
  `- Outcome: **${results.outcome}**`,
  `- Requirement: SURF-003-EV-01 — Browser evidence proves the public site is responsive and routes Get Started/Login correctly.`,
  `- Gate: SURF-003-GATE`,
  `- Work packet: ${results.work_packet_hash}`,
  `- Source binding: halthinks/clawkraft-web@${results.source_binding.base_sha} (${results.source_binding.binding_id})`,
  `- Generated: ${results.generated_at}`,
  `- Base URL: ${BASE}`,
  '',
  '## Routing',
  '',
  `- Get Started destinations: ${summary.get_started_destinations.join(', ')}`,
  `- Login destinations: ${summary.login_destinations.join(', ')}`,
  '',
  '## Viewports',
  '',
  ...VIEWPORTS.map(v => `- ${v.id}: ${v.width}x${v.height}${v.isMobile ? ' (mobile emulation)' : ''}`),
  '',
  '## Screenshots',
  '',
  ...results.pages.map(p => `- ${p.screenshot} (HTTP ${p.http_status}, overflow=${p.horizontal_overflow})`),
  '',
  '## Checks',
  '',
  `Total: ${summary.checks_total}, Failed: ${summary.checks_failed}`,
  '',
  ...(failed.length
    ? ['### Failures', '', ...failed.map(c => `- ${c.id}: ${c.status} — ${c.detail}`)]
    : ['All checks passed.']),
  '',
  '## Acceptance mapping',
  '',
  '- Desktop and mobile full-page screenshots captured for landing, product, how-it-works, use-cases, security, get-started, docs, and status surfaces.',
  '- Responsive check: no horizontal overflow at 1440x900 or 390x844.',
  '- Get Started routes to https://setup.clawkraft.dev (signup).',
  '- Login routes to https://app.clawkraft.dev/.',
  '- No privileged control element ids rendered on clawkraft.com surfaces.',
  '',
].join('\n');

await writeFile(path.join(OUT, 'README.md'), md);
console.log(JSON.stringify(summary, null, 2));
process.exit(results.outcome === 'PASS' ? 0 : 1);
