require('dotenv').config();
const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const XLSX = require('xlsx');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3001;
const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || 'llama3';
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';

// ─── SEEN TRACKER ─────────────────────────────────────────────────────────
const SEEN_FILE = path.join(__dirname, 'seen_companies.json');
function loadSeen() {
  try { if (fs.existsSync(SEEN_FILE)) return new Set(JSON.parse(fs.readFileSync(SEEN_FILE, 'utf8'))); } catch {}
  return new Set();
}
function saveSeen(seen) { fs.writeFileSync(SEEN_FILE, JSON.stringify([...seen]), 'utf8'); }
function markSeen(ids) { const s = loadSeen(); ids.forEach(i => s.add(i)); saveSeen(s); }
function getSeenCount() { return loadSeen().size; }

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function createSSE(res) {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  return {
    send: (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
    end: () => res.end()
  };
}

// ─── SOURCE 1: YC via Algolia ──────────────────────────────────────────────
async function fetchYCCompanies({ batches, maxPerSource }) {
  const seen = loadSeen();
  const results = [];
  const ALGOLIA_APP = '7H67QR2EQS';
  const ALGOLIA_KEY = '8ded26f9a246dabcf3d5e17e01c43576';
  const fetchPerBatch = Math.ceil((maxPerSource * 3) / batches.length);

  for (const batch of batches) {
    try {
      const resp = await axios.post(
        `https://${ALGOLIA_APP}-dsn.algolia.net/1/indexes/companies/query`,
        {
          hitsPerPage: fetchPerBatch,
          // Use facetFilters for string values (correct Algolia syntax)
          facetFilters: [[`batch:${batch}`]],
          numericFilters: ['team_size_max <= 50'],
          attributesToRetrieve: ['name', 'slug', 'one_liner', 'long_description', 'website', 'batch', 'team_size', 'industries', 'tags']
        },
        {
          headers: {
            'X-Algolia-Application-Id': ALGOLIA_APP,
            'X-Algolia-API-Key': ALGOLIA_KEY,
            'Content-Type': 'application/json'
          }
        }
      );

      const hits = (resp.data.hits || []).filter(c => {
        if (seen.has(`yc_${c.slug}`)) return false;
        const text = `${c.one_liner} ${c.long_description || ''} ${(c.industries || []).join(' ')} ${(c.tags || []).join(' ')}`.toLowerCase();
        const hasSoftware = ['software','saas','developer','api','platform','tool','code','engineer','ai','automation','devops','b2b'].some(w => text.includes(w));
        const notConsumer = !['consumer','food','delivery','fashion','retail','dating'].some(w => text.includes(w));
        return hasSoftware && notConsumer;
      });

      results.push(...hits.map(c => ({
        id: `yc_${c.slug}`,
        source: 'YC',
        name: c.name,
        slug: c.slug,
        description: c.one_liner || '',
        long_description: c.long_description || '',
        website: c.website || '',
        batch: c.batch,
        team_size: c.team_size || ''
      })));
    } catch (e) {
      console.error(`YC fetch error batch ${batch}:`, e.message);
    }
  }
  return results.slice(0, maxPerSource);
}

// ─── SOURCE 2: GitHub ──────────────────────────────────────────────────────
async function fetchGitHubLeads({ maxPerSource }) {
  const seen = loadSeen();
  const results = [];
  const headers = {
    'User-Agent': 'PrimatePipeline/1.0',
    'Accept': 'application/vnd.github.v3+json',
    ...(GITHUB_TOKEN ? { 'Authorization': `token ${GITHUB_TOKEN}` } : {})
  };

  // Multiple targeted searches to find small SaaS/dev-tool startups
  const searches = [
    'topic:developer-tools topic:saas stars:20..400 pushed:>2024-01-01 fork:false',
    'topic:devtools topic:startup stars:10..300 pushed:>2024-01-01 fork:false',
    'frontend testing automation tool stars:30..500 pushed:>2024-01-01 language:typescript fork:false',
    'qa automation platform saas stars:10..200 pushed:>2024-01-01 fork:false',
  ];

  for (const q of searches) {
    if (results.length >= maxPerSource * 2) break;
    try {
      const resp = await axios.get('https://api.github.com/search/repositories', {
        params: { q, per_page: 15, sort: 'updated' },
        headers,
        timeout: 10000
      });

      const repos = (resp.data.items || []).filter(r => {
        const id = `gh_${r.full_name}`;
        if (seen.has(id)) return false;
        if (!r.homepage && !r.description) return false;
        if (r.owner.type === 'Organization' && r.size < 50) return false; // skip huge orgs
        const desc = (r.description || '').toLowerCase();
        const notLib = !['library','framework','boilerplate','template','starter','awesome','list','tutorial'].some(w => desc.includes(w));
        return notLib;
      });

      for (const repo of repos) {
        results.push({
          id: `gh_${repo.full_name}`,
          source: 'GitHub',
          name: repo.name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          slug: repo.full_name,
          description: repo.description || '',
          long_description: repo.description || '',
          website: repo.homepage || `https://github.com/${repo.full_name}`,
          batch: 'GitHub',
          team_size: repo.owner.type === 'Organization' ? 'small org' : 'solo/small',
          owner_login: repo.owner.login,
          owner_type: repo.owner.type,
          stars: repo.stargazers_count,
          language: repo.language
        });
      }

      // Respect rate limit
      await new Promise(r => setTimeout(r, 1200));
    } catch (e) {
      if (e.response?.status === 403) {
        console.log('GitHub rate limited — add GITHUB_TOKEN to .env for higher limits');
        break;
      }
      console.error('GitHub search error:', e.message);
    }
  }

  return results.slice(0, maxPerSource);
}

// ─── SOURCE 3: Product Hunt via scraping ──────────────────────────────────
async function fetchProductHuntLeads({ maxPerSource }) {
  const seen = loadSeen();
  const results = [];
  try {
    // PH has a public API endpoint for topics - dev tools
    const resp = await axios.get('https://www.producthunt.com/frontend/graphql', {
      method: 'POST',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-requested-with': 'XMLHttpRequest'
      },
      data: {
        operationName: 'TopicPosts',
        query: `query TopicPosts { topic(slug: "developer-tools") { posts(first: 20, order: NEWEST) { edges { node { name tagline website makers { name username } } } } } }`
      },
      timeout: 10000
    });

    const posts = resp.data?.data?.topic?.posts?.edges || [];
    for (const { node: post } of posts) {
      const id = `ph_${post.name.toLowerCase().replace(/\s+/g, '-')}`;
      if (seen.has(id)) continue;
      results.push({
        id,
        source: 'Product Hunt',
        name: post.name,
        slug: id,
        description: post.tagline || '',
        long_description: post.tagline || '',
        website: post.website || '',
        batch: 'Product Hunt',
        team_size: 'small',
        maker: post.makers?.[0] || null
      });
    }
  } catch (e) {
    console.log('Product Hunt fetch failed (site may block scraping):', e.message);
  }
  return results.slice(0, maxPerSource);
}

// ─── SCRAPE YC FOUNDER ────────────────────────────────────────────────────
async function scrapeYCFounder(slug) {
  try {
    const resp = await axios.get(`https://www.ycombinator.com/companies/${slug}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36' },
      timeout: 10000
    });
    const $ = cheerio.load(resp.data);
    const scriptData = $('script#__NEXT_DATA__').html();
    if (scriptData) {
      const json = JSON.parse(scriptData);
      const founders = json?.props?.pageProps?.company?.founders;
      if (founders?.length) {
        return founders.map(f => ({
          name: f.full_name || f.name || 'Founder',
          title: f.title || 'Co-Founder',
          linkedin: f.linkedin_url || ''
        }));
      }
    }
    // Fallback cheerio
    const founders = [];
    $('a[href*="linkedin.com/in/"]').each((i, el) => {
      const name = $(el).closest('[class*="founder"]').find('[class*="name"]').text().trim() || $(el).text().trim();
      if (name) founders.push({ name, title: 'Co-Founder', linkedin: $(el).attr('href') });
    });
    return founders;
  } catch { return []; }
}

// ─── ENRICH GITHUB FOUNDER ───────────────────────────────────────────────
async function enrichGitHubFounder(company) {
  try {
    const headers = {
      'User-Agent': 'PrimatePipeline/1.0',
      'Accept': 'application/vnd.github.v3+json',
      ...(GITHUB_TOKEN ? { 'Authorization': `token ${GITHUB_TOKEN}` } : {})
    };
    const resp = await axios.get(`https://api.github.com/users/${company.owner_login}`, { headers, timeout: 8000 });
    const u = resp.data;
    return {
      name: u.name || company.owner_login,
      title: u.company ? `Founder at ${u.company}` : 'Founder',
      linkedin: '',
      email: u.email || '',
      bio: u.bio || '',
      location: u.location || '',
      github: u.html_url
    };
  } catch { return { name: company.owner_login, title: 'Founder', linkedin: '', email: '' }; }
}

// ─── EMAIL GUESS ──────────────────────────────────────────────────────────
function guessEmail(name, website) {
  try {
    const domain = new URL(website.startsWith('http') ? website : `https://${website}`).hostname.replace('www.', '');
    const parts = name.toLowerCase().trim().split(/\s+/);
    const first = parts[0] || '';
    const last = parts[parts.length - 1] || '';
    if (!first || !domain || domain.includes('github.com')) return '';
    return `${first}.${last}@${domain}`;
  } catch { return ''; }
}

// ─── OLLAMA ENRICH ────────────────────────────────────────────────────────
async function ollamaEnrich(company, founder, model) {
  const prompt = `You are a sales researcher for Primate — an AI-powered frontend QA platform that reviews GitHub pull requests by launching the real app in a browser, catching visual regressions, broken flows, and UI bugs that code review misses. Perfect for small teams shipping fast.

Company: ${company.name}
Source: ${company.source}
Description: ${company.description}. ${company.long_description || ''}
Founder: ${founder.name}, ${founder.title || 'Founder'}
${founder.bio ? 'Bio: ' + founder.bio : ''}

Tasks:
1. Score fit for Primate: "Strong fit", "Good fit", or "Weak fit"
2. Write a 1-sentence reason why they fit (or not)
3. Write a personalized cold email opening line for ${founder.name} that references something specific about what they're building. Sound human and researched, not templated. 2 sentences max. Don't mention Primate yet.

Return ONLY this JSON (no markdown, no backticks, no explanation):
{"score":"Strong fit","fit_reason":"...","email_opener":"..."}`;

  try {
    const resp = await axios.post(`${OLLAMA_URL}/api/generate`, {
      model, prompt, stream: false, options: { temperature: 0.7 }
    }, { timeout: 90000 });
    const text = resp.data.response || '';
    const start = text.indexOf('{'), end = text.lastIndexOf('}');
    if (start === -1 || end === -1) throw new Error('No JSON');
    return JSON.parse(text.slice(start, end + 1));
  } catch {
    return {
      score: 'Good fit',
      fit_reason: 'Small software team shipping products that benefit from automated QA.',
      email_opener: `I came across ${company.name} and loved what you're building.`
    };
  }
}

// ─── EXPORT ───────────────────────────────────────────────────────────────
function exportToXLSX(leads) {
  const rows = leads.map(l => ({
    'Source': l.source,
    'Founder Name': l.founder_name,
    'Title': l.founder_title,
    'Email': l.email,
    'LinkedIn': l.linkedin,
    'GitHub': l.github || '',
    'Company': l.company_name,
    'Website': l.website,
    'Batch / Origin': l.batch,
    'Team Size': l.team_size,
    'Description': l.description,
    'Fit Score': l.score,
    'Fit Reason': l.fit_reason,
    'Personalized Email Opener': l.email_opener
  }));
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(rows);
  ws['!cols'] = [
    {wch:14},{wch:22},{wch:18},{wch:32},{wch:40},{wch:36},
    {wch:22},{wch:28},{wch:12},{wch:12},{wch:50},{wch:14},{wch:40},{wch:60}
  ];
  XLSX.utils.book_append_sheet(wb, ws, 'Primate Leads');
  const filePath = path.join(__dirname, 'primate_leads.xlsx');
  XLSX.writeFile(wb, filePath);
  return filePath;
}

// ─── PIPELINE ─────────────────────────────────────────────────────────────
app.get('/api/pipeline', async (req, res) => {
  const sse = createSSE(res);
  const batches = (req.query.batches || 'W24,S23').split(',');
  const maxTotal = parseInt(req.query.max || '15');
  const model = req.query.model || OLLAMA_MODEL;
  const sources = (req.query.sources || 'yc,github').split(',');
  const maxPerSource = Math.ceil(maxTotal / sources.length);
  if (req.query.ghtoken) process.env.GITHUB_TOKEN = req.query.ghtoken;

  const leads = [];
  const processedIds = [];

  try {
    // ── Fetch from all sources ──
    let allCompanies = [];

    if (sources.includes('yc')) {
      sse.send('progress', { step: 1, message: `🔍 [YC] Fetching companies from batches: ${batches.join(', ')}...` });
      const yc = await fetchYCCompanies({ batches, maxPerSource });
      sse.send('progress', { step: 1, message: `✅ [YC] Found ${yc.length} new companies`, ok: true });
      allCompanies.push(...yc);
    }

    if (sources.includes('github')) {
      sse.send('progress', { step: 1, message: `🔍 [GitHub] Searching for dev-tool startups...` });
      const gh = await fetchGitHubLeads({ maxPerSource });
      sse.send('progress', { step: 1, message: `✅ [GitHub] Found ${gh.length} repos`, ok: true });
      allCompanies.push(...gh);
    }

    if (sources.includes('producthunt')) {
      sse.send('progress', { step: 1, message: `🔍 [Product Hunt] Fetching dev tool launches...` });
      const ph = await fetchProductHuntLeads({ maxPerSource });
      sse.send('progress', { step: 1, message: `✅ [Product Hunt] Found ${ph.length} products`, ok: true });
      allCompanies.push(...ph);
    }

    // Shuffle sources so results are mixed
    allCompanies = allCompanies.sort(() => Math.random() - 0.5).slice(0, maxTotal);

    if (allCompanies.length === 0) {
      sse.send('error', { message: 'No new companies found across all sources. Try resetting seen or adding more batches.' });
      return sse.end();
    }

    sse.send('progress', { step: 1, message: `📋 Processing ${allCompanies.length} companies total...` });

    // ── Process each ──
    for (let i = 0; i < allCompanies.length; i++) {
      const company = allCompanies[i];
      sse.send('progress', {
        step: 2,
        message: `[${i+1}/${allCompanies.length}] [${company.source}] ${company.name}`,
        progress: Math.round(((i+1) / allCompanies.length) * 100)
      });

      // Get founder info
      let founder = { name: 'Founder', title: 'Co-Founder', linkedin: '', email: '' };

      if (company.source === 'YC') {
        sse.send('progress', { step: 2, message: `  → Scraping YC page for founders...` });
        const founders = await scrapeYCFounder(company.slug);
        if (founders.length) founder = founders[0];
      } else if (company.source === 'GitHub') {
        sse.send('progress', { step: 2, message: `  → Fetching GitHub profile for ${company.owner_login}...` });
        founder = await enrichGitHubFounder(company);
        await new Promise(r => setTimeout(r, 800)); // rate limit
      } else if (company.source === 'Product Hunt' && company.maker) {
        founder = { name: company.maker.name || 'Founder', title: 'Maker', linkedin: '', email: '' };
      }

      const email = founder.email || guessEmail(founder.name, company.website);

      // Ollama
      sse.send('progress', { step: 3, message: `  → Scoring fit + writing personalized opener...` });
      const enriched = await ollamaEnrich(company, founder, model);

      processedIds.push(company.id);

      if (enriched.score === 'Weak fit') {
        sse.send('progress', { step: 3, message: `  ⚠️ Skipping ${company.name} (weak fit)` });
        continue;
      }

      const lead = {
        source: company.source,
        founder_name: founder.name,
        founder_title: founder.title || 'Co-Founder',
        email,
        linkedin: founder.linkedin || '',
        github: founder.github || '',
        company_name: company.name,
        website: company.website,
        batch: company.batch,
        team_size: company.team_size,
        description: company.description,
        score: enriched.score,
        fit_reason: enriched.fit_reason,
        email_opener: enriched.email_opener
      };

      leads.push(lead);
      sse.send('lead', { lead });
    }

    markSeen(processedIds);

    if (leads.length > 0) {
      sse.send('progress', { step: 5, message: `📊 Exporting ${leads.length} leads to spreadsheet...` });
      exportToXLSX(leads);
      sse.send('done', { count: leads.length, totalSeen: getSeenCount() });
    } else {
      sse.send('error', { message: 'No qualifying leads found. Try resetting seen or different sources.' });
    }
  } catch (err) {
    console.error('Pipeline error:', err.message);
    sse.send('error', { message: err.message });
  }
  sse.end();
});

app.get('/api/seen', (req, res) => res.json({ count: getSeenCount() }));
app.post('/api/seen/reset', (req, res) => { saveSeen(new Set()); res.json({ ok: true }); });

app.get('/download/leads', (req, res) => {
  const p = path.join(__dirname, 'primate_leads.xlsx');
  fs.existsSync(p) ? res.download(p, 'primate_leads.xlsx') : res.status(404).send('Run the pipeline first.');
});

app.get('/api/status', async (req, res) => {
  try {
    const r = await axios.get(`${OLLAMA_URL}/api/tags`, { timeout: 3000 });
    res.json({ ok: true, models: (r.data.models || []).map(m => m.name) });
  } catch { res.status(503).json({ ok: false, error: 'Ollama not running' }); }
});

app.listen(PORT, () => {
  console.log(`\n🐒 Primate Lead Pipeline running at http://localhost:${PORT}`);
  console.log(`   Sources: YC (Algolia) + GitHub + Product Hunt`);
  console.log(`   Ollama: ${OLLAMA_URL} | Model: ${OLLAMA_MODEL}\n`);
});
