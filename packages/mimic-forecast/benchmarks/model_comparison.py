"""CLI benchmark: compare all available models on a given series.

Usage:
    python benchmarks/model_comparison.py --ticker DCOILWTICO --source fred --horizon 30

Requires: pip install 'mimic-forecast[timesfm,chronos,data]'
"""

from __future__ import annotations

import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Compare mimic-forecast models on a series.")
    parser.add_argument("--ticker", default="DCOILWTICO", help="FRED or yfinance ticker")
    parser.add_argument("--source", default="fred", choices=["fred", "yfinance", "auto"])
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--frequency", default="D")
    parser.add_argument("--metric", default="RMSE", choices=["RMSE", "MAE", "MAPE"])
    parser.add_argument("--models", nargs="+", default=["timesfm", "chronos"])
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()

    from mimic_forecast.data.series import pull_series
    from mimic_forecast.registry import get_adapter
    from mimic_forecast.benchmarks import run_comparison

    series = pull_series(
        ticker=args.ticker,
        source=args.source,
        years=args.years,
        fred_api_key=os.environ.get("FRED_API_KEY"),
    )
    logger.info("Loaded '%s': %d observations (%s to %s)", args.ticker, len(series),
                series.index[0].date(), series.index[-1].date())

    adapters = [get_adapter(m) for m in args.models]
    result = run_comparison(series, adapters, horizon=args.horizon, metric=args.metric)

    print(f"\n{'Model':<30} {args.metric:>10}")
    print("-" * 42)
    for model_name, score in sorted(result.scores.items(), key=lambda x: x[1]):
        marker = " ← winner" if model_name == result.winner else ""
        print(f"{model_name:<30} {score:>10.4f}{marker}")

    print(f"\nWinner: {result.winner}")


if __name__ == "__main__":
    main()
