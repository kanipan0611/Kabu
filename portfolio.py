"""ポートフォリオ（資産配分）の入力と円グラフ表示。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ASSET_CATEGORIES = ["現金", "インデックス投信", "個別株"]
ASSET_COLORS = ["#8FBC8F", "#4682B4", "#DAA520"]


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
