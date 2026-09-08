"""
生成515180网格回测HTML报告
"""
import json

with open('D:/Backtesting/grid_515180_output/backtest_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取数据
strats = data['strategies']
strat_names = list(strats.keys())
metrics = {name: strats[name]['metrics'] for name in strat_names}

# 为图表准备数据
def prepare_chart_data():
    chart_data = {}
    for name in strat_names:
        nav_list = strats[name]['nav']
        dates = [d['date'] for d in nav_list]
        navs = [round(d['nav'], 2) for d in nav_list]
        prices = [round(d['price'], 4) for d in nav_list]
        chart_data[name] = {'dates': dates, 'navs': navs, 'prices': prices}
    return chart_data

chart_data = prepare_chart_data()

# 交易记录
def prepare_trades():
    trades = {}
    for name in strat_names:
        t = strats[name].get('trades', [])
        trades[name] = t[:50] if len(t) > 50 else t  # 最多显示50条
    return trades

trades_data = prepare_trades()

# 构建指标对比表
def metrics_row(name, m):
    return f"""
    <tr>
        <td class="strat-name">{name}</td>
        <td class="{'positive' if m['total_return'] > 0 else 'negative'}">{m['total_return']:.2%}</td>
        <td class="{'positive' if m['annual_return'] > 0 else 'negative'}">{m['annual_return']:.2%}</td>
        <td>{m['max_drawdown']:.2%}</td>
        <td>{m['sharpe']:.2f}</td>
        <td>{m['calmar']:.2f}</td>
        <td>{m['n_trades']}</td>
        <td>{m['win_rate']:.1%}</td>
        <td>{m['profit_factor']:.2f}</td>
        <td>{m['total_commission']:.0f}</td>
        <td class="{'positive' if m['excess_return'] > 0 else 'negative'}">{m['excess_return']:.2%}</td>
    </tr>"""

metrics_rows = ''.join(metrics_row(name, metrics[name]) for name in strat_names)

# 年度收益表
years = sorted(set(y for name in strat_names for y in metrics[name].get('yearly_returns', {})))
yearly_rows = ''
for year in years:
    cells = f'<td class="year-cell">{year}</td>'
    for name in strat_names:
        yr = metrics[name].get('yearly_returns', {}).get(year, None)
        if yr is not None:
            cells += f'<td class="{"positive" if yr > 0 else "negative"}">{yr:.2%}</td>'
        else:
            cells += '<td>-</td>'
    yearly_rows += f'<tr>{cells}</tr>'

# 交易记录表
def trades_table(name):
    t = trades_data.get(name, [])
    if not t:
        return '<p style="color:#999;">无交易记录</p>'
    rows = ''
    for r in t:
        action_class = 'buy' if r['action'] == '买入' else 'sell'
        profit_cell = f'<td class="{"positive" if r.get("profit",0) > 0 else "negative"}">{r.get("profit","-")}</td>' if r.get('profit') is not None else '<td>-</td>'
        rows += f"""
        <tr>
            <td>{r['date']}</td>
            <td class="{action_class}">{r['action']}</td>
            <td>{r.get('price','-')}</td>
            <td>{r.get('qty','-')}</td>
            <td>{r.get('grid_line','-')}</td>
            {profit_cell}
        </tr>"""
    return f"""
    <table class="trades-table">
        <thead><tr><th>日期</th><th>方向</th><th>价格</th><th>数量</th><th>网格线</th><th>盈亏</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <p style="color:#999;font-size:12px;">共{len(strats[name].get('trades',[]))}笔交易，展示前50笔</p>"""

# 参数卡片
def params_card(name):
    params = strats[name].get('params', {})
    items = ''.join(f'<div class="param-item"><span class="param-key">{k}</span><span class="param-val">{v}</span></div>' for k, v in params.items())
    return f'<div class="params-grid">{items}</div>'

# 图表数据嵌入
nav_chart_labels = chart_data['买入持有']['dates']
nav_datasets = ''
colors = ['#e74c3c', '#3498db', '#2ecc71', '#95a5a6']
for i, name in enumerate(strat_names):
    nav_datasets += f"""{{
        label: '{name}',
        data: {chart_data[name]['navs']},
        borderColor: '{colors[i]}',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.1
    }},"""

# 价格图表
price_data = chart_data['买入持有']['prices']

# 回撤图表数据
drawdown_datasets = ''
for i, name in enumerate(strat_names[:3]):  # 只画网格策略的回撤
    navs = chart_data[name]['navs']
    peak_navs = []
    peak = 0
    dd_list = []
    for n in navs:
        peak = max(peak, n)
        dd_list.append(round(-(n - peak) / peak * 100, 2) if peak > 0 else 0)
    drawdown_datasets += f"""{{
        label: '{name}',
        data: {dd_list},
        borderColor: '{colors[i]}',
        backgroundColor: '{colors[i]}22',
        borderWidth: 1,
        pointRadius: 0,
        fill: true
    }},"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>515180 红利ETF易方达 — 网格策略回测报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background:#0f1923; color:#e0e6ed; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px; }}
h1 {{ font-size:28px; color:#fff; text-align:center; padding:30px 0 10px; letter-spacing:2px; }}
h1 span {{ color:#e74c3c; }}
.subtitle {{ text-align:center; color:#8899aa; font-size:14px; margin-bottom:30px; }}
h2 {{ font-size:20px; color:#3498db; margin:30px 0 15px; padding-left:12px; border-left:4px solid #3498db; }}

/* 顶部概览卡片 */
.overview {{ display:grid; grid-template-columns:repeat(4,1fr); gap:15px; margin:20px 0; }}
.card {{ background:#1a2733; border-radius:10px; padding:20px; text-align:center; border:1px solid #2a3a4a; }}
.card .label {{ font-size:12px; color:#8899aa; margin-bottom:8px; }}
.card .value {{ font-size:22px; font-weight:700; }}
.card .value.red {{ color:#e74c3c; }}
.card .value.green {{ color:#2ecc71; }}
.card .value.blue {{ color:#3498db; }}
.card .value.yellow {{ color:#f39c12; }}

/* 指标对比表 */
.metrics-table {{ width:100%; border-collapse:collapse; background:#1a2733; border-radius:8px; overflow:hidden; margin:15px 0; }}
.metrics-table th {{ background:#243444; padding:12px 8px; font-size:12px; color:#8899aa; text-align:center; white-space:nowrap; }}
.metrics-table td {{ padding:10px 8px; text-align:center; font-size:13px; border-bottom:1px solid #2a3a4a; }}
.strat-name {{ font-weight:600; color:#3498db; white-space:nowrap; }}
.positive {{ color:#e74c3c; font-weight:600; }}
.negative {{ color:#2ecc71; font-weight:600; }}

/* 年度收益表 */
.yearly-table {{ width:100%; border-collapse:collapse; background:#1a2733; border-radius:8px; overflow:hidden; margin:15px 0; }}
.yearly-table th {{ background:#243444; padding:10px; font-size:12px; color:#8899aa; text-align:center; }}
.yearly-table td {{ padding:8px; text-align:center; font-size:13px; border-bottom:1px solid #2a3a4a; }}
.year-cell {{ font-weight:600; color:#f39c12; }}

/* 图表容器 */
.chart-box {{ background:#1a2733; border-radius:10px; padding:20px; margin:15px 0; border:1px solid #2a3a4a; }}
.chart-box canvas {{ max-height:400px; }}

/* 参数卡片 */
.params-grid {{ display:flex; flex-wrap:wrap; gap:10px; }}
.param-item {{ background:#243444; padding:8px 14px; border-radius:6px; font-size:13px; }}
.param-key {{ color:#8899aa; margin-right:8px; }}
.param-val {{ color:#e0e6ed; font-weight:600; }}

/* 交易记录 */
.trades-table {{ width:100%; border-collapse:collapse; background:#1a2733; border-radius:8px; overflow:hidden; margin:10px 0; font-size:12px; }}
.trades-table th {{ background:#243444; padding:8px; color:#8899aa; text-align:center; }}
.trades-table td {{ padding:6px; text-align:center; border-bottom:1px solid #2a3a4a; }}
.buy {{ color:#e74c3c; }}
.sell {{ color:#2ecc71; }}

/* 策略说明 */
.strategy-desc {{ background:#1a2733; border-radius:10px; padding:20px; margin:15px 0; border:1px solid #2a3a4a; }}
.strategy-desc h3 {{ color:#f39c12; margin-bottom:10px; font-size:16px; }}
.strategy-desc p {{ font-size:13px; color:#aabbcc; margin-bottom:8px; }}

/* 底部 */
.footer {{ text-align:center; color:#556677; font-size:12px; padding:30px 0 20px; border-top:1px solid #2a3a4a; margin-top:30px; }}

/* Tab切换 */
.tabs {{ display:flex; gap:5px; margin:15px 0; }}
.tab-btn {{ padding:10px 20px; background:#1a2733; color:#8899aa; border:1px solid #2a3a4a; border-radius:8px 8px 0 0; cursor:pointer; font-size:14px; transition:all 0.2s; }}
.tab-btn.active {{ background:#243444; color:#3498db; border-bottom-color:#243444; }}
.tab-content {{ display:none; background:#1a2733; border-radius:0 8px 8px 8px; padding:20px; border:1px solid #2a3a4a; }}
.tab-content.active {{ display:block; }}
</style>
</head>
<body>
<div class="container">

<h1>📊 <span>515180</span> 红利ETF易方达 · 网格策略回测报告</h1>
<p class="subtitle">
    跟踪指数：{data['index_name']} | 回测区间：{data['backtest_period']} | 
    初始资金：{data['initial_cash']:,}元 | 手续费：万分之一 | 印花税：无 | 交易日：{data['n_trading_days']}天
</p>

<!-- 顶部概览 -->
<div class="overview">
    <div class="card">
        <div class="label">最佳策略</div>
        <div class="value yellow">ATR自适应网格</div>
    </div>
    <div class="card">
        <div class="label">最佳策略收益</div>
        <div class="value red">+{metrics['ATR自适应网格']['total_return']:.2%}</div>
    </div>
    <div class="card">
        <div class="label">Buy&Hold收益</div>
        <div class="value red">+{metrics['买入持有']['total_return']:.2%}</div>
    </div>
    <div class="card">
        <div class="label">最低回撤策略</div>
        <div class="value green">等距静态 -{metrics['等距静态网格']['max_drawdown']:.2%}</div>
    </div>
</div>

<!-- 策略说明 -->
<div class="strategy-desc">
    <h3>💡 为什么选515180做网格？</h3>
    <p>① <b>低波动+高股息</b>：中证红利指数成分股以银行、煤炭、公路为主，日波动率仅{data['daily_vol']:.2%}，天然适合网格</p>
    <p>② <b>均值回归性强</b>：红利指数长期围绕股息率均值波动，跌多了会回来，涨多了会回落</p>
    <p>③ <b>ETF T+0</b>：当日买入当日可卖出，网格触发后可即时反向交易</p>
    <p>④ <b>费率极低</b>：本ETF管理费仅0.20%/年，万分之一交易佣金，网格交易成本极低</p>
</div>

<!-- 核心指标对比 -->
<h2>📈 核心指标对比</h2>
<table class="metrics-table">
<thead><tr>
    <th>策略</th><th>总收益</th><th>年化收益</th><th>最大回撤</th><th>夏普比率</th>
    <th>Calmar</th><th>交易次数</th><th>胜率</th><th>盈亏比</th><th>总手续费</th><th>超额收益</th>
</tr></thead>
<tbody>{metrics_rows}</tbody>
</table>

<!-- 净值曲线 -->
<h2>📉 净值曲线对比</h2>
<div class="chart-box">
    <canvas id="navChart"></canvas>
</div>

<!-- 价格走势 + 回撤 -->
<h2>📊 价格走势与回撤分析</h2>
<div class="chart-box">
    <canvas id="priceChart"></canvas>
</div>
<div class="chart-box">
    <h3 style="color:#f39c12;font-size:14px;margin-bottom:10px;">网格策略回撤对比</h3>
    <canvas id="drawdownChart"></canvas>
</div>

<!-- 年度收益 -->
<h2>📅 年度收益分解</h2>
<table class="yearly-table">
<thead><tr><th>年度</th>{''.join(f'<th>{name}</th>' for name in strat_names)}</tr></thead>
<tbody>{yearly_rows}</tbody>
</table>

<!-- 各策略详情 -->
<h2>🔍 策略详情与参数</h2>
<div class="tabs">
    <button class="tab-btn active" onclick="switchTab(0)">等距静态网格</button>
    <button class="tab-btn" onclick="switchTab(1)">等比网格(1.5%)</button>
    <button class="tab-btn" onclick="switchTab(2)">ATR自适应网格</button>
    <button class="tab-btn" onclick="switchTab(3)">买入持有</button>
</div>

<div class="tab-content active" id="tab-0">
    <h3 style="color:#e74c3c;margin-bottom:10px;">等距静态网格</h3>
    {params_card('等距静态网格')}
    <p style="margin-top:15px;color:#aabbcc;font-size:13px;">
        固定价差画网格线，简单直接。区间和间距根据上市初期60日数据一次性确定，后续不再调整。
        适合初学者，但无法适应市场结构变化。
    </p>
    {trades_table('等距静态网格')}
</div>
<div class="tab-content" id="tab-1">
    <h3 style="color:#3498db;margin-bottom:10px;">等比网格（1.5%间距，±12%区间）</h3>
    {params_card('等比网格(1.5%)')}
    <p style="margin-top:15px;color:#aabbcc;font-size:13px;">
        用百分比间距代替绝对价差，高价区间和低价区间的触发概率更均匀。
        每120个交易日重新计算网格中心，自动适应价格趋势。
        这是《网格交易策略全解析》推荐的红利ETF首选策略。
    </p>
    {trades_table('等比网格(1.5%)')}
</div>
<div class="tab-content" id="tab-2">
    <h3 style="color:#2ecc71;margin-bottom:10px;">ATR自适应网格</h3>
    {params_card('ATR自适应网格')}
    <p style="margin-top:15px;color:#aabbcc;font-size:13px;">
        用20日波动率近似ATR，动态调整网格间距：波动大时间距大（避免手续费吞噬），
        波动小时间距小（保证触发频率）。每60个交易日重算一次。
        本次回测中表现最优，兼顾收益和回撤控制。
    </p>
    {trades_table('ATR自适应网格')}
</div>
<div class="tab-content" id="tab-3">
    <h3 style="color:#95a5a6;margin-bottom:10px;">买入持有（基准）</h3>
    {params_card('买入持有')}
    <p style="margin-top:15px;color:#aabbcc;font-size:13px;">
        上市首日全仓买入，持有至今。作为基准对比网格策略的表现。
        Buy&Hold收益+75.91%远超网格策略，但最大回撤-17.55%也远大于网格策略。
        网格策略的核心优势在于<b>低回撤+稳定</b>，而非追求绝对收益。
    </p>
</div>

<!-- 结论 -->
<h2>🧠 基金经理结论</h2>
<div class="strategy-desc">
    <h3>关键发现</h3>
    <p>① <b>网格赚的是"波动率"的钱，不是"方向"的钱</b>——515180上市至今累计涨幅75.91%，但网格策略只赚了5~18%，因为大部分时间在"等待"和"低买高卖小波段"</p>
    <p>② <b>回撤控制是网格策略的绝对优势</b>——等距静态网格最大回撤仅1.26%，而Buy&Hold为17.55%，差距13倍</p>
    <p>③ <b>ATR自适应网格综合最优</b>——收益最高(18.15%)，回撤仅2.86%，夏普比率0.68，交易次数适中(57笔)</p>
    <p>④ <b>网格策略与Buy&Hold不冲突</b>——建议组合：70% Buy&Hold + 30% 网格增强，享受长期上涨+波动增强</p>
    
    <h3 style="margin-top:15px;">建议配置</h3>
    <p>🔴 <b>保守型</b>（风险厌恶）：100%等距静态网格，回撤1.26%，年化收益~0.9%</p>
    <p>🟡 <b>稳健型</b>（推荐）：70% Buy&Hold + 30% ATR自适应网格，综合回撤~12%，年化~8%</p>
    <p>🟢 <b>进取型</b>：50% Buy&Hold + 50% 等比网格，综合回撤~9%，年化~6%+网格增强</p>
</div>

<div class="footer">
    <p>⚠️ 免责声明：本报告仅供策略学习与探讨，不构成任何投资建议。网格交易存在本金亏损风险，历史回测不代表未来表现。</p>
    <p>回测引擎：Python + efinance | 数据来源：东方财富 | 生成时间：2026-06-05</p>
</div>

</div>

<script>
// 净值曲线
const navCtx = document.getElementById('navChart').getContext('2d');
new Chart(navCtx, {{
    type: 'line',
    data: {{
        labels: {nav_chart_labels},
        datasets: [{nav_datasets}]
    }},
    options: {{
        responsive: true,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{ labels: {{ color: '#8899aa', font: {{size:11}} }} }},
            title: {{ display: false }}
        }},
        scales: {{
            x: {{ ticks: {{ color:'#556677', maxTicksLimit:10, font:{{size:10}} }}, grid: {{ color:'#1a2733' }} }},
            y: {{ ticks: {{ color:'#556677', font:{{size:10}} }}, grid: {{ color:'#1a2733' }} }}
        }}
    }}
}});

// 价格走势
const priceCtx = document.getElementById('priceChart').getContext('2d');
new Chart(priceCtx, {{
    type: 'line',
    data: {{
        labels: {nav_chart_labels},
        datasets: [{{
            label: '515180 累计净值',
            data: {price_data},
            borderColor: '#f39c12',
            backgroundColor: '#f39c1222',
            borderWidth: 1.5,
            pointRadius: 0,
            fill: true
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ labels: {{ color: '#8899aa' }} }}
        }},
        scales: {{
            x: {{ ticks: {{ color:'#556677', maxTicksLimit:10, font:{{size:10}} }}, grid: {{ color:'#1a2733' }} }},
            y: {{ ticks: {{ color:'#556677', font:{{size:10}} }}, grid: {{ color:'#1a2733' }} }}
        }}
    }}
}});

// 回撤
const ddCtx = document.getElementById('drawdownChart').getContext('2d');
new Chart(ddCtx, {{
    type: 'line',
    data: {{
        labels: {nav_chart_labels},
        datasets: [{drawdown_datasets}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ labels: {{ color: '#8899aa', font:{{size:11}} }} }}
        }},
        scales: {{
            x: {{ ticks: {{ color:'#556677', maxTicksLimit:10, font:{{size:10}} }}, grid: {{ color:'#1a2733' }} }},
            y: {{ ticks: {{ color:'#556677', font:{{size:10}}, callback: v => v+'%' }}, grid: {{ color:'#1a2733' }} }}
        }}
    }}
}});

// Tab切换
function switchTab(idx) {{
    document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.toggle('active', i===idx));
    document.querySelectorAll('.tab-content').forEach((c,i) => c.classList.toggle('active', i===idx));
}}
</script>
</body>
</html>"""

with open('D:/Backtesting/grid_515180_output/grid_515180_report.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML report saved: D:/Backtesting/grid_515180_output/grid_515180_report.html")
