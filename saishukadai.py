import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import google.generativeai as genai

st.title("為替変換アプリ(日本円 ⇄ 他通貨)")

# 通貨リスト
currencies = ["JPY", "USD", "EUR", "GBP"]

# 履歴初期化

if "history" not in st.session_state:
    st.session_state.history = []

# 通貨選択（双方向）
from_currency = st.selectbox("変換元通貨", currencies, index = 1)
to_currency = st.selectbox("変換先通貨", [c for c in currencies if c != from_currency])

# 為替レート取得関数
def get_live_rate(from_cur, to_cur):
    try:
        url = f"https://api.frankfurter.app/latest?from={from_cur}&to={to_cur}"
        response = requests.get(url)
        data = response.json()
        rate = data["rates"][to_cur]
        return rate
    except Exception as e:
        st.error(f"為替レート取得中にエラーが発生しました: {e}")
        return None

# レート取得
if "live_rate" not in st.session_state or st.button("最新レートを取得"):
    st.session_state.live_rate = get_live_rate(from_currency, to_currency)

# レートの使用方法選択
rate_source = st.radio("為替レートの使用方法を選択", ("APIの最新レートを使用", "手動で入力する"))

# レート設定
if rate_source == "APIの最新レートを使用":
    rate = st.session_state.live_rate
    if rate is not None:
        st.write(f"現在のレート: **1 {from_currency} = {rate:.6f} {to_currency}**")
    else:
        st.warning("最新レートを取得できなかったため、手動入力を使用してください。")
        rate = st.number_input("手動レート", min_value=0.0001, format="%.6f")
else:
    rate = st.number_input("手動レート", min_value=0.0001, format="%.6f")

# 金額入力と変換
amount = st.number_input(f"{from_currency}の金額を入力", value=0.0, min_value=0.0, format="%.2f")
if st.button("変換"):
    if amount == 0.0:
        st.warning("金額を入力してください")
    elif rate is None:
        st.error("レートが無効です。")
    else:
        result = amount * rate
        st.success(f"{amount:.2f} {from_currency} は 約 {result:.2f} {to_currency} です（使用レート: 1 {from_currency} = {rate} {to_currency}）")

        # 履歴に追加
        st.session_state.history.append({
            "direction": f"{from_currency} to {to_currency}",
            "input": f"{amount:.2f} {from_currency}",
            "output": f"{result:.2f} {to_currency}",
            "rate": rate,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# 履歴表示とCSVダウンロード
if st.session_state.history:
    st.subheader("変換履歴")
    with st.expander("履歴を表示/非表示"):
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("履歴をCSVでダウンロード", data=csv, file_name="kawase_history.csv", mime="text/csv")

    if st.button("履歴をクリア"):
        st.session_state.history = []
        st.rerun()

#期間
days = st.slider("過去何日間のレートを表示する？", min_value = 7, max_value = 90, value = 30)

end_date = datetime.today()
start_date = end_date - timedelta(days=days)

#API（期間）
url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}?from={from_currency}&to={to_currency}"

#データ取得
response = requests.get(url)
if response.status_code != 200:
    st.error("APIからデータを取得できませんでした")
else:
    data = response.json()
    rates = data['rates']

    # データをデータフレーム化
    df = pd.DataFrame([
        {"date": pd.to_datetime(date), "rate": rate[to_currency]}
        for date, rate in rates.items()
    ]).sort_values('date')

    df = df.set_index('date')

    st.line_chart(df['rate'])

# Gemini API呼び出し関数
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def get_gemini_prediction(prompt_text):
    try:
        model = genai.GenerativeModel("gemini-flash")  # または "gemini-pro"
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        st.error(f"Gemini API エラー: {e}")
        return None
with st.expander("Gemini AIによる為替レート予測"):

    # 通貨ペア名を生成
    currency_pair = f"{from_currency}/{to_currency}"

    # 通貨ペアごとの質問テンプレート辞書
    pair_prompts = {
        "USD/JPY": {
            "今週のドル円動向を予測": "今後1週間のUSD/JPY（ドル円）の為替相場について、アメリカのインフレ、FRBの金利政策、日本の経済情勢を踏まえて、予想されるトレンドを分析してください。",
            "円安要因を解説": "2024年以降の円安傾向に関する主な要因を、アメリカと日本の政策・景気・金利差から解説してください。",
        },
        "EUR/JPY": {
            "ユーロ円の影響要因": "EUR/JPY（ユーロ円）相場に影響を与える要因を、ECBの金融政策やユーロ圏の経済状況、日本の景気との比較から分析してください。",
            "今後の為替の見通し": "今後1ヶ月のユーロ円相場について、為替変動に影響するイベントや指標を踏まえて、複数のシナリオを解説してください。",
        },
        "GBP/JPY": {
            "ポンド円のトレンド分析": "GBP/JPY（ポンド円）の相場が最近どのようなトレンドを示しているかを、英中銀の政策や英国の経済情勢に基づいて解説してください。",
        },
        "USD/EUR": {
            "ドルユーロの今後": "米ドルとユーロの相場（USD/EUR）について、FRBとECBのスタンスや欧米経済指標の違いから、今後の見通しを分析してください。",
        },
        # デフォルト
        "default": {
            "一般的な為替動向の分析": "最近の為替相場の変動について、各国の金融政策や国際情勢がどう影響しているかをわかりやすく解説してください。"
        }
    }

    # 対応テンプレートを取得（ない場合はdefaultを使う）
    prompts_for_pair = pair_prompts.get(currency_pair, pair_prompts["default"])

    selected_prompt_title = st.selectbox("質問テンプレートを選ぶ（通貨ペアに応じて表示）", ["選択してください"] + list(prompts_for_pair.keys()))
    if selected_prompt_title != "選択してください":
        st.session_state["gemini_prompt"] = prompts_for_pair[selected_prompt_title]

    # テキストエリアにテンプレ反映
    prompt = st.text_area("分析してほしい内容を入力してください", key="gemini_prompt")

    if st.button("Geminiに依頼する"):
        if prompt.strip() == "":
            st.warning("質問内容を入力してください")
        else:
            prediction = get_gemini_prediction(prompt)
            st.session_state["gemini_prediction"] = prediction

    if "gemini_prediction" in st.session_state:
        st.markdown("### Geminiの分析結果")
        st.write(st.session_state["gemini_prediction"])

    # 使い方のガイド
    with st.expander("📘 Geminiの使い方ガイド"):
        st.markdown(f"""
        - **Geminiは未来の為替レートを断定しません。**
        - 通貨ペア「**{currency_pair}**」に関する背景分析・要因説明に強みがあります。
        - 質問のヒント：
            - 「最近の金利差の影響は？」
            - 「中央銀行の政策スタンスはどう変化しているか？」
            - 「地政学リスクが為替に与える影響は？」
        """)
