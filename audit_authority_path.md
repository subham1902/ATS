=== LIVE AUTHORITY PATH AUDIT ===
OpportunityCandidate -> Portfolio Brain -> RiskFacts -> RiskDecision -> A04 -> AutonomyToken -> OrderIntent -> PaperBroker -> Fill -> Position -> Exit

Files/Functions:
1. OpportunityCandidate: contracts/governance/models.py (OpportunityCandidate)
2. Portfolio Brain: portfolio/brain/engine.py (PortfolioManagerBrain.allocate)
3. RiskFacts: contracts/domain/models.py (RiskFacts)
4. RiskDecision: contracts/domain/models.py (RiskDecision)
5. A04: trading_runtime/authority_service.py (TradingAuthorityService / PortfolioAuthorityService)
6. AutonomyToken: contracts/domain/models.py (AutonomyToken)
7. OrderIntent: contracts/domain/models.py (OrderIntent)
8. PaperBroker: trading_runtime/broker.py (PaperBrokerAdapter)
9. Fill: contracts/domain/models.py (Fill)
10. Position: contracts/domain/models.py (Position) + trading_runtime/position_monitor.py (MonitoredPosition)
11. Exit: contracts/domain/models.py (ExitIntent) + trading_runtime/engine.py
12. P&L: portfolio/persistence.py / trading_runtime/runtime_provider.py
