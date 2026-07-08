"""証券会社接続の抽象レイヤー ―― 将来のリアル売買用【休眠コード】。

現在アプリが行うのは仮想売買（PaperBroker相当のロジック）のみで、
このファイルはまだどこからも使われていない。実際の発注に進むと決めたときに、
下のスタブ（KabuStationBroker / IBKRBroker）を実装して run_signals.py 側で
差し替えれば、シグナル判定・予算管理・損切り/利確のロジックは
一切変えずにリアル売買へ移行できる、という設計図として置いてある。

⚠️ 実装時の鉄則:
- APIキー・パスワードは絶対にコードに書かない（st.secrets / 環境変数 / GitHub Secretsで渡す）
- まず証券会社のデモ・検証環境で動かし、次に最小単位の少額で試す
- 1日の損失上限・1回あたりのリスク上限をBroker側でも二重にチェックする
"""

from abc import ABC, abstractmethod


class Broker(ABC):
    """発注インターフェース。仮想でも実口座でも同じ形で扱えるようにする。"""

    @abstractmethod
    def get_cash(self) -> float:
        """発注に使える現金残高（円）を返す。"""

    @abstractmethod
    def get_positions(self) -> dict:
        """保有ポジションを {銘柄コード: {"shares": 株数, "avg_price": 平均取得単価}} で返す。"""

    @abstractmethod
    def market_buy(self, code: str, shares: int) -> float:
        """成行買いを発注し、約定単価を返す。"""

    @abstractmethod
    def market_sell(self, code: str, shares: int) -> float:
        """成行売りを発注し、約定単価を返す。"""


class PaperBroker(Broker):
    """仮想売買。data/paper_trading.json と同じ形式のstate辞書を操作する。

    現在の run_paper_trading はstateを直接更新しているため、このクラスは
    まだ使われていない。リアル売買対応の際に、エンジンをBroker経由に
    リファクタリングして Paper / 実口座 を差し替え可能にする。
    """

    def __init__(self, state: dict, price_lookup):
        self.state = state
        self._price = price_lookup  # code -> 現在値 を返す関数

    def get_cash(self) -> float:
        return self.state["cash"]

    def get_positions(self) -> dict:
        return self.state["positions"]

    def market_buy(self, code: str, shares: int) -> float:
        price = self._price(code)
        cost = price * shares
        if cost > self.state["cash"]:
            raise ValueError(f"現金不足: {cost:,.0f}円 > {self.state['cash']:,.0f}円")
        self.state["cash"] -= cost
        pos = self.state["positions"].get(code)
        if pos:
            total_shares = pos["shares"] + shares
            pos["avg_price"] = (pos["avg_price"] * pos["shares"] + cost) / total_shares
            pos["shares"] = total_shares
        else:
            self.state["positions"][code] = {"shares": shares, "avg_price": price}
        return price

    def market_sell(self, code: str, shares: int) -> float:
        pos = self.state["positions"].get(code)
        if not pos or pos["shares"] < shares:
            raise ValueError(f"保有株数が不足しています: {code}")
        price = self._price(code)
        self.state["cash"] += price * shares
        if pos["shares"] == shares:
            del self.state["positions"][code]
        else:
            pos["shares"] -= shares
        return price


class KabuStationBroker(Broker):
    """三菱UFJ eスマート証券（旧auカブコム証券）kabuステーションAPI用スタブ。

    実装時のメモ:
    - Windows上でkabuステーションを起動し、ローカルREST API（既定 localhost:18080）を叩く
    - 認証: POST /kabusapi/token にAPIパスワードを送りトークン取得
    - 発注: POST /kabusapi/sendorder（現物成行: FrontOrderType=10）
    - 残高: GET /kabusapi/wallet/cash ・ 建玉/保有: GET /kabusapi/positions
    - 常時起動のWindows環境（Windows VPS等）が必要
    """

    def __init__(self, api_password: str, host: str = "localhost:18080"):
        raise NotImplementedError(
            "実発注は未実装です（休眠スタブ）。口座開設・検証環境での確認後に実装してください。"
        )

    def get_cash(self) -> float: ...
    def get_positions(self) -> dict: ...
    def market_buy(self, code: str, shares: int) -> float: ...
    def market_sell(self, code: str, shares: int) -> float: ...


class IBKRBroker(Broker):
    """Interactive Brokers証券用スタブ（日本株・米国株の両対応が可能）。

    実装時のメモ:
    - IB Gateway（Linux可）を起動し、ib_insync等のライブラリで接続する
    - ペーパートレード口座が公式に用意されているので、必ずそちらで先に検証する
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 1):
        raise NotImplementedError(
            "実発注は未実装です（休眠スタブ）。IBペーパートレード口座での検証後に実装してください。"
        )

    def get_cash(self) -> float: ...
    def get_positions(self) -> dict: ...
    def market_buy(self, code: str, shares: int) -> float: ...
    def market_sell(self, code: str, shares: int) -> float: ...
