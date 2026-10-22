use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscrowDecision {
    pub release_permitted: bool,
    pub status: String,
    pub rejection_reason: Option<String>,
}

/// Formally evaluates release predicates for funds held in escrow
pub fn evaluate_escrow_release_pure(
    timelock_expired: bool,
    milestones_total: i32,
    milestones_completed: i32,
    signers_required: i32,
    signatures_collected: i32,
    dispute_active: bool,
    rule_mode: &str, // "ALL_CONDITIONS", "TIMELOCK_ONLY", "CONSENSUS_ONLY", "MILESTONE_AND_CONSENSUS", "TIMELOCK_OR_CONSENSUS"
) -> EscrowDecision {
    if dispute_active {
        return EscrowDecision {
            release_permitted: false,
            status: "DISPUTED".to_string(),
            rejection_reason: Some("Escrow payout is locked due to an active dispute or arbitration filing.".to_string()),
        };
    }

    let milestones_met = milestones_total <= 0 || milestones_completed >= milestones_total;
    let consensus_met = signers_required <= 0 || signatures_collected >= signers_required;

    match rule_mode.to_uppercase().as_str() {
        "TIMELOCK_ONLY" => {
            if timelock_expired {
                EscrowDecision {
                    release_permitted: true,
                    status: "PERMITTED".to_string(),
                    rejection_reason: None,
                }
            } else {
                EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_TIMELOCK".to_string(),
                    rejection_reason: Some("Timelock has not expired yet.".to_string()),
                }
            }
        }
        "CONSENSUS_ONLY" => {
            if consensus_met {
                EscrowDecision {
                    release_permitted: true,
                    status: "PERMITTED".to_string(),
                    rejection_reason: None,
                }
            } else {
                EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_SIGNATURES".to_string(),
                    rejection_reason: Some(format!(
                        "Insufficient signatures. Required: {}, Collected: {}.",
                        signers_required, signatures_collected
                    )),
                }
            }
        }
        "MILESTONE_AND_CONSENSUS" => {
            if !milestones_met {
                return EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_MILESTONES".to_string(),
                    rejection_reason: Some(format!(
                        "Milestones incomplete. Required: {}, Completed: {}.",
                        milestones_total, milestones_completed
                    )),
                };
            }
            if !consensus_met {
                return EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_SIGNATURES".to_string(),
                    rejection_reason: Some(format!(
                        "Quorum not reached. Required signers: {}, Collected: {}.",
                        signers_required, signatures_collected
                    )),
                };
            }
            EscrowDecision {
                release_permitted: true,
                status: "PERMITTED".to_string(),
                rejection_reason: None,
            }
        }
        "TIMELOCK_OR_CONSENSUS" => {
            if timelock_expired || consensus_met {
                EscrowDecision {
                    release_permitted: true,
                    status: "PERMITTED".to_string(),
                    rejection_reason: None,
                }
            } else {
                EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_TIMELOCK_OR_CONSENSUS".to_string(),
                    rejection_reason: Some(
                        "Neither the timelock expiration nor the signature threshold has been satisfied.".to_string(),
                    ),
                }
            }
        }
        _ /* "ALL_CONDITIONS" default */ => {
            if !timelock_expired {
                return EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_TIMELOCK".to_string(),
                    rejection_reason: Some("Timelock period is still active.".to_string()),
                };
            }
            if !milestones_met {
                return EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_MILESTONES".to_string(),
                    rejection_reason: Some(format!(
                        "All milestones must be verified prior to release. {}/{} verified.",
                        milestones_completed, milestones_total
                    )),
                };
            }
            if !consensus_met {
                return EscrowDecision {
                    release_permitted: false,
                    status: "LOCKED_SIGNATURES".to_string(),
                    rejection_reason: Some(format!(
                        "Multi-sig approval quorum required. {}/{} signed.",
                        signatures_collected, signers_required
                    )),
                };
            }
            EscrowDecision {
                release_permitted: true,
                status: "PERMITTED".to_string(),
                rejection_reason: None,
            }
        }
    }
}

// ----------------- PyO3 Bindings -----------------

#[pyfunction]
#[pyo3(signature = (
    timelock_expired,
    milestones_total=0,
    milestones_completed=0,
    signers_required=0,
    signatures_collected=0,
    dispute_active=false,
    rule_mode="ALL_CONDITIONS"
))]
pub fn evaluate_escrow_release(
    timelock_expired: bool,
    milestones_total: i32,
    milestones_completed: i32,
    signers_required: i32,
    signatures_collected: i32,
    dispute_active: bool,
    rule_mode: &str,
) -> PyResult<String> {
    let res = evaluate_escrow_release_pure(
        timelock_expired,
        milestones_total,
        milestones_completed,
        signers_required,
        signatures_collected,
        dispute_active,
        rule_mode,
    );
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_escrow_dispute() {
        let res = evaluate_escrow_release_pure(true, 3, 3, 2, 2, true, "ALL_CONDITIONS");
        assert!(!res.release_permitted);
        assert_eq!(res.status, "DISPUTED");
    }

    #[test]
    fn test_escrow_all_conditions() {
        let pass = evaluate_escrow_release_pure(true, 3, 3, 2, 2, false, "ALL_CONDITIONS");
        assert!(pass.release_permitted);
        assert_eq!(pass.status, "PERMITTED");

        let fail_timelock = evaluate_escrow_release_pure(false, 3, 3, 2, 2, false, "ALL_CONDITIONS");
        assert!(!fail_timelock.release_permitted);
        assert_eq!(fail_timelock.status, "LOCKED_TIMELOCK");
    }

    #[test]
    fn test_escrow_timelock_or_consensus() {
        let res = evaluate_escrow_release_pure(false, 0, 0, 3, 3, false, "TIMELOCK_OR_CONSENSUS");
        assert!(res.release_permitted);
    }
}
