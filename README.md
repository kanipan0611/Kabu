# 🥚 Nest Egg — 投資学習 & 財務管理ダッシュボード

投資初心者が自分の手で分析しながらスキルを磨くための、Streamlit製の学習用ダッシュボードです。

## 構成

- `app.py` — エントリーポイント
- `finance_planner.py` — マイ・ファイナンス設定（サイドバー）と投資予算の計算
- `portfolio.py` — 資産配分（現金／インデックス投信／個別株）の入力と円グラフ表示、保有個別株の配当チェック（自動取得）
- `stock_analysis.py` — 株価チャート取得・移動平均線・RSI・配当利回り（自動取得）・初心者向けヒント・2銘柄比較モード
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

## スマホからアクセスする（Streamlit Community Cloudへのデプロイ）

1. https://share.streamlit.io にアクセスし、GitHubアカウントでログイン
2. 「New app」→ 以下を指定
   - Repository: `kanipan0611/Kabu`
   - Branch: `claude/investment-dashboard-streamlit-4bzaax`（または `main` にマージ後ならそちら）
   - Main file path: `app.py`
3. 「Advanced settings」→「Secrets」に以下を貼り付け（Claude解説機能を使う場合のみ）
   ```toml
   ANTHROPIC_API_KEY = "sk-ここに自分のAPIキー"
   ```
4. 「Deploy」をクリックすると数分で `https://〇〇.streamlit.app` のようなURLが発行される
5. そのURLをスマホのブラウザで開けば、どこからでも利用可能

### 注意点

- 無料プランのストレージは再起動・再デプロイ時にリセットされる場合があります。
  `data/notes.json` に保存した分析メモは永続化されない可能性があるため、
  長期保存したいメモは別途バックアップすることをおすすめします。

## 注意

このアプリが表示する内容はすべて教育目的の参考情報であり、投資助言ではありません。
最終的な投資判断は自己責任で行ってください。
