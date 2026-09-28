import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import optuna

LOGGER = logging.getLogger(__name__)

# Simple in-memory state for UI
optimization_state: dict[str, Any] = {
    "status": "STOPPED",
    "active_trials": 0,
    "total_trials": 0,
    "best_results": {},
    "recent_trials": []
}

class OptimizationWorker:
    def __init__(self, fabric: Any, candle_engine: Any, journal: Any) -> None:
        self.fabric = fabric
        self.candle_engine = candle_engine
        self.journal = journal
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # Hide Optuna logging output
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self.studies: dict[str, optuna.Study] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        optimization_state["status"] = "RUNNING"
        self._task = asyncio.create_task(self._loop())
        LOGGER.info("Optimization Worker Started")

    async def stop(self) -> None:
        self._running = False
        optimization_state["status"] = "STOPPED"
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        LOGGER.info("Optimization Worker Stopped")

    async def _loop(self) -> None:
        # Continuous Bayesian optimization over selected strategies
        strategies = ["S01_ORB_NR7", "S02_TSMOM", "S04_VOL_TARGET"]
        
        while self._running:
            try:
                for strat in strategies:
                    if not self._running:
                        break
                    
                    if strat not in self.studies:
                        self.studies[strat] = optuna.create_study(direction="maximize")
                    
                    study = self.studies[strat]
                    
                    def objective(trial: optuna.Trial, strat: str = strat) -> float:
                        # Bind `strat` explicitly so the search space can never be
                        # attributed to the wrong strategy (late-binding closure bug).
                        # Define hyperparameter search spaces based on strategy
                        if strat == "S01_ORB_NR7":
                            sl = trial.suggest_float("stop_loss_mult", 0.5, 3.0)
                            tp = trial.suggest_float("take_profit_mult", 1.0, 5.0)
                            lookback = trial.suggest_int("lookback_bars", 5, 20)
                            ideal_lb = 12.0
                        elif strat == "S02_TSMOM":
                            sl = trial.suggest_float("stop_loss_mult", 1.0, 4.0)
                            tp = trial.suggest_float("take_profit_mult", 1.0, 5.0)
                            lookback = trial.suggest_int("momentum_period", 10, 60)
                            ideal_lb = 30.0
                        else:
                            sl = trial.suggest_float("stop_loss_mult", 0.5, 4.0)
                            tp = trial.suggest_float("take_profit_mult", 1.0, 6.0)
                            lookback = trial.suggest_int("vol_window", 14, 100)
                            ideal_lb = 40.0

                        # MOCK OBJECTIVE -- this is a synthetic peak, NOT a backtest.
                        # Replace with a real historical backtest before any result
                        # from this worker is treated as evidence.
                        import random

                        score = (
                            100
                            - (sl - 1.5) ** 2 * 20
                            - (tp - 3.2) ** 2 * 10
                            - (lookback - ideal_lb) ** 2 * 0.5
                            + random.gauss(0, 5)
                        )

                        return score

                    optimization_state["active_trials"] += 1
                    
                    # Run a batch of trials
                    def run_optimize(
                        study: optuna.Study = study, objective: Any = objective
                    ) -> None:
                        study.optimize(objective, n_trials=3)
                    
                    await asyncio.to_thread(run_optimize)
                    
                    optimization_state["active_trials"] -= 1
                    optimization_state["total_trials"] += 3
                    
                    try:
                        best = study.best_trial
                        best_value = cast("float", best.value)
                        optimization_state["best_results"][strat] = {
                            "value": round(best_value, 2),
                            "params": {
                                k: round(v, 2) if isinstance(v, float) else v
                                for k, v in best.params.items()
                            },
                            "updated_at": datetime.now(UTC).isoformat()
                        }
                        optimization_state["recent_trials"].insert(0, {
                            "strategy": strat,
                            "trial_id": str(uuid.uuid4())[:8],
                            "params": {
                                k: round(v, 2) if isinstance(v, float) else v
                                for k, v in best.params.items()
                            },
                            "score": round(best_value, 2),
                            "timestamp": datetime.now(UTC).isoformat()
                        })
                        optimization_state["recent_trials"] = (
                            optimization_state["recent_trials"][:30]
                        )
                    except ValueError:
                        pass # No completed trials yet
                        
                await asyncio.sleep(2) # Prevent starving event loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(5)
