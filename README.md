# Kabu — 投資学習 & 財務管理ダッシュボード

投資初心者が自分の手で分析しながらスキルを磨くための、Streamlit製の学習用ダッシュボードです。

## 構成

- `app.py` — エントリーポイント
- `finance_planner.py` — マイ・ファイナンス設定（サイドバー）と投資予算の計算
- `stock_analysis.py` — 株価チャート取得・移動平均線・RSI・初心者向けヒント
- `fundamentals.py` — ファンダメンタルズ入力とClaudeによる解説
- `notes_store.py` — 分析メモのローカル保存（`data/notes.json`）

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Claudeによる解説機能を使う場合は、環境変数 `ANTHROPIC_API_KEY` を設定してください
（未設定でも簡易ルールベースの解説にフォールバックして動作します）。

```bash
export ANTHROPIC_API_KEY=sk-...
```

## 起動

```bash
streamlit run app.py
```

## 注意

このアプリが表示する内容はすべて教育目的の参考情報であり、投資助言ではありません。
最終的な投資判断は自己責任で行ってください。
