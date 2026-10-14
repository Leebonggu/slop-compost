# Default sources

Shipped with the skill. On the first run (or whenever `<LEDGER>/sources.md` is missing) this file is copied to `<LEDGER>/sources.md`, and from then on **the user's copy is the list that counts**. Rules for using sources: `README.md`.

Entry fields:

| field | values |
|---|---|
| `id` | kebab-case, unique, never reused (the `## ` heading) |
| `category` | `trend` \| `ai-trend` \| `revenue` \| `failure` \| `community-ko` |
| `type` | one or more of `web` (WebSearch query) \| `fetch` (WebFetch a URL) \| `local` (folder or git ref on this machine) |
| `how` | URLs and/or query templates; `{keyword}` is replaced with a keyword from the parts and lessons |
| `limits` | request cap per run and access rules |
| `notes` | what it is good for, caveats |
| `enabled` | `true` \| `false` |
| `removed` | optional, `YYYY-MM-DD` (set by `sources remove`; the entry stays) |

Common limit for every source: **1-2 requests per source per run** unless the entry says otherwise.

**Parsing rule**: every `## ` heading in this file (and in `<LEDGER>/sources.md`) is exactly one source, and its text is the id. Do not use `## ` for anything else; notes go in HTML comments.

## hn-show
- category: trend
- type: fetch, web
- how: fetch `https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&hitsPerPage=30`; search `site:news.ycombinator.com "Show HN" {keyword}`
- limits: 1 fetch + 1 search
- notes: What builders are shipping this week, with comment reactions. Good for "is anyone already doing this" and early demand signals.
- enabled: true

## github-trending
- category: ai-trend
- type: fetch
- how: `https://github.com/trending?since=weekly` (language filter: `https://github.com/trending/<lang>?since=weekly`)
- limits: 1 fetch
- notes: Open-source tools gaining stars. Shows which capabilities just became cheap to reuse.
- enabled: true

## hf-papers
- category: ai-trend
- type: fetch
- how: `https://huggingface.co/papers`
- limits: 1 fetch
- notes: Daily AI papers. Use only for "a new capability makes this part cheaper or better", never as demand evidence.
- enabled: true

## trustmrr
- category: revenue
- type: fetch, web
- how: fetch `https://trustmrr.com/startups`; search `site:trustmrr.com {keyword} revenue`
- limits: 1 fetch + 1 search
- notes: Startups with verified revenue (MRR). Cite the MRR, subscriber count, and growth as shown on the page, with the access date.
- enabled: true

## failory
- category: failure
- type: fetch, web
- how: lists `https://www.failory.com/cemetery` (about 135 failed startups), `https://www.failory.com/interview` (about 300 founder interviews about failure), `https://www.failory.com/google` (about 100 discontinued Google products); detail pages `https://www.failory.com/cemetery/<slug>`, `/interview/<slug>`, `/google/<slug>`; search `site:failory.com/cemetery {keyword}`, `site:failory.com/interview {keyword}`; slug lookup: fetch `https://www.failory.com/sitemap.xml` once and grep for the keyword
- limits: 1 list (or sitemap) request + at most 3 detail pages per run. robots.txt disallows only `/startup/`, `/get/`, `/author/`: never fetch those paths.
- notes: Detail pages have structured fields: Country, Started, Closed, Outcome, Cause, Funding. When citing counter-evidence, quote **Cause** and the **Closed** year from these fields.
- enabled: true

## failure-search
- category: failure
- type: web
- how: `{keyword} startup shut down post-mortem`; Korean `{keyword} 서비스 종료 후기`
- limits: 1 search per candidate, at most 4 per run (mix languages as useful). When the cap is reached, skip and note `cap reached (failure-search)`.
- notes: General failure-case search. Always run for every Track B candidate (survivorship-bias guard), also in lightweight mode.
- enabled: true

## geeknews
- category: community-ko
- type: fetch, web
- how: fetch `https://news.hada.io/rss/news`; search `site:news.hada.io {keyword}`
- limits: 1 fetch + 1 search
- notes: Korean developer news and Show GN posts. Prefer the RSS fetch: WebSearch coverage of Korean domains is thin.
- enabled: true

## disquiet
- category: community-ko
- type: web
- how: `site:disquiet.io {keyword}`
- limits: 1 search
- notes: Korean maker community (product launches, build logs). Good for Korean competitors and early-stage attempts.
- enabled: true

## exploding-topics
- category: trend
- type: fetch, web
- how: fetch `https://explodingtopics.com`; search `site:explodingtopics.com {keyword}`
- limits: 1 fetch + 1 search
- notes: Rising search topics. Treat growth claims as trend signals, not demand proof.
- enabled: true

<!--
Not included (and why):

| Source | Reason |
|---|---|
| Product Hunt | Pages return 403 to automated fetch; the API needs a token. |
| Reddit | robots.txt disallows all crawling. |
| Indie Hackers | Returns 403 to automated fetch. A user may add it with `sources add` if it works in their environment. |
| Subscription-gated idea banks | Paid or member-only content is never fetched. If the user has downloaded material they are entitled to, add it as a `local` source. |
-->
