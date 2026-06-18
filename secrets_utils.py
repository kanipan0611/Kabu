"""Streamlit Cloudのst.secretsを優先し、ローカルの環境変数にもフォールバックする共通ヘルパー。"""

import os

import streamlit as st


def get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")
