"""新NISAプランナー — 枠管理と複利シミュレーション。"""

import plotly.graph_objects as go
import streamlit as st

from secrets_utils import get_secret

TSUMITATE_ANNUAL = 1_200_000   # つみたて投資枠 年120万
GROWTH_ANNUAL = 2_400_000      # 成長投資枠 年240万
GROWTH_LIFETIME = 12_000_000   # 成長投資枠 生涯1200万
LIFETIME_TOTAL = 18_000_000    # 生涯非課税限度額 1800万


def render_nisa_section(monthly_budget: float = 30_000) -> None:
    st.header("🌱 新NISAプランナー")
    st.caption(
        "2024年開始の新NISA制度に対応。"
        "つみたて投資枠（年120万円）・成長投資枠（年240万円）・生涯1800万円の枠を管理し、"
        "複利シミュレーションで将来の資産額を試算します。"
    )

    # ── 枠管理 ──────────────────────────────────────────
    st.subheader("📋 NISA枠チェック")

    col1, col2, col3 = st.columns(3)
    with col1:
        ts_used = st.number_input(
            "つみたて枠 今年の累計（円）",
            min_value=0, value=0, step=10_000, key="nisa_ts_used",
        )
    with col2:
        gr_used = st.number_input(
            "成長投資枠 今年の累計（円）",
            min_value=0, value=0, step=10_000, key="nisa_gr_used",
        )
    with col3:
        lifetime_used = st.number_input(
            "生涯累計投資額（円）※過去分含む",
            min_value=0, value=0, step=100_000, key="nisa_lifetime",
        )

    ts_remain = max(0, TSUMITATE_ANNUAL - ts_used)
    gr_remain = max(0, GROWTH_ANNUAL - gr_used)
    lifetime_remain = max(0, LIFETIME_TOTAL - lifetime_used)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("つみたて枠 今年の残り", f"{ts_remain:,.0f}円",
                  delta=f"使用 {ts_used:,.0f}円")
    with m2:
        st.metric("成長投資枠 今年の残り", f"{gr_remain:,.0f}円",
                  delta=f"使用 {gr_used:,.0f}円")
    with m3:
        st.metric("生涯枠の残り", f"{lifetime_remain:,.0f}円",
                  delta=f"使用 {lifetime_used:,.0f}円")

    st.progress(
        min(1.0, ts_used / TSUMITATE_ANNUAL) if TSUMITATE_ANNUAL else 0,
        text=f"つみたて投資枠 今年: {ts_used / TSUMITATE_ANNUAL * 100:.1f}%使用",
    )
    st.progress(
        min(1.0, lifetime_used / LIFETIME_TOTAL) if LIFETIME_TOTAL else 0,
        text=f"生涯非課税限度額: {lifetime_used / LIFETIME_TOTAL * 100:.1f}%使用",
    )

    st.markdown("---")

    # ── 複利シミュレーション ────────────────────────────
    st.subheader("📈 複利シミュレーション")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        monthly = st.number_input(
            "毎月の積立額（円）",
            min_value=0, value=int(monthly_budget), step=1_000, key="nisa_monthly",
        )
    with sc2:
        rate = st.slider("年間想定利回り（%）", 1, 15, 5, key="nisa_rate")
    with sc3:
        years = st.slider("積立期間（年）", 1, 40, 30, key="nisa_years")

    r_m = rate / 100 / 12
    year_labels = list(range(1, years + 1))
    invested_list, fv_list = [], []
    for y in year_labels:
        n = y * 12
        fv = monthly * ((1 + r_m) ** n - 1) / r_m if r_m > 0 else monthly * n
        invested_list.append(monthly * n)
        fv_list.append(fv)

    gain_list = [fv - inv for fv, inv in zip(fv_list, invested_list)]
    final_fv = fv_list[-1]
    final_inv = invested_list[-1]
    final_gain = gain_list[-1]

    ra, rb, rc = st.columns(3)
    with ra:
        st.metric("積立元本合計", f"{final_inv:,.0f}円")
    with rb:
        st.metric("想定運用益", f"{final_gain:,.0f}円")
    with rc:
        st.metric(f"{years}年後の資産（想定）", f"{final_fv:,.0f}円",
                  delta=f"+{final_gain / final_inv * 100:.1f}%" if final_inv else None)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=year_labels, y=invested_list, name="積立元本",
        marker_color="#4682B4",
    ))
    fig.add_trace(go.Bar(
        x=year_labels, y=gain_list, name="運用益（想定）",
        marker_color="#DAA520", base=invested_list,
    ))
    fig.add_trace(go.Scatter(
        x=year_labels, y=fv_list, name="資産合計",
        mode="lines", line=dict(color="#E84040", width=2),
    ))
    fig.update_layout(
        barmode="stack",
        xaxis_title="経過年数",
        yaxis_title="金額（円）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        margin=dict(t=40, b=20),
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    st.plotly_chart(
        fig, use_container_width=True,
        config={"scrollZoom": False, "displayModeBar": False},
    )

    # NISAとの照合
    annual_invest = monthly * 12
    if annual_invest == 0:
        pass
    elif annual_invest <= TSUMITATE_ANNUAL:
        st.success(
            f"毎月{monthly:,.0f}円（年{annual_invest:,.0f}円）は"
            f"つみたて投資枠（年{TSUMITATE_ANNUAL:,.0f}円）内に収まります。"
        )
    elif annual_invest <= TSUMITATE_ANNUAL + GROWTH_ANNUAL:
        st.info(
            f"毎月{monthly:,.0f}円（年{annual_invest:,.0f}円）はつみたて投資枠を超えています。"
            f"成長投資枠（年{GROWTH_ANNUAL:,.0f}円）との併用が必要です。"
        )
    else:
        st.warning(
            f"毎月{monthly:,.0f}円（年{annual_invest:,.0f}円）は"
            f"新NISAの年間上限（最大{TSUMITATE_ANNUAL + GROWTH_ANNUAL:,.0f}円）を超えています。"
            "超過分は課税口座での運用になります。"
        )

    st.caption(
        "※シミュレーションは複利計算（毎月積立）による試算です。"
        "実際の運用成果・税制優遇額は保証されません。"
    )

    # ── プラン相談（Claude・オンデマンド） ──
    if st.button("🌱 この積立プランについてコメントをもらう（Claude）", key="nisa_advice"):
        api_key = get_secret("ANTHROPIC_API_KEY")
        if not api_key:
            st.caption("ANTHROPIC_API_KEY が未設定のためコメントを生成できません。")
        else:
            prompt = (
                "あなたは投資初心者向けのファイナンス教育アシスタントです。"
                "以下の新NISAの積立プランについて、想定利回りの現実性・期間設定・"
                "枠の使い方の観点から気づいた点を、初心者にも分かりやすい日本語で"
                "400字程度でコメントしてください。"
                "特定の商品を勧めるような断定的な助言は避けてください。\n\n"
                f"毎月の積立額: {monthly:,.0f}円（年{annual_invest:,.0f}円）\n"
                f"想定利回り: 年{rate}%\n"
                f"積立期間: {years}年\n"
                f"{years}年後の想定資産: {final_fv:,.0f}円（元本{final_inv:,.0f}円 + 運用益{final_gain:,.0f}円）\n"
                f"今年のつみたて投資枠 使用額: {ts_used:,.0f}円 / {TSUMITATE_ANNUAL:,.0f}円\n"
                f"今年の成長投資枠 使用額: {gr_used:,.0f}円 / {GROWTH_ANNUAL:,.0f}円\n"
                f"生涯累計投資額: {lifetime_used:,.0f}円 / {LIFETIME_TOTAL:,.0f}円\n"
            )
            try:
                from claude_client import call_claude
                with st.spinner("プランへのコメントを作成しています..."):
                    advice, model_used = call_claude(api_key, prompt, max_tokens=800)
                st.info(advice)
                st.caption(f"生成モデル: {model_used} ／ 投資助言ではありません。")
            except Exception as e:
                st.warning(f"コメントの生成に失敗しました（{e}）")
