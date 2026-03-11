import json
import math
import numpy as np
from datetime import datetime

class PensionSimulator:
    def __init__(self, config_path):
        """初始化並讀取設定檔"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.cfg = json.load(f)
            
        # 基本參數設定
        self.current_age = self.cfg.get('currentAge', 30)
        self.retire_age = self.cfg.get('retireAge', 65)
        self.life_expectancy = self.cfg.get('lifeExpectancy', 90)
        self.working_years = max(0, self.retire_age - self.current_age)
        self.working_months = self.working_years * 12
        self.retirement_years = max(0, self.life_expectancy - self.retire_age)
        self.retirement_months = self.retirement_years * 12
        
        # 財務參數
        self.current_salary = self.cfg.get('currentSalary', 50000)
        self.expected_living_cost = self.cfg.get('expectedLivingCost', 40000)
        self.inflation = self.cfg.get('inflation', 2) / 100.0
        self.account_balance = self.cfg.get('accountBalance', 300000)
        
        # 投資與提撥率
        self.employer_rate = self.cfg.get('employerRate', 6) / 100.0
        self.self_rate = self.cfg.get('selfRate', 6) / 100.0
        self.total_contribution_rate = self.employer_rate + self.self_rate
        
        self.fund_return_mean = self.cfg.get('fundReturnMean', 4) / 100.0
        self.fund_return_vol = self.cfg.get('fundReturnVol', 10) / 100.0
        
        # 計算通膨調整後的目標退休月開銷
        self.target_monthly_cost = self.expected_living_cost * ((1 + self.inflation) ** self.working_years)

    def calc_pillar_1(self):
        """計算第一支柱：勞保老年年金 (取最優方案)"""
        # 採用現行勞保公式：平均月投保薪資 × 年資 × 1.55%
        # 年資 = 已保年資 + 未來工作年資
        total_years = self.cfg.get('insuredYears', 0) + self.working_years
        avg_salary = min(self.cfg.get('avgSalary', 45800), 45800) # 勞保天花板
        
        pension_a = avg_salary * 0.00775 * total_years + 3000
        pension_b = avg_salary * 0.0155 * total_years
        
        return max(pension_a, pension_b)

    def run_monte_carlo(self, n_simulations=10000):
        """執行蒙地卡羅模擬 (第二支柱：勞退)"""
        monthly_contribution = self.current_salary * self.total_contribution_rate
        
        # 將年化報酬與波動率轉為月化
        mu_monthly = self.fund_return_mean / 12
        vol_monthly = self.fund_return_vol / np.sqrt(12)
        
        # 產生 N 條路徑，每條路徑 M 個月的隨機報酬率矩陣
        random_returns = np.random.normal(mu_monthly, vol_monthly, (n_simulations, self.working_months))
        
        # 建立資產矩陣
        assets = np.zeros((n_simulations, self.working_months + 1))
        assets[:, 0] = self.account_balance
        
        # 向量化計算每月資產累積
        for m in range(self.working_months):
            assets[:, m+1] = assets[:, m] * (1 + random_returns[:, m]) + monthly_contribution
            
        final_assets = assets[:, -1]
        
        return {
            "mean": np.mean(final_assets),
            "p25": np.percentile(final_assets, 25),
            "median": np.median(final_assets),
            "p75": np.percentile(final_assets, 75),
            "raw_paths": final_assets
        }

    def calc_success_rate_and_advice(self, pillar1_monthly, mc_results):
        """計算退休成功率與改善建議"""
        # 計算退休期間的總資金缺口
        monthly_gap = self.target_monthly_cost - pillar1_monthly
        if monthly_gap <= 0:
            return 100.0, 0, 0, 0, 0
            
        # 假設退休後資產不再高風險投資，僅抗通膨 (實質報酬為0)
        target_total_wealth = monthly_gap * self.retirement_months
        
        # 成功率：最終資產大於目標總財富的比例
        success_rate = np.mean(mc_results['raw_paths'] >= target_total_wealth) * 100
        
        # 使用中位數資產來計算建議 (目標是補齊中位數的缺口)
        shortfall = max(0, target_total_wealth - mc_results['median'])
        
        # 方案A: 增加一次性投入 (PV計算)
        monthly_rate = self.fund_return_mean / 12
        advice_a = shortfall / ((1 + monthly_rate) ** self.working_months)
        
        # 方案B: 每月增加投資 (PMT計算)
        if monthly_rate > 0:
            advice_b = (shortfall * monthly_rate) / (((1 + monthly_rate) ** self.working_months) - 1)
        else:
            advice_b = shortfall / self.working_months
            
        # 方案C: 減少每月開銷 (直接砍除缺口分攤到退休的每個月)
        advice_c = shortfall / self.retirement_months
        
        # 方案D: 延長退休年齡 (粗估)
        # 假設每年能多存的錢 + 資產成長，簡單推估需要幾年
        yearly_accumulation = self.current_salary * self.total_contribution_rate * 12 + mc_results['median'] * self.fund_return_mean
        advice_d = shortfall / yearly_accumulation if yearly_accumulation > 0 else 0
        
        return success_rate, advice_a, advice_b, advice_c, math.ceil(advice_d)

    def generate_html_report(self, output_path):
        """產出 HTML 報告"""
        pillar1 = self.calc_pillar_1()
        mc_res = self.run_monte_carlo()
        success_rate, adv_a, adv_b, adv_c, adv_d = self.calc_success_rate_and_advice(pillar1, mc_res)
        
        today_str = datetime.now().strftime("%Y/%m/%d")
        
        # HTML 模板字串 (使用 Tailwind)
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>退休金規劃分析報告</title>
          <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 p-8 text-gray-900">
          <div class="max-w-4xl mx-auto bg-white shadow-lg rounded-lg p-8">
            <h1 class="text-3xl font-bold text-center text-blue-800 mb-2">📊 台灣退休金規劃分析報告</h1>
            <p class="text-center text-gray-500 mb-4">產生日期: {today_str}</p>
            
            <div class="text-center mb-6">
               <span class="inline-block px-4 py-1 text-base font-semibold text-white bg-blue-600 rounded-full shadow-sm">
                  職業身份：勞工
               </span>
            </div>

            <div class="bg-blue-50 p-6 rounded-lg mb-8 text-center">
              <h2 class="text-xl font-semibold text-gray-700">退休成功機率</h2>
              <p class="text-6xl font-bold my-4 text-red-600">{success_rate:.1f}%</p>
              <p class="text-gray-600">目標退休後每月生活費: <strong>${int(self.target_monthly_cost):,}</strong></p>
            </div>
            
            <div class="bg-orange-50 p-6 rounded-lg mb-8 border border-orange-200">
                <h3 class="text-xl font-bold text-orange-800 mb-4">💡 提升成功率行動建議 (四選一)</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-white p-4 rounded shadow"><h4 class="font-bold">方案 A: 增加一次性投入</h4><p class="text-xl text-blue-600">${int(adv_a):,}</p></div>
                    <div class="bg-white p-4 rounded shadow"><h4 class="font-bold">方案 B: 每月增加投資</h4><p class="text-xl text-blue-600">${int(adv_b):,}</p></div>
                    <div class="bg-white p-4 rounded shadow"><h4 class="font-bold">方案 C: 減少每月開銷</h4><p class="text-xl text-green-600">-${int(adv_c):,}</p></div>
                    <div class="bg-white p-4 rounded shadow"><h4 class="font-bold">方案 D: 延長退休年齡</h4><p class="text-xl text-purple-600">+ {adv_d} 年</p></div>
                </div>
            </div>

            <div class="bg-white p-4 rounded-lg border border-blue-100 mb-8 text-center">
               <h4 class="font-semibold">第一支柱：勞保老年年金</h4>
               <p class="text-2xl font-bold text-blue-800">${int(pillar1):,} / 月</p>
            </div>
            
            <h3 class="text-2xl font-bold mb-6 text-center text-gray-800">資產預估詳情</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div class="mb-6 md:col-span-2">
                <h4 class="font-semibold text-md text-blue-600 mb-2">第二支柱：勞退個人專戶 (資產累積)</h4>
                <div class="overflow-x-auto">
                  <table class="w-full text-sm text-left text-gray-500 border border-gray-200">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50">
                      <tr><th class="px-4 py-2">統計量</th><th class="px-4 py-2 text-right">數值</th></tr>
                    </thead>
                    <tbody>
                      <tr class="bg-white border-b"><td class="px-4 py-2 font-medium">平均數</td><td class="px-4 py-2 text-right">${int(mc_res['mean']):,}</td></tr>
                      <tr class="bg-white border-b"><td class="px-4 py-2 font-medium">25%位 (悲觀)</td><td class="px-4 py-2 text-right">${int(mc_res['p25']):,}</td></tr>
                      <tr class="bg-white border-b"><td class="px-4 py-2 font-medium">中位數 (正常)</td><td class="px-4 py-2 text-right">${int(mc_res['median']):,}</td></tr>
                      <tr class="bg-white border-b"><td class="px-4 py-2 font-medium">75%位 (樂觀)</td><td class="px-4 py-2 text-right">${int(mc_res['p75']):,}</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ 報表已成功生成：{output_path}")

if __name__ == "__main__":
    # 使用時請確保目錄下有你的 json 檔案
    simulator = PensionSimulator('retirement_config_labor_2026-03-11.json')
    simulator.generate_html_report('retirement_report_output.html')