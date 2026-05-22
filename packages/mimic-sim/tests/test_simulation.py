"""Tests for Simulation and SimulationResult."""

import numpy as np
import pytest

from mimic_sim import Distribution, ParameterSpace, Simulation, SimulationResult
from mimic_sim.execution.tier3_formulas import CompanyProfile


@pytest.fixture
def small_sim():
    space = ParameterSpace(
        severity=Distribution.triangular(0.4, 0.7, 0.95),
        duration_days=Distribution.lognormal(3.4, 0.5),
        macro_conditions={
            "oil_price": Distribution.normal(85, 15),
            "usd_cny": Distribution.normal(7.3, 0.2),
        },
        company_behavior={
            "WMT": {"risk_appetite_delta": Distribution.normal(0, 0.05)},
        },
        intervention_probability=0.15,
    )
    return Simulation(
        profiles=[
            CompanyProfile.walmart(),
            CompanyProfile.apple(),
            CompanyProfile.fedex(),
        ],
        scenario_name="taiwan_strait_closure_30d",
        parameter_space=space,
        n_runs=200,
        seed=42,
    )


class TestSimulationSetup:
    def test_mode_tier2_returns_result(self, small_sim):
        result = small_sim.run(mode="tier2")
        assert isinstance(result, SimulationResult)
        assert result.mode == "tier2"

    def test_mode_tier2_impacts_negative(self, small_sim):
        result = small_sim.run(mode="tier2")
        assert result.mean("WMT") < 0

    def test_mode_tier1_not_implemented(self, small_sim):
        with pytest.raises(NotImplementedError):
            small_sim.run(mode="tier1")

    def test_unknown_mode(self, small_sim):
        with pytest.raises(ValueError):
            small_sim.run(mode="tier99")


class TestTier3Run:
    def test_returns_simulation_result(self, small_sim):
        result = small_sim.run(mode="tier3")
        assert isinstance(result, SimulationResult)

    def test_n_runs_correct(self, small_sim):
        result = small_sim.run(mode="tier3")
        assert result.n_runs == 200
        assert len(result.runs) == 200

    def test_tickers_present(self, small_sim):
        result = small_sim.run(mode="tier3")
        assert set(result.tickers) == {"WMT", "AAPL", "FDX"}

    def test_impacts_are_negative(self, small_sim):
        """Supply-chain disruptions should produce losses (negative impact)."""
        result = small_sim.run(mode="tier3")
        wmt_mean = result.mean("WMT")
        assert wmt_mean < 0, f"Expected negative impact, got {wmt_mean:.3f}"

    def test_reproducibility(self):
        space = ParameterSpace(severity=Distribution.uniform(0.5, 0.8))
        sim_a = Simulation(
            profiles=[CompanyProfile.walmart()],
            scenario_name="test",
            parameter_space=space,
            n_runs=50,
            seed=7,
        )
        sim_b = Simulation(
            profiles=[CompanyProfile.walmart()],
            scenario_name="test",
            parameter_space=space,
            n_runs=50,
            seed=7,
        )
        r_a = sim_a.run("tier3")
        r_b = sim_b.run("tier3")
        assert abs(r_a.mean("WMT") - r_b.mean("WMT")) < 1e-10


class TestSimulationResult:
    @pytest.fixture(autouse=True)
    def result(self, small_sim):
        self.result = small_sim.run(mode="tier3")

    def test_percentile_ordering(self):
        p5 = self.result.percentile("WMT", "financial_impact", 5)
        p50 = self.result.percentile("WMT", "financial_impact", 50)
        p95 = self.result.percentile("WMT", "financial_impact", 95)
        assert p5 < p50 < p95

    def test_var_worse_than_mean(self):
        var = self.result.var("WMT", 0.95)
        mean = self.result.mean("WMT")
        assert var <= mean

    def test_cvar_worse_than_var(self):
        var = self.result.var("WMT", 0.95)
        cvar = self.result.cvar("WMT", 0.95)
        assert cvar <= var

    def test_correlation_matrix_shape(self):
        corr = self.result.correlation_matrix()
        assert corr.shape == (3, 3)

    def test_correlation_diagonal_ones(self):
        corr = self.result.correlation_matrix()
        diag = np.diag(corr.values)
        assert np.allclose(diag, 1.0)

    def test_tail_coincidence_between_zero_and_one(self):
        tc = self.result.tail_coincidence("WMT", "AAPL", percentile_threshold=20)
        assert 0.0 <= tc <= 1.0

    def test_sensitivity_sums_to_one(self):
        sens = self.result.sensitivity("WMT")
        total = sum(sens.values())
        assert abs(total - 1.0) < 0.01

    def test_worst_runs_count(self):
        worst = self.result.worst_runs(n=5)
        assert len(worst) == 5

    def test_best_runs_better_than_worst(self):
        best = self.result.best_runs(n=10, ticker="WMT")
        worst = self.result.worst_runs(n=10, ticker="WMT")
        best_mean = np.mean([r.company_outcomes["WMT"].financial_impact for r in best])
        worst_mean = np.mean([r.company_outcomes["WMT"].financial_impact for r in worst])
        assert best_mean > worst_mean

    def test_median_run_exists(self):
        median = self.result.median_run("WMT")
        assert median is not None

    def test_summary_dataframe(self):
        df = self.result.summary()
        assert "WMT" in df.index
        assert "var_95_bn" in df.columns
        assert df.loc["WMT", "var_95_bn"] < 0

    def test_describe_keys(self):
        desc = self.result.describe("WMT")
        for key in ["mean", "std", "p5", "p50", "p95"]:
            assert key in desc.index

    def test_unknown_ticker_raises(self):
        with pytest.raises(KeyError):
            self.result.mean("TSLA")

    def test_time_series_shape(self):
        ts = self.result._time_series("WMT")
        assert ts.shape == (200, 4)
