"""ポートフォリオ（資産配分）の入力と円グラフ表示。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_analysis import calculate_trailing_dividend_yield

ASSET_CATEGORIES = ["現金", "インデックス投信", "個別株"]
ASSET_COLORS = ["#8FBC8F", "#4682B4", "#DAA520"]

DEFAULT_HOLDINGS = pd.DataFrame([{"銘柄コード": "7203.T", "株数": 0}])


def render_portfolio_section() -> None:
    st.header("🥧 ポートフォリオ可視化")
    st.caption("保有額（または投資予定額）を入力すると、資産配分が円グラフで確認できます。")

    cols = st.columns(len(ASSET_CATEGORIES))
    amounts = []
    for col, label in zip(cols, ASSET_CATEGORIES):
        with col:
            amount = st.number_input(
                f"{label}（円）", min_value=0, value=0, step=10_000, key=f"portfolio_{label}"
            )
            amounts.append(amount)

    total = sum(amounts)
    if total <= 0:
        st.info("各資産の保有額（または投資予定額）を入力すると、円グラフが表示されます。")
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=ASSET_CATEGORIES,
                values=amounts,
                hole=0.4,
                marker=dict(colors=ASSET_COLORS),
                textinfo="label+percent",
                sort=False,
            )
        ]
    )
    fig.update_layout(
        title=f"資産配分（合計 {total:,.0f}円）",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=60, b=20),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    df = pd.DataFrame({"資産クラス": ASSET_CATEGORIES, "金額（円）": amounts})
    df["割合"] = (df["金額（円）"] / total * 100).round(1).astype(str) + "%"
    st.dataframe(df, hide_index=True, use_container_width=True)

    render_dividend_summary()


def render_dividend_summary() -> None:
    st.markdown("---")
    st.subheader("💴 保有個別株の配当チェック（自動取得）")
    st.caption(
        "保有している個別株の銘柄コードと株数を入力すると、各銘柄の配当利回りをyfinanceから取得し、"
        "ポートフォリオ全体の年間想定配当額をまとめて確認できます。"
    )

    holdings_df = st.data_editor(
        DEFAULT_HOLDINGS,
        num_rows="dynamic",
        use_container_width=True,
        key="dividend_holdings_editor",
        column_config={
            "銘柄コード": st.column_config.TextColumn(required=True),
            "株数": st.column_config.NumberColumn(min_value=0, step=1, required=True),
        },
    )

    rows = []
    total_annual_dividend = 0.0
    total_value = 0.0
    for _, holding in holdings_df.iterrows():
        ticker = str(holding.get("銘柄コード") or "").strip()
        shares = holding.get("株数") or 0
        if not ticker or shares <= 0:
            continue

        info = calculate_trailing_dividend_yield(ticker)
        if info["price"] is None:
            continue

        annual_dividend = info["annual_dividend"] * shares
        value = info["price"] * shares
        total_annual_dividend += annual_dividend
        total_value += value
        rows.append(
            {
                "銘柄コード": ticker,
                "株数": shares,
                "現在値": round(info["price"], 1),
                "配当利回り(%)": round(info["yield_pct"], 2) if info["yield_pct"] is not None else None,
                "年間想定配当額": round(annual_dividend, 0),
            }
        )

    if not rows:
        st.caption("銘柄コードと株数を入力すると、配当の見積もりが表示されます。")
        return

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("年間想定配当合計", f"{total_annual_dividend:,.0f} 円")
    with col2:
        avg_yield = (total_annual_dividend / total_value * 100) if total_value else 0
        st.metric("加重平均配当利回り", f"{avg_yield:.2f}%")
