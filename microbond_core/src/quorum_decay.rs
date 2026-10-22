use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuorumDecayParams {
    pub initial_required_approvals: i32,
    pub minimum_decay_floor_approvals: i32,
    pub decay_interval_hours: i64,
    pub max_decay_intervals: Option<i32>,
    pub enable_decay: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuorumDecayEvaluation {
    pub is_approved: bool,
    pub initial_approvals: i32,
    pub current_required_approvals: i32,
    pub current_approvals_count: i32,
    pub elapsed_hours: i64,
    pub intervals_elapsed: i64,
    pub approvals_still_needed: i32,
    pub decay_applied: bool,
    pub status: String, // "APPROVED_IMMEDIATE" | "APPROVED_BY_DECAY" | "PENDING_APPROVALS" | "DECAY_DISABLED"
}

/// Pure calculation of Time-Locked Quorum Decay (TLQD).
/// Prevents unresponsive signers from permanently locking pooled shared funds.
pub fn calculate_decayed_quorum_pure(
    params: &QuorumDecayParams,
    request_created_at_epoch_ms: i64,
    current_time_epoch_ms: i64,
    current_approvals_count: i32,
) -> QuorumDecayEvaluation {
    if !params.enable_decay || params.decay_interval_hours <= 0 {
        let needed = (params.initial_required_approvals - current_approvals_count).max(0);
        let approved = current_approvals_count >= params.initial_required_approvals;
        return QuorumDecayEvaluation {
            is_approved: approved,
            initial_approvals: params.initial_required_approvals,
            current_required_approvals: params.initial_required_approvals,
            current_approvals_count,
            elapsed_hours: 0,
            intervals_elapsed: 0,
            approvals_still_needed: needed,
            decay_applied: false,
            status: if approved {
                "APPROVED_IMMEDIATE".to_string()
            } else {
                "DECAY_DISABLED".to_string()
            },
        };
    }

    let elapsed_ms = (current_time_epoch_ms - request_created_at_epoch_ms).max(0);
    let elapsed_hours = elapsed_ms / (1000 * 60 * 60);

    let mut intervals = elapsed_hours / params.decay_interval_hours;
    if let Some(max_i) = params.max_decay_intervals {
        intervals = intervals.min(max_i as i64);
    }

    let decayed_quorum = if intervals > 0 {
        (params.initial_required_approvals - intervals as i32).max(params.minimum_decay_floor_approvals)
    } else {
        params.initial_required_approvals
    };

    let approvals_still_needed = (decayed_quorum - current_approvals_count).max(0);
    let is_approved = current_approvals_count >= decayed_quorum;

    let status = if is_approved {
        if decayed_quorum < params.initial_required_approvals {
            "APPROVED_BY_DECAY".to_string()
        } else {
            "APPROVED_IMMEDIATE".to_string()
        }
    } else {
        "PENDING_APPROVALS".to_string()
    };

    QuorumDecayEvaluation {
        is_approved,
        initial_approvals: params.initial_required_approvals,
        current_required_approvals: decayed_quorum,
        current_approvals_count,
        elapsed_hours,
        intervals_elapsed: intervals,
        approvals_still_needed,
        decay_applied: decayed_quorum < params.initial_required_approvals,
        status,
    }
}

// ---------------------------------------------------------------------------
// PyO3 Bindings
// ---------------------------------------------------------------------------

#[pyfunction]
pub fn calculate_decayed_quorum(
    params_json: &str,
    request_created_at_ms: i64,
    current_time_ms: i64,
    current_approvals: i32,
) -> PyResult<String> {
    let params: QuorumDecayParams = serde_json::from_str(params_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid params JSON: {}", e)))?;

    let res = calculate_decayed_quorum_pure(&params, request_created_at_ms, current_time_ms, current_approvals);
    serde_json::to_string(&res)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e)))
}
