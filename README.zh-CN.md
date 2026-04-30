# customer-discovery-agent

[English](README.md) | **中文**

> 扫线上社区找**独立开发者真实痛点**，聚类成主题，每周一份 digest 告诉你未来用户在真正吐槽什么。

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/customer-discovery-agent.svg)](https://pypi.org/project/customer-discovery-agent/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#)
[![Tests](https://img.shields.io/badge/tests-13%20passing-brightgreen.svg)](#)
[![Sources](https://img.shields.io/badge/sources-Reddit_(v0.1)-FF4500.svg)](#)

作者 [Alex Ji](https://github.com/alex-jb) —— 独立开发者,在做 [VibeXForge](https://vibexforge.com)、[Orallexa](https://github.com/alex-jb/orallexa-ai-trading-agent) 和 [marketing-agent](https://github.com/alex-jb/orallexa-marketing-agent)。这工具来自一个想法:

> *我一直在猜独立开发者到底需要什么。Reddit 上其实早就有答案。*

## 它干什么

```bash
customer-discovery-agent scan \
  --subreddits SaaS IndieHackers SideProject Entrepreneur \
  --hours 168 \
  --out digest.md
```

每个 enabled subreddit 上,agent 会:

1. 拉过去 `--hours` 窗口里 top + new 的帖子
2. 用**痛点关键词**过滤(默认 17 个 pattern 比如 *"i wish"*、*"frustrated"*、*"is there a tool"*、*"struggle with"*)
3. 把匹配的内容送给 Claude Haiku 做**主题聚类**(3-7 个 cluster)
4. 输出一份 markdown digest,带代表性引用 + 示例链接

没有 `ANTHROPIC_API_KEY` 时,会退化成关键词分组聚类 —— 依然有用,只是没那么连贯。

## 输出样例

```markdown
# Customer Discovery Digest

*窗口:过去 168h · 来源:reddit*
*扫到痛点:47 个 · 聚类数:5*

## 热门主题

### 独立开发者在为 Vercel build minutes 头疼

**8 条帖 · 平均评分 42.5**

> 这个月在 build minutes 上烧了 $130,一半都是 type-check 没过的失败 push

示例帖子:
- https://reddit.com/r/SaaS/comments/...
- https://reddit.com/r/IndieHackers/comments/...
```

## 安装

```bash
git clone https://github.com/alex-jb/customer-discovery-agent.git
cd customer-discovery-agent
pip install -e .
```

配 Reddit 凭证(在 https://reddit.com/prefs/apps 创建一个 PRAW script app):

```bash
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_USERNAME=...
export REDDIT_PASSWORD=...
export REDDIT_USER_AGENT="customer-discovery-agent/0.1 by yourname"
```

可选:`ANTHROPIC_API_KEY` 启用 LLM 聚类。

## CLI

```
customer-discovery-agent scan
  --subreddits SaaS IndieHackers SideProject ...   (必填)
  --hours 168                                       (回溯窗口)
  --keywords "i wish" "frustrated" ...             (覆盖默认列表)
  --min-score 5                                     (低于此分数的帖子跳过)
  --limit 100                                       (每个 sub 每个 stream 最多扫多少)
  --max-clusters 7
  --out digest.md                                   (默认 stdout)
```

## Roadmap

- [x] **v0.1** —— Reddit 抓取 + 关键词过滤 + Claude 聚类 + markdown digest
- [ ] **v0.2** —— IndieHackers RSS、X timeline、即刻 search、知乎问题抓取
- [ ] **v0.3** —— Email 投递(Resend / Mailgun)、GitHub Actions 每周 cron
- [ ] **v0.4** —— Embedding 语义聚类(替代 LLM 聚类调用,成本更低)
- [ ] **v0.5** —— 周与周对比 —— "这个主题这周热度涨了 3 倍"

## 为什么做这个

独立开发者在用户调研上有两个系统性错误:

1. **凭感觉做产品**:跳过 discovery → 做出来没买家的东西
2. **手动调研**:刷 Reddit 几小时 → 要么烧掉几周,要么直接放弃做了

这个 agent 周日晚上 cron 跑一下,周一早上你 inbox 就有一份 digest,你的猜测变成**未来用户的原话**。模板模式下 ~$0.001 / 次扫描,LLM 聚类模式忙周也就 ~$0.05。

## MCP server(Claude Desktop / Cursor / Zed)

让 AI 助手直接问 "扫一下 IndieHackers 这周的痛点"。

```bash
pip install 'customer-discovery-agent[mcp]'
```

```json
{
  "mcpServers": {
    "customer-discovery": {
      "command": "customer-discovery-mcp",
      "env": { "ANTHROPIC_API_KEY": "..." }
    }
  }
}
```

工具:`scan(subreddits, hours, …)` · `latest_digest(directory)` · `keyword_list()`

## 协议

MIT —— 用它,fork 它,把 IndieHackers 和即刻也加进去。
