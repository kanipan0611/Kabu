# VPSデプロイキット【休眠中 — VPSを契約したら使う】

このディレクトリは「VPSを借りたその日に、コマンド数回でNest Eggを常時稼働させる」
ための一式です。**今は何もしなくてOK**。リポジトリに置いてあるだけで、
アプリの動作には影響しません。

## 構成

| ファイル | 役割 |
|---|---|
| `vps_setup.sh` | Ubuntu VPSの初期セットアップ（Python・アプリ配置・systemd登録） |
| `nestegg-ui.service` | Streamlit UIを常時起動するsystemdサービス |
| `nestegg-signals.service` | 仮想売買エンジン（run_signals.py）を1回実行するサービス |
| `nestegg-signals.timer` | 上を平日15:40（大引け後）に自動実行するタイマー |

## 使い方（VPS契約後）

1. VPSを契約する（Ubuntu 22.04/24.04、メモリ1GBで十分。月500〜1,000円程度）
2. SSHでログインし、このリポジトリのセットアップスクリプトを実行:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/kanipan0611/Kabu/main/deploy/vps_setup.sh | bash
   ```

   ※ ブランチがmainでない場合はURLを読み替えるか、`git clone`してから
   `bash deploy/vps_setup.sh` を実行。

3. 有効化（スクリプトの最後にも表示されます）:

   ```bash
   sudo systemctl enable --now nestegg-ui.service       # ブラウザUI
   sudo systemctl enable --now nestegg-signals.timer    # 平日15:40の自動シグナル実行
   ```

4. UIへのアクセスは**SSHトンネル経由**（安全な既定設定）:

   ```bash
   ssh -L 8501:localhost:8501 ユーザー名@VPSのIP
   # → 手元のブラウザで http://localhost:8501 を開く
   ```

## 放置運用について

- **エンジンは完全放置でOK**: systemdタイマーが平日15:40に自動実行し、
  失敗してもVPSが再起動しても、次の予定時刻にまた動きます。
  結果は `journalctl -u nestegg-signals` で確認できます。
- **データはVPSのディスクに永続化**: Streamlit Cloudと違い、
  入力値・取引履歴が消えることはありません。
- **現実的なメンテナンス**: 月1回程度、(1) 取引履歴の確認、
  (2) `sudo apt upgrade` でのOS更新、をおすすめします。
  一番ありそうな故障は「yfinanceの仕様変更でデータ取得が止まる」で、
  その場合はホームタブの価格が取れなくなるのですぐ気づけます。

## セキュリティの注意

- UIは `localhost` のみにバインドしてあり、インターネットには公開されません
  （Streamlitには認証機能がないため。公開したい場合はnginx+Basic認証を挟むこと）
- SSHは公開鍵認証にし、パスワードログインは無効化すること
- APIキー類は `.streamlit/secrets.toml` に置き、リポジトリにはコミットしないこと
- 将来リアル売買に進む場合も、このVPSにエンジンごと載せる構成がそのまま使えます
  （kabuステーションAPIはWindows VPSが必要になる点だけ注意。IBKRならこのLinux構成でOK）
