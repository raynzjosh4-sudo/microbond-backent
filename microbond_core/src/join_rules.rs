use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum JoinStatus {
    Active,
    PendingGuarantor,
    PendingApproval,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JoinDecision {
    pub status: JoinStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason_code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason_message: Option<String>,
}

pub fn evaluate_join_rules(
    member_count: i32,
    max_members: Option<i32>,
    already_member_or_pending: bool,
    has_arrears: bool,
    trust_score: i32,
    minimum_trust_score: Option<i32>,
    kyc_tier: i32,
    required_kyc_tier: i32,
    requires_guarantor: bool,
    requires_admin_approval: bool,
) -> JoinDecision {
    let reject = |code: &str, message: &str| JoinDecision {
        status: JoinStatus::Rejected,
        reason_code: Some(code.to_string()),
        reason_message: Some(message.to_string()),
    };

    if let Some(limit) = max_members {
        if member_count >= limit {
            return reject("GROUP_FULL", "Group reached maximum capacity");
        }
    }

    if already_member_or_pending {
        return reject("ALREADY_MEMBER_OR_PENDING", "Already in group or pending");
    }

    if has_arrears {
        return reject("ARREARS", "Settle missed payments first");
    }

    if let Some(min_score) = minimum_trust_score {
        if trust_score < min_score {
            return reject("TRUST_SCORE", "Trust score is below the group requirement");
        }
    }

    if kyc_tier < required_kyc_tier {
        return reject("KYC_TIER", "Complete the required KYC tier");
    }

    let status = if requires_guarantor {
        JoinStatus::PendingGuarantor
    } else if requires_admin_approval {
        JoinStatus::PendingApproval
    } else {
        JoinStatus::Active
    };

    JoinDecision {
        status,
        reason_code: None,
        reason_message: None,
    }
}

#[pyfunction]
#[pyo3(signature = (
    member_count,
    max_members=None,
    already_member_or_pending=false,
    has_arrears=false,
    trust_score=0,
    minimum_trust_score=None,
    kyc_tier=0,
    required_kyc_tier=0,
    requires_guarantor=false,
    requires_admin_approval=false
))]
pub fn check_join_rules(
    member_count: i32,
    max_members: Option<i32>,
    already_member_or_pending: bool,
    has_arrears: bool,
    trust_score: i32,
    minimum_trust_score: Option<i32>,
    kyc_tier: i32,
    required_kyc_tier: i32,
    requires_guarantor: bool,
    requires_admin_approval: bool,
) -> PyResult<String> {
    let decision = evaluate_join_rules(
        member_count,
        max_members,
        already_member_or_pending,
        has_arrears,
        trust_score,
        minimum_trust_score,
        kyc_tier,
        required_kyc_tier,
        requires_guarantor,
        requires_admin_approval,
    );

    serde_json::to_string(&decision)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capacity_rejection() {
        let decision = evaluate_join_rules(10, Some(10), false, false, 80, Some(50), 2, 1, false, false);
        assert_eq!(decision.status, JoinStatus::Rejected);
        assert_eq!(decision.reason_code.as_deref(), Some("GROUP_FULL"));
    }

    #[test]
    fn test_arrears_rejection() {
        let decision = evaluate_join_rules(5, Some(10), false, true, 80, Some(50), 2, 1, false, false);
        assert_eq!(decision.status, JoinStatus::Rejected);
        assert_eq!(decision.reason_code.as_deref(), Some("ARREARS"));
    }

    #[test]
    fn test_kyc_rejection() {
        let decision = evaluate_join_rules(5, Some(10), false, false, 80, Some(50), 1, 2, false, false);
        assert_eq!(decision.status, JoinStatus::Rejected);
        assert_eq!(decision.reason_code.as_deref(), Some("KYC_TIER"));
    }

    #[test]
    fn test_guarantor_required() {
        let decision = evaluate_join_rules(5, Some(10), false, false, 80, Some(50), 2, 1, true, false);
        assert_eq!(decision.status, JoinStatus::PendingGuarantor);
    }

    #[test]
    fn test_admin_approval_required() {
        let decision = evaluate_join_rules(5, Some(10), false, false, 80, Some(50), 2, 1, false, true);
        assert_eq!(decision.status, JoinStatus::PendingApproval);
    }

    #[test]
    fn test_active_direct_join() {
        let decision = evaluate_join_rules(5, Some(10), false, false, 80, Some(50), 2, 1, false, false);
        assert_eq!(decision.status, JoinStatus::Active);
    }
}
