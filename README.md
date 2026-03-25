# daily-topic-collector

`topic + day + source` を入力として、ソースごとの検索条件生成、取得、正規化、ソース内 dedupe、保存を行う小さな Python ツールです。

## 特徴

- source ごとの差分を `sources/*.py` に閉じ込める
- 共通側は request / storage / runner のみ
- source 間 dedupe は行わない
- 前日取得済みの `dedupe_key` を用いた source 内 dedupe のみ行う
- `ollama` を使って
  - source ごとの検索語候補生成
  - 各 item の短い summary / tags 生成
- 標準ライブラリ中心で実装

## 対応ソース

- `arxiv`
- `hacker_news`
- `reddit`
- `hatena`

## 必須環境変数

### Ollama

- `OLLAMA_BASE_URL` 例: `http://localhost:11434`
- `OLLAMA_SMALL_MODEL` 例: `qwen2.5:3b`

### Reddit 利用時のみ

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT` 例: `daily-topic-collector/0.1 by yourname`

## インストール

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 使い方

```bash
daily-topic-collector \
  --topic "local llm agent" \
  --day 2026-03-25 \
  --source arxiv \
  --data-dir ./data
```

同じ日に複数ソースを実行する場合は source ごとに呼びます。

```bash
daily-topic-collector --topic "local llm agent" --day 2026-03-25 --source arxiv
daily-topic-collector --topic "local llm agent" --day 2026-03-25 --source hacker_news
daily-topic-collector --topic "local llm agent" --day 2026-03-25 --source reddit
daily-topic-collector --topic "local llm agent" --day 2026-03-25 --source hatena
```

## 出力構成

```text
data/
  runs/
    2026-03/
      2026-03-25/
        arxiv/
          request.json
          queries.json
          items.jsonl
          manifest.json
```

## 保存される item

```json
{
  "id": "arxiv:2503.12345",
  "source": "arxiv",
  "topic": "local llm agent",
  "url": "https://arxiv.org/abs/2503.12345",
  "title": "Example title",
  "summary": "短い要約",
  "tags": ["llm", "agent"],
  "created_at": "2026-03-25T03:12:00+00:00",
  "collected_at": "2026-03-25T09:00:00+00:00",
  "dedupe_key": "arxiv:2503.12345"
}
```

## 実装方針

- `runner.py` が request を受けて source pipeline を呼ぶ
- `storage.py` が request / queries / items / manifest を保存する
- `sources/base.py` に source pipeline の共通インターフェースを置く
- `ollama.py` は JSON schema を返す最小ラッパーのみ
- summary / tags 生成は小型モデルを利用

## 補足

- Hacker News は公式 API に全文検索がないため、`topstories` と `newstories` を走査してローカルフィルタします。
- Hatena は RSS フィードを取得して topic によるローカルフィルタを行います。
- Hatena は過剰アクセス防止の注意があるため、短時間の多重実行は避けてください。
