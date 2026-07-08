#!/usr/bin/env python3
"""仮想売買エンジンのヘッドレス実行用スクリプト（UIなしで1回実行する）。

Streamlitアプリは画面を開いている間しか動かないため、常時運用したい場合は
このスクリプトをcron等のスケジューラから定期実行する。UIタブと同じ設定
（data/user_settings.json の paper_config）・同じ状態（data/paper_trading.json）を
共有するので、実行結果はアプリの「🤖 仮想売買」タブにそのまま反映される。

日足シグナルなので、平日の大引け後に1日1回実行すれば十分:

    # crontab例（平日15:40 JST）
    40 15 * * 1-5 cd /path/to/Kabu && python3 run_signals.py >> logs/signals.log 2>&1
"""

from datetime import datetime

from auto_trader import _load_state, _new_state, _save_state, run_paper_trading
from user_store import get_setting
from watchlist import get_monitored_tickers


def main() -> int:
    print(f"===== run_signals {datetime.now():%Y-%m-%d %H:%M:%S} =====")

    tickers = get_monitored_tickers()
    if not tickers:
        print("対象銘柄がありません（ウォッチリスト・保有株が空です）。")
        return 1

    cfg = get_setting("paper_config", {})
    budget = cfg.get("budget", 300_000)
    fundamental_min = cfg.get("fundamental_min", 40) if cfg.get("use_fund", True) else None

    state = _load_state() or _new_state(budget)
    state, actions = run_paper_trading(
        state,
        tickers,
        per_trade_max=cfg.get("per_trade_max", 100_000),
        stop_loss_pct=cfg.get("stop_loss", 8),
        take_profit_pct=cfg.get("take_profit", 15),
        sma_short=cfg.get("sma_short", 25),
        sma_long=cfg.get("sma_long", 75),
        fundamental_min=fundamental_min,
    )
    _save_state(state)

    for action in actions:
        print(f"[{action['判定']}] {action['銘柄']}: {action['理由']}")
    print(f"現金: {state['cash']:,.0f}円 / 保有: {len(state['positions'])}銘柄 / 履歴: {len(state['history'])}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
