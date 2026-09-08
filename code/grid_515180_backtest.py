"""
515180 红利ETF易方达 — 网格交易策略回测 v2
核心修复：用"穿越网格线"逻辑实现网格触发
回测区间：2019-11-26 至 2026-06-05
手续费：万分之一（0.01%），无印花税
"""

import json, os
import numpy as np
import pandas as pd


def fetch_data():
    import efinance as ef
    df = ef.fund.get_quote_history('515180')
    df = df.iloc[::-1].reset_index(drop=True)
    df['日期'] = pd.to_datetime(df['日期'])
    df['price'] = df['累计净值'].astype(float)
    df = df.rename(columns={'日期': 'date'})
    return df[['date', 'price']]


def build_grid_lines(center, lower_pct, upper_pct, spacing_pct, method='pct'):
    """构建网格线
    method='pct': 等比网格，spacing_pct为百分比间距
    method='fixed': 等距网格，spacing_pct为绝对间距
    """
    lower = center * (1 - lower_pct)
    upper = center * (1 + upper_pct)
    
    if method == 'pct':
        lines = [lower]
        while lines[-1] < upper:
            lines.append(lines[-1] * (1 + spacing_pct))
        if lines[-1] > upper * 1.05:
            lines.pop()
    else:
        n = int((upper - lower) / spacing_pct)
        n = max(n, 3)
        lines = list(np.linspace(lower, upper, n + 1))
    
    return np.array(lines), lower, upper


def grid_backtest(prices, dates, grid_lines, qty_per_grid, initial_cash=1_000_000,
                  commission_rate=0.0001):
    """通用网格回测引擎
    核心逻辑：记录每根网格线的持仓状态
    - 价格从上方穿越某条网格线向下 → 买入该网格线对应的份额
    - 价格从下方穿越某条网格线向上 → 卖出该网格线下方一格的持仓
    """
    n = len(prices)
    cash = initial_cash
    position = 0
    # 跟踪每根网格线是否已有买入持仓
    grid_bought = {}  # {grid_price: True/False}
    # 跟踪每根网格线的买入成本
    grid_cost = {}    # {grid_price: avg_cost}
    
    nav_history = []
    trade_records = []
    prev_price = None
    
    for i in range(n):
        price = prices[i]
        date = dates[i]
        
        if prev_price is not None:
            # 检查穿越了哪些网格线
            for gl in grid_lines:
                # 向下穿越：前收盘>=网格线 且 当前收盘<网格线 → 买入
                if prev_price >= gl and price < gl:
                    if not grid_bought.get(gl, False):
                        buy_amount = qty_per_grid * price
                        commission = buy_amount * commission_rate
                        if cash >= buy_amount + commission:
                            cash -= (buy_amount + commission)
                            position += qty_per_grid
                            grid_bought[gl] = True
                            grid_cost[gl] = price
                            trade_records.append({
                                'date': pd.Timestamp(date),
                                'action': '买入',
                                'price': round(price, 4),
                                'qty': qty_per_grid,
                                'grid_line': round(gl, 4),
                                'amount': round(buy_amount, 2),
                                'commission': round(commission, 2),
                            })
                
                # 向上穿越：前收盘<=网格线 且 当前收盘>网格线 → 卖出该线下方一格的持仓
                if prev_price <= gl and price > gl:
                    # 找到该网格线下方紧邻的一格
                    gl_idx = np.searchsorted(grid_lines, gl)
                    if gl_idx > 0:
                        sell_gl = grid_lines[gl_idx - 1]
                        if grid_bought.get(sell_gl, False):
                            sell_amount = qty_per_grid * price
                            commission = sell_amount * commission_rate
                            cash += (sell_amount - commission)
                            position -= qty_per_grid
                            buy_cost = grid_cost.get(sell_gl, 0)
                            profit = (price - buy_cost) * qty_per_grid - commission
                            grid_bought[sell_gl] = False
                            trade_records.append({
                                'date': pd.Timestamp(date),
                                'action': '卖出',
                                'price': round(price, 4),
                                'qty': qty_per_grid,
                                'grid_line': round(gl, 4),
                                'buy_at': round(sell_gl, 4),
                                'amount': round(sell_amount, 2),
                                'commission': round(commission, 2),
                                'profit': round(profit, 2),
                            })
        
        market_value = cash + position * price
        nav_history.append({
            'date': pd.Timestamp(date),
            'nav': market_value,
            'cash': cash,
            'position': position,
            'price': price,
        })
        prev_price = price
    
    return pd.DataFrame(nav_history), pd.DataFrame(trade_records)


def calc_metrics(nav_df, trades_df, initial_cash):
    """计算绩效指标"""
    navs = nav_df['nav'].values
    total_return = (navs[-1] / initial_cash) - 1
    
    days = (nav_df['date'].iloc[-1] - nav_df['date'].iloc[0]).days
    annual_return = (1 + total_return) ** (365 / max(days, 1)) - 1 if days > 0 else 0
    
    # 最大回撤
    peak = np.maximum.accumulate(navs)
    drawdown = (peak - navs) / peak
    max_drawdown = np.max(drawdown)
    max_dd_end = np.argmax(drawdown)
    max_dd_start = np.argmax(navs[:max_dd_end+1]) if max_dd_end > 0 else 0
    
    # 夏普比率
    daily_returns = nav_df['nav'].pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
    
    # Calmar比率
    calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
    
    # 交易统计
    n_trades = len(trades_df)
    n_buy = len(trades_df[trades_df['action'] == '买入']) if n_trades > 0 else 0
    n_sell = len(trades_df[trades_df['action'] == '卖出']) if n_trades > 0 else 0
    
    total_commission = trades_df['commission'].sum() if n_trades > 0 else 0
    
    # 盈亏统计
    sells = trades_df[trades_df['action'] == '卖出'] if n_trades > 0 else pd.DataFrame()
    profit_trades = 0
    loss_trades = 0
    total_profit = 0
    total_loss = 0
    if len(sells) > 0:
        for _, row in sells.iterrows():
            p = row.get('profit', 0)
            if p > 0:
                profit_trades += 1
                total_profit += p
            else:
                loss_trades += 1
                total_loss += p
    
    win_rate = profit_trades / max(n_sell, 1)
    avg_profit = total_profit / max(profit_trades, 1)
    avg_loss = total_loss / max(loss_trades, 1) if loss_trades > 0 else 0
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
    
    # Buy & Hold
    price_start = nav_df['price'].iloc[0]
    price_end = nav_df['price'].iloc[-1]
    bh_return = (price_end / price_start) - 1
    bh_annual = (1 + bh_return) ** (365 / max(days, 1)) - 1 if days > 0 else 0
    
    # 年度收益分解
    nav_df['year'] = nav_df['date'].dt.year
    yearly_returns = {}
    for year, group in nav_df.groupby('year'):
        yr = (group['nav'].iloc[-1] / group['nav'].iloc[0]) - 1
        yearly_returns[int(year)] = round(yr, 4)
    
    return {
        'total_return': float(total_return),
        'annual_return': float(annual_return),
        'max_drawdown': float(max_drawdown),
        'max_dd_start': nav_df['date'].iloc[max_dd_start].strftime('%Y-%m-%d'),
        'max_dd_end': nav_df['date'].iloc[max_dd_end].strftime('%Y-%m-%d'),
        'sharpe': float(sharpe),
        'calmar': float(calmar),
        'n_trades': n_trades,
        'n_buy': n_buy,
        'n_sell': n_sell,
        'win_rate': float(win_rate),
        'total_commission': float(total_commission),
        'total_profit': float(total_profit),
        'total_loss': float(total_loss),
        'avg_profit': float(avg_profit),
        'avg_loss': float(avg_loss),
        'profit_factor': float(profit_factor) if profit_factor != float('inf') else 999.99,
        'bh_return': float(bh_return),
        'bh_annual': float(bh_annual),
        'days': days,
        'yearly_returns': yearly_returns,
        'excess_return': float(total_return - bh_return),
    }


def run_backtest():
    """主回测函数"""
    print("=" * 60)
    print("515180 红利ETF易方达 — 网格交易策略回测")
    print("=" * 60)
    
    df = fetch_data()
    prices = df['price'].values
    dates = df['date'].values
    
    print(f"\n数据概览:")
    print(f"  数据量: {len(df)} 个交易日")
    print(f"  时间: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"  价格(累计净值): {prices.min():.4f} ~ {prices.max():.4f}")
    print(f"  日波动率: {np.std(np.diff(prices)/prices[:-1]):.4%}")
    
    initial_cash = 1_000_000
    commission_rate = 0.0001
    
    # ===== 策略1: 等距静态网格 =====
    # 参数来源：《网格交易策略全解析》— 红利ETF建议间距1.5%，区间±12%
    # 等距：用中心价×1.5%作为固定间距
    center = np.mean(prices[:60])
    spacing_fixed = center * 0.015
    grid_lines_1, lower_1, upper_1 = build_grid_lines(
        center, 0.15, 0.15, spacing_fixed, method='fixed'
    )
    qty_1 = int((initial_cash * 0.5 / len(grid_lines_1)) / center)
    qty_1 = max((qty_1 // 100) * 100, 100)
    
    print(f"\n策略1: 等距静态网格")
    print(f"  区间: {lower_1:.4f} ~ {upper_1:.4f}")
    print(f"  网格数: {len(grid_lines_1)}")
    print(f"  间距: {spacing_fixed:.4f} ({spacing_fixed/center:.2%})")
    print(f"  每格份额: {qty_1}")
    
    nav1, trades1 = grid_backtest(prices, dates, grid_lines_1, qty_1, initial_cash, commission_rate)
    metrics1 = calc_metrics(nav1, trades1, initial_cash)
    print(f"  总收益: {metrics1['total_return']:.2%}, 最大回撤: {metrics1['max_drawdown']:.2%}, 交易: {metrics1['n_trades']}笔")
    
    # ===== 策略2: 等比网格（1.5%间距，±12%区间）=====
    # 每120个交易日重新计算网格中心
    # 先做初始网格
    center2 = np.mean(prices[:60])
    grid_lines_2, lower_2, upper_2 = build_grid_lines(
        center2, 0.12, 0.12, 0.015, method='pct'
    )
    qty_2 = int((initial_cash * 0.5 / len(grid_lines_2)) / center2)
    qty_2 = max((qty_2 // 100) * 100, 100)
    
    print(f"\n策略2: 等比网格(1.5%间距,±12%区间)")
    print(f"  区间: {lower_2:.4f} ~ {upper_2:.4f}")
    print(f"  网格数: {len(grid_lines_2)}")
    print(f"  每格份额: {qty_2}")
    
    # 动态等比网格：每120日重算中心
    # 需要分段回测
    segment_size = 120
    all_nav2 = []
    all_trades2 = []
    seg_cash = initial_cash
    seg_position = 0
    
    for seg_start in range(0, len(prices), segment_size):
        seg_end = min(seg_start + segment_size, len(prices))
        seg_prices = prices[seg_start:seg_end]
        seg_dates = dates[seg_start:seg_end]
        
        # 重算网格
        if seg_start == 0:
            c = np.mean(prices[:min(60, seg_end)])
        else:
            c = np.mean(prices[max(0, seg_start-60):seg_start])
        
        gl, lo, hi = build_grid_lines(c, 0.12, 0.12, 0.015, method='pct')
        qty = int((initial_cash * 0.5 / len(gl)) / c)
        qty = max((qty // 100) * 100, 100)
        
        # 用段内现金和持仓继续
        seg_nav, seg_trades = grid_backtest(
            seg_prices, seg_dates, gl, qty, 
            seg_cash + seg_position * seg_prices[0],  # 用当前总市值作为初始资金
            commission_rate
        )
        
        # 调整净值（因为每段重新开始计算）
        if len(all_nav2) > 0:
            prev_nav = all_nav2[-1]['nav']
            scale = prev_nav / seg_nav['nav'].iloc[0]
            seg_nav['nav'] = seg_nav['nav'] * scale
        
        all_nav2.extend(seg_nav.to_dict('records'))
        all_trades2.extend(seg_trades.to_dict('records'))
        
        # 更新下一段的现金和持仓
        seg_cash = seg_nav['cash'].iloc[-1]
        seg_position = seg_nav['position'].iloc[-1]
    
    nav2 = pd.DataFrame(all_nav2)
    trades2 = pd.DataFrame(all_trades2) if all_trades2 else pd.DataFrame()
    metrics2 = calc_metrics(nav2, trades2, initial_cash)
    print(f"  总收益: {metrics2['total_return']:.2%}, 最大回撤: {metrics2['max_drawdown']:.2%}, 交易: {metrics2['n_trades']}笔")
    
    # ===== 策略3: ATR自适应网格 =====
    # 用20日收益率波动率近似ATR，每60日重算
    segment_size_atr = 60
    all_nav3 = []
    all_trades3 = []
    
    for seg_start in range(0, len(prices), segment_size_atr):
        seg_end = min(seg_start + segment_size_atr, len(prices))
        seg_prices = prices[seg_start:seg_end]
        seg_dates = dates[seg_start:seg_end]
        
        if seg_start == 0:
            c = np.mean(prices[:min(40, seg_end)])
            hist = prices[:min(40, seg_end)]
        else:
            c = prices[seg_start - 1]
            hist = prices[max(0, seg_start-40):seg_start]
        
        # ATR近似
        rets = np.diff(hist) / hist[:-1]
        daily_vol = np.std(rets) if len(rets) > 5 else 0.01
        atr_approx = c * daily_vol * np.sqrt(20)
        spacing = atr_approx * 1.5
        spacing = max(spacing, c * 0.008)  # 最小0.8%间距
        
        lo = min(hist) * 0.95
        hi = max(hist) * 1.05
        
        n_grids = max(int((hi - lo) / spacing), 3)
        n_grids = min(n_grids, 30)
        gl = np.linspace(lo, hi, n_grids + 1)
        
        qty = int((initial_cash * 0.5 / n_grids) / c)
        qty = max((qty // 100) * 100, 100)
        
        if seg_start == 0:
            seg_init_cash = initial_cash
        else:
            seg_init_cash = all_nav3[-1]['nav']
        
        seg_nav, seg_trades = grid_backtest(
            seg_prices, seg_dates, gl, qty, seg_init_cash, commission_rate
        )
        
        if len(all_nav3) > 0:
            prev_nav = all_nav3[-1]['nav']
            scale = prev_nav / seg_nav['nav'].iloc[0]
            seg_nav['nav'] = seg_nav['nav'] * scale
        
        all_nav3.extend(seg_nav.to_dict('records'))
        all_trades3.extend(seg_trades.to_dict('records'))
    
    nav3 = pd.DataFrame(all_nav3)
    trades3 = pd.DataFrame(all_trades3) if all_trades3 else pd.DataFrame()
    metrics3 = calc_metrics(nav3, trades3, initial_cash)
    print(f"\n策略3: ATR自适应网格")
    print(f"  总收益: {metrics3['total_return']:.2%}, 最大回撤: {metrics3['max_drawdown']:.2%}, 交易: {metrics3['n_trades']}笔")
    
    # ===== Buy & Hold =====
    bh_price = prices[0]
    bh_commission = initial_cash * commission_rate
    bh_shares = int((initial_cash - bh_commission) / bh_price / 100) * 100
    bh_cash = initial_cash - bh_shares * bh_price - bh_shares * bh_price * commission_rate
    
    bh_nav = pd.DataFrame({
        'date': dates,
        'nav': [bh_cash + bh_shares * p for p in prices],
        'cash': bh_cash,
        'position': bh_shares,
        'price': prices,
    })
    bh_nav['date'] = pd.to_datetime(bh_nav['date'])
    
    bh_trades = pd.DataFrame([{
        'date': pd.Timestamp(dates[0]),
        'action': '买入',
        'price': round(bh_price, 4),
        'qty': bh_shares,
        'amount': round(bh_shares * bh_price, 2),
        'commission': round(bh_shares * bh_price * commission_rate, 2),
    }])
    metrics_bh = calc_metrics(bh_nav, bh_trades, initial_cash)
    metrics_bh['n_trades'] = 1
    metrics_bh['n_buy'] = 1
    metrics_bh['n_sell'] = 0
    metrics_bh['win_rate'] = 1.0 if metrics_bh['total_return'] > 0 else 0.0
    metrics_bh['profit_factor'] = 999.99
    print(f"\nBuy&Hold: {metrics_bh['total_return']:.2%}, 最大回撤: {metrics_bh['max_drawdown']:.2%}")
    
    # ===== 汇总保存 =====
    os.makedirs('D:/Backtesting/grid_515180_output', exist_ok=True)
    
    def serialize_df(df):
        d = df.copy()
        d['date'] = d['date'].dt.strftime('%Y-%m-%d')
        return d.to_dict('records')
    
    output = {
        'etf_code': '515180',
        'etf_name': '红利ETF易方达',
        'index_name': '中证红利指数',
        'backtest_period': f"{df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}",
        'initial_cash': initial_cash,
        'commission_rate': commission_rate,
        'n_trading_days': len(df),
        'price_range': f"{prices.min():.4f} ~ {prices.max():.4f}",
        'daily_vol': float(np.std(np.diff(prices)/prices[:-1])),
        'strategies': {
            '等距静态网格': {
                'nav': serialize_df(nav1),
                'trades': serialize_df(trades1) if len(trades1) > 0 else [],
                'metrics': metrics1,
                'params': {
                    '区间': f"{lower_1:.4f}~{upper_1:.4f}",
                    '间距': f"{spacing_fixed:.4f}({spacing_fixed/center:.1%})",
                    '网格数': len(grid_lines_1),
                    '每格份额': qty_1,
                }
            },
            '等比网格(1.5%)': {
                'nav': serialize_df(nav2),
                'trades': serialize_df(trades2) if len(trades2) > 0 else [],
                'metrics': metrics2,
                'params': {
                    '区间': '±12%（动态重算）',
                    '间距': '1.5%（等比）',
                    '每格份额': qty_2,
                    '重算周期': '120个交易日',
                }
            },
            'ATR自适应网格': {
                'nav': serialize_df(nav3),
                'trades': serialize_df(trades3) if len(trades3) > 0 else [],
                'metrics': metrics3,
                'params': {
                    '区间': '90日极值±5%（动态）',
                    '间距': 'ATR×1.5（动态）',
                    '重算周期': '60个交易日',
                }
            },
            '买入持有': {
                'nav': serialize_df(bh_nav),
                'trades': serialize_df(bh_trades),
                'metrics': metrics_bh,
                'params': {'说明': '上市首日全仓买入，持有至今'}
            },
        }
    }
    
    with open('D:/Backtesting/grid_515180_output/backtest_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, default=str)
    
    print(f"\n✅ 回测数据已保存")
    return output


if __name__ == '__main__':
    run_backtest()
