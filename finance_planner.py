"""サイドバーの「マイ・ファイナンス設定」と、安全な投資予算の計算ロジック。"""

import streamlit as st

from user_store import get_setting, set_setting


def calculate_safe_investment_budget(
    savings: float,
    monthly_income: float,
    monthly_expense: float,
    emergency_months: int = 6,
    ratio_with_efund: float = 0.5,
    ratio_without_efund: float = 0.1,
) -> dict:
    """生活防衛資金の確保状況に応じて、月々の安全な投資予算を計算する。

    防衛資金が貯まっていないうちは投資に回す比率を低く抑え、
    確保済みになったら比率を上げる、という初心者向けの簡易ルール。
    """
    efund_target = monthly_expense * emergency_months
    monthly_surplus = max(monthly_income - monthly_expense, 0)
    efund_satisfied = savings >= efund_target
    ratio = ratio_with_efund if efund_satisfied else ratio_without_efund
    safe_budget = monthly_surplus * ratio

    return {
        "efund_target": efund_target,
        "monthly_surplus": monthly_surplus,
        "efund_satisfied": efund_satisfied,
        "ratio": ratio,
        "safe_budget": safe_budget,
    }


def render_finance_sidebar() -> dict:
    st.sidebar.header("💰 マイ・ファイナンス設定")

    saved = get_setting("finance", {})
    savings = st.sidebar.number_input(
        "現在の貯金額（円）", min_value=0,
        value=int(saved.get("savings", 500_000)), step=10_000, key="fin_savings",
    )
    monthly_income = st.sidebar.number_input(
        "来年からの予定月収（円）", min_value=0,
        value=int(saved.get("monthly_income", 250_000)), step=5_000, key="fin_income",
    )
    monthly_expense = st.sidebar.number_input(
        "想定される月々の生活費（円）", min_value=0,
        value=int(saved.get("monthly_expense", 150_000)), step=5_000, key="fin_expense",
    )
    emergency_months = st.sidebar.slider(
        "生活防衛資金の目安（生活費の何ヶ月分）", min_value=3, max_value=12,
        value=int(saved.get("emergency_months", 6)), key="fin_emonths",
    )
    set_setting("finance", {
        "savings": savings, "monthly_income": monthly_income,
        "monthly_expense": monthly_expense, "emergency_months": emergency_months,
    })

    result = calculate_safe_investment_budget(
        savings, monthly_income, monthly_expense, emergency_months
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 安全な投資予算（月額）")
    st.sidebar.metric("毎月の投資予算の目安", f"{result['safe_budget']:,.0f} 円")

    if result["efund_satisfied"]:
        st.sidebar.success(
            f"生活防衛資金（目安 {result['efund_target']:,.0f}円）は確保済みです。"
        )
    else:
        gap = result["efund_target"] - savings
        st.sidebar.warning(
            f"生活防衛資金（目安 {result['efund_target']:,.0f}円）まで "
            f"あと{gap:,.0f}円です。まずは貯金を優先し、投資は少額にとどめましょう。"
        )

    st.sidebar.caption(
        f"月の余剰額 {result['monthly_surplus']:,.0f}円 × "
        f"投資に回す割合 {result['ratio']:.0%} で計算しています。"
    )

    return result
