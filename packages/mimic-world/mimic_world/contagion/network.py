"""FIBO-shaped liability network builder — Plan §3.3 W-04.

Builds an (n x n) liability matrix from FIBO-shaped entity records so that
both EN clearing and DebtRank can operate on real institution data.

Minimal usage::

    net = LiabilityNetwork()
    net.add_node("BankA", equity=50e9, total_assets=500e9)
    net.add_node("BankB", equity=30e9, total_assets=300e9)
    net.add_bilateral_exposure("BankA", "BankB", amount=10e9)
    L, v, names = net.to_matrix()
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class _Node:
    name: str
    equity: float
    total_assets: float
    fibo_iri: str | None = None
    metadata: dict = field(default_factory=dict)


class LiabilityNetwork:
    """Builds liability and value matrices from entity-level data.

    Nodes are identified by string names (ticker symbols, LEIs, FIBO IRIs,
    or any unique identifier). The resulting matrices are used as inputs to
    `eisenberg_noe_clearing` and `debt_rank`.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, _Node] = {}
        self._exposures: list[tuple[str, str, float]] = []

    def add_node(
        self,
        name: str,
        equity: float,
        total_assets: float,
        fibo_iri: str | None = None,
        **metadata,
    ) -> None:
        """Register a financial institution node.

        Args:
            name: Unique identifier (ticker, LEI, or FIBO entity IRI).
            equity: Book equity in any consistent currency unit.
            total_assets: Total assets (used as economic value v in DebtRank).
            fibo_iri: Optional FIBO entity IRI for schema-canonical use.
            **metadata: Arbitrary extra fields (e.g. country, sector).
        """
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already registered")
        self._nodes[name] = _Node(
            name=name,
            equity=equity,
            total_assets=total_assets,
            fibo_iri=fibo_iri,
            metadata=dict(metadata),
        )

    def add_bilateral_exposure(
        self,
        debtor: str,
        creditor: str,
        amount: float,
    ) -> None:
        """Record that debtor owes creditor `amount` in gross notional.

        In EN notation: L[debtor_idx, creditor_idx] += amount.
        """
        if debtor not in self._nodes:
            raise ValueError(f"Unknown debtor node: {debtor!r}")
        if creditor not in self._nodes:
            raise ValueError(f"Unknown creditor node: {creditor!r}")
        if amount < 0:
            raise ValueError("Exposure amount must be non-negative")
        self._exposures.append((debtor, creditor, amount))

    def node_names(self) -> list[str]:
        return list(self._nodes.keys())

    def to_matrix(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Return (L, v, names) ready for EN or DebtRank.

        Returns:
            L: (n, n) liability matrix. L[i, j] = gross amount i owes j.
            v: (n,) economic value vector (total assets).
            names: Ordered list of node names corresponding to matrix indices.
        """
        names = list(self._nodes.keys())
        idx = {name: i for i, name in enumerate(names)}
        n = len(names)

        L = np.zeros((n, n))
        for debtor, creditor, amount in self._exposures:
            L[idx[debtor], idx[creditor]] += amount

        v = np.array([self._nodes[name].total_assets for name in names])
        return L, v, names

    def external_assets(self) -> np.ndarray:
        """Return equity vector (e) for EN clearing.

        For EN the 'external assets' e[i] represent cash + external claims.
        Using book equity as a proxy when more granular data isn't available.
        """
        return np.array([self._nodes[n].equity for n in self._nodes])
