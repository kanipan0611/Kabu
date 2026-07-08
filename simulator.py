"""投資シミュレーター — 購入価格・株数・目標価格を入力して損益を試算する。"""

import pandas as pd
import streamlit as st


def render_simulator_section() -> None:
    st.header("🧮 投資シミュレーター")
    st.caption("購入価格・株数・目標価格/損切りラインを入力すると、複数シナリオの損益を自動計算します。")

    col1, col2 = st.columns(2)
    with col1:
        buy_price = st.number_input(
            "購入予定価格（円/株）", min_value=0.0, value=0.0, step=100.0, key="sim_buy"
        )
        shares = st.number_input(
            "購入予定株数", min_value=0, value=100, step=100, key="sim_shares"
        )
    with col2:
        target_price = st.number_input(
            "目標価格（円）", min_value=0.0, value=0.0, step=100.0, key="sim_target",
            help="達成したいと思っている目標株価",
        )
        stop_loss = st.number_input(
            "損切りライン（円）", min_value=0.0, value=0.0, step=100.0, key="sim_stop",
            help="これ以上下がったら売ると決めるライン",
        )

    if buy_price <= 0 or shares <= 0:
        st.info("購入予定価格と株数を入力すると試算が始まります。")
        return

    total_cost = buy_price * shares
    st.markdown("---")

    metric_cols = [st.columns(3)[0]]  # start with purchase total
    c_cost, c_target, c_stop = st.columns(3)
    with c_cost:
        st.metric("購入総額", f"¥{total_cost:,.0f}")
    with c_target:
        if target_price > 0:
            gain = (target_price - buy_price) * shares
            pct = (target_price - buy_price) / buy_price * 100
            st.metric("目標達成時の損益", f"¥{gain:+,.0f}", delta=f"{pct:+.2f}%")
        else:
            st.metric("目標達成時の損益", "—")
    with c_stop:
        if stop_loss > 0:
            loss = (stop_loss - buy_price) * shares
            pct = (stop_loss - buy_price) / buy_price * 100
            st.metric("損切り時の損失", f"¥{loss:+,.0f}", delta=f"{pct:+.2f}%")
        else:
            st.metric("損切り時の損失", "—")

    st.markdown("**価格シナリオ別 損益試算**")
    pct_steps = [-50, -30, -20, -10, -5, 0, 5, 10, 20, 30, 50]
    rows = []
    for pct in pct_steps:
        price = buy_price * (1 + pct / 100)
        gain = (price - buy_price) * shares
        rows.append({
            "株価変動": f"{pct:+d}%",
            "想定株価（円）": f"¥{price:,.1f}",
            "損益（円）": f"¥{gain:+,.0f}",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # リスク・リワード比
    if target_price > 0 and stop_loss > 0 and stop_loss < buy_price < target_price:
        reward = target_price - buy_price
        risk = buy_price - stop_loss
        rr = reward / risk
        st.info(
            f"リスク・リワード比: {rr:.2f}（目標利益 {reward:,.1f}円 / リスク {risk:,.1f}円）。"
            "一般的に1.5以上が望ましいとされています。"
        )
