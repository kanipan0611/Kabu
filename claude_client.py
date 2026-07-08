"""Claude API呼び出しの共通ヘルパー。

第一候補のFable 5が使えなくなっても（モデル廃止・アクセス権変更・安全性による拒否など）、
自動的に後継・下位モデルへフォールバックしてアプリが動き続けるようにする。
全モデルが失敗した場合は例外を投げるので、呼び出し側はルールベースの解説などに
フォールバックすること。
"""

PRIMARY_MODEL = "claude-fable-5"
# Fable 5が使えない場合に順に試すモデル（新しい順）
FALLBACK_MODELS = ["claude-opus-4-8", "claude-sonnet-4-6"]


def _extract_text(message) -> str:
    for block in message.content:
        if block.type == "text":
            return block.text
    raise RuntimeError("テキスト応答が含まれていませんでした")


def call_claude(api_key: str, prompt: str, max_tokens: int = 600) -> tuple[str, str]:
    """Claudeにプロンプトを送り、(応答テキスト, 実際に使われたモデル名) を返す。

    1. まずFable 5をサーバー側フォールバック付きで呼ぶ
       （安全性の理由で拒否された場合、APIがサーバー側でOpusに切り替えて応答する）
    2. Fable 5自体が呼べない場合（モデル廃止・権限・パラメータ非対応など）は、
       FALLBACK_MODELSを順に通常呼び出しで試す
    3. ネットワーク断はモデルを変えても直らないため即座に例外を投げる
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    last_error: Exception | None = None

    # ── 第一候補: Fable 5（サーバー側フォールバック付き）──
    try:
        message = client.beta.messages.create(
            model=PRIMARY_MODEL,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-06-01"],
            fallbacks=[{"model": "claude-opus-4-8"}],
            messages=[{"role": "user", "content": prompt}],
        )
        if message.stop_reason != "refusal":
            return _extract_text(message), message.model
        last_error = RuntimeError("安全性の理由で応答が生成されませんでした")
    except anthropic.APIConnectionError:
        raise
    except anthropic.BadRequestError as e:
        # betaパラメータが将来使えなくなった場合に備え、Fable 5を通常呼び出しでも試す
        last_error = e
        try:
            message = client.messages.create(
                model=PRIMARY_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            if message.stop_reason != "refusal":
                return _extract_text(message), message.model
        except anthropic.APIConnectionError:
            raise
        except Exception as e2:
            last_error = e2
    except Exception as e:
        last_error = e

    # ── 第二候補以降: 通常呼び出しで順に試す ──
    for model in FALLBACK_MODELS:
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            if message.stop_reason == "refusal":
                last_error = RuntimeError("安全性の理由で応答が生成されませんでした")
                continue
            return _extract_text(message), model
        except anthropic.APIConnectionError:
            raise
        except Exception as e:
            last_error = e

    raise last_error or RuntimeError("Claude APIを呼び出せませんでした")
