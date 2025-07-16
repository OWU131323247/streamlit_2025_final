import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd

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
        st.experimental_rerun()

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
def get_gemini_prediction(prompt_text):
    api_key = st.secrets["GEMINI_API_KEY"]
    url = "https://geminiapi.googleapis.com/v1/generateText"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "gemini-1",
        "prompt": prompt_text,
        "maxTokens": 200,
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["text"]
    else:
        st.error(f"Gemini APIエラー: {response.status_code}")
        return None

with st.expander("Gemini AIによる為替レート予測"):
    prompt = st.text_area("予測したい内容を入力してください（例：USD/JPYの来週の為替レート予測）", key="gemini_prompt")

    if st.button("予測を取得"):
        if prompt.strip() == "":
            st.warning("予測内容を入力してください")
        else:
            prediction = get_gemini_prediction(prompt)
            st.session_state["gemini_prediction"] = prediction

    if "gemini_prediction" in st.session_state:
        st.markdown("### 予測結果")
        st.write(st.session_state["gemini_prediction"])
