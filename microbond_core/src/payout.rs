use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RotatingPayoutResult {
    pub payout_minor: i64,
    pub penalty_minor: i64,
    pub net_payout_minor: i64,
    pub currency: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PenaltyResult {
    pub penalty_minor: i64,
    pub is_late: bool,
    pub late_days: i32,
    pub currency: String,
}

pub fn evaluate_rotating_payout(
    contribution_minor: i64,
    member_count: i32,
    late_days: i32,
    grace_period_days: i32,
    late_fee_minor: i64,
) -> Result<RotatingPayoutResult, String> {
    if contribution_minor <= 0 {
        return Err("Contribution amount must be greater than zero".to_string());
    }
    if member_count <= 0 {
        return Err("Member count must be greater than zero".to_string());
    }

    let payout_minor = contribution_minor
        .checked_mul(member_count as i64)
        .ok_or_else(|| "Payout calculation caused integer overflow".to_string())?;

    let penalty_minor = if late_days > grace_period_days {
        late_fee_minor.max(0)
    } else {
        0
    };

    let net_payout_minor = payout_minor.saturating_sub(penalty_minor);

    Ok(RotatingPayoutResult {
        payout_minor,
        penalty_minor,
        net_payout_minor,
        currency: "UGX".to_string(),
    })
}

pub fn evaluate_penalty(
    amount_minor: i64,
    late_days: i32,
    grace_period_days: i32,
    penalty_fixed_minor: i64,
    penalty_daily_rate_bps: i32,
) -> Result<PenaltyResult, String> {
    if late_days <= grace_period_days {
        return Ok(PenaltyResult {
            penalty_minor: 0,
            is_late: false,
            late_days: late_days.max(0),
            currency: "UGX".to_string(),
        });
    }

    let overdue_days = (late_days - grace_period_days) as i64;
    // BPS = basis points (1 bps = 0.01% = 1/10000)
    let daily_penalty = amount_minor
        .checked_mul(penalty_daily_rate_bps as i64)
        .map(|val| val / 10_000)
        .unwrap_or(0);

    let variable_penalty = daily_penalty
        .checked_mul(overdue_days)
        .unwrap_or(0);

    let total_penalty = penalty_fixed_minor
        .checked_add(variable_penalty)
        .unwrap_or(penalty_fixed_minor);

    Ok(PenaltyResult {
        penalty_minor: total_penalty.max(0),
        is_late: true,
        late_days,
        currency: "UGX".to_string(),
    })
}

#[pyfunction]
#[pyo3(signature = (
    contribution_minor,
    member_count,
    late_days=0,
    grace_period_days=0,
    late_fee_minor=0
))]
pub fn calculate_rotating_payout(
    contribution_minor: i64,
    member_count: i32,
    late_days: i32,
    grace_period_days: i32,
    late_fee_minor: i64,
) -> PyResult<String> {
    evaluate_rotating_payout(
        contribution_minor,
        member_count,
        late_days,
        grace_period_days,
        late_fee_minor,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[pyfunction]
#[pyo3(signature = (
    amount_minor,
    late_days,
    grace_period_days=0,
    penalty_fixed_minor=0,
    penalty_daily_rate_bps=0
))]
pub fn calculate_penalty(
    amount_minor: i64,
    late_days: i32,
    grace_period_days: i32,
    penalty_fixed_minor: i64,
    penalty_daily_rate_bps: i32,
) -> PyResult<String> {
    evaluate_penalty(
        amount_minor,
        late_days,
        grace_period_days,
        penalty_fixed_minor,
        penalty_daily_rate_bps,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LiquidityReserveDecision {
    pub is_permitted: bool,
    pub total_balance_minor: i64,
    pub locked_buffer_minor: i64,
    pub max_available_disbursal_minor: i64,
    pub requested_disbursal_minor: i64,
    pub shortfall_minor: i64,
    pub rejection_reason: Option<String>,
}

pub fn evaluate_liquidity_reserve_pure(
    total_balance_minor: i64,
    buffer_percentage: f64,
    requested_disbursal_minor: i64,
) -> LiquidityReserveDecision {
    let pct = buffer_percentage.clamp(0.0, 100.0);
    let locked_buffer_minor = ((total_balance_minor.max(0) as f64) * (pct / 100.0)).round() as i64;
    let max_available = (total_balance_minor.saturating_sub(locked_buffer_minor)).max(0);

    if requested_disbursal_minor <= max_available {
        LiquidityReserveDecision {
            is_permitted: true,
            total_balance_minor,
            locked_buffer_minor,
            max_available_disbursal_minor: max_available,
            requested_disbursal_minor,
            shortfall_minor: 0,
            rejection_reason: None,
        }
    } else {
        let shortfall = requested_disbursal_minor - max_available;
        LiquidityReserveDecision {
            is_permitted: false,
            total_balance_minor,
            locked_buffer_minor,
            max_available_disbursal_minor: max_available,
            requested_disbursal_minor,
            shortfall_minor: shortfall,
            rejection_reason: Some(format!(
                "Requested disbursal of {} UGX breaches the {}% liquidity buffer. Maximum permitted disbursal is {} UGX.",
                requested_disbursal_minor, pct, max_available
            )),
        }
    }
}

#[pyfunction]
#[pyo3(signature = (
    total_balance_minor,
    buffer_percentage,
    requested_disbursal_minor
))]
pub fn evaluate_liquidity_reserve(
    total_balance_minor: i64,
    buffer_percentage: f64,
    requested_disbursal_minor: i64,
) -> PyResult<String> {
    let res = evaluate_liquidity_reserve_pure(
        total_balance_minor,
        buffer_percentage,
        requested_disbursal_minor,
    );
    serde_json::to_string(&res)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalatedLateFeeResult {
    pub base_fee_minor: i64,
    pub total_late_fee_minor: i64,
    pub late_days: i32,
    pub escalation_multiplier: f64,
    pub is_escalated: bool,
}

pub fn calculate_escalated_late_fee_pure(
    base_fee_minor: i64,
    late_days: i32,
    grace_period_days: i32,
    escalation_enabled: bool,
) -> EscalatedLateFeeResult {
    if late_days <= grace_period_days {
        return EscalatedLateFeeResult {
            base_fee_minor,
            total_late_fee_minor: 0,
            late_days: late_days.max(0),
            escalation_multiplier: 1.0,
            is_escalated: false,
        };
    }

    let overdue_days = late_days - grace_period_days;
    if !escalation_enabled {
        return EscalatedLateFeeResult {
            base_fee_minor,
            total_late_fee_minor: base_fee_minor,
            late_days,
            escalation_multiplier: 1.0,
            is_escalated: false,
        };
    }

    let multiplier = if overdue_days <= 7 {
        1.0
    } else if overdue_days <= 14 {
        1.5
    } else {
        2.0
    };

    let total_late_fee_minor = ((base_fee_minor as f64) * multiplier).round() as i64;

    EscalatedLateFeeResult {
        base_fee_minor,
        total_late_fee_minor,
        late_days,
        escalation_multiplier: multiplier,
        is_escalated: multiplier > 1.0,
    }
}

#[pyfunction]
#[pyo3(signature = (
    base_fee_minor,
    late_days,
    grace_period_days=0,
    escalation_enabled=true
))]
pub fn calculate_escalated_late_fee(
    base_fee_minor: i64,
    late_days: i32,
    grace_period_days: i32,
    escalation_enabled: bool,
) -> PyResult<String> {
    let res = calculate_escalated_late_fee_pure(
        base_fee_minor,
        late_days,
        grace_period_days,
        escalation_enabled,
    );
    serde_json::to_string(&res)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}



#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_rotating_payout() {
        let result = evaluate_rotating_payout(50_000_00, 10, 0, 3, 5_000_00).unwrap();
        assert_eq!(result.payout_minor, 500_000_00);
        assert_eq!(result.penalty_minor, 0);
        assert_eq!(result.net_payout_minor, 500_000_00);
        assert_eq!(result.currency, "UGX");
    }

    #[test]
    fn test_late_penalty_applied() {
        let result = evaluate_rotating_payout(50_000_00, 10, 5, 3, 5_000_00).unwrap();
        assert_eq!(result.payout_minor, 500_000_00);
        assert_eq!(result.penalty_minor, 5_000_00);
        assert_eq!(result.net_payout_minor, 495_000_00);
    }

    #[test]
    fn test_invalid_negative_contribution() {
        let err = evaluate_rotating_payout(-100, 10, 0, 0, 0);
        assert!(err.is_err());
    }

    #[test]
    fn test_overflow_protection() {
        let err = evaluate_rotating_payout(i64::MAX, 2, 0, 0, 0);
        assert!(err.is_err());
    }
}
