# XAU-019 performance

Latest $1,000 frozen setting: completed M5, three-bar structure, 1.25% planned risk ceiling, 2R target, no optional protection, target holding 240 minutes, UTC `NEW_YORK` admission; target is snapped toward entry on the observed broker tick grid.

| March–August 2026 | Closed trades | Net booked return | Close-mark drawdown | Worst day | Worst month |
| ----------------- | ------------- | ----------------- | ------------------- | --------- | ----------- |
| BASE              | 7             | 0.1913%           | 4.4816%             | -1.7283%  | -2.7724%    |
| STRESS            | 7             | 0.01495%          | 4.6242%             | -1.7986%  | -2.8768%    |

BASE uses observed spread plus modeled $22/lot round-trip charges; STRESS widens spread 1.5 times, charges $44/lot and halves modeled leverage. These are assumptions. The later STRESS gain is approximately $0.1495; small cost errors could erase it. Full-period results include tuning data and cannot establish future edge.

These are documentation references to historical local artifacts, not authority-bearing store results. Runtime-approved dataset/result arrays remain empty; future return and empirical probability remain UNKNOWN. See [complete report](../../docs/research/GOLD_TRIPLE_WINNING_CONDITIONS_2026-10-08.md) and the exact verification JSON.
