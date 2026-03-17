# daily-report-agent

LangGraph ベースの日次レポート作成エージェントです。1日1回、arXiv / Reddit / Hacker News / はてなブックマークから情報を収集し、

- 簡単な要約
- tag 一覧
- レポート本文

を**別々の生成ステップ**で作成し、`reports/YYYY-MM/` 配下に日別ファイルとして保存します。

## なぜ LangGraph か

この用途は「毎日同じ順序で実行する定型ワークフロー」なので、自由度の高い汎用エージェントよりも、
**収集 → 整形 → 要約 → タグ → 本文 → 保存** を固定化した LangGraph の方が単純で壊れにくいです。

一方で、各生成ステップは LangChain / Ollama を使って LLM 化しているため、後から `create_agent` や `create_deep_agent` に差し替えやすい構成にしています。

## API 方針

- **arXiv**: 公式 API は Atom XML を返す検索 APIです。大量同期には OAI-PMH / bulk data が推奨されていますが、日次の少量収集なら通常 API で十分です。citeturn3view0turn0search8
- **Hacker News**: 公式 Firebase API のベース URL は `https://hacker-news.firebaseio.com/v0/` で、現時点では rate limit なしとされています。citeturn3view1
- **Reddit**: 公式 OAuth API を使います。`/best` などの listing endpoint があり、limit は最大 100 です。OAuth 前提です。citeturn3view2turn4view0
- **はてなブックマーク**: 公式 REST API はありますが、人気エントリー収集用途では公開 RSS の方が単純です。フィード仕様ではページングや日付絞り込みが定義されています。エントリー個別情報には `entry/jsonlite` を使えます。citeturn3view3turn5view0turn2search3

## モデル方針

- **small LLM**: 収集済み項目の一次圧縮、簡易要約、タグ抽出
- **main LLM**: 最終レポート本文の生成

例:

- small: `qwen3:4b`
- main: `qwen3:14b`
- embeddings は今回は不要

## ディレクトリ構成

```text
src/daily_report_agent/
  __init__.py
  config.py
  models.py
  prompts.py
  skills/
    summarize.md
    tagging.md
    report.md
  clients.py
  tools.py
  pipeline.py
  save.py
  main.py
reports/
```

## セットアップ

```bash
uv venv
source .venv/bin/activate
uv pip install -U \
  langchain langgraph langchain-ollama pydantic httpx feedparser
```

必要な環境変数:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_SMALL_MODEL=qwen3:4b
export OLLAMA_MAIN_MODEL=qwen3:14b

# Reddit を使う場合のみ
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_USER_AGENT=daily-report-agent/0.1 by yourname
```

## 実行

```bash
python -m daily_report_agent.main run
```

出力例:

```text
reports/
  2026-03/
    2026-03-17.summary.md
    2026-03-17.tags.json
    2026-03-17.report.md
    2026-03-17.raw.json
```

## 定期実行

systemd timer か cron を使ってください。アプリ本体は「1回分を実行するだけ」にしてあります。

cron 例:

```cron
5 8 * * * cd /path/to/daily-report-agent && /path/to/.venv/bin/python -m daily_report_agent.main run >> logs/daily-report.log 2>&1
```

## create_agent / deep_agent を使わなかった理由

LangChain 公式では `create_agent` が LangGraph 上で動く標準入口で、従来の LangGraph `create_react_agent` は非推奨です。Deep Agents は subagent や filesystem を含む上位ハーネスです。今回の要件は自由対話より「決まった毎日バッチ」なので、最小構成の StateGraph を採用しています。citeturn3view5turn3view6turn3view4turn3view7
