# 🥚 Nest Egg — 投資学習 & 財務管理ダッシュボード

投資初心者が自分の手で分析しながらスキルを磨くための、Streamlit製の学習用ダッシュボードです。

## 構成

- `app.py` — エントリーポイント
- `finance_planner.py` — マイ・ファイナンス設定（サイドバー）と投資予算の計算
- `portfolio.py` — 資産配分（現金／インデックス投信／個別株）の入力と円グラフ表示、保有個別株の配当・損益チェック（配当利回り・現在値は自動取得、購入単価を入力すると損益も自動計算）
- `stock_analysis.py` — 株価チャート取得・移動平均線・RSI・配当利回り（自動取得）・PER/PBR/ROE（自動取得）・初心者向けヒント・2銘柄比較モード
- `fundamentals.py` — ファンダメンタルズ（PER/PBR/ROEは自動取得・編集可）とClaudeによる解説
- `notes_store.py` — 分析メモの保存（Notionデータベース、未設定時は`data/notes.json`にフォールバック）

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
  分析メモを消えないように保存したい場合は、下記の「Notionとの連携」を設定してください。

## 分析メモをNotionに保存する（推奨・データが消えない）

Streamlit Cloud無料プランはアプリ再起動時にローカルファイルが消えることがあるため、
分析メモはNotionのデータベースに保存するのがおすすめです。未設定の場合は自動的に
ローカルファイル保存にフォールバックするので、設定しなくてもアプリは動きます。

1. **Notionでインテグレーションを作成**
   https://www.notion.so/my-integrations を開き、「+ New integration」で
   新規インテグレーションを作成し、表示された「Internal Integration Secret」をコピーする
   （これが `NOTION_API_KEY` になります）。

2. **メモ保存用のデータベース（テーブル）をNotion上に作成**
   新しいページに「テーブル」のデータベースを作成し、以下のプロパティ（列）を用意する。
   - `銘柄コード` … タイトル（Title）型（テーブル作成時に最初から入っている列をリネームしてOK）
   - `メモ` … テキスト（Text）型
   - `保存日時` … 日付（Date）型

3. **データベースにインテグレーションを接続**
   作成したデータベースページ右上の「…」メニュー →「コネクトを追加」から、
   手順1で作ったインテグレーションを選択して接続する。

4. **データベースIDを取得**
   データベースをブラウザで開いたときのURLから32文字の英数字部分を取得する。
   ```
   https://www.notion.so/your-workspace/1a2b3c4d5e6f7890abcd1234ef567890?v=...
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ← これがDATABASE_ID
   ```

5. **Secretsに設定**
   ローカルなら環境変数、Streamlit Cloudなら「Advanced settings」→「Secrets」に以下を追加。
   ```toml
   NOTION_API_KEY = "secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   NOTION_DATABASE_ID = "1a2b3c4d5e6f7890abcd1234ef567890"
   ```

設定後にアプリで保存したメモは、指定したNotionデータベースに1件ずつページとして追加されます。

## 注意

このアプリが表示する内容はすべて教育目的の参考情報であり、投資助言ではありません。
最終的な投資判断は自己責任で行ってください。
