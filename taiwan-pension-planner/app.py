import streamlit as st
import os
import json
import streamlit.components.v1 as components
from simulator import PensionSimulator # 匯入上一篇寫好的核心模組

# --- 頁面基本設定 ---
st.set_page_config(page_title="退休金規劃系統", page_icon="📊", layout="wide")
st.title("📊 台灣三支柱退休金規劃與風險診斷")
st.markdown("透過蒙地卡羅模擬，調整參數並即時重新計算退休成功率。")

# --- 讀取預設參數 ---
base_path = os.path.dirname(__file__)
config_file = os.path.join(base_path, 'labor_config.json')

try:
    with open(config_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
except FileNotFoundError:
    st.error(f"找不到設定檔：{config_file}。請確認檔案已上傳至 GitHub。")
    st.stop()

# --- 側邊欄：動態輸入介面 ---
st.sidebar.header("⚙️ 參數微調")

# 基本資料
st.sidebar.subheader("基本資料")
new_current_age = st.sidebar.number_input("目前年齡", value=cfg.get('currentAge', 30), step=1)
new_retire_age = st.sidebar.number_input("預計退休年齡", value=cfg.get('retireAge', 65), step=1)
new_current_salary = st.sidebar.number_input("目前月薪 (元)", value=cfg.get('currentSalary', 50000), step=1000)
new_living_cost = st.sidebar.number_input("期望退休月生活費 (現值)", value=cfg.get('expectedLivingCost', 40000), step=1000)

# 投資與資產
st.sidebar.subheader("投資與資產")
new_balance = st.sidebar.number_input("目前專戶餘額 (元)", value=cfg.get('accountBalance', 300000), step=10000)
new_return_mean = st.sidebar.slider("預期年化報酬率 (%)", min_value=1.0, max_value=15.0, value=float(cfg.get('fundReturnMean', 4)), step=0.5)
new_return_vol = st.sidebar.slider("市場波動率 (%)", min_value=1.0, max_value=30.0, value=float(cfg.get('fundReturnVol', 10)), step=1.0)

# --- 執行模擬區塊 ---
if st.sidebar.button("🚀 重新執行模擬", use_container_width=True):
    with st.spinner("系統正在執行 10,000 次蒙地卡羅路徑模擬..."):
        
        # 1. 更新設定字典
        cfg.update({
            'currentAge': new_current_age,
            'retireAge': new_retire_age,
            'currentSalary': new_current_salary,
            'expectedLivingCost': new_living_cost,
            'accountBalance': new_balance,
            'fundReturnMean': new_return_mean,
            'fundReturnVol': new_return_vol
        })
        
        # 2. 寫入暫存檔供 Simulator 讀取 (保持低耦合)
        temp_config_path = 'temp_config.json'
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            
        # 3. 呼叫核心引擎產出新報表
        output_html = 'retirement_report_output.html'
        sim = PensionSimulator(temp_config_path)
        sim.generate_html_report(output_html)
        
        st.success("✅ 模擬完成！")
        
        # 4. 直接在 Streamlit 中嵌入並顯示產出的 Tailwind HTML 報表
        with open(output_html, 'r', encoding='utf-8') as f:
            html_data = f.read()
            components.html(html_data, height=850, scrolling=True)

else:
    st.info("請調整左側參數，並點擊「重新執行模擬」來檢視報告。")