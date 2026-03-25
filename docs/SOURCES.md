# Source implementation notes

## arXiv

- Endpoint: `https://export.arxiv.org/api/query`
- Query style: `search_query`, `start`, `max_results`, `sortBy=submittedDate`, `sortOrder=descending`
- Day filter: `submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]`
- Matching fields: title / abstract / all
- Parsing: Atom XML

## Hacker News

- Endpoint base: `https://hacker-news.firebaseio.com/v0/`
- Candidate IDs: `topstories.json`, `newstories.json`
- Item fetch: `item/<id>.json`
- Search strategy: no official full-text search is used; titles, URLs, and text are filtered locally by topic-derived queries

## Reddit

- OAuth token: `https://www.reddit.com/api/v1/access_token`
- Search endpoint: `https://oauth.reddit.com/search`
- Parameters: `q`, `sort=new`, `t=day`, `type=link`, `limit=50`
- Search strategy: official OAuth search endpoint with day filter and per-query retrieval

## Hatena Bookmark

- Feed endpoints:
  - `https://b.hatena.ne.jp/hotentry/it.rss`
  - `https://b.hatena.ne.jp/hotentry.rss`
- Search strategy: use RSS feeds and filter locally by topic-derived queries
- Parsing: RSS XML
- Operational note: avoid high-frequency access and consider cache layers if you schedule frequent runs
