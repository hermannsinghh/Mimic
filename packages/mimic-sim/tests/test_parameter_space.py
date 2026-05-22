"""Tests for ParameterSpace and Distribution."""

import numpy as np
import pytest

from mimic_sim.parameter_space import Distribution, ParameterSpace, SampledParams


class TestDistribution:
    def test_uniform_bounds(self):
        d = Distribution.uniform(0.4, 0.9)
        rng = np.random.default_rng(0)
        samples = d.sample_many(5000, rng)
        assert samples.min() >= 0.4 - 1e-9
        assert samples.max() <= 0.9 + 1e-9

    def test_normal_mean(self):
        d = Distribution.normal(85, 20)
        rng = np.random.default_rng(1)
        samples = d.sample_many(10000, rng)
        assert abs(samples.mean() - 85) < 2.0

    def test_lognormal_positive(self):
        d = Distribution.lognormal(3.4, 0.5)
        rng = np.random.default_rng(2)
        samples = d.sample_many(1000, rng)
        assert (samples > 0).all()

    def test_triangular_mode(self):
        d = Distribution.triangular(0.4, 0.7, 0.95)
        rng = np.random.default_rng(3)
        samples = d.sample_many(10000, rng)
        assert 0.4 <= samples.mean() <= 0.95
        assert samples.min() >= 0.4 - 1e-9
        assert samples.max() <= 0.95 + 1e-9

    def test_empirical_sampling(self):
        historical = [10.0, 12.0, 15.0, 11.0, 13.0, 14.0]
        d = Distribution.empirical(historical)
        rng = np.random.default_rng(4)
        samples = d.sample_many(500, rng)
        assert len(samples) == 500

    def test_constant(self):
        d = Distribution.constant(42.0)
        rng = np.random.default_rng(5)
        # Constant distribution: sample should be very close to 42
        s = d.sample(rng)
        assert abs(s - 42.0) < 1e-6

    def test_single_sample(self):
        d = Distribution.normal(0, 1)
        rng = np.random.default_rng(6)
        s = d.sample(rng)
        assert isinstance(s, float)


class TestParameterSpace:
    def _default_space(self):
        return ParameterSpace(
            severity=Distribution.triangular(0.4, 0.7, 0.95),
            duration_days=Distribution.lognormal(3.4, 0.5),
            macro_conditions={
                "oil_price": Distribution.normal(85, 20),
                "usd_cny": Distribution.normal(7.3, 0.3),
            },
            company_behavior={
                "WMT": {"risk_appetite_delta": Distribution.normal(0, 0.05)}
            },
            intervention_probability=0.15,
        )

    def test_sample_returns_sampled_params(self):
        space = self._default_space()
        rng = np.random.default_rng(0)
        params = space.sample(rng)
        assert isinstance(params, SampledParams)

    def test_severity_in_range(self):
        space = self._default_space()
        rng = np.random.default_rng(0)
        batch = space.sample_batch(500, seed=0)
        severities = [p.severity for p in batch]
        assert all(0.4 <= s <= 0.95 for s in severities)

    def test_duration_positive(self):
        space = self._default_space()
        batch = space.sample_batch(200, seed=1)
        assert all(p.duration_days >= 1.0 for p in batch)

    def test_macro_keys_present(self):
        space = self._default_space()
        rng = np.random.default_rng(2)
        p = space.sample(rng)
        assert "oil_price" in p.macro_conditions
        assert "usd_cny" in p.macro_conditions

    def test_intervention_rate(self):
        space = self._default_space()
        batch = space.sample_batch(2000, seed=3)
        rate = sum(p.intervention_triggered for p in batch) / len(batch)
        assert 0.08 < rate < 0.25  # 15% ± tolerance

    def test_reproducibility(self):
        space = self._default_space()
        b1 = space.sample_batch(10, seed=99)
        b2 = space.sample_batch(10, seed=99)
        for p1, p2 in zip(b1, b2):
            assert abs(p1.severity - p2.severity) < 1e-12
