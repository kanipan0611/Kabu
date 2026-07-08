"""ポートフォリオ（資産配分）の入力と円グラフ表示。"""

from io import StringIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from secrets_utils import get_secret
from stock_analysis import calculate_trailing_dividend_yield
from user_store import get_setting, set_setting

ASSET_CATEGORIES = ["現金", "インデックス投信", "個別株"]
ASSET_COLORS = ["#8FBC8F", "#4682B4", "#DAA520"]

DEFAULT_HOLDINGS = pd.DataFrame([{"銘柄コード": "7203.T", "株数": 0, "購入単価": 0.0}])


def _initial_holdings() -> pd.DataFrame:
    """保存済みの保有株リストがあればそれを、なければデフォルト行を返す。"""
    saved = get_setting("holdings")
    if saved:
        try:
            df = pd.DataFrame(saved)
            if not df.empty and "銘柄コード" in df.columns:
                for col, default in [("株数", 0), ("購入単価", 0.0)]:
                    if col not in df.columns:
                        df[col] = default
                return df[["銘柄コード", "株数", "購入単価"]]
        except Exception:
            pass
    return DEFAULT_HOLDINGS


def _save_holdings(holdings_df: pd.DataFrame) -> None:
    """編集された保有株リストをJSONに保存する（空行は除外）。"""
    records = []
    for _, row in holdings_df.iterrows():
        code = str(row.get("銘柄コード") or "").strip()
        if not code or code == "nan":
            continue
        try:
            records.append({
                "銘柄コード": code,
                "株数": int(row.get("株数") or 0),
                "購入単価": float(row.get("購入単価") or 0.0),
            })
        except (TypeError, ValueError):
            continue
    if records:
        set_setting("holdings", records)

# Rakuten CSV: possible column name variants → canonical names
_RAKUTEN_COL_MAP = {
    "銘柄コード": "銘柄コード",
    "コード": "銘柄コード",
    "銘柄名": "銘柄名",
    "保有数量": "株数",
    "数量": "株数",
    "平均取得単価": "購入単価",
    "取得単価": "購入単価",
    "平均取得価格": "購入単価",
    "取得金額": None,  # ignore
}
_RAKUTEN_HEADER_KEYWORDS = {"銘柄コード", "コード", "銘柄名", "保有数量", "数量"}


def parse_rakuten_holdings_csv(file) -> pd.DataFrame | None:
    """楽天証券エクスポートCSVを解析し、銘柄コード・銘柄名・株数・購入単価のDataFrameを返す。"""
    try:
        content = file.read()
        try:
            text = content.decode("cp932")
        except (UnicodeDecodeError, AttributeError):
            text = content.decode("utf-8", errors="replace")

        lines = text.splitlines()

        # Find the first row that looks like the data header
        header_idx = None
        for i, line in enumerate(lines):
            cols = {c.strip() for c in line.split(",")}
            if cols & _RAKUTEN_HEADER_KEYWORDS:
                header_idx = i
                break

        if header_idx is None:
            return None

        data_str = "\n".join(lines[header_idx:])
        df = pd.read_csv(StringIO(data_str))

        # Rename columns to canonical names, drop unknowns
        rename = {k: v for k, v in _RAKUTEN_COL_MAP.items() if k in df.columns and v is not None}
        df = df.rename(columns=rename)

        keep = [c for c in ["銘柄コード", "銘柄名", "株数", "購入単価"] if c in df.columns]
        df = df[keep].copy()

        df["銘柄コード"] = df["銘柄コード"].astype(str).str.strip()
        # Drop totals / metadata rows (codes that don't start with alphanumeric)
        df = df[df["銘柄コード"].str.match(r"^[0-9A-Za-z]", na=False)]
        df = df.dropna(subset=["銘柄コード"])

        return df if not df.empty else None
    except Exception:
        return None


def render_rakuten_import_section() -> None:
    """楽天証券CSVをアップロードして保有株の損益を確認するセクション。"""
    st.subheader("📥 楽天証券 保有株CSVインポート")
    st.caption(
        "楽天証券の「保有証券一覧」からCSVをダウンロードしてアップロードしてください。"
        "スクレイピングは行わず、CSVファイルの内容だけで処理します。"
    )

    uploaded = st.file_uploader(
        "楽天証券 保有証券CSV（Shift-JIS/cp932）",
        type=["csv"],
        key="rakuten_csv_upload",
        help="楽天証券の「口座管理」→「保有証券」画面からダウンロードしたCSVファイル",
    )

    if uploaded is None:
        st.info("CSVファイルをアップロードすると、保有銘柄と損益が自動計算されます。")
        return

    df = parse_rakuten_holdings_csv(uploaded)
    if df is None or df.empty:
        st.error(
            "CSVの解析に失敗しました。"
            "楽天証券からエクスポートしたCSVファイルか確認してください（文字コード: Shift-JIS）。"
        )
        return

    st.success(f"{len(df)}銘柄を読み込みました。")
    st.dataframe(df, hide_index=True, use_container_width=True)

    if "株数" not in df.columns:
        return

    with st.spinner("現在値と損益を取得中..."):
        rows = []
        for _, row in df.iterrows():
            ticker = str(row.get("銘柄コード", "")).strip()
            shares = float(row.get("株数", 0) or 0)
            purchase_price = float(row.get("購入単価", 0) or 0)
            if not ticker or shares <= 0:
                continue
            try:
                info = calculate_trailing_dividend_yield(ticker)
                current = info.get("price")
                if current is None:
                    continue
                entry = {
                    "銘柄コード": ticker,
                    "銘柄名": row.get("銘柄名", ""),
                    "株数": int(shares),
                    "現在値": round(current, 1),
                    "評価額": round(current * shares, 0),
                }
                if purchase_price > 0:
                    pl_yen = (current - purchase_price) * shares
                    pl_pct = (current - purchase_price) / purchase_price * 100
                    entry["取得単価"] = purchase_price
                    entry["損益(円)"] = round(pl_yen, 0)
                    entry["損益(%)"] = round(pl_pct, 2)
                rows.append(entry)
            except Exception:
                pass

    if rows:
        result_df = pd.DataFrame(rows)
        st.dataframe(result_df, hide_index=True, use_container_width=True)
        total_val = sum(r["評価額"] for r in rows)
        st.metric("合計評価額", f"{total_val:,.0f}円")
    else:
        st.caption("現在値の取得に失敗しました。しばらくしてから再試行してください。")


def render_portfolio_section(safe_budget: float = 0.0) -> None:
    st.header("🥧 ポートフォリオ可視化")
    st.caption("保有額（または投資予定額）を入力すると、資産配分が円グラフで確認できます。")

    saved_alloc = get_setting("portfolio_allocation", {})
    cols = st.columns(len(ASSET_CATEGORIES))
    amounts = []
    for col, label in zip(cols, ASSET_CATEGORIES):
        with col:
            amount = st.number_input(
                f"{label}（円）", min_value=0,
                value=int(saved_alloc.get(label, 0)), step=10_000,
                key=f"portfolio_{label}",
            )
            amounts.append(amount)
    set_setting("portfolio_allocation", dict(zip(ASSET_CATEGORIES, amounts)))

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

    # Budget ratio: compare total portfolio to monthly investable budget
    if safe_budget > 0:
        months_equiv = total / safe_budget
        bm1, bm2 = st.columns(2)
        with bm1:
            st.metric("月間投資可能額（財務設定より）", f"{safe_budget:,.0f}円")
        with bm2:
            st.metric("評価額は月間投資可能額の", f"{months_equiv:.1f}ヶ月分")

    render_holdings_summary()


def render_holdings_summary() -> None:
    st.markdown("---")
    st.subheader("💴 保有個別株の配当・損益チェック（自動取得）")
    st.caption(
        "保有している個別株の銘柄コード・株数を入力すると、各銘柄の配当利回りをyfinanceから取得し、"
        "ポートフォリオ全体の年間想定配当額をまとめて確認できます。"
        "購入単価も入力すると、購入時からの値動き（損益）も合わせて確認できます（未入力の銘柄は損益計算をスキップします）。"
    )

    holdings_df = st.data_editor(
        _initial_holdings(),
        num_rows="dynamic",
        use_container_width=True,
        key="dividend_holdings_editor",
        column_config={
            "銘柄コード": st.column_config.TextColumn(required=True),
            "株数": st.column_config.NumberColumn(min_value=0, step=1, required=True),
            "購入単価": st.column_config.NumberColumn(
                min_value=0.0, step=1.0, help="購入時の1株あたりの価格（円）。任意項目です。"
            ),
        },
    )
    _save_holdings(holdings_df)

    rows = []
    total_annual_dividend = 0.0
    total_value = 0.0
    total_cost = 0.0
    total_pl = 0.0
    has_cost_basis = False
    for _, holding in holdings_df.iterrows():
        ticker = str(holding.get("銘柄コード") or "").strip()
        shares = holding.get("株数") or 0
        purchase_price = holding.get("購入単価") or 0
        if not ticker or shares <= 0:
            continue

        info = calculate_trailing_dividend_yield(ticker)
        if info["price"] is None:
            continue

        annual_dividend = info["annual_dividend"] * shares
        value = info["price"] * shares
        total_annual_dividend += annual_dividend
        total_value += value

        row = {
            "銘柄コード": ticker,
            "株数": shares,
            "購入単価": purchase_price if purchase_price > 0 else None,
            "現在値": round(info["price"], 1),
            "損益(円)": None,
            "損益(%)": None,
            "配当利回り(%)": round(info["yield_pct"], 2) if info["yield_pct"] is not None else None,
            "年間想定配当額": round(annual_dividend, 0),
        }

        if purchase_price > 0:
            has_cost_basis = True
            cost = purchase_price * shares
            pl_total = value - cost
            total_cost += cost
            total_pl += pl_total
            row["損益(円)"] = round(pl_total, 0)
            row["損益(%)"] = round((info["price"] - purchase_price) / purchase_price * 100, 2)

        rows.append(row)

    if not rows:
        st.caption("銘柄コードと株数を入力すると、配当・損益の見積もりが表示されます。")
        return

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("年間想定配当合計", f"{total_annual_dividend:,.0f} 円")
    with col2:
        avg_yield = (total_annual_dividend / total_value * 100) if total_value else 0
        st.metric("加重平均配当利回り", f"{avg_yield:.2f}%")

    if has_cost_basis:
        col3, col4 = st.columns(2)
        with col3:
            pl_pct = (total_pl / total_cost * 100) if total_cost else 0
            st.metric("保有株の損益合計（購入単価入力分）", f"{total_pl:,.0f} 円", delta=f"{pl_pct:.2f}%")
        with col4:
            st.metric("購入額合計 → 現在評価額", f"{total_cost:,.0f} 円 → {total_cost + total_pl:,.0f} 円")

    # ── ポートフォリオ診断（Claude・オンデマンド） ──
    if st.button("🧭 ポートフォリオ診断を生成（Claude）", key="pf_diagnosis"):
        api_key = get_secret("ANTHROPIC_API_KEY")
        if not api_key:
            st.caption("ANTHROPIC_API_KEY が未設定のため診断を生成できません。")
        else:
            cash = st.session_state.get("portfolio_現金", 0)
            index_fund = st.session_state.get("portfolio_インデックス投信", 0)
            stocks_amt = st.session_state.get("portfolio_個別株", 0)
            holdings_lines = "\n".join(
                f"- {r['銘柄コード']}: {r['株数']}株 現在値{r['現在値']:,.0f}円 "
                f"配当利回り{r['配当利回り(%)'] or '不明'}%"
                + (f" 損益{r['損益(%)']:+.1f}%" if r["損益(%)"] is not None else "")
                for r in rows
            )
            prompt = (
                "あなたは投資初心者向けのファイナンス教育アシスタントです。"
                "以下のポートフォリオについて、資産配分のバランス・銘柄の集中度・"
                "配当依存度などの観点から気づいた点を、初心者にも分かりやすい日本語で"
                "400字程度で診断してください。"
                "「買い」「売り」のような断定的な助言は避け、"
                "考えるべき観点の提示に留めてください。\n\n"
                f"資産配分: 現金{cash:,.0f}円 / インデックス投信{index_fund:,.0f}円 / 個別株{stocks_amt:,.0f}円\n"
                f"年間想定配当合計: {total_annual_dividend:,.0f}円\n"
                f"保有個別株:\n{holdings_lines}\n"
            )
            try:
                from claude_client import call_claude
                with st.spinner("ポートフォリオを診断しています..."):
                    diagnosis, model_used = call_claude(api_key, prompt, max_tokens=800)
                st.info(diagnosis)
                st.caption(f"生成モデル: {model_used} ／ 投資助言ではありません。最終判断は自己責任で。")
            except Exception as e:
                st.warning(f"診断の生成に失敗しました（{e}）")
