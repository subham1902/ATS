# Alpha R&D V4 Sources

Access date for all web sources: 2026-08-30.

| Source | Main insight | ATS applicability | Decision |
|---|---|---|---|
| [The Microstructure of Stock Markets — Biais, Glosten, Spatt](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=310105) | Spread, price impact, inventory and adverse-selection costs are part of price formation. | A small directional probability is not an edge unless it clears observable and latent execution friction. | Adopt explicit spread, slippage, liquidity and uncertainty deductions. |
| [Asset Prices and Trading Volume Under Fixed Transactions Costs — Lo, Mamaysky, Wang](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID270733_code010607500.pdf?abstractid=270733&mirid=1) | Even small fixed costs can create economically rational no-trade regions. | Supports HOLD in quiet markets when small gross payoff does not clear fixed/variable costs. | Adopt; reject activity targets. |
| [Reducing Transaction Costs with Low-Latency Trading Algorithms — Stoikov, Waeber](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2661618) | Book imbalance can be predictive, but latency can rapidly dissipate its value. | Depth imbalance is eligible only when provider depth and timestamps are fresh; it is not fabricated from OHLC. | Defer specialist until forward depth evidence is recorded. |
| [Probability calibration — scikit-learn documentation](https://scikit-learn.org/stable/modules/calibration.html) | Calibrators must be fitted on evidence independent of model training data to avoid biased probabilities. | Confirms isolated challenger calibration and chronological calibration folds. | Preserve existing isolated calibration; do not share C0 calibration. |
| [Upstox Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/) | Full mode exposes bid/ask depth, OI, IV, Greeks, OHLC and provider timestamps. | These are legitimate inputs for future option-flow/microstructure specialists and real option payoff evidence. | Adopt only fields actually received and freshness-validated. |
| [Upstox Option Greeks API](https://upstox.com/developer/api-documentation/option-greek/) | Provider supplies delta, gamma, theta, vega, IV, volume and instrument identity. | Avoid inferred Greeks where live provider evidence is available. | Adopt as optional contemporaneous evidence; fail closed when absent. |
| [NSE Individual Securities F&O contract specifications](https://www.nseindia.com/static/products-services/equity-derivatives-individual-securities) | Exchange contract identity includes underlying, expiry, option type and strike; market lots are contract metadata. | Reinforces provider/exchange-driven contract and lot truth. | Adopt; reject hard-coded lot/expiry/strike schedules. |
| [QuantConnect slippage concepts](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts) | Slippage depends on latency, brokerage connection and market dynamics; explicit modeling improves realism. | Stress execution assumptions and do not equate quoted midpoints with fills. | Adopt explicit stress; do not import LEAN architecture. |

## Open-source systems considered

- QuantConnect LEAN: useful separation of fee, fill and slippage models. Adopted the conceptual separation only.
- scikit-learn: existing ATS calibration is sufficient; no new dependency was needed.
- Qlib, vectorbt, Backtrader, NautilusTrader, vn.py, Freqtrade, PyBroker, River, LightGBM, XGBoost, CatBoost and statsmodels: not imported. Current evidence does not justify a new framework or model stack.

