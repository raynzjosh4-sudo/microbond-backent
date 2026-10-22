use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrossGroupRiskDecision {
    pub is_eligible: bool,
    pub risk_tier: String,
    pub rejection_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuarantorCapacityResult {
    pub is_approved: bool,
    pub dynamic_max_liability_minor: i64,
    pub total_projected_liability_minor: i64,
    pub remaining_capacity_minor: i64,
    pub rejection_reason: Option<String>,
}

/// Detects if adding a directed vouching edge (new_guarantor -> new_borrower)
/// creates a cyclic dependency in the vouching graph.
pub fn detect_guarantor_cycle_pure(
    existing_edges: &[(String, String)], // (guarantor, borrower)
    new_guarantor: &str,
    new_borrower: &str,
) -> bool {
    if new_guarantor == new_borrower {
        return true;
    }

    let mut adj: HashMap<&str, Vec<&str>> = HashMap::new();
    for (g, b) in existing_edges {
        adj.entry(g.as_str()).or_default().push(b.as_str());
    }

    let mut visited: HashSet<&str> = HashSet::new();
    let mut queue: VecDeque<&str> = VecDeque::new();

    queue.push_back(new_borrower);
    visited.insert(new_borrower);

    while let Some(current) = queue.pop_front() {
        if current == new_guarantor {
            return true;
        }

        if let Some(neighbors) = adj.get(current) {
            for &neighbor in neighbors {
                if !visited.contains(neighbor) {
                    visited.insert(neighbor);
                    queue.push_back(neighbor);
                }
            }
        }
    }

    false
}

/// Evaluates multi-group cross exposure and anti-fraud rules
pub fn evaluate_cross_group_exposure_pure(
    user_active_rotating_groups: i32,
    max_allowed_rotating: i32,
    has_unpaid_hit_and_run: bool,
    late_obligations_count: i32,
    historical_penalties: i32,
    max_historical_penalties: i32,
    user_trust_score: i32,
    min_trust_score: Option<i32>,
    user_kyc_tier: i32,
    min_kyc_tier: i32,
    is_payout_order_locked: bool,
) -> CrossGroupRiskDecision {
    if is_payout_order_locked {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_CYCLE_LOCKED".to_string(),
            rejection_reason: Some("The payout cycle has already started. You cannot join mid-way.".to_string()),
        };
    }

    if user_active_rotating_groups >= max_allowed_rotating {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_OVER_CAPACITY".to_string(),
            rejection_reason: Some(format!(
                "You are already in {} active rotating groups. Maximum allowed is {}.",
                user_active_rotating_groups, max_allowed_rotating
            )),
        };
    }

    if has_unpaid_hit_and_run {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_HIT_AND_RUN".to_string(),
            rejection_reason: Some(
                "You have received a payout in another group but still owe contributions to that cycle.".to_string(),
            ),
        };
    }

    if late_obligations_count > 0 {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_ARREARS".to_string(),
            rejection_reason: Some(
                "You currently have an unpaid missed payment or arrears in another group.".to_string(),
            ),
        };
    }

    if historical_penalties >= max_historical_penalties {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_PENALTIES".to_string(),
            rejection_reason: Some(format!(
                "Your account has a history of slow payments ({} penalties). You are restricted from joining new groups.",
                historical_penalties
            )),
        };
    }

    if let Some(req_trust) = min_trust_score {
        if user_trust_score < req_trust {
            return CrossGroupRiskDecision {
                is_eligible: false,
                risk_tier: "REJECTED_TRUST_SCORE".to_string(),
                rejection_reason: Some(format!(
                    "Your Trust Score ({}) is below the required {}.",
                    user_trust_score, req_trust
                )),
            };
        }
    }

    if user_kyc_tier < min_kyc_tier {
        return CrossGroupRiskDecision {
            is_eligible: false,
            risk_tier: "REJECTED_KYC".to_string(),
            rejection_reason: Some(format!(
                "You need KYC Tier {} to join this group. Current tier: {}.",
                min_kyc_tier, user_kyc_tier
            )),
        };
    }

    CrossGroupRiskDecision {
        is_eligible: true,
        risk_tier: "APPROVED".to_string(),
        rejection_reason: None,
    }
}

/// Evaluates dynamic guarantor risk capacity based on trust score and contribution history
pub fn evaluate_guarantor_capacity_pure(
    guarantor_trust_score: i32,
    min_guarantor_trust_score: i32,
    bad_obligations_count: i32,
    total_contributed_minor: i64,
    current_active_liability_minor: i64,
    new_pledge_minor: i64,
    base_allowance_minor: i64,
) -> GuarantorCapacityResult {
    if bad_obligations_count > 0 {
        return GuarantorCapacityResult {
            is_approved: false,
            dynamic_max_liability_minor: 0,
            total_projected_liability_minor: current_active_liability_minor + new_pledge_minor,
            remaining_capacity_minor: 0,
            rejection_reason: Some(
                "Guarantor currently has overdue or defaulted payments and cannot take on risk.".to_string(),
            ),
        };
    }

    if guarantor_trust_score < min_guarantor_trust_score {
        return GuarantorCapacityResult {
            is_approved: false,
            dynamic_max_liability_minor: 0,
            total_projected_liability_minor: current_active_liability_minor + new_pledge_minor,
            remaining_capacity_minor: 0,
            rejection_reason: Some(format!(
                "Guarantor has a Trust Score of {}. A minimum of {} is required to vouch for others.",
                guarantor_trust_score, min_guarantor_trust_score
            )),
        };
    }

    let historical_weight = (total_contributed_minor
        .saturating_mul(5)
        .saturating_mul(guarantor_trust_score as i64))
        / 100;

    let dynamic_max_liability = std::cmp::max(base_allowance_minor, historical_weight);
    let total_projected = current_active_liability_minor.saturating_add(new_pledge_minor);

    if total_projected > dynamic_max_liability {
        return GuarantorCapacityResult {
            is_approved: false,
            dynamic_max_liability_minor: dynamic_max_liability,
            total_projected_liability_minor: total_projected,
            remaining_capacity_minor: 0,
            rejection_reason: Some(format!(
                "Guarantor is over-leveraged. Dynamic risk capacity is {} UGX, projected liability is {} UGX.",
                dynamic_max_liability, total_projected
            )),
        };
    }

    let remaining = dynamic_max_liability.saturating_sub(total_projected);
    GuarantorCapacityResult {
        is_approved: true,
        dynamic_max_liability_minor: dynamic_max_liability,
        total_projected_liability_minor: total_projected,
        remaining_capacity_minor: remaining,
        rejection_reason: None,
    }
}

// ----------------- PyO3 Bindings -----------------

#[pyfunction]
pub fn detect_guarantor_cycle(
    existing_edges: Vec<(String, String)>,
    new_guarantor: String,
    new_borrower: String,
) -> bool {
    detect_guarantor_cycle_pure(&existing_edges, &new_guarantor, &new_borrower)
}

#[pyfunction]
#[pyo3(signature = (
    user_active_rotating_groups,
    max_allowed_rotating=10,
    has_unpaid_hit_and_run=false,
    late_obligations_count=0,
    historical_penalties=0,
    max_historical_penalties=3,
    user_trust_score=50,
    min_trust_score=None,
    user_kyc_tier=1,
    min_kyc_tier=1,
    is_payout_order_locked=false
))]
pub fn evaluate_cross_group_exposure(
    user_active_rotating_groups: i32,
    max_allowed_rotating: i32,
    has_unpaid_hit_and_run: bool,
    late_obligations_count: i32,
    historical_penalties: i32,
    max_historical_penalties: i32,
    user_trust_score: i32,
    min_trust_score: Option<i32>,
    user_kyc_tier: i32,
    min_kyc_tier: i32,
    is_payout_order_locked: bool,
) -> PyResult<String> {
    let res = evaluate_cross_group_exposure_pure(
        user_active_rotating_groups,
        max_allowed_rotating,
        has_unpaid_hit_and_run,
        late_obligations_count,
        historical_penalties,
        max_historical_penalties,
        user_trust_score,
        min_trust_score,
        user_kyc_tier,
        min_kyc_tier,
        is_payout_order_locked,
    );
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (
    guarantor_trust_score,
    total_contributed_minor,
    current_active_liability_minor,
    new_pledge_minor,
    bad_obligations_count=0,
    min_guarantor_trust_score=70,
    base_allowance_minor=500_000
))]
pub fn evaluate_guarantor_capacity(
    guarantor_trust_score: i32,
    total_contributed_minor: i64,
    current_active_liability_minor: i64,
    new_pledge_minor: i64,
    bad_obligations_count: i32,
    min_guarantor_trust_score: i32,
    base_allowance_minor: i64,
) -> PyResult<String> {
    let res = evaluate_guarantor_capacity_pure(
        guarantor_trust_score,
        min_guarantor_trust_score,
        bad_obligations_count,
        total_contributed_minor,
        current_active_liability_minor,
        new_pledge_minor,
        base_allowance_minor,
    );
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cycle_detection() {
        let edges = vec![
            ("UserA".to_string(), "UserB".to_string()),
            ("UserB".to_string(), "UserC".to_string()),
        ];
        assert_eq!(detect_guarantor_cycle_pure(&edges, "UserC", "UserA"), true);
        assert_eq!(detect_guarantor_cycle_pure(&edges, "UserD", "UserA"), false);
        assert_eq!(detect_guarantor_cycle_pure(&edges, "UserX", "UserX"), true);
    }

    #[test]
    fn test_cross_group_exposure() {
        let ok = evaluate_cross_group_exposure_pure(
            2, 10, false, 0, 0, 3, 80, Some(70), 2, 1, false,
        );
        assert!(ok.is_eligible);

        let hit_and_run = evaluate_cross_group_exposure_pure(
            2, 10, true, 0, 0, 3, 80, Some(70), 2, 1, false,
        );
        assert!(!hit_and_run.is_eligible);
        assert_eq!(hit_and_run.risk_tier, "REJECTED_HIT_AND_RUN");
    }

    #[test]
    fn test_guarantor_capacity() {
        let res = evaluate_guarantor_capacity_pure(
            80, 70, 0, 100_000, 200_000, 250_000, 500_000,
        );
        assert!(res.is_approved);
        assert_eq!(res.dynamic_max_liability_minor, 500_000);
        assert_eq!(res.remaining_capacity_minor, 50_000);

        let over = evaluate_guarantor_capacity_pure(
            80, 70, 0, 100_000, 300_000, 250_000, 500_000,
        );
        assert!(!over.is_approved);
    }
}
