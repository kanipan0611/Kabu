"""ルールベースの銘柄スコアリングエンジン（Claudeなど外部APIを使わずにアプリ内で完結）。"""

import pandas as pd
import streamlit as st

PER_LOW, PER_HIGH = 15, 25
PBR_LOW, PBR_HIGH = 1, 3
ROE_LOW, ROE_HIGH = 8, 15
RSI_OVERSOLD, RSI_OVERBOUGHT = 30, 70
YIELD_LOW, YIELD_HIGH = 2, 4


def _s(score, label, color):
    return score, label, color


def _score_per(per):
    if per is None or per <= 0:
        return _s(None, "データなし", "gray")
    if per < PER_LOW:
        return _s(75, f"PER {per:.1f}倍 — 割安水準", "green")
    if per <= PER_HIGH:
        return _s(50, f"PER {per:.1f}倍 — 標準水準", "blue")
    return _s(25, f"PER {per:.1f}倍 — 割高水準", "red")


def _score_pbr(pbr):
    if pbr is None or pbr <= 0:
        return _s(None, "データなし", "gray")
    if pbr < PBR_LOW:
        return _s(75, f"PBR {pbr:.2f}倍 — 資産割安", "green")
    if pbr <= PBR_HIGH:
        return _s(50, f"PBR {pbr:.2f}倍 — 標準水準", "blue")
    return _s(25, f"PBR {pbr:.2f}倍 — 資産割高", "red")


def _score_roe(roe):
    if roe is None or roe <= 0:
        return _s(None, "データなし", "gray")
    if roe >= ROE_HIGH:
        return _s(75, f"ROE {roe:.1f}% — 高効率", "green")
    if roe >= ROE_LOW:
        return _s(50, f"ROE {roe:.1f}% — 標準水準", "blue")
    return _s(25, f"ROE {roe:.1f}% — 効率低め", "red")


def _score_rsi(df):
    if df.empty or "RSI" not in df.columns:
        return _s(None, "データなし", "gray")
    rsi = df["RSI"].iloc[-1]
    if pd.isna(rsi):
        return _s(None, "データ不足", "gray")
    if rsi <= RSI_OVERSOLD:
        return _s(70, f"RSI {rsi:.0f} — 売られすぎ付近（反発期待）", "green")
    if rsi >= RSI_OVERBOUGHT:
        return _s(25, f"RSI {rsi:.0f} — 買われすぎ付近（過熱感）", "red")
    return _s(50, f"RSI {rsi:.0f} — 中立", "blue")


def _score_trend(df):
    if df.empty or "SMA_short" not in df.columns:
        return _s(None, "データなし", "gray")
    last = df.iloc[-1]
    price, sma_s, sma_l = last.get("Close"), last.get("SMA_short"), last.get("SMA_long")
    if any(pd.isna(v) for v in [price, sma_s, sma_l] if v is not None):
        return _s(None, "データ不足", "gray")
    if price > sma_s > sma_l:
        return _s(75, "上昇トレンド（価格 > 短期 > 長期線）", "green")
    if price < sma_s < sma_l:
        return _s(25, "下降トレンド（価格 < 短期 < 長期線）", "red")
    return _s(50, "中立（移動平均線が交錯）", "blue")


def _score_dividend(yield_pct):
    if yield_pct is None:
        return _s(None, "データなし", "gray")
    if yield_pct == 0:
        return _s(30, "無配当", "gray")
    if YIELD_LOW <= yield_pct <= YIELD_HIGH:
        return _s(65, f"配当利回り {yield_pct:.2f}% — 標準的", "green")
    if yield_pct > YIELD_HIGH:
        return _s(55, f"配当利回り {yield_pct:.2f}% — 高配当（要確認）", "blue")
    return _s(40, f"配当利回り {yield_pct:.2f}% — 低め", "gray")


def _avg(lst):
    lst = [x for x in lst if x is not None]
    return sum(lst) / len(lst) if lst else None


def _grade(score):
    if score is None:
        return "N/A"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def compute_stock_score(
    df: pd.DataFrame, per, pbr, roe, div_yield
) -> dict:
    """チャートデータとファンダメンタルズからルールベースでスコアを計算する。"""
    sections = {
        "トレンド": _score_trend(df),
        "RSI": _score_rsi(df),
        "PER": _score_per(per),
        "PBR": _score_pbr(pbr),
        "ROE": _score_roe(roe),
        "配当利回り": _score_dividend(div_yield),
    }
    tech = _avg([sections["トレンド"][0], sections["RSI"][0]])
    value = _avg([sections["PER"][0], sections["PBR"][0], sections["ROE"][0]])
    income = sections["配当利回り"][0]
    overall = _avg([tech, value, income])
    return {
        "overall": overall,
        "grade": _grade(overall),
        "sections": sections,
        "category_scores": {"テクニカル": tech, "バリュー": value, "インカム": income},
    }


_GRADE_ICON = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴", "N/A": "⬜"}
_COLOR_DOT = {"green": "🟢", "blue": "🔵", "red": "🔴", "gray": "⬜"}


def render_auto_analysis(
    df: pd.DataFrame, per, pbr, roe, div_yield
) -> None:
    """ルールベースの自動分析パネルを描画する（Claudeなど外部APIなし）。"""
    st.markdown("**🤖 自動分析スコア**")
    data = compute_stock_score(df, per, pbr, roe, div_yield)

    grade = data["grade"]
    icon = _GRADE_ICON.get(grade, "⬜")
    overall = data["overall"]

    c0, c1, c2, c3 = st.columns(4)
    with c0:
        st.metric("総合グレード", f"{icon} {grade}",
                  help="A=良好 B=やや良好 C=要注意 D=不調。あくまで参考スコアです。")
    for col, (cat, score) in zip([c1, c2, c3], data["category_scores"].items()):
        with col:
            st.metric(cat, f"{score:.0f}/100" if score is not None else "N/A")

    with st.expander("詳細スコア内訳を見る"):
        for name, (score, label, color) in data["sections"].items():
            dot = _COLOR_DOT.get(color, "⬜")
            score_str = f"（{score:.0f}点）" if score is not None else ""
            st.write(f"{dot} **{name}**: {label} {score_str}")

    st.caption(
        "このスコアはルールベースの参考値です（PER/RSIなどの一般的な閾値を使用）。"
        "銘柄ごとの業界特性・成長性・経営環境は反映されていません。最終判断は自己責任で。"
    )
