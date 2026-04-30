# customer-discovery-agent

**English** | [中文](README.zh-CN.md)

> Scan online communities for **maker pain points**. Cluster into themes. Get a weekly digest of what your future users are actually frustrated about.

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/customer-discovery-agent.svg)](https://pypi.org/project/customer-discovery-agent/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
[![Tests](https://img.shields.io/badge/tests-13%20passing-brightgreen.svg)](#)
[![Sources](https://img.shields.io/badge/sources-Reddit_(v0.1)-FF4500.svg)](#)

Built by [Alex Ji](https://github.com/alex-jb) — solo founder shipping [VibeXForge](https://vibexforge.com), [Orallexa](https://github.com/alex-jb/orallexa-ai-trading-agent), and [marketing-agent](https://github.com/alex-jb/orallexa-marketing-agent). Born from this thought:

> *I keep guessing what indie makers actually need. Reddit knows.*

## What it does

```bash
customer-discovery-agent scan \
  --subreddits SaaS IndieHackers SideProject Entrepreneur \
  --hours 168 \
  --out digest.md
```

For each enabled subreddit, the agent:

1. Pulls top + new posts in the last `--hours` window
2. Filters by **pain-pattern keywords** (default: 17 phrases like *"i wish"*, *"frustrated"*, *"is there a tool"*, *"struggle with"*)
3. Sends matches to Claude Haiku for **theme clustering** (3-7 clusters)
4. Renders a markdown digest with representative quotes + sample URLs

Without `ANTHROPIC_API_KEY`, falls back to deterministic keyword-based clustering — still useful, just less coherent.

## Sample output

```markdown
# Customer Discovery Digest

*Window: last 168h · Sources: reddit*
*Pain points scanned: 47 · Clusters: 5*

## Top themes

### Founders frustrated with Vercel build minutes

**8 posts · avg score 42.5**

> $130 in build minutes this month, half from failed type-check pushes

Sample posts:
- https://reddit.com/r/SaaS/comments/...
- https://reddit.com/r/IndieHackers/comments/...
```

## Install

```bash
git clone https://github.com/alex-jb/customer-discovery-agent.git
cd customer-discovery-agent
pip install -e .
```

Set Reddit credentials (PRAW script app at https://reddit.com/prefs/apps):

```bash
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_USERNAME=...
export REDDIT_PASSWORD=...
export REDDIT_USER_AGENT="customer-discovery-agent/0.1 by yourname"
```

Optional: `ANTHROPIC_API_KEY` for LLM clustering.

## CLI

```
customer-discovery-agent scan
  --subreddits SaaS IndieHackers SideProject ...   (required)
  --hours 168                                       (lookback window)
  --keywords "i wish" "frustrated" ...             (override default list)
  --min-score 5                                     (skip posts below this)
  --limit 100                                       (max posts per subreddit per stream)
  --max-clusters 7
  --out digest.md                                   (default: stdout)
```

## Roadmap

- [x] **v0.1** — Reddit scraper + keyword filter + Claude clustering + markdown digest
- [ ] **v0.2** — IndieHackers RSS, X timeline, 即刻 search, 知乎 question scraper
- [ ] **v0.3** — Email shipping (Resend / Mailgun), GitHub Actions weekly cron
- [ ] **v0.4** — Embedding-based semantic clustering (replaces LLM cluster call for cost)
- [ ] **v0.5** — Cross-week diffing — "this theme grew 3x this week"

## Why this exists

Solo founders make two systematic mistakes about user research:

1. **Building from gut**: skipping discovery → product-without-buyers
2. **Doing it manually**: scrolling Reddit for hours → either burns weeks or stops happening

This agent runs as a Sunday night cron, drops a digest in your inbox Monday morning, and your guesses become **literal quotes from your future users**. ~$0.001 / scan in template mode, ~$0.05 / scan with LLM clustering on a busy week.

## License

MIT — use it, fork it, add IndieHackers and 即刻 to it.
