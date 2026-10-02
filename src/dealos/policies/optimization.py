"""Interface for a future optimization policy. V1 does not solve it."""

from __future__ import annotations

from dealos.domain.models import AllocationAction, PortfolioState, Scenario


class OptimizationPolicy:
    """Placeholder for the mathematical program. `select_action` does not solve.

    At a fixed time t, Ready_ij(x_i(t)), φ_ij, α_jr, and q_jr are known, so the
    one-step progress increment is linear in the allocation:

        Δx_ij = φ_ij * Ready_ij * Σ_r α_jr q_jr a_ijr
        a_ijr ∈ [0, 1]
        Σ_i Σ_j a_ijr ≤ C_r(t)

    A myopic linear program could maximize a weighted sum of those increments.
    That proxy is not the portfolio objective. The objective defined for this
    project is the terminal count

        maximize Σ_i y_i
        y_i = 1 iff x_ij(T) = 1 for every j ∈ Target_i

    subject to the dynamics

        x_ij(t+1) = min(1, x_ij(t) + Δx_ij(t))
        Ready_ij = 1 if Pred_ij is empty, else min_{k ∈ Pred_ij} x_ik

    Future readiness depends on future progress, so the horizon problem is not
    the one-step linear program. Neither problem is solved here.
    """

    name = "optimization"

    def select_action(self, state: PortfolioState, scenario: Scenario) -> AllocationAction:
        del state, scenario
        raise NotImplementedError(
            "OptimizationPolicy is an interface only. No optimizer is implemented in V1."
        )
