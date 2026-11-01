use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmergencyClaimEvaluationResult {
    pub is_eligible: bool,
    pub status: String, // "APPROVED", "REJECTED"
    pub reason: Option<String>,
    pub requested_amount: i64,
    pub net_disbursable: i64,
    pub remaining_reserve: i64,
    pub remaining_member_annual_limit: i64,
}

pub fn evaluate_emergency_claim_pure(
    current_balance: i64,
    minimum_reserve_balance: i64,
    requested_amount: i64,
    max_claim_per_incident: i64,
    member_annual_claimed: i64,
    annual_limit: i64,
    member_in_arrears: bool,
    missed_payment_action: &str,
) -> EmergencyClaimEvaluationResult {
    if requested_amount <= 0 {
        return EmergencyClaimEvaluationResult {
            is_eligible: false,
            status: "REJECTED".to_string(),
            reason: Some("Requested amount must be greater than zero.".to_string()),
            requested_amount,
            net_disbursable: 0,
            remaining_reserve: current_balance,
            remaining_member_annual_limit: (annual_limit - member_annual_claimed).max(0),
        };
    }

    if member_in_arrears && missed_payment_action == "SUSPEND_CLAIM_RIGHTS" {
        return EmergencyClaimEvaluationResult {
            is_eligible: false,
            status: "REJECTED".to_string(),
            reason: Some("Member emergency claim rights are suspended due to arrears in routine dues.".to_string()),
            requested_amount,
            net_disbursable: 0,
            remaining_reserve: current_balance,
            remaining_member_annual_limit: (annual_limit - member_annual_claimed).max(0),
        };
    }

    if requested_amount > max_claim_per_incident {
        return EmergencyClaimEvaluationResult {
            is_eligible: false,
            status: "REJECTED".to_string(),
            reason: Some(format!(
                "Requested amount (UGX {}) exceeds maximum per-incident claim cap of UGX {}.",
                requested_amount, max_claim_per_incident
            )),
            requested_amount,
            net_disbursable: 0,
            remaining_reserve: current_balance,
            remaining_member_annual_limit: (annual_limit - member_annual_claimed).max(0),
        };
    }

    let total_annual_after = member_annual_claimed + requested_amount;
    if total_annual_after > annual_limit {
        return EmergencyClaimEvaluationResult {
            is_eligible: false,
            status: "REJECTED".to_string(),
            reason: Some(format!(
                "Requested amount breaches annual member claim limit. Already claimed: UGX {}, Requested: UGX {}, Annual Limit: UGX {}.",
                member_annual_claimed, requested_amount, annual_limit
            )),
            requested_amount,
            net_disbursable: 0,
            remaining_reserve: current_balance,
            remaining_member_annual_limit: (annual_limit - member_annual_claimed).max(0),
        };
    }

    if (current_balance - requested_amount) < minimum_reserve_balance {
        let max_available = (current_balance - minimum_reserve_balance).max(0);
        return EmergencyClaimEvaluationResult {
            is_eligible: false,
            status: "REJECTED".to_string(),
            reason: Some(format!(
                "Insufficient fund reserve balance. The fund requires maintaining a minimum reserve of UGX {}. Maximum available for disbursement is UGX {}.",
                minimum_reserve_balance, max_available
            )),
            requested_amount,
            net_disbursable: 0,
            remaining_reserve: current_balance,
            remaining_member_annual_limit: (annual_limit - member_annual_claimed).max(0),
        };
    }

    let remaining_reserve = current_balance - requested_amount;
    let remaining_annual = (annual_limit - total_annual_after).max(0);

    EmergencyClaimEvaluationResult {
        is_eligible: true,
        status: "APPROVED".to_string(),
        reason: None,
        requested_amount,
        net_disbursable: requested_amount,
        remaining_reserve,
        remaining_member_annual_limit: remaining_annual,
    }
}

#[pyfunction]
#[pyo3(signature = (
    current_balance,
    minimum_reserve_balance,
    requested_amount,
    max_claim_per_incident,
    member_annual_claimed,
    annual_limit,
    member_in_arrears,
    missed_payment_action
))]
pub fn evaluate_emergency_claim(
    current_balance: i64,
    minimum_reserve_balance: i64,
    requested_amount: i64,
    max_claim_per_incident: i64,
    member_annual_claimed: i64,
    annual_limit: i64,
    member_in_arrears: bool,
    missed_payment_action: &str,
) -> PyResult<String> {
    let res = evaluate_emergency_claim_pure(
        current_balance,
        minimum_reserve_balance,
        requested_amount,
        max_claim_per_incident,
        member_annual_claimed,
        annual_limit,
        member_in_arrears,
        missed_payment_action,
    );
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_claim_approved() {
        let res = evaluate_emergency_claim_pure(
            5_000_000, 1_000_000, 500_000, 1_000_000, 200_000, 2_000_000, false, "SUSPEND_CLAIM_RIGHTS"
        );
        assert!(res.is_eligible);
        assert_eq!(res.status, "APPROVED");
        assert_eq!(res.net_disbursable, 500_000);
        assert_eq!(res.remaining_reserve, 4_500_000);
    }

    #[test]
    fn test_claim_rejected_arrears() {
        let res = evaluate_emergency_claim_pure(
            5_000_000, 1_000_000, 500_000, 1_000_000, 0, 2_000_000, true, "SUSPEND_CLAIM_RIGHTS"
        );
        assert!(!res.is_eligible);
        assert_eq!(res.status, "REJECTED");
    }

    #[test]
    fn test_claim_rejected_exceeds_incident_cap() {
        let res = evaluate_emergency_claim_pure(
            5_000_000, 1_000_000, 1_500_000, 1_000_000, 0, 2_000_000, false, "SUSPEND_CLAIM_RIGHTS"
        );
        assert!(!res.is_eligible);
        assert_eq!(res.status, "REJECTED");
    }

    #[test]
    fn test_claim_rejected_insufficient_reserve() {
        // Balance is 1,200,000, reserve is 1,000,000, requested is 500,000 (only 200,000 available)
        let res = evaluate_emergency_claim_pure(
            1_200_000, 1_000_000, 500_000, 1_000_000, 0, 2_000_000, false, "SUSPEND_CLAIM_RIGHTS"
        );
        assert!(!res.is_eligible);
        assert_eq!(res.status, "REJECTED");
    }
}

