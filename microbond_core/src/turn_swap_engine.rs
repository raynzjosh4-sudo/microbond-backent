use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemberTurnState {
    pub user_id: String,
    pub assigned_cycle: i32,
    pub membership_status: String,
    pub has_received_payout: bool,
    pub overdue_obligations_count: i32,
    pub unpaid_penalties_count: i32,
    pub trust_score: i32,
    pub kyc_tier: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupTurnSwapRules {
    pub current_active_cycle: i32,
    pub minimum_trust_score: i32,
    pub minimum_kyc_tier: i32,
    pub is_rotation_locked: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TurnSwapDecision {
    pub is_permitted: bool,
    pub requester_new_cycle: i32,
    pub target_new_cycle: i32,
    pub rejection_reason: Option<String>,
}

/// Validates strict invariants for payout turn position swaps between two members.
pub fn validate_turn_swap_pure(
    requester: &MemberTurnState,
    target: &MemberTurnState,
    rules: &GroupTurnSwapRules,
) -> TurnSwapDecision {
    if rules.is_rotation_locked {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Turn swapping is locked for this group by admin policy.".to_string()),
        };
    }

    if requester.user_id == target.user_id {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Cannot swap turn positions with yourself.".to_string()),
        };
    }

    if requester.membership_status != "ACTIVE" || target.membership_status != "ACTIVE" {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Both members must be in ACTIVE status to execute a turn swap.".to_string()),
        };
    }

    // Invariant 1: Neither member has already received a payout
    if requester.has_received_payout {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Requester has already received a payout in this round.".to_string()),
        };
    }
    if target.has_received_payout {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Target member has already received a payout in this round.".to_string()),
        };
    }

    // Invariant 2: Neither member has arrears or unpaid penalties
    if requester.overdue_obligations_count > 0 || requester.unpaid_penalties_count > 0 {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Requester has overdue obligations or unpaid late penalties.".to_string()),
        };
    }
    if target.overdue_obligations_count > 0 || target.unpaid_penalties_count > 0 {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some("Target member has overdue obligations or unpaid late penalties.".to_string()),
        };
    }

    // Invariant 3: Both cycles must be strictly in the future relative to current active cycle
    let earlier_cycle = requester.assigned_cycle.min(target.assigned_cycle);
    if earlier_cycle <= rules.current_active_cycle {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some(format!(
                "Cannot swap into or from cycle {} because current round is already at or past cycle {}.",
                earlier_cycle, rules.current_active_cycle
            )),
        };
    }

    // Invariant 4: Swapping to earlier cycle requires meeting group trust score and KYC requirements
    let earlier_recipient = if requester.assigned_cycle < target.assigned_cycle {
        requester
    } else {
        target
    };

    if earlier_recipient.trust_score < rules.minimum_trust_score {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some(format!(
                "Member moving to earlier cycle has trust score ({}) below group threshold ({}).",
                earlier_recipient.trust_score, rules.minimum_trust_score
            )),
        };
    }

    if earlier_recipient.kyc_tier < rules.minimum_kyc_tier {
        return TurnSwapDecision {
            is_permitted: false,
            requester_new_cycle: requester.assigned_cycle,
            target_new_cycle: target.assigned_cycle,
            rejection_reason: Some(format!(
                "Member moving to earlier cycle has KYC tier ({}) below group threshold ({}).",
                earlier_recipient.kyc_tier, rules.minimum_kyc_tier
            )),
        };
    }

    // Valid swap: requester gets target's cycle, target gets requester's cycle
    TurnSwapDecision {
        is_permitted: true,
        requester_new_cycle: target.assigned_cycle,
        target_new_cycle: requester.assigned_cycle,
        rejection_reason: None,
    }
}

// ---------------------------------------------------------------------------
// PyO3 Bindings
// ---------------------------------------------------------------------------

#[pyfunction]
pub fn validate_turn_swap_eligibility(
    requester_json: &str,
    target_json: &str,
    rules_json: &str,
) -> PyResult<String> {
    let req: MemberTurnState = serde_json::from_str(requester_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid requester JSON: {}", e)))?;
    let tgt: MemberTurnState = serde_json::from_str(target_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid target JSON: {}", e)))?;
    let rls: GroupTurnSwapRules = serde_json::from_str(rules_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid rules JSON: {}", e)))?;

    let res = validate_turn_swap_pure(&req, &tgt, &rls);
    serde_json::to_string(&res)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e)))
}
