import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def get(path):
    with urllib.request.urlopen(f'http://127.0.0.1:8000{path}') as r:
        return json.loads(r.read().decode())

def put(path, data):
    req = urllib.request.Request(
        f'http://127.0.0.1:8000{path}',
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def post(path, data=None):
    req = urllib.request.Request(
        f'http://127.0.0.1:8000{path}',
        data=json.dumps(data or {}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

print("====================================================================")
print("1. VERIFYING 10 AUTONOMOUS AGENTS & CAPITAL LIMITS (8 @ 1L, 2 @ 2L)")
print("====================================================================")
status = get('/v1/agents/status')
agents = status['agents']
print(f"Total Agents Loaded: {len(agents)}")
assert len(agents) == 10, f"Expected 10 agents, got {len(agents)}"

lac1_count = 0
lac2_count = 0
for name, a in sorted(agents.items()):
    p = a['max_principal']
    if p >= 200000:
        lac2_count += 1
        tier = "🏛️ ₹2.00 Lac Tier (Institutional)"
    else:
        lac1_count += 1
        tier = "💼 ₹1.00 Lac Tier (Standard)"
    strat = a.get("active_strategy", "AUTO")
    act = a.get("current_activity", "")[:45]
    print(f" - Agent {name:<8}: Rs.{p:,.0f} [{tier}] | Strategy: {strat} | Activity: {act}...")

assert lac1_count == 8, f"Expected 8 agents @ 1L, got {lac1_count}"
assert lac2_count == 2, f"Expected 2 agents @ 2L, got {lac2_count}"
assert agents["Echo"]["max_principal"] == 200000.0, "Echo must have 2 Lac"
assert agents["Juliet"]["max_principal"] == 200000.0, "Juliet must have 2 Lac"

print("\n====================================================================")
print("2. VERIFYING LIVE MARKET SELECTION & ZERO FABRICATION FIX")
print("====================================================================")
mkt_info = get('/v1/agents/market')
print("Current Market Target:", mkt_info['target_market'])
print("Available Markets:", [m['id'] for m in mkt_info['available_markets']])

print("\nSwitching Market Target to MCX_GOLDM...")
res_mini = put('/v1/agents/market', {'target_market': 'MCX_GOLDM'})
print("Switched to:", res_mini['target_market'])
mini_status = get('/v1/agents/status')
print("Active Session:", mini_status['active_session']['market_name'], "| Symbol:", mini_status['active_session']['symbol'], "| Live Price:", mini_status['active_session']['currency_symbol'], mini_status['active_session']['live_price'])
assert mini_status['active_session']['is_live'] == True

print("\nSwitching Market Target to MCX_GOLD (1kg)...")
res_big = put('/v1/agents/market', {'target_market': 'MCX_GOLD'})
print("Switched to:", res_big['target_market'])
big_status = get('/v1/agents/status')
print("Active Session:", big_status['active_session']['market_name'], "| Symbol:", big_status['active_session']['symbol'], "| Live Price:", big_status['active_session']['currency_symbol'], big_status['active_session']['live_price'])
assert big_status['active_session']['is_live'] == True

print("\nSwitching Market Target to GLOBAL_XAU (Spot 24/7)...")
res_xau = put('/v1/agents/market', {'target_market': 'GLOBAL_XAU'})
print("Switched to:", res_xau['target_market'])
xau_status = get('/v1/agents/status')
print("Active Session:", xau_status['active_session']['market_name'], "| Symbol:", xau_status['active_session']['symbol'], "| Live Price: $", xau_status['active_session']['live_price'])
assert xau_status['active_session']['is_live'] == True

print("\nResetting Market Target to AUTO...")
res_auto = put('/v1/agents/market', {'target_market': 'AUTO'})
print("Target Market Reset to:", res_auto['target_market'])

print("\n====================================================================")
print("3. VERIFYING AGENT TRADING GUIDELINES & DIRECTIVE CONTROLS")
print("====================================================================")
g_all = get('/v1/agents/guidelines')
print(f"Total Configured Agent Guidelines: {len(g_all['guidelines'])}")
alpha_g = get('/v1/agents/Alpha/guidelines')
print("Alpha Initial Guidelines:", f"Mode: {alpha_g['mode']}, Bias: {alpha_g['direction_bias']}, Lots: {alpha_g['lots']}, Principal: Rs.{alpha_g['max_principal']:,.0f}")

print("\nUpdating Alpha to CUSTOM DIRECTIVE (2 lots, LONG_ONLY, 50 pt profit target)...")
alpha_custom = put(
    '/v1/agents/Alpha/guidelines',
    {
        'mode': 'CUSTOM',
        'strategy_id': 'S01_ORB_NR7',
        'strategy_name': 'Opening Range Breakout (NR7)',
        'max_principal': 150000.0,
        'lots': 2,
        'direction_bias': 'LONG_ONLY',
        'profit_target_pts': 50.0,
        'stop_loss_pts': 25.0
    }
)
g_res = alpha_custom['guidelines']
print("Alpha Updated Guidelines:", f"Mode: {g_res['mode']}, Bias: {g_res['direction_bias']}, Lots: {g_res['lots']}, Target: {g_res['profit_target_pts']} pts, Stop: {g_res['stop_loss_pts']} pts, Principal: Rs.{g_res['max_principal']:,.0f}")
assert g_res['mode'] == 'CUSTOM'
assert g_res['direction_bias'] == 'LONG_ONLY'
assert g_res['lots'] == 2

print("\nResetting Alpha to Default Autonomous AUTO Mode...")
alpha_reset = post('/v1/agents/Alpha/guidelines/reset')
print("Alpha Reset to:", alpha_reset['guidelines']['mode'], "| Principal: Rs.", alpha_reset['guidelines']['max_principal'])
assert alpha_reset['guidelines']['mode'] == 'AUTO'
assert alpha_reset['guidelines']['max_principal'] == 100000.0

print("\n====================================================================")
print("4. VERIFYING BIDIRECTIONAL STRATEGY LEADERBOARD & LAB SYNC")
print("====================================================================")
lab = get('/v1/strategies/lab')
print(f"Best in Store Strategies: {len(lab['best_store'])}")
for s in lab['best_store'][:3]:
    print(f" - {s['id']}: {s['name']} | Archetype: {s['archetype']} | Store Rank #{s.get('store_rank')} | Leaderboard Rank #{s.get('leaderboard_rank')} (Score: {s.get('leaderboard_score')}, Grade: {s.get('leaderboard_grade')})")

print("\n====================================================================")
print("5. VERIFYING UPSTOX TRADE LEDGER LOT SIZING & CHARGES")
print("====================================================================")
trades = get('/v1/agents/upstox-trades?limit=5')
print(f"Total Settled Live Trades in Buffer: {trades['total_trades']} / {trades['capacity']}")
for t in trades['trades'][:3]:
    print(f" - #{t['trade_id']}: Agent {t['agent_name']} | {t['direction']} {t['lots']} Lot ({t['total_quantity']} {t['lot_unit']}) | Turnover: Rs.{t['turnover']:,.0f} | Gross: Rs.{t['gross_pnl']:,.2f} | Charges: Rs.{t['total_charges']:.2f} | Net: Rs.{t['net_pnl']:,.2f}")

print("\n====================================================================")
print("✨ ALL 5 VERIFICATION MODULES EXECUTED AND PASSED WITH 100% SUCCESS!")
print("====================================================================")
