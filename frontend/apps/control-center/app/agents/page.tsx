"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";

interface Trade {
  trade_id?: string;
  id?: string;
  timestamp: string;
  strategy_id: string;
  strategy_name: string;
  direction: "LONG" | "SHORT";
  lots: number;
  lot_size: number;
  total_quantity: number;
  entry_price: number;
  exit_price: number;
  pnl_change: number;
  exit_reason: string;
  duration_seconds?: number;
}

interface AgentGuidelines {
  name: string;
  max_principal: number;
  mode: "AUTO" | "CUSTOM";
  strategy_id: string;
  strategy_name: string;
  target_market: string;
  allowed_lot_size: number;
  lots: number;
  direction_bias: "BOTH" | "LONG_ONLY" | "SHORT_ONLY";
  profit_target_pts: number;
  stop_loss_pts: number;
  max_risk_pct_per_trade: number;
  max_lots: number;
  is_active: boolean;
  goal?: string;
  goal_description?: string;
  horizon?: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
  target_net_pnl_increment?: number;
  retest_winning_strategies?: boolean;
  condition_gated_entry?: boolean;
}

interface Agent {
  id: string;
  name: string;
  avatar: string;
  specialization: string;
  max_principal: number;
  initial_capital: number;
  current_capital: number;
  allocated_margin: number;
  available_capital: number;
  pnl: number;
  win_rate: number;
  winning_tests: number;
  total_tests: number;
  history: Trade[];
  current_activity: string;
  current_hypothesis: string;
  active_strategy: string;
  active_strategy_name: string;
  active_strategy_status: string;
  active_market: string;
  last_price: number;
  last_updated: string;
  learning_progress: number;
  position: {
    direction: "LONG" | "SHORT";
    lots: number;
    lot_size: number;
    total_quantity: number;
    lot_unit: string;
    entry_price: number;
    target_price: number;
    stop_loss: number;
    margin_utilized: number;
    strategy_id: string;
    strategy_name: string;
    hypothesis: string;
    opened_at: string;
    hold_cycles: number;
    unrealized_pnl: number;
    breakeven_locked?: boolean;
    horizon?: string;
  } | null;
  guidelines?: AgentGuidelines;
  goal?: string;
  goal_description?: string;
  horizon?: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
  target_net_pnl_increment?: number;
  retest_winning_strategies?: boolean;
  condition_gated_entry?: boolean;
  strategy_retests?: number;
  strategy_net_pnl?: number;
  strategy_wins?: number;
  strategy_losses?: number;
  strategy_edge_status?: string;
  condition_status?: {
    matched: boolean;
    regime_type: string;
    condition_name: string;
    condition_label: string;
    strength_score: number;
    recommended_direction?: string | null;
  };
  net_pnl_increment?: number;
  goal_progress_pct?: number;
}

interface ActiveSession {
  mode: string;
  is_mcx_session?: boolean;
  market_name?: string;
  contract_type?: string;
  contract_name?: string;
  currency_symbol?: string;
  live_price: number;
  bid_price?: number | null;
  ask_price?: number | null;
  source?: string;
  session_desc?: string;
  is_live?: boolean;
  last_tick_time?: string;
}

interface UpstoxLedgerSummary {
  capacity: number;
  total_trades: number;
  total_lots_traded: number;
  total_turnover: number;
  gross_pnl: number;
  total_upstox_charges: number;
  net_pnl: number;
  win_rate: number;
  profit_factor: number;
}

interface StateResponse {
  active_session: ActiveSession;
  target_market: string;
  agents: Record<string, Agent>;
  upstox_ledger_summary?: UpstoxLedgerSummary;
}

interface LabStrategy {
  id: string;
  name: string;
  archetype: string;
  leaderboard_rank?: number;
  leaderboard_score?: number;
}

const AGENT_ORDER = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"];

const INITIAL_AGENTS_CACHE: Record<string, Agent> = {
  Alpha: {
    id: "agt-alpha",
    name: "Alpha",
    avatar: "⚡",
    specialization: "Trend & Momentum Specialist",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Observing Live Market Feed: Monitoring quantitative breakout triggers...",
    current_hypothesis: "Awaiting initial live market tick breakout",
    active_strategy: "S01_ORB_NR7",
    active_strategy_name: "Opening Range Breakout (NR7)",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Alpha",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Bravo: {
    id: "agt-bravo",
    name: "Bravo",
    avatar: "🎯",
    specialization: "Statistical Mean Reversion AI",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Monitoring VWAP mean reversion bands...",
    current_hypothesis: "Tracking price variance from session VWAP",
    active_strategy: "S02_VWAP_MEAN_REVERSION",
    active_strategy_name: "VWAP Dynamic Bands Mean Reversion",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Bravo",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Charlie: {
    id: "agt-charlie",
    name: "Charlie",
    avatar: "⚖️",
    specialization: "Statistical Arbitrage & Volatility Control",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Tracking dynamic volatility envelope...",
    current_hypothesis: "Measuring Parkinson volatility against rolling ATR",
    active_strategy: "S04_VOL_TARGET",
    active_strategy_name: "Dynamic Volatility Targeting",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Charlie",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Delta: {
    id: "agt-delta",
    name: "Delta",
    avatar: "👑",
    specialization: "Price × OI × Volume Specialist (#1 Ranked Strategy)",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Tracking Price × OI × Volume State Machine (#1 Strategy)...",
    current_hypothesis: "Monitoring 4-quadrant open interest expansion",
    active_strategy: "S17_OI_VOLUME_MACHINE",
    active_strategy_name: "Price × OI × Volume State Machine",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Delta",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "S17_OI_VOLUME_MACHINE",
      strategy_name: "Price × OI × Volume State Machine",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Echo: {
    id: "agt-echo",
    name: "Echo",
    avatar: "🌐",
    specialization: "Global Macro & Breakout Strategist",
    max_principal: 200000,
    initial_capital: 200000,
    current_capital: 200000,
    allocated_margin: 0,
    available_capital: 200000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Analyzing international spot gold & macro currency flows...",
    current_hypothesis: "Evaluating US Dollar Index DXY divergence",
    active_strategy: "S15_MACRO_GOLD_DXY",
    active_strategy_name: "Macro Gold-USD Flow Divergence",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "LONG_TERM_SWING",
    target_net_pnl_increment: 50000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Echo",
      max_principal: 200000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 2.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 4,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "LONG_TERM_SWING",
      target_net_pnl_increment: 50000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Foxtrot: {
    id: "agt-foxtrot",
    name: "Foxtrot",
    avatar: "⚡",
    specialization: "Microstructure & Scalping Specialist",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Monitoring tick-by-tick order imbalance...",
    current_hypothesis: "Detecting aggressive taker liquidity blocks",
    active_strategy: "S09_VWAP_IMBALANCE",
    active_strategy_name: "Order Flow & VWAP Imbalance",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Foxtrot",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Golf: {
    id: "agt-golf",
    name: "Golf",
    avatar: "🌅",
    specialization: "Auction Market & Opening Gap Specialist",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Evaluating opening gap & initial balance...",
    current_hypothesis: "Testing session auction equilibrium range",
    active_strategy: "S03_GAP_FILL",
    active_strategy_name: "Opening Auction Gap Fill",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Golf",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Hotel: {
    id: "agt-hotel",
    name: "Hotel",
    avatar: "🧬",
    specialization: "ML Regime Shift & Trend Filter",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Classifying market regime state...",
    current_hypothesis: "HMM regime state transition probability",
    active_strategy: "S06_REGIME_FILTER",
    active_strategy_name: "Machine Learning Regime Shift Filter",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Hotel",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  India: {
    id: "agt-india",
    name: "India",
    avatar: "📐",
    specialization: "Multi-Timeframe Consolidation Breakout",
    max_principal: 100000,
    initial_capital: 100000,
    current_capital: 100000,
    allocated_margin: 0,
    available_capital: 100000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Analyzing 1m/5m/15m multi-timeframe consolidation...",
    current_hypothesis: "Awaiting synchronized compression expansion",
    active_strategy: "S08_MTF_CONSOL",
    active_strategy_name: "Multi-Timeframe Consolidation",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "TACTICAL_INTRADAY",
    target_net_pnl_increment: 25000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "India",
      max_principal: 100000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 1.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 2,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "TACTICAL_INTRADAY",
      target_net_pnl_increment: 25000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
  Juliet: {
    id: "agt-juliet",
    name: "Juliet",
    avatar: "🛡️",
    specialization: "Institutional Hedging & Counter-Trend",
    max_principal: 200000,
    initial_capital: 200000,
    current_capital: 200000,
    allocated_margin: 0,
    available_capital: 200000,
    pnl: 0,
    win_rate: 0,
    winning_tests: 0,
    total_tests: 0,
    history: [],
    current_activity: "Monitoring institutional flow exhaustion signals...",
    current_hypothesis: "Detecting liquidity absorption at key support/resistance",
    active_strategy: "S10_INST_FLOW",
    active_strategy_name: "Institutional Flow Reversal",
    active_strategy_status: "TESTING",
    active_market: "MCX_UPSTOX_LIVE",
    last_price: 75420.0,
    last_updated: "",
    learning_progress: 0,
    position: null,
    goal: "SUCCESS_MAX_INCREMENT",
    goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
    horizon: "LONG_TERM_SWING",
    target_net_pnl_increment: 50000,
    retest_winning_strategies: true,
    condition_gated_entry: true,
    strategy_retests: 0,
    strategy_net_pnl: 0,
    strategy_wins: 0,
    strategy_losses: 0,
    strategy_edge_status: "EXPLORING",
    net_pnl_increment: 0,
    goal_progress_pct: 0,
    guidelines: {
      name: "Juliet",
      max_principal: 200000,
      mode: "AUTO",
      strategy_id: "AUTO",
      strategy_name: "Auto-Selected Strategy",
      target_market: "AUTO",
      allowed_lot_size: 2.0,
      lots: 0,
      direction_bias: "BOTH",
      profit_target_pts: 0,
      stop_loss_pts: 0,
      max_risk_pct_per_trade: 2.0,
      max_lots: 4,
      is_active: true,
      goal: "SUCCESS_MAX_INCREMENT",
      goal_description: "Discover winning strategies, retest in right conditions, and maximize net P&L increment",
      horizon: "LONG_TERM_SWING",
      target_net_pnl_increment: 50000,
      retest_winning_strategies: true,
      condition_gated_entry: true,
    },
  },
};

const INITIAL_STATE: StateResponse = {
  active_session: {
    mode: "MCX_UPSTOX_LIVE",
    is_mcx_session: true,
    contract_type: "MCX_GOLDM",
    contract_name: "MCX Gold Mini 100g (Live Data)",
    currency_symbol: "₹",
    live_price: 75420.0,
    bid_price: 75418.0,
    ask_price: 75422.0,
    source: "Upstox Live WebSocket (MCX Mini)",
    session_desc: "MCX Live Regular Session Active (09:00 - 23:30 IST)",
    is_live: true,
    last_tick_time: "2026-09-25T08:00:00.000Z",
  },
  target_market: "AUTO",
  agents: INITIAL_AGENTS_CACHE,
};

export default function AgentsPlaygroundPage() {
  const [state, setState] = useState<StateResponse>(INITIAL_STATE);
  const [labStrategies, setLabStrategies] = useState<LabStrategy[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [settingMarket, setSettingMarket] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Master Tuning Studio State
  const [selectedAgentName, setSelectedAgentName] = useState<string>("Alpha");
  const [studioMode, setStudioMode] = useState<"AUTO" | "CUSTOM">("AUTO");
  const [studioPrincipal, setStudioPrincipal] = useState<number>(100000);
  const [studioAllowedLotSize, setStudioAllowedLotSize] = useState<number>(1.0);
  const [studioStrategyId, setStudioStrategyId] = useState<string>("AUTO");
  const [studioTargetMarket, setStudioTargetMarket] = useState<string>("AUTO");
  const [studioDirectionBias, setStudioDirectionBias] = useState<"BOTH" | "LONG_ONLY" | "SHORT_ONLY">("BOTH");
  const [studioProfitTarget, setStudioProfitTarget] = useState<number>(0);
  const [studioStopLoss, setStudioStopLoss] = useState<number>(0);
  const [studioMaxRiskPct, setStudioMaxRiskPct] = useState<number>(2.0);
  const [studioHorizon, setStudioHorizon] = useState<"TACTICAL_INTRADAY" | "LONG_TERM_SWING">("TACTICAL_INTRADAY");
  const [studioTargetNetPnL, setStudioTargetNetPnL] = useState<number>(25000);
  const [savingStudio, setSavingStudio] = useState(false);
  const [batchUpdating, setBatchUpdating] = useState(false);
  const [settingGoals, setSettingGoals] = useState(false);

  // Horizon Filter for Agent Grid
  const [horizonFilter, setHorizonFilter] = useState<"ALL" | "LONG_TERM_SWING" | "TACTICAL_INTRADAY">("ALL");

  // Inline tuning drawer toggle map for each agent card
  const [openCardTuner, setOpenCardTuner] = useState<Record<string, boolean>>({});
  // Inline card edit drafts
  const [cardDrafts, setCardDrafts] = useState<Record<string, Partial<AgentGuidelines>>>({});
  const [savingCardAgent, setSavingCardAgent] = useState<string | null>(null);

  // Direction filter for trade history display on cards
  const [cardHistoryFilter, _setCardHistoryFilter] = useState<Record<string, string>>({});
  const [expandedCardHistory, setExpandedCardHistory] = useState<Record<string, boolean>>({});

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const fetchState = async () => {
    try {
      const res = await fetch("/v1/agents/status");
      if (res.ok) {
        const data: StateResponse = await res.json();
        setState(data);
      }
    } catch (e) {
      console.error("Failed to fetch agents status:", e);
    }
  };

  const fetchStrategies = async () => {
    try {
      const res = await fetch("/v1/strategies/lab");
      if (res.ok) {
        const data = await res.json();
        if (data.strategies && Array.isArray(data.strategies)) {
          setLabStrategies(data.strategies);
        }
      }
    } catch (e) {
      console.error("Failed to fetch lab strategies:", e);
    }
  };

  useEffect(() => {
    setMounted(true);
    fetchState();
    fetchStrategies();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  // When selectedAgentName changes or state updates on initial load, populate studio values
  useEffect(() => {
    if (!state?.agents) return;
    const ag = state.agents[selectedAgentName];
    if (ag && !hasInitialized) {
      const g = ag.guidelines;
      setStudioMode(g?.mode ?? "AUTO");
      setStudioPrincipal(g?.max_principal ?? ag.max_principal);
      setStudioAllowedLotSize(g?.allowed_lot_size ?? (ag.max_principal >= 200000 ? 2.0 : 1.0));
      if (selectedAgentName === "Delta") {
        setStudioStrategyId("S17_OI_VOLUME_MACHINE");
      } else {
        setStudioStrategyId(g?.strategy_id ?? "AUTO");
      }
      setStudioTargetMarket(g?.target_market ?? "AUTO");
      setStudioDirectionBias(g?.direction_bias ?? "BOTH");
      setStudioProfitTarget(g?.profit_target_pts ?? 0);
      setStudioStopLoss(g?.stop_loss_pts ?? 0);
      setStudioMaxRiskPct(g?.max_risk_pct_per_trade ?? 2.0);
      setStudioHorizon(
        g?.horizon ??
          ag.horizon ??
          (selectedAgentName === "Echo" || selectedAgentName === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY"),
      );
      setStudioTargetNetPnL(
        g?.target_net_pnl_increment ??
          ag.target_net_pnl_increment ??
          (selectedAgentName === "Echo" || selectedAgentName === "Juliet" ? 50000 : 25000),
      );
      setHasInitialized(true);
    }
  }, [state, hasInitialized, selectedAgentName]);

  // Master Studio Agent Selection
  const handleSelectStudioAgent = (name: string) => {
    setSelectedAgentName(name);
    const ag = state?.agents?.[name];
    if (ag) {
      const g = ag.guidelines;
      setStudioMode(g?.mode ?? "AUTO");
      setStudioPrincipal(g?.max_principal ?? ag.max_principal);
      setStudioAllowedLotSize(g?.allowed_lot_size ?? (ag.max_principal >= 200000 ? 2.0 : 1.0));
      if (name === "Delta") {
        setStudioStrategyId("S17_OI_VOLUME_MACHINE");
      } else {
        setStudioStrategyId(g?.strategy_id ?? "AUTO");
      }
      setStudioTargetMarket(g?.target_market ?? "AUTO");
      setStudioDirectionBias(g?.direction_bias ?? "BOTH");
      setStudioProfitTarget(g?.profit_target_pts ?? 0);
      setStudioStopLoss(g?.stop_loss_pts ?? 0);
      setStudioMaxRiskPct(g?.max_risk_pct_per_trade ?? 2.0);
      setStudioHorizon(
        g?.horizon ?? ag.horizon ?? (name === "Echo" || name === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY"),
      );
      setStudioTargetNetPnL(
        g?.target_net_pnl_increment ??
          ag.target_net_pnl_increment ??
          (name === "Echo" || name === "Juliet" ? 50000 : 25000),
      );
    }
  };

  // Master Studio Apply Configuration
  const handleApplyStudio = async () => {
    try {
      setSavingStudio(true);
      const isDelta = selectedAgentName === "Delta";
      const stratId = isDelta ? "S17_OI_VOLUME_MACHINE" : studioStrategyId;
      const selectedStratObj = labStrategies.find((s) => s.id === stratId);
      const stratName = isDelta
        ? "Price × OI × Volume State Machine"
        : selectedStratObj
          ? selectedStratObj.name
          : stratId === "AUTO"
            ? "Auto-Selected Strategy"
            : stratId;

      const payload = {
        mode: studioMode,
        strategy_id: stratId,
        strategy_name: stratName,
        max_principal: Number(studioPrincipal),
        allowed_lot_size: Number(studioAllowedLotSize),
        lots: 0,
        target_market: studioTargetMarket,
        direction_bias: studioDirectionBias,
        profit_target_pts: Number(studioProfitTarget),
        stop_loss_pts: Number(studioStopLoss),
        max_risk_pct_per_trade: Number(studioMaxRiskPct),
        horizon: studioHorizon,
        target_net_pnl_increment: Number(studioTargetNetPnL),
        retest_winning_strategies: true,
        condition_gated_entry: true,
        goal: "SUCCESS_MAX_INCREMENT",
      };

      const res = await fetch(`/v1/agents/${selectedAgentName}/guidelines`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        showToast(
          `✅ Agent ${selectedAgentName} configured: Mode ${studioMode} · Principal ₹${Number(studioPrincipal).toLocaleString()} · Lot Ceiling: ${studioAllowedLotSize} Lot`,
        );
        fetchState();
      } else {
        const err = await res.json();
        alert(`Failed: ${err.detail || "Could not apply setup"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error applying configuration");
    } finally {
      setSavingStudio(false);
    }
  };

  // Reset Single Agent to AUTO
  const handleResetAgentToAuto = async (name: string) => {
    try {
      const res = await fetch(`/v1/agents/${name}/guidelines/reset`, { method: "POST" });
      if (res.ok) {
        showToast(`🔄 Reset Agent ${name} to default AUTO autonomous mode`);
        fetchState();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Batch Preset: Set all agents allowed lot ceiling
  const handleBatchLotCeiling = async (lotCeiling: number) => {
    try {
      setBatchUpdating(true);
      const res = await fetch("/v1/agents/guidelines/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowed_lot_size: lotCeiling }),
      });
      if (res.ok) {
        showToast(`⚡ All 10 Agents configured to Allowed Lot Ceiling: ${lotCeiling} Lot Max`);
        fetchState();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setBatchUpdating(false);
    }
  };

  // Batch Preset: Set all agents to AUTO
  const handleBatchResetToAuto = async () => {
    try {
      setBatchUpdating(true);
      const res = await fetch("/v1/agents/guidelines/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "AUTO" }),
      });
      if (res.ok) {
        showToast("🤖 All 10 Agents reset to Autonomous Engine (AUTO)");
        fetchState();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setBatchUpdating(false);
    }
  };

  // Set All 10 Agent Goals to Success & Max Net P&L Increment
  const handleSetAllGoalsToSuccess = async () => {
    try {
      setSettingGoals(true);
      const res = await fetch("/v1/agents/goals/set-success", { method: "POST" });
      if (res.ok) {
        showToast(
          "🎯 All 10 Agents configured to Unified Goal: Success & Max Net P&L Increment! (Echo & Juliet: Long-Term Swing, 8 Agents: Tactical Intraday)",
        );
        fetchState();
      } else {
        const err = await res.json();
        alert(`Failed: ${err.detail || "Could not set goals"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error setting goals to success");
    } finally {
      setSettingGoals(false);
    }
  };

  // Reset All Agents to 0 Numbers & Start Fresh
  const handleResetAllAgents = async () => {
    if (
      !confirm(
        "🔄 Reset ALL 10 Agents to 0 numbers?\n\nThis will immediately:\n• Set realized P&L to ₹0.00 across all agents\n• Set win rates to 0.0% and completed tests to 0\n• Close all active open positions and release margins\n• Reset strategy retest counters and edge statuses to candidate\n• Clear trade history & Upstox ledger\n\nAll agents will start completely fresh. Proceed?",
      )
    )
      return;
    try {
      setClearingHistory(true);
      const res = await fetch("/v1/agents/reset", { method: "POST" });
      if (res.ok) {
        showToast("✨ All 10 agents reset to 0 numbers! Started completely fresh.");
        await fetchState();
      } else {
        // Fallback to history reset if /reset is not recognized
        const fallback = await fetch("/v1/agents/history/reset", { method: "POST" });
        if (fallback.ok) {
          showToast("✨ All 10 agents reset to 0 numbers! Started completely fresh.");
          await fetchState();
        } else {
          showToast("❌ Failed to reset agents.");
        }
      }
    } catch (e) {
      console.error("Error resetting all agents:", e);
      showToast("❌ Error resetting agents.");
    } finally {
      setClearingHistory(false);
    }
  };

  // Reset Single Agent to 0 Numbers & Start Fresh
  const handleResetSingleAgent = async (agentName: string) => {
    if (
      !confirm(
        `🔄 Reset Agent ${agentName} to 0 numbers?\n\nThis will reset P&L to ₹0.00, win rate to 0%, completed tests to 0, close any open position, and clear its trade history to start fresh.`,
      )
    )
      return;
    try {
      setSavingCardAgent(agentName);
      const res = await fetch(`/v1/agents/${agentName}/reset`, { method: "POST" });
      if (res.ok) {
        showToast(`✨ Agent ${agentName} reset to 0 numbers and started fresh!`);
        await fetchState();
      } else {
        showToast(`❌ Failed to reset Agent ${agentName}`);
      }
    } catch (e) {
      console.error(`Error resetting Agent ${agentName}:`, e);
      showToast(`❌ Error resetting Agent ${agentName}`);
    } finally {
      setSavingCardAgent(null);
    }
  };

  // Alias for backward compatibility
  const _handleResetAllHistory = handleResetAllAgents;

  // Set Global Playground Market
  const handleSelectMarket = async (mkt: string) => {
    try {
      setSettingMarket(true);
      const res = await fetch("/v1/agents/market", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_market: mkt }),
      });
      if (res.ok) {
        showToast(`🎯 Playground Target Market set to: ${mkt}`);
        fetchState();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSettingMarket(false);
    }
  };

  // Inline Card Tuner Handlers
  const toggleCardTuner = (agentName: string) => {
    setOpenCardTuner((prev) => {
      const willOpen = !prev[agentName];
      if (willOpen && state?.agents?.[agentName]) {
        const ag = state.agents[agentName];
        const g = ag.guidelines;
        setCardDrafts((drafts) => ({
          ...drafts,
          [agentName]: {
            mode: g?.mode ?? "AUTO",
            max_principal: g?.max_principal ?? ag.max_principal,
            allowed_lot_size: g?.allowed_lot_size ?? (ag.max_principal >= 200000 ? 2.0 : 1.0),
            strategy_id: agentName === "Delta" ? "S17_OI_VOLUME_MACHINE" : (g?.strategy_id ?? "AUTO"),
            target_market: g?.target_market ?? "AUTO",
            direction_bias: g?.direction_bias ?? "BOTH",
            profit_target_pts: g?.profit_target_pts ?? 0,
            stop_loss_pts: g?.stop_loss_pts ?? 0,
            max_risk_pct_per_trade: g?.max_risk_pct_per_trade ?? 2.0,
            horizon:
              g?.horizon ??
              ag.horizon ??
              (agentName === "Echo" || agentName === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY"),
            target_net_pnl_increment:
              g?.target_net_pnl_increment ??
              ag.target_net_pnl_increment ??
              (agentName === "Echo" || agentName === "Juliet" ? 50000 : 25000),
          },
        }));
      }
      return { ...prev, [agentName]: willOpen };
    });
  };

  const handleSaveCardDraft = async (agentName: string) => {
    const draft = cardDrafts[agentName];
    if (!draft) return;
    try {
      setSavingCardAgent(agentName);
      const isDelta = agentName === "Delta";
      const stratId = isDelta ? "S17_OI_VOLUME_MACHINE" : draft.strategy_id || "AUTO";
      const selectedStratObj = labStrategies.find((s) => s.id === stratId);
      const stratName = isDelta
        ? "Price × OI × Volume State Machine"
        : selectedStratObj
          ? selectedStratObj.name
          : stratId === "AUTO"
            ? "Auto-Selected Strategy"
            : stratId;

      const payload = {
        mode: draft.mode || "AUTO",
        strategy_id: stratId,
        strategy_name: stratName,
        max_principal: Number(draft.max_principal),
        allowed_lot_size: Number(draft.allowed_lot_size),
        lots: 0,
        target_market: draft.target_market || "AUTO",
        direction_bias: draft.direction_bias || "BOTH",
        profit_target_pts: Number(draft.profit_target_pts || 0),
        stop_loss_pts: Number(draft.stop_loss_pts || 0),
        max_risk_pct_per_trade: Number(draft.max_risk_pct_per_trade || 2.0),
        horizon:
          draft.horizon || (agentName === "Echo" || agentName === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY"),
        target_net_pnl_increment: Number(draft.target_net_pnl_increment || 25000),
        retest_winning_strategies: true,
        condition_gated_entry: true,
        goal: "SUCCESS_MAX_INCREMENT",
      };

      const res = await fetch(`/v1/agents/${agentName}/guidelines`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        showToast(`✅ Agent ${agentName} manual configuration saved and active!`);
        fetchState();
      }
    } catch (e) {
      console.error(e);
      alert(`Error saving configuration for Agent ${agentName}`);
    } finally {
      setSavingCardAgent(null);
    }
  };

  const session = state?.active_session;
  const currentTargetMarket = state?.target_market || "AUTO";
  const ledgerSummary = state?.upstox_ledger_summary;
  const agentsMap = state?.agents || INITIAL_AGENTS_CACHE;
  const agentList = useMemo(() => {
    return AGENT_ORDER.map((name) => agentsMap[name] || INITIAL_AGENTS_CACHE[name]).filter(Boolean);
  }, [agentsMap]);

  const filteredAgentList = useMemo(() => {
    if (horizonFilter === "ALL") return agentList;
    return agentList.filter((ag) => {
      const h = ag?.horizon || (ag?.name === "Echo" || ag?.name === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY");
      return h === horizonFilter;
    });
  }, [agentList, horizonFilter]);

  // Aggregate Metrics
  const totalPrincipal = useMemo(() => {
    return agentList.reduce((sum, a) => sum + (a?.max_principal || 0), 0);
  }, [agentList]);

  const totalPnL = useMemo(() => {
    return agentList.reduce((sum, a) => sum + (a?.pnl || 0), 0);
  }, [agentList]);

  const totalTradesCount = useMemo(() => {
    return agentList.reduce((sum, a) => sum + (a?.total_tests || 0), 0);
  }, [agentList]);

  if (!mounted) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 22, minHeight: "100vh" }}>
        <div
          style={{
            background: "linear-gradient(135deg, #090e1a 0%, #0f172a 40%, #1e1b4b 100%)",
            borderRadius: 22,
            padding: "26px 30px",
            color: "#ffffff",
            boxShadow: "0 12px 36px rgba(15, 23, 42, 0.45)",
            border: "2px solid #3b82f6",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 34 }}>🤖</span>
            <div>
              <h2 style={{ margin: 0, fontSize: 24, fontWeight: 900 }}>Autonomous Agents Playground</h2>
              <p style={{ margin: "4px 0 0 0", color: "#94a3b8", fontSize: 13 }}>
                Live multi-agent execution with manual configuration tuning, dynamic principal bounds, and allowed lot
                ceilings.
              </p>
            </div>
          </div>
          <div
            style={{ display: "flex", alignItems: "center", gap: 10, color: "#38bdf8", fontWeight: 700, fontSize: 14 }}
          >
            <span
              style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", background: "#38bdf8" }}
            />
            Ready · Initializing High-Speed Agents Engine...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22, minHeight: "100vh" }}>
      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: "fixed",
            top: 24,
            right: 24,
            background: "#0f172a",
            color: "#ffffff",
            padding: "14px 22px",
            borderRadius: 14,
            boxShadow: "0 12px 28px rgba(0,0,0,0.35)",
            zIndex: 9999,
            fontWeight: 800,
            fontSize: 14,
            border: "1px solid #38bdf8",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span>⚡</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 1. SOPHISTICATED COMMAND HEADER & TELEMETRY RIBBON                       */}
      {/* ========================================================================= */}
      <div
        style={{
          background: "linear-gradient(135deg, #090e1a 0%, #0f172a 40%, #1e1b4b 100%)",
          borderRadius: 22,
          padding: "26px 30px",
          color: "#ffffff",
          boxShadow: "0 12px 36px rgba(15, 23, 42, 0.45)",
          border: "2px solid #3b82f6",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span
              style={{
                fontSize: 34,
                background: "linear-gradient(135deg, #1e293b 0%, #334155 100%)",
                padding: "10px 14px",
                borderRadius: 18,
                border: "1px solid #60a5fa",
                boxShadow: "0 4px 14px rgba(59, 130, 246, 0.25)",
              }}
            >
              🤖
            </span>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <h2 style={{ margin: 0, fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em" }}>
                  Autonomous Agents Playground
                </h2>
                <span
                  style={{
                    background: "rgba(59, 130, 246, 0.2)",
                    color: "#93c5fd",
                    border: "1px solid rgba(59, 130, 246, 0.5)",
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 900,
                    textTransform: "uppercase",
                  }}
                >
                  10 Autonomous Agents · ₹1.20 Crore Pool
                </span>
                <span
                  style={{
                    background: "rgba(245, 158, 11, 0.2)",
                    color: "#fde68a",
                    border: "1px solid rgba(245, 158, 11, 0.5)",
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 900,
                  }}
                >
                  👑 Delta Pinned: S17 Price × OI × Volume
                </span>
              </div>
              <p style={{ margin: "4px 0 0 0", color: "#94a3b8", fontSize: 13 }}>
                Live multi-agent execution with manual configuration tuning, dynamic principal bounds, and allowed lot
                ceilings.
              </p>
            </div>
          </div>

          {/* Action Links */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Link
              href="/upstox-ledger"
              style={{
                background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                color: "#ffffff",
                padding: "10px 18px",
                borderRadius: 12,
                fontSize: 13,
                fontWeight: 900,
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                border: "1px solid #34d399",
                boxShadow: "0 4px 14px rgba(5, 150, 105, 0.3)",
              }}
            >
              <span>⚡ Dedicated Upstox Trade Ledger</span>
              <span style={{ background: "#065f46", padding: "2px 6px", borderRadius: 999, fontSize: 11 }}>
                {ledgerSummary?.total_trades || 0} / 1,000
              </span>
            </Link>

            <button
              onClick={handleSetAllGoalsToSuccess}
              disabled={settingGoals}
              style={{
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                border: "1px solid #34d399",
                color: "#ffffff",
                padding: "10px 18px",
                borderRadius: 12,
                fontSize: 13,
                fontWeight: 900,
                cursor: settingGoals ? "not-allowed" : "pointer",
                boxShadow: "0 4px 14px rgba(16, 185, 129, 0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
              title="Set all 10 agents to discover and retest winning strategies in right conditions for max Net P&L increment"
            >
              <span>🎯</span>
              <span>{settingGoals ? "Applying Success Directive..." : "Set All Goals to Success"}</span>
            </button>

            <button
              id="btn-reset-all-agents"
              onClick={handleResetAllAgents}
              disabled={clearingHistory}
              style={{
                background: "linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)",
                border: "1px solid #f87171",
                color: "#ffffff",
                padding: "10px 18px",
                borderRadius: 12,
                fontSize: 13,
                fontWeight: 900,
                cursor: clearingHistory ? "not-allowed" : "pointer",
                boxShadow: "0 4px 16px rgba(239, 68, 68, 0.4)",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                transition: "all 0.15s ease",
              }}
              title="Reset all 10 agents to 0 numbers (₹0 P&L, 0 trades, 0% win rate, 0 positions) and start completely fresh"
            >
              <span
                style={{
                  fontSize: 15,
                  display: "inline-block",
                  animation: clearingHistory ? "spin 1s linear infinite" : "none",
                }}
              >
                🔄
              </span>
              <span>{clearingHistory ? "Resetting to 0 Numbers..." : "Reset All Agents to 0"}</span>
              <span
                style={{
                  background: "rgba(0, 0, 0, 0.25)",
                  border: "1px solid rgba(255, 255, 255, 0.3)",
                  padding: "2px 8px",
                  borderRadius: 999,
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: "0.02em",
                }}
              >
                Fresh Start
              </span>
            </button>
          </div>
        </div>

        {/* Live Market Session Banner */}
        {session && (
          <div
            style={{
              background: "rgba(15, 23, 42, 0.8)",
              borderRadius: 14,
              padding: "12px 18px",
              border: "1px solid #1e3a8a",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "#22c55e",
                  boxShadow: "0 0 10px #22c55e",
                }}
              />
              <span style={{ fontSize: 13, fontWeight: 800, color: "#e2e8f0" }}>
                {session.contract_name || session.market_name || "MCX Gold Mini"} ({session.mode})
              </span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>·</span>
              <span style={{ fontSize: 15, fontWeight: 900, fontFamily: "monospace", color: "#38bdf8" }}>
                {session.currency_symbol || "₹"}
                {(session.live_price || 75420.0).toLocaleString("en-IN", {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 2,
                })}
              </span>
              <span style={{ fontSize: 12, color: "#64748b" }}>
                (Bid: ₹{session.bid_price != null ? session.bid_price.toFixed(1) : "--"} / Ask: ₹
                {session.ask_price != null ? session.ask_price.toFixed(1) : "--"})
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#a5b4fc" }}>
              <span>📡 Feed: {session.source}</span>
              <span>·</span>
              <span>
                🕒{" "}
                {mounted && session.last_tick_time ? new Date(session.last_tick_time).toLocaleTimeString() : "--:--:--"}{" "}
                IST
              </span>
            </div>
          </div>
        )}

        {/* Unified Goal Success Banner */}
        <div
          style={{
            background:
              "linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(59, 130, 246, 0.15) 50%, rgba(139, 92, 246, 0.15) 100%)",
            borderRadius: 16,
            padding: "16px 20px",
            border: "2px solid #10b981",
            boxShadow: "0 4px 20px rgba(16, 185, 129, 0.2)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 26 }}>🎯</span>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 15, fontWeight: 900, color: "#ffffff", letterSpacing: "0.01em" }}>
                    UNIFIED OBJECTIVE: DISCOVER WINNING STRATEGIES & MAXIMIZE NET P&L INCREMENT
                  </span>
                  <span
                    style={{
                      background: "#059669",
                      color: "#ecfdf5",
                      padding: "2px 8px",
                      borderRadius: 999,
                      fontSize: 10,
                      fontWeight: 900,
                    }}
                  >
                    ACTIVE ACROSS ALL 10 AGENTS
                  </span>
                </div>
                <p style={{ margin: "3px 0 0 0", color: "#cbd5e1", fontSize: 12 }}>
                  Every agent scans Strategy Lab for candidates, condition-gates entries to right market regimes, trails
                  stops to breakeven after +40% target progress, and repeatedly retests confirmed winning edges for
                  maximum incremental Net P&L.
                </p>
              </div>
            </div>
            <button
              onClick={handleSetAllGoalsToSuccess}
              disabled={settingGoals}
              style={{
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                border: "1px solid #34d399",
                color: "#ffffff",
                padding: "8px 16px",
                borderRadius: 10,
                fontSize: 12,
                fontWeight: 900,
                cursor: settingGoals ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
              }}
            >
              <span>⚡</span>
              <span>{settingGoals ? "Applying..." : "Sync All Goals to Success"}</span>
            </button>
          </div>

          {/* Horizon Split Badges */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
            <div
              style={{
                background: "rgba(15, 23, 42, 0.7)",
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #a855f7",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ fontSize: 20 }}>⏳</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 900, color: "#d8b4fe" }}>
                  LONG-TERM SWING HORIZON (2 AGENTS: ECHO & JULIET)
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>
                  Target Net Increment: ₹50,000 · 60 Hold Cycles · Multi-Cycle Macro Trend & Institutional Hedging
                </div>
              </div>
            </div>
            <div
              style={{
                background: "rgba(15, 23, 42, 0.7)",
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid #38bdf8",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ fontSize: 20 }}>⚡</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 900, color: "#7dd3fc" }}>
                  TACTICAL INTRADAY HORIZON (8 AGENTS: ALPHA - HOTEL)
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8" }}>
                  Target Net Increment: ₹25,000 · High-Velocity Micro Breakout & VWAP Mean Reversion
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Aggregate KPI Badges */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          <div
            style={{
              background: "rgba(30, 41, 59, 0.6)",
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid #334155",
            }}
          >
            <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
              Total Pool Capital
            </div>
            <div style={{ fontSize: 20, fontWeight: 900, color: "#ffffff", marginTop: 2, fontFamily: "monospace" }}>
              ₹{((totalPrincipal || 1200000) / 100000).toFixed(1)} Lac
            </div>
            <div style={{ fontSize: 10, color: "#38bdf8" }}>8 @ ₹1L · 2 @ ₹2L</div>
          </div>

          <div
            style={{
              background: "rgba(30, 41, 59, 0.6)",
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid #334155",
            }}
          >
            <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
              Collective Realized P&L
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 900,
                color: totalPnL >= 0 ? "#4ade80" : "#f87171",
                marginTop: 2,
                fontFamily: "monospace",
              }}
            >
              {totalPnL >= 0 ? "+" : ""}₹
              {(totalPnL || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Across all 10 agents</div>
          </div>

          <div
            style={{
              background: "rgba(30, 41, 59, 0.6)",
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid #334155",
            }}
          >
            <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
              Completed Trades
            </div>
            <div style={{ fontSize: 20, fontWeight: 900, color: "#38bdf8", marginTop: 2, fontFamily: "monospace" }}>
              {totalTradesCount} Trades
            </div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Fresh session data</div>
          </div>

          <div
            style={{
              background: "rgba(30, 41, 59, 0.6)",
              padding: "12px 16px",
              borderRadius: 14,
              border: "1px solid #334155",
            }}
          >
            <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase" }}>
              Upstox Ledger Stats
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 900,
                color: (ledgerSummary?.net_pnl || 0) >= 0 ? "#4ade80" : "#f87171",
                marginTop: 2,
                fontFamily: "monospace",
              }}
            >
              {(ledgerSummary?.net_pnl || 0) >= 0 ? "+" : ""}₹
              {(ledgerSummary?.net_pnl || 0).toLocaleString("en-IN", {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              })}
            </div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>{ledgerSummary?.total_trades || 0} Trades Traded</div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. GLOBAL TARGET MARKET DIRECTIVE BAR                                    */}
      {/* ========================================================================= */}
      <div
        style={{
          background: "#ffffff",
          borderRadius: 16,
          padding: "16px 22px",
          border: "1px solid #e2e8f0",
          boxShadow: "0 2px 6px rgba(0,0,0,0.03)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>🌐</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 900, color: "#0f172a" }}>Target Market Execution Target</div>
            <div style={{ fontSize: 11, color: "#64748b" }}>
              Select which contract the agents trade during live market hours.
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            { id: "AUTO", label: "⚡ AUTO (MCX Day / Global Night)", desc: "Autonomous session detection" },
            { id: "MCX_GOLDM", label: "🪙 MCX Gold Mini (100g)", desc: "100g contract, 10x multiplier" },
            { id: "MCX_GOLD", label: "🥇 MCX Gold (1kg Big)", desc: "1,000g standard contract" },
            { id: "GLOBAL_XAU", label: "🌍 Global Spot (XAU/USD)", desc: "24/7 continuous dollar feed" },
          ].map((mkt) => {
            const isActive = currentTargetMarket === mkt.id;
            return (
              <button
                key={mkt.id}
                onClick={() => handleSelectMarket(mkt.id)}
                disabled={settingMarket}
                style={{
                  background: isActive ? "#2563eb" : "#f8fafc",
                  color: isActive ? "#ffffff" : "#334155",
                  border: isActive ? "2px solid #1d4ed8" : "1px solid #cbd5e1",
                  padding: "8px 14px",
                  borderRadius: 10,
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  boxShadow: isActive ? "0 4px 10px rgba(37,99,235,0.2)" : "none",
                }}
              >
                {mkt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. DEDICATED AGENT CONFIGURATION SETUP & MANUAL TUNING STUDIO            */}
      {/* ========================================================================= */}
      <div
        style={{
          background: "linear-gradient(135deg, #0b1329 0%, #172554 50%, #0f172a 100%)",
          borderRadius: 20,
          padding: "24px 28px",
          color: "#ffffff",
          boxShadow: "0 10px 30px rgba(15, 23, 42, 0.4)",
          border: "2px solid #2563eb",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {/* Studio Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: 14,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                fontSize: 28,
                background: "#1e293b",
                padding: "8px 12px",
                borderRadius: 14,
                border: "1px solid #3b82f6",
              }}
            >
              🎛️
            </span>
            <div>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 900, color: "#ffffff", letterSpacing: "-0.01em" }}>
                Agent Configuration Studio & Manual Tuning Console
              </h2>
              <div style={{ fontSize: 13, color: "#93c5fd", marginTop: 2 }}>
                Tune individual agents manually or deploy custom strategies, principals, and allowed lot ceilings.
              </div>
            </div>
          </div>

          {/* Quick Batch Presets */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, fontWeight: 800, color: "#93c5fd", marginRight: 4 }}>BATCH PRESETS:</span>
            <button
              onClick={() => handleBatchLotCeiling(0.1)}
              disabled={batchUpdating}
              style={{
                background: "#1e293b",
                border: "1px solid #3b82f6",
                color: "#60a5fa",
                padding: "5px 10px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              All 0.1 Lot
            </button>
            <button
              onClick={() => handleBatchLotCeiling(0.2)}
              disabled={batchUpdating}
              style={{
                background: "#1e293b",
                border: "1px solid #3b82f6",
                color: "#60a5fa",
                padding: "5px 10px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              All 0.2 Lot
            </button>
            <button
              onClick={() => handleBatchLotCeiling(1.0)}
              disabled={batchUpdating}
              style={{
                background: "#1e293b",
                border: "1px solid #3b82f6",
                color: "#60a5fa",
                padding: "5px 10px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              All 1.0 Lot
            </button>
            <button
              onClick={handleBatchResetToAuto}
              disabled={batchUpdating}
              style={{
                background: "#15803d",
                border: "1px solid #4ade80",
                color: "#ffffff",
                padding: "5px 10px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              All to AUTO 🤖
            </button>
            <button
              onClick={handleResetAllAgents}
              disabled={clearingHistory}
              style={{
                background: "#7f1d1d",
                border: "1px solid #ef4444",
                color: "#fecaca",
                padding: "5px 11px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 800,
                cursor: clearingHistory ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
              title="Reset all 10 agents to 0 numbers and start fresh"
            >
              <span>🔄</span>
              <span>{clearingHistory ? "Resetting..." : "Reset All to 0"}</span>
            </button>
          </div>
        </div>

        {/* 10 Agent Selector Carousel Pills */}
        <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 6 }}>
          {AGENT_ORDER.map((name) => {
            const isSelected = selectedAgentName === name;
            const ag = agentsMap[name] || INITIAL_AGENTS_CACHE[name];
            const isCustom = ag?.guidelines?.mode === "CUSTOM";
            const lotCeiling =
              ag?.guidelines?.allowed_lot_size ?? (ag?.max_principal && ag.max_principal >= 200000 ? 2.0 : 1.0);
            return (
              <button
                key={name}
                type="button"
                onClick={() => handleSelectStudioAgent(name)}
                style={{
                  background: isSelected
                    ? "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)"
                    : "rgba(15, 23, 42, 0.7)",
                  border: isSelected ? "2px solid #60a5fa" : isCustom ? "2px solid #a855f7" : "1px solid #334155",
                  borderRadius: 12,
                  padding: "8px 12px",
                  color: "#ffffff",
                  cursor: "pointer",
                  textAlign: "left",
                  minWidth: 120,
                  boxShadow: isSelected ? "0 4px 14px rgba(37,99,235,0.4)" : "none",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 4 }}>
                  <span style={{ fontWeight: 900, fontSize: 13 }}>Agent {name}</span>
                  {name === "Delta" && <span>👑</span>}
                </div>
                <div style={{ fontSize: 10, color: isSelected ? "#e0f2fe" : "#94a3b8", marginTop: 2 }}>
                  {isCustom ? "🎯 MANUAL" : "🤖 AUTO"} · {lotCeiling}L Max
                </div>
              </button>
            );
          })}
        </div>

        {/* Studio Tuning Input Deck */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.7)",
            padding: "20px",
            borderRadius: 16,
            border: "1px solid #1e3a8a",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          {/* 1. Mode Selector */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              1. Execution Directive Mode
            </label>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => setStudioMode("AUTO")}
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: "pointer",
                  background: studioMode === "AUTO" ? "#15803d" : "#1e293b",
                  color: studioMode === "AUTO" ? "#ffffff" : "#94a3b8",
                  border: studioMode === "AUTO" ? "2px solid #86efac" : "1px solid #334155",
                }}
              >
                🤖 AUTO
              </button>
              <button
                type="button"
                onClick={() => setStudioMode("CUSTOM")}
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: "pointer",
                  background: studioMode === "CUSTOM" ? "#7e22ce" : "#1e293b",
                  color: studioMode === "CUSTOM" ? "#ffffff" : "#94a3b8",
                  border: studioMode === "CUSTOM" ? "2px solid #d8b4fe" : "1px solid #334155",
                }}
              >
                🎯 MANUAL
              </button>
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>
              {studioMode === "AUTO" ? "Autonomous engine selection" : "Strict manual parameters applied"}
            </div>
          </div>

          {/* 2. Allowed Lot Size Ceiling */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              2. Allowed Lot Size Ceiling (Max Limit)
            </label>
            <div style={{ display: "flex", gap: 4 }}>
              {[0.1, 0.2, 0.5, 1.0, 2.0].map((lotVal) => (
                <button
                  key={lotVal}
                  type="button"
                  onClick={() => setStudioAllowedLotSize(lotVal)}
                  style={{
                    flex: 1,
                    background: studioAllowedLotSize === lotVal ? "#0284c7" : "#1e293b",
                    color: studioAllowedLotSize === lotVal ? "#ffffff" : "#94a3b8",
                    border: `1px solid ${studioAllowedLotSize === lotVal ? "#38bdf8" : "#334155"}`,
                    borderRadius: 6,
                    padding: "4px 2px",
                    fontSize: 11,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  {lotVal}L
                </button>
              ))}
            </div>
            <input
              type="number"
              step="0.05"
              min="0.05"
              max="10.0"
              value={studioAllowedLotSize}
              onChange={(e) => setStudioAllowedLotSize(parseFloat(e.target.value) || 0.1)}
              style={{
                background: "#0f172a",
                color: "#38bdf8",
                border: "2px solid #3b82f6",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 14,
                fontWeight: 900,
                fontFamily: "monospace",
                outline: "none",
              }}
            />
            <div style={{ fontSize: 10, color: "#94a3b8" }}>
              Can take smaller sub-lots, but never exceeds this ceiling.
            </div>
          </div>

          {/* 3. Typeable Principal INR */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              3. Max Principal Allocation (₹ INR)
            </label>
            <div style={{ display: "flex", gap: 4 }}>
              {[
                { label: "50K", val: 50000 },
                { label: "1L", val: 100000 },
                { label: "1.5L", val: 150000 },
                { label: "2L", val: 200000 },
              ].map((p) => (
                <button
                  key={p.val}
                  type="button"
                  onClick={() => setStudioPrincipal(p.val)}
                  style={{
                    flex: 1,
                    background: studioPrincipal === p.val ? "#15803d" : "#1e293b",
                    color: studioPrincipal === p.val ? "#ffffff" : "#94a3b8",
                    border: `1px solid ${studioPrincipal === p.val ? "#86efac" : "#334155"}`,
                    borderRadius: 6,
                    padding: "4px 2px",
                    fontSize: 11,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  ₹{p.label}
                </button>
              ))}
            </div>
            <input
              type="number"
              step="5000"
              min="10000"
              value={studioPrincipal}
              onChange={(e) => setStudioPrincipal(parseFloat(e.target.value) || 100000)}
              style={{
                background: "#0f172a",
                color: "#22c55e",
                border: "2px solid #3b82f6",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 14,
                fontWeight: 900,
                fontFamily: "monospace",
                outline: "none",
              }}
            />
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Direct custom principal in INR</div>
          </div>

          {/* 4. Strategy Setup */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              4. Strategy Setup for Testing
            </label>
            {selectedAgentName === "Delta" ? (
              <div
                style={{
                  background: "#0f172a",
                  border: "2px solid #f59e0b",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 12,
                  fontWeight: 900,
                  color: "#fbbf24",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span>👑 S17: Price × OI × Volume</span>
                <span
                  style={{ fontSize: 9, background: "#78350f", color: "#fef3c7", padding: "1px 5px", borderRadius: 4 }}
                >
                  #1 RANKED
                </span>
              </div>
            ) : (
              <select
                value={studioStrategyId}
                onChange={(e) => setStudioStrategyId(e.target.value)}
                style={{
                  background: "#0f172a",
                  color: "#ffffff",
                  border: "2px solid #3b82f6",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 12,
                  fontWeight: 800,
                  outline: "none",
                }}
              >
                <option value="AUTO">⚡ Auto-Select (Optimal Lab Leaderboard)</option>
                <option value="S17_OI_VOLUME_MACHINE">👑 #1: Price × OI × Volume State Machine</option>
                <option value="S01_ORB_NR7">S01: Opening Range Breakout (NR7)</option>
                <option value="S02_VWAP_MEAN_REVERSION">S02: VWAP Dynamic Bands Mean Reversion</option>
                <option value="S03_GAP_FILL">S03: Opening Auction Gap Fill</option>
                <option value="S04_VOL_TARGET">S04: Dynamic Volatility Targeting</option>
                <option value="S05_MEAN_REV">S05: Statistical Mean Reversion AI</option>
                <option value="S06_REGIME_FILTER">S06: Machine Learning Regime Shift Filter</option>
                <option value="S08_MTF_CONSOL">S08: Multi-Timeframe Consolidation</option>
                <option value="S09_VWAP_IMBALANCE">S09: Order Flow & VWAP Imbalance</option>
                <option value="S10_INST_FLOW">S10: Institutional Flow Reversal</option>
                <option value="S15_MACRO_GOLD_DXY">S15: Macro Gold-USD Flow Divergence</option>
                <option value="S34_REGIME_ROUTER">S34: Regime Adaptive Router</option>
                {labStrategies
                  .filter(
                    (s) =>
                      ![
                        "AUTO",
                        "S17_OI_VOLUME_MACHINE",
                        "S01_ORB_NR7",
                        "S02_VWAP_MEAN_REVERSION",
                        "S03_GAP_FILL",
                        "S04_VOL_TARGET",
                        "S05_MEAN_REV",
                        "S06_REGIME_FILTER",
                        "S08_MTF_CONSOL",
                        "S09_VWAP_IMBALANCE",
                        "S10_INST_FLOW",
                        "S15_MACRO_GOLD_DXY",
                        "S34_REGIME_ROUTER",
                      ].includes(s.id),
                  )
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.id}: {s.name}
                    </option>
                  ))}
              </select>
            )}
            <div style={{ fontSize: 10, color: selectedAgentName === "Delta" ? "#fbbf24" : "#94a3b8" }}>
              {selectedAgentName === "Delta"
                ? "🔒 Pinned to #1 Price × OI × Volume"
                : "Fully customizable strategy directive"}
            </div>
          </div>

          {/* 5. Direction Bias */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              5. Direction Bias
            </label>
            <select
              value={studioDirectionBias}
              onChange={(e) => setStudioDirectionBias(e.target.value as any)}
              style={{
                background: "#0f172a",
                color: "#ffffff",
                border: "2px solid #3b82f6",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 12,
                fontWeight: 800,
                outline: "none",
              }}
            >
              <option value="BOTH">🔄 BOTH (Long & Short)</option>
              <option value="LONG_ONLY">📈 LONG ONLY (Bullish)</option>
              <option value="SHORT_ONLY">📉 SHORT ONLY (Bearish)</option>
            </select>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Filter long/short trades</div>
          </div>

          {/* 6. Horizon Duration Strategy */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              6. Horizon Duration Strategy
            </label>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => setStudioHorizon("TACTICAL_INTRADAY")}
                style={{
                  flex: 1,
                  padding: "8px 8px",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 800,
                  cursor: "pointer",
                  background: studioHorizon === "TACTICAL_INTRADAY" ? "#0284c7" : "#1e293b",
                  color: studioHorizon === "TACTICAL_INTRADAY" ? "#ffffff" : "#94a3b8",
                  border: studioHorizon === "TACTICAL_INTRADAY" ? "2px solid #38bdf8" : "1px solid #334155",
                }}
              >
                ⚡ Tactical
              </button>
              <button
                type="button"
                onClick={() => setStudioHorizon("LONG_TERM_SWING")}
                style={{
                  flex: 1,
                  padding: "8px 8px",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 800,
                  cursor: "pointer",
                  background: studioHorizon === "LONG_TERM_SWING" ? "#7e22ce" : "#1e293b",
                  color: studioHorizon === "LONG_TERM_SWING" ? "#ffffff" : "#94a3b8",
                  border: studioHorizon === "LONG_TERM_SWING" ? "2px solid #d8b4fe" : "1px solid #334155",
                }}
              >
                ⏳ Swing
              </button>
            </div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>
              {studioHorizon === "LONG_TERM_SWING"
                ? "Multi-cycle trend (60 hold cycles)"
                : "Fast intraday velocity (15 cycles)"}
            </div>
          </div>

          {/* 7. Target Net P&L Increment */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 11, color: "#93c5fd", fontWeight: 800, textTransform: "uppercase" }}>
              7. Target Net P&L Increment (₹)
            </label>
            <div style={{ display: "flex", gap: 4 }}>
              {[10000, 25000, 50000, 100000].map((inc) => (
                <button
                  key={inc}
                  type="button"
                  onClick={() => setStudioTargetNetPnL(inc)}
                  style={{
                    flex: 1,
                    background: studioTargetNetPnL === inc ? "#15803d" : "#1e293b",
                    color: studioTargetNetPnL === inc ? "#ffffff" : "#94a3b8",
                    border: `1px solid ${studioTargetNetPnL === inc ? "#86efac" : "#334155"}`,
                    borderRadius: 6,
                    padding: "4px 2px",
                    fontSize: 11,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  ₹{inc >= 100000 ? "1L" : `${inc / 1000}k`}
                </button>
              ))}
            </div>
            <input
              type="number"
              step="5000"
              min="5000"
              value={studioTargetNetPnL}
              onChange={(e) => setStudioTargetNetPnL(parseFloat(e.target.value) || 25000)}
              style={{
                background: "#0f172a",
                color: "#4ade80",
                border: "2px solid #3b82f6",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 14,
                fontWeight: 900,
                fontFamily: "monospace",
                outline: "none",
              }}
            />
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Target net growth from winning strategy retests</div>
          </div>
        </div>

        {/* Studio Action Buttons */}
        <div
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}
        >
          <div style={{ fontSize: 12, color: "#93c5fd" }}>
            Active Tuning Target: <b>Agent {selectedAgentName}</b> · Principal:{" "}
            <b>₹{Number(studioPrincipal).toLocaleString()}</b> · Lot Ceiling: <b>{studioAllowedLotSize} Lot Max</b> ·
            Horizon: <b>{studioHorizon === "LONG_TERM_SWING" ? "⏳ Long-Term Swing" : "⚡ Tactical Intraday"}</b> ·
            Target Increment: <b>₹{Number(studioTargetNetPnL).toLocaleString()}</b>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => handleResetAgentToAuto(selectedAgentName)}
              disabled={savingStudio}
              style={{
                background: "#1e293b",
                border: "1px solid #475569",
                color: "#cbd5e1",
                padding: "9px 16px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              🔄 Reset Agent to AUTO
            </button>
            <button
              type="button"
              onClick={() => handleResetSingleAgent(selectedAgentName)}
              disabled={savingStudio || clearingHistory}
              style={{
                background: "#450a0a",
                border: "1px solid #b91c1c",
                color: "#fca5a5",
                padding: "9px 16px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
              title={`Reset Agent ${selectedAgentName} numbers to 0 and start fresh`}
            >
              <span>🔄</span>
              <span>Reset {selectedAgentName} to 0</span>
            </button>
            <button
              type="button"
              onClick={handleApplyStudio}
              disabled={savingStudio}
              style={{
                background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                border: "1px solid #60a5fa",
                color: "#ffffff",
                padding: "9px 20px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 900,
                cursor: savingStudio ? "not-allowed" : "pointer",
                boxShadow: "0 4px 14px rgba(37, 99, 235, 0.4)",
              }}
            >
              {savingStudio ? "Deploying..." : `🚀 Save & Deploy to Agent ${selectedAgentName}`}
            </button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. THE 10 AGENT CARDS GRID WITH IN-CARD MANUAL TUNING DRAWERS            */}
      {/* ========================================================================= */}
      {/* Horizon Filter Tabs */}
      <div
        style={{
          background: "#ffffff",
          borderRadius: 14,
          padding: "12px 20px",
          border: "1px solid #e2e8f0",
          boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16 }}>⏱️</span>
          <span style={{ fontSize: 13, fontWeight: 900, color: "#0f172a" }}>Filter Horizon:</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[
              { id: "ALL", label: `All 10 Agents` },
              { id: "LONG_TERM_SWING", label: `⏳ Long-Term Swing (2: Echo & Juliet)` },
              { id: "TACTICAL_INTRADAY", label: `⚡ Tactical Intraday (8 Agents)` },
            ].map((tab) => {
              const isActive = horizonFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setHorizonFilter(tab.id as any)}
                  style={{
                    background: isActive ? "#0f172a" : "#f1f5f9",
                    color: isActive ? "#ffffff" : "#475569",
                    border: isActive ? "1px solid #0f172a" : "1px solid #e2e8f0",
                    padding: "6px 14px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>
          Showing <b>{filteredAgentList.length}</b> of 10 Agents Active
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(520px, 1fr))", gap: 20 }}>
        {filteredAgentList.map((agent) => {
          if (!agent) return null;
          const isTwoLacTier = (agent.max_principal || 100000) >= 200000;
          const g = agent.guidelines;
          const isCustomMode = g?.mode === "CUSTOM";
          const isDelta = agent.name === "Delta";
          const isTunerOpen = !!openCardTuner[agent.name];
          const isHistoryExpanded = !!expandedCardHistory[agent.name];
          const cardDraft = cardDrafts[agent.name] || {};
          const isSavingCard = savingCardAgent === agent.name;
          const historyFilter = cardHistoryFilter[agent.name] || "ALL";

          const filteredHistory = (agent.history || []).filter((h) => {
            if (historyFilter === "ALL") return true;
            return h.direction === historyFilter;
          });

          return (
            <div
              key={agent.id || agent.name}
              style={{
                background: "#ffffff",
                border: agent.position
                  ? "2px solid #22c55e"
                  : isCustomMode
                    ? "2px solid #a855f7"
                    : isTwoLacTier
                      ? "2px solid #f59e0b"
                      : "1px solid #e2e8f0",
                borderRadius: 20,
                padding: "24px",
                boxShadow: agent.position
                  ? "0 10px 25px -5px rgba(34, 197, 94, 0.15)"
                  : "0 4px 14px rgba(0, 0, 0, 0.04)",
                display: "flex",
                flexDirection: "column",
                gap: 16,
                transition: "all 0.25s ease",
              }}
            >
              {/* Card Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  borderBottom: "1px solid #f1f5f9",
                  paddingBottom: "14px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span
                    style={{
                      fontSize: 32,
                      background: isTwoLacTier ? "#fef3c7" : "#f8fafc",
                      padding: "8px",
                      borderRadius: 14,
                      border: `1px solid ${isTwoLacTier ? "#fde68a" : "#e2e8f0"}`,
                    }}
                  >
                    {agent.avatar || "🤖"}
                  </span>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <h2 style={{ margin: 0, fontSize: 21, fontWeight: 900, color: "#0f172a" }}>Agent {agent.name}</h2>
                      {/* Capital Tier */}
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 800,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: isTwoLacTier ? "#fef3c7" : "#eff6ff",
                          color: isTwoLacTier ? "#b45309" : "#1d4ed8",
                          border: `1px solid ${isTwoLacTier ? "#fde68a" : "#bfdbfe"}`,
                        }}
                      >
                        ₹{((agent.max_principal || 100000) / 100000).toFixed(1)}L{" "}
                        {isTwoLacTier ? "Institutional" : "Standard"}
                      </span>
                      {/* Mode Badge */}
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 900,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: isCustomMode ? "#faf5ff" : "#f0fdf4",
                          color: isCustomMode ? "#7e22ce" : "#15803d",
                          border: `1px solid ${isCustomMode ? "#d8b4fe" : "#bbf7d0"}`,
                        }}
                      >
                        {isCustomMode ? "🎯 MANUAL DIRECTIVE" : "🤖 AUTONOMOUS"}
                      </span>
                      {/* Lot Ceiling Badge */}
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: "#f0f9ff",
                          color: "#0369a1",
                          border: "1px solid #bae6fd",
                        }}
                      >
                        Ceiling: {g?.allowed_lot_size || (isTwoLacTier ? 2.0 : 1.0)} Lot Max
                      </span>
                      {/* Horizon Badge */}
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 900,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: agent.horizon === "LONG_TERM_SWING" ? "#4c1d95" : "#0c4a6e",
                          color: agent.horizon === "LONG_TERM_SWING" ? "#f3e8ff" : "#e0f2fe",
                          border: `1px solid ${agent.horizon === "LONG_TERM_SWING" ? "#a855f7" : "#0284c7"}`,
                        }}
                      >
                        {agent.horizon === "LONG_TERM_SWING" ? "⏳ LONG-TERM SWING" : "⚡ TACTICAL INTRADAY"}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{agent.specialization}</div>
                  </div>
                </div>

                {/* Inline Tuner Toggle Button */}
                <button
                  onClick={() => toggleCardTuner(agent.name)}
                  style={{
                    background: isTunerOpen ? "#0f172a" : "#f1f5f9",
                    color: isTunerOpen ? "#ffffff" : "#334155",
                    border: "1px solid #cbd5e1",
                    padding: "7px 12px",
                    borderRadius: 10,
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span>🛠️</span>
                  <span>{isTunerOpen ? "Close Tuner" : "Manual Tuning"}</span>
                </button>
              </div>

              {/* Strategy Badge */}
              <div
                style={{
                  background: isDelta ? "#fef9c3" : "#f8fafc",
                  border: isDelta ? "2px solid #eab308" : "1px solid #e2e8f0",
                  padding: "10px 14px",
                  borderRadius: 12,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 10,
                      color: isDelta ? "#854d0e" : "#64748b",
                      fontWeight: 800,
                      textTransform: "uppercase",
                    }}
                  >
                    {isDelta ? "👑 SOLE DEDICATED #1 STRATEGY TESTER" : "ACTIVE STRATEGY DIRECTIVE"}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 900, color: isDelta ? "#854d0e" : "#0f172a" }}>
                    {agent.active_strategy}: {agent.active_strategy_name}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 10, color: "#64748b", fontWeight: 800 }}>DIRECTION BIAS</div>
                  <div style={{ fontSize: 12, fontWeight: 800, color: "#2563eb" }}>{g?.direction_bias || "BOTH"}</div>
                </div>
              </div>

              {/* Real-time Market Condition Evaluation Pill */}
              {agent.condition_status && (
                <div
                  style={{
                    background: agent.condition_status.matched ? "#f0fdf4" : "#fffbeb",
                    border: `1px solid ${agent.condition_status.matched ? "#86efac" : "#fde68a"}`,
                    padding: "8px 12px",
                    borderRadius: 10,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 6,
                    fontSize: 11,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span>{agent.condition_status.matched ? "🟢" : "🟡"}</span>
                    <span style={{ fontWeight: 800, color: agent.condition_status.matched ? "#166534" : "#92400e" }}>
                      {agent.condition_status.matched ? "CONDITION MATCHED" : "OBSERVING REGIME"}
                    </span>
                    <span style={{ color: "#64748b" }}>·</span>
                    <span style={{ fontWeight: 700, color: "#0f172a" }}>{agent.condition_status.condition_label}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>
                      Alignment: <b>{agent.condition_status.strength_score}%</b>
                    </span>
                    {agent.condition_status.recommended_direction && (
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 900,
                          padding: "1px 5px",
                          borderRadius: 4,
                          background: agent.condition_status.recommended_direction === "LONG" ? "#dcfce7" : "#fee2e2",
                          color: agent.condition_status.recommended_direction === "LONG" ? "#15803d" : "#b91c1c",
                        }}
                      >
                        {agent.condition_status.recommended_direction} BIAS
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Strategy Retesting & Edge Tracker */}
              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 10,
                  padding: "8px 12px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 8,
                  fontSize: 11,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 800, color: "#475569" }}>🔄 Retest Cycle:</span>
                  <span style={{ fontWeight: 900, color: "#0f172a", fontFamily: "monospace" }}>
                    {agent.strategy_retests || 0} Retests ({agent.strategy_wins || 0}W / {agent.strategy_losses || 0}L)
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 999,
                      fontSize: 10,
                      fontWeight: 900,
                      background:
                        agent.strategy_edge_status === "CONFIRMED_EDGE"
                          ? "#dcfce7"
                          : agent.strategy_edge_status === "PROVING_EDGE"
                            ? "#dbeafe"
                            : agent.strategy_edge_status === "ROTATING_STRATEGY"
                              ? "#fef3c7"
                              : "#f1f5f9",
                      color:
                        agent.strategy_edge_status === "CONFIRMED_EDGE"
                          ? "#166534"
                          : agent.strategy_edge_status === "PROVING_EDGE"
                            ? "#1e40af"
                            : agent.strategy_edge_status === "ROTATING_STRATEGY"
                              ? "#92400e"
                              : "#475569",
                      border: `1px solid ${
                        agent.strategy_edge_status === "CONFIRMED_EDGE"
                          ? "#86efac"
                          : agent.strategy_edge_status === "PROVING_EDGE"
                            ? "#93c5fd"
                            : agent.strategy_edge_status === "ROTATING_STRATEGY"
                              ? "#fde68a"
                              : "#cbd5e1"
                      }`,
                    }}
                  >
                    {agent.strategy_edge_status || "EXPLORING"}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 900,
                      fontFamily: "monospace",
                      color: (agent.strategy_net_pnl || 0) >= 0 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {(agent.strategy_net_pnl || 0) >= 0 ? "+" : ""}₹{(agent.strategy_net_pnl || 0).toFixed(1)}
                  </span>
                </div>
              </div>

              {/* Net P&L Increment & Goal Progress Bar */}
              <div
                style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 10, border: "1px solid #f1f5f9" }}
              >
                <div
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}
                >
                  <span style={{ fontSize: 11, fontWeight: 800, color: "#334155" }}>
                    🎯 Goal Net Increment: ₹
                    {(
                      agent.target_net_pnl_increment || (agent.horizon === "LONG_TERM_SWING" ? 50000 : 25000)
                    ).toLocaleString()}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 900,
                      fontFamily: "monospace",
                      color: (agent.net_pnl_increment || agent.pnl || 0) >= 0 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {(agent.net_pnl_increment || agent.pnl || 0) >= 0 ? "+" : ""}₹
                    {(agent.net_pnl_increment || agent.pnl || 0).toLocaleString("en-IN", {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}{" "}
                    <span style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>
                      ({Math.min(100, Math.max(0, agent.goal_progress_pct || 0)).toFixed(0)}%)
                    </span>
                  </span>
                </div>
                <div style={{ width: "100%", height: 6, background: "#e2e8f0", borderRadius: 999, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, agent.goal_progress_pct || ((agent.pnl || 0) > 0 ? ((agent.pnl || 0) / (agent.target_net_pnl_increment || 25000)) * 100 : 0)))}%`,
                      height: "100%",
                      background:
                        agent.horizon === "LONG_TERM_SWING"
                          ? "linear-gradient(90deg, #8b5cf6 0%, #a855f7 100%)"
                          : "linear-gradient(90deg, #0284c7 0%, #10b981 100%)",
                      borderRadius: 999,
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
              </div>

              {/* Live Activity & Hypothesis */}
              <div
                style={{ background: "#f8fafc", padding: "12px 14px", borderRadius: 12, border: "1px solid #f1f5f9" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: agent.position ? "#22c55e" : "#3b82f6",
                      display: "inline-block",
                    }}
                  />
                  <span style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase" }}>
                    Live Market State
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>{agent.current_activity}</div>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                  Hypothesis: <i>{agent.current_hypothesis}</i>
                </div>
              </div>

              {/* Active Position Widget */}
              {agent.position ? (
                <div
                  style={{
                    background: agent.position.direction === "LONG" ? "#f0fdf4" : "#fef2f2",
                    border: `2px solid ${agent.position.direction === "LONG" ? "#22c55e" : "#ef4444"}`,
                    padding: "14px 18px",
                    borderRadius: 14,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 10,
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          background: agent.position.direction === "LONG" ? "#22c55e" : "#ef4444",
                          color: "#ffffff",
                          padding: "2px 8px",
                          borderRadius: 6,
                          fontWeight: 900,
                          fontSize: 11,
                        }}
                      >
                        {agent.position.direction}
                      </span>
                      <span style={{ fontWeight: 900, fontSize: 14, color: "#0f172a" }}>
                        {agent.position.lots} Lot ({agent.position.total_quantity} {agent.position.lot_unit})
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 2, fontFamily: "monospace" }}>
                      Entry: ₹{agent.position.entry_price != null ? agent.position.entry_price.toFixed(1) : "--"} ·
                      Target: ₹{agent.position.target_price != null ? agent.position.target_price.toFixed(1) : "--"} ·
                      Stop: ₹{agent.position.stop_loss != null ? agent.position.stop_loss.toFixed(1) : "--"}
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>UNREALIZED P&L</div>
                    <div
                      style={{
                        fontSize: 18,
                        fontWeight: 900,
                        fontFamily: "monospace",
                        color: (agent.position.unrealized_pnl ?? 0) >= 0 ? "#16a34a" : "#dc2626",
                      }}
                    >
                      {(agent.position.unrealized_pnl ?? 0) >= 0 ? "+" : ""}₹
                      {(agent.position.unrealized_pnl ?? 0).toFixed(2)}
                    </div>
                    <div style={{ fontSize: 10, color: "#64748b" }}>Hold: {(agent.position.hold_cycles || 0) * 2}s</div>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    background: "#f8fafc",
                    padding: "10px 14px",
                    borderRadius: 10,
                    border: "1px dashed #cbd5e1",
                    textAlign: "center",
                    fontSize: 11,
                    color: "#64748b",
                  }}
                >
                  📡 No active position · Monitoring real-time price action & quantitative triggers
                </div>
              )}

              {/* Performance Metrics */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <div
                  style={{
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 10,
                    textAlign: "center",
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>NET REALIZED P&L</div>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 900,
                      fontFamily: "monospace",
                      color: (agent.pnl || 0) >= 0 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {(agent.pnl || 0) >= 0 ? "+" : ""}₹
                    {(agent.pnl || 0).toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </div>
                </div>

                <div
                  style={{
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 10,
                    textAlign: "center",
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>WIN RATE</div>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 900,
                      color: (agent.win_rate || 0) >= 50 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {agent.win_rate || 0}%
                  </div>
                </div>

                <div
                  style={{
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 10,
                    textAlign: "center",
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>COMPLETED TESTS</div>
                  <div style={{ fontSize: 15, fontWeight: 900, color: "#0f172a" }}>{agent.total_tests || 0}</div>
                </div>

                <div
                  style={{
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 10,
                    textAlign: "center",
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>AVAILABLE CAPITAL</div>
                  <div style={{ fontSize: 15, fontWeight: 900, fontFamily: "monospace", color: "#0284c7" }}>
                    ₹{((agent.available_capital ?? agent.max_principal ?? 100000) / 1000).toFixed(0)}k
                  </div>
                </div>
              </div>

              {/* ================================================================= */}
              {/* INLINE MANUAL TUNING DRAWER (Opened per-card)                    */}
              {/* ================================================================= */}
              {isTunerOpen && (
                <div
                  style={{
                    background: "#0f172a",
                    color: "#ffffff",
                    borderRadius: 14,
                    padding: "18px",
                    border: "2px solid #8b5cf6",
                    display: "flex",
                    flexDirection: "column",
                    gap: 14,
                    boxShadow: "0 8px 24px rgba(139, 92, 246, 0.2)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 16 }}>🛠️</span>
                      <span style={{ fontSize: 14, fontWeight: 900, color: "#c084fc" }}>
                        Manual Tuning Console: Agent {agent.name}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>Overrides autonomous engine</span>
                  </div>

                  {/* Tuning Inputs Grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {/* Execution Mode */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Execution Mode:
                      </label>
                      <select
                        value={cardDraft.mode || "AUTO"}
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], mode: e.target.value as any },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#ffffff",
                          fontSize: 12,
                          fontWeight: 800,
                        }}
                      >
                        <option value="AUTO">🤖 AUTO (Autonomous Engine)</option>
                        <option value="CUSTOM">🎯 MANUAL DIRECTIVE</option>
                      </select>
                    </div>

                    {/* Allowed Lot Size Ceiling */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Allowed Lot Ceiling:
                      </label>
                      <input
                        type="number"
                        step="0.05"
                        min="0.05"
                        max="10.0"
                        value={cardDraft.allowed_lot_size ?? 1.0}
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], allowed_lot_size: parseFloat(e.target.value) || 0.1 },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#38bdf8",
                          fontSize: 12,
                          fontWeight: 900,
                          fontFamily: "monospace",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>

                    {/* Principal Amount */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Max Principal (₹ INR):
                      </label>
                      <input
                        type="number"
                        step="5000"
                        min="10000"
                        value={cardDraft.max_principal ?? agent.max_principal ?? 100000}
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], max_principal: parseFloat(e.target.value) || 100000 },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#4ade80",
                          fontSize: 12,
                          fontWeight: 900,
                          fontFamily: "monospace",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>

                    {/* Strategy Directive */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Strategy Assignment:
                      </label>
                      {isDelta ? (
                        <div
                          style={{
                            padding: "8px",
                            borderRadius: 8,
                            border: "1px solid #eab308",
                            background: "#78350f",
                            color: "#fef3c7",
                            fontSize: 11,
                            fontWeight: 900,
                          }}
                        >
                          👑 S17 Price × OI × Volume (#1)
                        </div>
                      ) : (
                        <select
                          value={cardDraft.strategy_id || "AUTO"}
                          onChange={(e) =>
                            setCardDrafts((prev) => ({
                              ...prev,
                              [agent.name]: { ...prev[agent.name], strategy_id: e.target.value },
                            }))
                          }
                          style={{
                            width: "100%",
                            padding: "8px",
                            borderRadius: 8,
                            border: "1px solid #475569",
                            background: "#1e293b",
                            color: "#ffffff",
                            fontSize: 11,
                            fontWeight: 800,
                          }}
                        >
                          <option value="AUTO">🤖 Auto-Selected (Optimal Rank)</option>
                          <option value="S17_OI_VOLUME_MACHINE">👑 #1: Price × OI × Volume State Machine</option>
                          <option value="S01_ORB_NR7">S01: Opening Range Breakout (NR7)</option>
                          <option value="S02_VWAP_MEAN_REVERSION">S02: VWAP Dynamic Bands Mean Reversion</option>
                          <option value="S03_GAP_FILL">S03: Opening Auction Gap Fill</option>
                          <option value="S04_VOL_TARGET">S04: Dynamic Volatility Targeting</option>
                          <option value="S05_MEAN_REV">S05: Statistical Mean Reversion AI</option>
                          <option value="S06_REGIME_FILTER">S06: Machine Learning Regime Shift Filter</option>
                          <option value="S08_MTF_CONSOL">S08: Multi-Timeframe Consolidation</option>
                          <option value="S09_VWAP_IMBALANCE">S09: Order Flow & VWAP Imbalance</option>
                          <option value="S10_INST_FLOW">S10: Institutional Flow Reversal</option>
                          <option value="S15_MACRO_GOLD_DXY">S15: Macro Gold-USD Flow Divergence</option>
                          <option value="S34_REGIME_ROUTER">S34: Regime Adaptive Router</option>
                        </select>
                      )}
                    </div>

                    {/* Direction Bias */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Direction Bias:
                      </label>
                      <select
                        value={cardDraft.direction_bias || "BOTH"}
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], direction_bias: e.target.value as any },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#ffffff",
                          fontSize: 12,
                          fontWeight: 800,
                        }}
                      >
                        <option value="BOTH">🔄 BOTH (Long & Short)</option>
                        <option value="LONG_ONLY">📈 LONG ONLY</option>
                        <option value="SHORT_ONLY">📉 SHORT ONLY</option>
                      </select>
                    </div>

                    {/* Target Market */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Target Contract:
                      </label>
                      <select
                        value={cardDraft.target_market || "AUTO"}
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], target_market: e.target.value },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#ffffff",
                          fontSize: 12,
                          fontWeight: 800,
                        }}
                      >
                        <option value="AUTO">AUTO (Session-Aware)</option>
                        <option value="MCX_GOLDM">MCX Gold Mini (100g)</option>
                        <option value="MCX_GOLD">MCX Gold (1kg)</option>
                        <option value="GLOBAL_XAU">Global Spot Gold</option>
                      </select>
                    </div>

                    {/* Horizon Duration */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Horizon Strategy:
                      </label>
                      <select
                        value={
                          cardDraft.horizon ||
                          (agent.name === "Echo" || agent.name === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY")
                        }
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: { ...prev[agent.name], horizon: e.target.value as any },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#ffffff",
                          fontSize: 12,
                          fontWeight: 800,
                        }}
                      >
                        <option value="TACTICAL_INTRADAY">⚡ Tactical Intraday (15 Cycles)</option>
                        <option value="LONG_TERM_SWING">⏳ Long-Term Swing (60 Cycles)</option>
                      </select>
                    </div>

                    {/* Target Net Increment */}
                    <div>
                      <label
                        style={{ display: "block", fontSize: 11, fontWeight: 800, color: "#c084fc", marginBottom: 4 }}
                      >
                        Target Net Increment (₹):
                      </label>
                      <input
                        type="number"
                        step="5000"
                        min="5000"
                        value={
                          cardDraft.target_net_pnl_increment ??
                          (agent.name === "Echo" || agent.name === "Juliet" ? 50000 : 25000)
                        }
                        onChange={(e) =>
                          setCardDrafts((prev) => ({
                            ...prev,
                            [agent.name]: {
                              ...prev[agent.name],
                              target_net_pnl_increment: parseFloat(e.target.value) || 25000,
                            },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: "8px",
                          borderRadius: 8,
                          border: "1px solid #475569",
                          background: "#1e293b",
                          color: "#4ade80",
                          fontSize: 12,
                          fontWeight: 900,
                          fontFamily: "monospace",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  </div>

                  {/* Save or Reset Controls */}
                  <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() => handleResetAgentToAuto(agent.name)}
                      disabled={isSavingCard}
                      style={{
                        flex: 1,
                        padding: "8px",
                        borderRadius: 8,
                        border: "1px solid #475569",
                        background: "#1e293b",
                        color: "#cbd5e1",
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: "pointer",
                      }}
                    >
                      🔄 Reset AUTO
                    </button>
                    <button
                      type="button"
                      onClick={() => handleResetSingleAgent(agent.name)}
                      disabled={isSavingCard}
                      style={{
                        flex: 1,
                        padding: "8px",
                        borderRadius: 8,
                        border: "1px solid #ef4444",
                        background: "#450a0a",
                        color: "#fca5a5",
                        fontSize: 12,
                        fontWeight: 800,
                        cursor: "pointer",
                      }}
                      title={`Reset Agent ${agent.name} metrics to 0 and start fresh`}
                    >
                      🔄 Reset to 0
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSaveCardDraft(agent.name)}
                      disabled={isSavingCard}
                      style={{
                        flex: 2,
                        padding: "8px",
                        borderRadius: 8,
                        border: "none",
                        background: "linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)",
                        color: "#ffffff",
                        fontSize: 12,
                        fontWeight: 900,
                        cursor: isSavingCard ? "not-allowed" : "pointer",
                      }}
                    >
                      {isSavingCard ? "Saving..." : `💾 Save & Deploy to Agent ${agent.name}`}
                    </button>
                  </div>
                </div>
              )}

              {/* Expandable Agent History */}
              <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <button
                    onClick={() =>
                      setExpandedCardHistory((prev) => ({
                        ...prev,
                        [agent.name]: !prev[agent.name],
                      }))
                    }
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#2563eb",
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span>{isHistoryExpanded ? "▼ Hide Recent Trade History" : "▶ View Recent Trades"}</span>
                    <span
                      style={{
                        background: "#eff6ff",
                        color: "#1d4ed8",
                        padding: "1px 6px",
                        borderRadius: 999,
                        fontSize: 11,
                      }}
                    >
                      {(agent.history || []).length}
                    </span>
                  </button>

                  <Link
                    href="/upstox-ledger"
                    style={{ fontSize: 11, fontWeight: 700, color: "#059669", textDecoration: "none" }}
                  >
                    View in Full Upstox Ledger →
                  </Link>
                </div>

                {isHistoryExpanded && (
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                    {(agent.history || []).length === 0 ? (
                      <div style={{ padding: "16px", textAlign: "center", color: "#94a3b8", fontSize: 12 }}>
                        No trades yet. Awaiting live market breakout signals.
                      </div>
                    ) : (
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                          <thead>
                            <tr style={{ background: "#f8fafc", color: "#64748b", textAlign: "left" }}>
                              <th style={{ padding: "6px" }}>Time</th>
                              <th style={{ padding: "6px" }}>Dir</th>
                              <th style={{ padding: "6px" }}>Lots (Qty)</th>
                              <th style={{ padding: "6px" }}>Entry</th>
                              <th style={{ padding: "6px" }}>Exit</th>
                              <th style={{ padding: "6px" }}>Net PnL</th>
                              <th style={{ padding: "6px" }}>Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredHistory.slice(0, 5).map((t, idx) => (
                              <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                                <td style={{ padding: "6px", fontFamily: "monospace", color: "#64748b" }}>
                                  {mounted && t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : "--:--:--"}
                                </td>
                                <td style={{ padding: "6px" }}>
                                  <span
                                    style={{
                                      fontWeight: 800,
                                      color: t.direction === "LONG" ? "#15803d" : "#b91c1c",
                                    }}
                                  >
                                    {t.direction}
                                  </span>
                                </td>
                                <td style={{ padding: "6px", fontFamily: "monospace" }}>
                                  {t.lots} lot ({t.total_quantity}g)
                                </td>
                                <td style={{ padding: "6px", fontFamily: "monospace" }}>
                                  ₹{t.entry_price != null ? t.entry_price.toFixed(1) : "--"}
                                </td>
                                <td style={{ padding: "6px", fontFamily: "monospace" }}>
                                  ₹{t.exit_price != null ? t.exit_price.toFixed(1) : "--"}
                                </td>
                                <td
                                  style={{
                                    padding: "6px",
                                    fontFamily: "monospace",
                                    fontWeight: 900,
                                    color: (t.pnl_change ?? 0) >= 0 ? "#16a34a" : "#dc2626",
                                  }}
                                >
                                  {(t.pnl_change ?? 0) >= 0 ? "+" : ""}₹{(t.pnl_change ?? 0).toFixed(2)}
                                </td>
                                <td style={{ padding: "6px", fontSize: 10, color: "#64748b" }}>{t.exit_reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
