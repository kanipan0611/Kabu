"""ファンダメンタルズ手入力フォームと、Claudeによる解説／分析メモ機能。"""

import os

import streamlit as st

from notes_store import get_notes, save_note

PER_THRESHOLDS = (15, 25)
PBR_THRESHOLDS = (1, 3)
ROE_THRESHOLDS = (8, 15)


def rule_based_commentary(per: float | None, pbr: float | None, roe: float | None) -> list[str]:
    """ANTHROPIC_API_KEY が無い場合に使う、簡易ルールベースの解説。"""
    lines = []
    if per:
        if per < PER_THRESHOLDS[0]:
            lines.append(f"PER {per:.1f}倍は一般的に「割安」とされる水準です。成長期待が低いために安いだけ、というケースもあるので理由を調べましょう。")
        elif per <= PER_THRESHOLDS[1]:
            lines.append(f"PER {per:.1f}倍は市場平均に近い「標準的」な水準です。")
        else:
            lines.append(f"PER {per:.1f}倍は「高め」の水準です。将来の高成長が期待されているか、割高な可能性があります。")
    if pbr:
        if pbr < PBR_THRESHOLDS[0]:
            lines.append(f"PBR {pbr:.2f}倍は会社の資産価値より株価が低い「割安」水準です。")
        elif pbr <= PBR_THRESHOLDS[1]:
            lines.append(f"PBR {pbr:.2f}倍は「標準的」な水準です。")
        else:
            lines.append(f"PBR {pbr:.2f}倍は資産価値に対して「高め」の評価です。")
    if roe:
        if roe < ROE_THRESHOLDS[0]:
            lines.append(f"ROE {roe:.1f}%は資本効率が「やや低め」です。")
        elif roe <= ROE_THRESHOLDS[1]:
            lines.append(f"ROE {roe:.1f}%は「標準的」な資本効率です。")
        else:
            lines.append(f"ROE {roe:.1f}%は「高い」資本効率で、効率的に利益を生み出せている会社と言えます。")
    return lines or ["値を入力すると、ここに簡易的な評価が表示されます。"]


def claude_commentary(api_key: str, ticker: str, per, pbr, roe, memo: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "あなたは投資初心者向けのファイナンス教育アシスタントです。"
        "以下のファンダメンタルズ指標について、それぞれの数値が一般的にどう評価されるかを、"
        "初心者にも分かりやすい日本語で300字程度で解説してください。"
        "「買い」「売り」のような断定的な助言はせず、指標の読み方の教育に留めてください。\n\n"
        f"銘柄: {ticker}\n"
        f"PER: {per if per else '未入力'}\n"
        f"PBR: {pbr if pbr else '未入力'}\n"
        f"ROE: {roe if roe else '未入力'}%\n"
        f"投資家自身のメモ: {memo or '(なし)'}\n"
    )
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def render_fundamentals_section(default_ticker: str = "7203.T") -> None:
    st.header("📝 分析ノート & ファンダメンタルズ入力")

    ticker = st.text_input("対象銘柄コード", value=default_ticker, key="fund_ticker")

    col1, col2, col3 = st.columns(3)
    with col1:
        per = st.number_input("PER（倍）", min_value=0.0, value=0.0, step=0.1, format="%.1f")
    with col2:
        pbr = st.number_input("PBR（倍）", min_value=0.0, value=0.0, step=0.1, format="%.2f")
    with col3:
        roe = st.number_input("ROE（%）", min_value=0.0, value=0.0, step=0.1, format="%.1f")

    memo = st.text_area("分析メモ（なぜこの株に注目したか）", height=120, key="memo_input")

    if st.button("📊 この数値を評価する"):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        st.subheader("評価")
        if api_key:
            try:
                with st.spinner("Claudeが解説を作成しています..."):
                    commentary = claude_commentary(api_key, ticker, per or None, pbr or None, roe or None, memo)
                st.write(commentary)
            except Exception as e:
                st.warning(f"Claude APIの呼び出しに失敗したため、簡易解説を表示します（{e}）")
                for line in rule_based_commentary(per or None, pbr or None, roe or None):
                    st.write(f"- {line}")
        else:
            st.caption("ANTHROPIC_API_KEY が未設定のため、簡易ルールベースの解説を表示しています。")
            for line in rule_based_commentary(per or None, pbr or None, roe or None):
                st.write(f"- {line}")

    st.markdown("---")
    st.subheader("🗒 分析メモ（ローカル保存）")

    if st.button("💾 メモを保存"):
        if memo:
            save_note(ticker, memo)
            st.success("メモを保存しました。")
        else:
            st.warning("メモが空です。")

    notes = get_notes(ticker)
    if not notes:
        st.caption("この銘柄の保存済みメモはまだありません。")
    else:
        for note in reversed(notes):
            st.markdown(f"**{note['timestamp']}**")
            st.write(note["memo"])
            st.markdown("---")
