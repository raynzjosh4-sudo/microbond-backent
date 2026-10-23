use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlexibleRotateDepositResult {
    pub deposit_amount: i64,
    pub base_charge_amount: i64,
    pub mtn_deposit_fee: i64,
    pub microbond_base_fee: i64,
    pub hidden_payout_fee: i64,
    pub final_charge_amount: i64,
    pub milestone_triggered_now: bool,
    pub new_cumulative_total: i64,
    pub assigned_value_milestone: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseFeeBreakdown {
    pub group_target_amount: i64,
    pub mtn_fee: i64,
    pub platform_fee: i64,
    pub total_fee: i64,
    pub charge_amount: i64,
    pub psychological_offset: i64,
    pub microbond_net_revenue: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetDepositCalculation {
    pub deposit_amount: i64,
    pub base_charge_amount: i64,
    pub mtn_deposit_fee: i64,
    pub microbond_deposit_fee: i64,
    pub hidden_payout_fee: i64,
    pub final_charge_amount: i64,
    pub is_fee_milestone: bool,
    pub milestone_triggered_now: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvestmentDepositCalculation {
    pub deposit_amount: i64,
    pub base_charge_amount: i64,
    pub mtn_deposit_fee: i64,
    pub microbond_deposit_fee: i64,
    pub hidden_payout_fee: i64,
    pub final_charge_amount: i64,
    pub is_fee_milestone: bool,
    pub this_deposit_number: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmergencyDepositCalculation {
    pub deposit_amount: i64,
    pub base_charge_amount: i64,
    pub mtn_deposit_fee: i64,
    pub microbond_deposit_fee: i64,
    pub hidden_payout_fee: i64,
    pub final_charge_amount: i64,
    pub cleared_pending_fee: bool,
    pub fees_cleared: i32,
}

pub fn get_psychological_offset_pure(amount: i64) -> i64 {
    if amount < 5_001 {
        15
    } else if amount < 10_001 {
        16
    } else if amount < 20_001 {
        17
    } else if amount < 50_001 {
        18
    } else if amount < 100_001 {
        19
    } else if amount < 500_001 {
        21
    } else {
        22
    }
}

pub fn calculate_base_deposit_fee_pure(group_target_amount: i64) -> Result<BaseFeeBreakdown, String> {
    if group_target_amount <= 0 {
        return Err("group_target_amount must be a positive integer".to_string());
    }

    let offset = get_psychological_offset_pure(group_target_amount);
    let mtn_fee = ((group_target_amount as f64) * 0.015).round() as i64;
    let platform_fee = (mtn_fee - offset).max(0);
    let total_fee = mtn_fee + platform_fee;
    let charge_amount = group_target_amount + total_fee;

    Ok(BaseFeeBreakdown {
        group_target_amount,
        mtn_fee,
        platform_fee,
        total_fee,
        charge_amount,
        psychological_offset: offset,
        microbond_net_revenue: platform_fee,
    })
}

pub fn calculate_target_deposit_fee_pure(
    deposit_amount: i64,
    current_saved_amount: i64,
    target_goal_amount: i64,
    assigned_milestone_threshold: f64,
    fee_already_collected: bool,
    target_payout_fee: i64,
) -> Result<TargetDepositCalculation, String> {
    if deposit_amount <= 0 {
        return Err("deposit_amount must be a positive integer".to_string());
    }
    if target_goal_amount <= 0 {
        return Err("target_goal_amount must be a positive integer".to_string());
    }

    let base = calculate_base_deposit_fee_pure(deposit_amount)?;
    let new_cumulative = current_saved_amount + deposit_amount;
    let threshold_amount = ((target_goal_amount as f64) * assigned_milestone_threshold).round() as i64;

    let should_charge_milestone = !fee_already_collected
        && (new_cumulative >= threshold_amount || new_cumulative >= target_goal_amount);

    let payout_fee = if should_charge_milestone {
        target_payout_fee
    } else {
        0
    };
    let final_charge = base.charge_amount + payout_fee;

    Ok(TargetDepositCalculation {
        deposit_amount,
        base_charge_amount: base.charge_amount,
        mtn_deposit_fee: base.mtn_fee,
        microbond_deposit_fee: base.platform_fee,
        hidden_payout_fee: payout_fee,
        final_charge_amount: final_charge,
        is_fee_milestone: should_charge_milestone,
        milestone_triggered_now: should_charge_milestone,
    })
}

pub fn calculate_investment_deposit_fee_pure(
    deposit_amount: i64,
    current_annual_deposit_count: i32,
    assigned_milestone_count: i32,
    fee_collected_this_year: bool,
    target_payout_fee: i64,
) -> Result<InvestmentDepositCalculation, String> {
    if deposit_amount <= 0 {
        return Err("deposit_amount must be a positive integer".to_string());
    }

    let base = calculate_base_deposit_fee_pure(deposit_amount)?;
    let this_deposit_number = current_annual_deposit_count + 1;

    let should_charge_milestone = !fee_collected_this_year && (this_deposit_number >= assigned_milestone_count);
    let payout_fee = if should_charge_milestone {
        target_payout_fee
    } else {
        0
    };
    let final_charge = base.charge_amount + payout_fee;

    Ok(InvestmentDepositCalculation {
        deposit_amount,
        base_charge_amount: base.charge_amount,
        mtn_deposit_fee: base.mtn_fee,
        microbond_deposit_fee: base.platform_fee,
        hidden_payout_fee: payout_fee,
        final_charge_amount: final_charge,
        is_fee_milestone: should_charge_milestone,
        this_deposit_number,
    })
}

pub fn calculate_emergency_deposit_fee_pure(
    deposit_amount: i64,
    group_pending_payout_fees_count: i32,
    target_payout_fee: i64,
) -> Result<EmergencyDepositCalculation, String> {
    if deposit_amount <= 0 {
        return Err("deposit_amount must be a positive integer".to_string());
    }
    if group_pending_payout_fees_count < 0 {
        return Err("group_pending_payout_fees_count cannot be negative".to_string());
    }

    let base = calculate_base_deposit_fee_pure(deposit_amount)?;
    let fees_to_clear = group_pending_payout_fees_count;
    let total_payout_fee = (fees_to_clear as i64) * target_payout_fee;
    let final_charge = base.charge_amount + total_payout_fee;

    Ok(EmergencyDepositCalculation {
        deposit_amount,
        base_charge_amount: base.charge_amount,
        mtn_deposit_fee: base.mtn_fee,
        microbond_deposit_fee: base.platform_fee,
        hidden_payout_fee: total_payout_fee,
        final_charge_amount: final_charge,
        cleared_pending_fee: fees_to_clear > 0,
        fees_cleared: fees_to_clear,
    })
}

pub fn calculate_flexible_rotate_deposit_pure(
    deposit_amount: i64,
    current_saved_amount: i64,
    assigned_value_milestone: i64,
    fee_already_collected: bool,
    target_payout_fee: i64,
    mtn_flat_fee: i64,
    platform_fee_bps: i32,
) -> Result<FlexibleRotateDepositResult, String> {
    if deposit_amount <= 0 {
        return Err("deposit_amount must be positive".to_string());
    }
    if assigned_value_milestone <= 0 {
        return Err("assigned_value_milestone must be positive".to_string());
    }

    let platform_fee = (deposit_amount
        .checked_mul(platform_fee_bps as i64)
        .ok_or_else(|| "Platform fee calculation overflowed".to_string())?)
        / 10_000;

    let base_charge = deposit_amount
        .checked_add(mtn_flat_fee)
        .and_then(|val| val.checked_add(platform_fee))
        .ok_or_else(|| "Base charge calculation overflowed".to_string())?;

    let new_cumulative = current_saved_amount
        .checked_add(deposit_amount)
        .ok_or_else(|| "Cumulative savings overflowed".to_string())?;

    let should_trigger = !fee_already_collected && new_cumulative >= assigned_value_milestone;

    let payout_fee = if should_trigger {
        target_payout_fee
    } else {
        0
    };

    let final_charge = base_charge
        .checked_add(payout_fee)
        .ok_or_else(|| "Final charge calculation overflowed".to_string())?;

    Ok(FlexibleRotateDepositResult {
        deposit_amount,
        base_charge_amount: base_charge,
        mtn_deposit_fee: mtn_flat_fee,
        microbond_base_fee: platform_fee,
        hidden_payout_fee: payout_fee,
        final_charge_amount: final_charge,
        milestone_triggered_now: should_trigger,
        new_cumulative_total: new_cumulative,
        assigned_value_milestone,
    })
}

#[pyfunction]
#[pyo3(signature = (group_target_amount))]
pub fn calculate_base_deposit_fee(group_target_amount: i64) -> PyResult<String> {
    calculate_base_deposit_fee_pure(group_target_amount)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
        .and_then(|res| {
            serde_json::to_string(&res)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
        })
}

#[pyfunction]
#[pyo3(signature = (
    deposit_amount,
    current_saved_amount,
    target_goal_amount,
    assigned_milestone_threshold,
    fee_already_collected=false,
    target_payout_fee=979
))]
pub fn calculate_target_deposit_fee(
    deposit_amount: i64,
    current_saved_amount: i64,
    target_goal_amount: i64,
    assigned_milestone_threshold: f64,
    fee_already_collected: bool,
    target_payout_fee: i64,
) -> PyResult<String> {
    calculate_target_deposit_fee_pure(
        deposit_amount,
        current_saved_amount,
        target_goal_amount,
        assigned_milestone_threshold,
        fee_already_collected,
        target_payout_fee,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[pyfunction]
#[pyo3(signature = (
    deposit_amount,
    current_annual_deposit_count,
    assigned_milestone_count,
    fee_collected_this_year=false,
    target_payout_fee=979
))]
pub fn calculate_investment_deposit_fee(
    deposit_amount: i64,
    current_annual_deposit_count: i32,
    assigned_milestone_count: i32,
    fee_collected_this_year: bool,
    target_payout_fee: i64,
) -> PyResult<String> {
    calculate_investment_deposit_fee_pure(
        deposit_amount,
        current_annual_deposit_count,
        assigned_milestone_count,
        fee_collected_this_year,
        target_payout_fee,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[pyfunction]
#[pyo3(signature = (
    deposit_amount,
    group_pending_payout_fees_count,
    target_payout_fee=979
))]
pub fn calculate_emergency_deposit_fee(
    deposit_amount: i64,
    group_pending_payout_fees_count: i32,
    target_payout_fee: i64,
) -> PyResult<String> {
    calculate_emergency_deposit_fee_pure(
        deposit_amount,
        group_pending_payout_fees_count,
        target_payout_fee,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[pyfunction]
#[pyo3(signature = (
    deposit_amount,
    current_saved_amount,
    assigned_value_milestone,
    fee_already_collected=false,
    target_payout_fee=1500,
    mtn_flat_fee=500,
    platform_fee_bps=100
))]
pub fn calculate_flexible_rotate_deposit(
    deposit_amount: i64,
    current_saved_amount: i64,
    assigned_value_milestone: i64,
    fee_already_collected: bool,
    target_payout_fee: i64,
    mtn_flat_fee: i64,
    platform_fee_bps: i32,
) -> PyResult<String> {
    calculate_flexible_rotate_deposit_pure(
        deposit_amount,
        current_saved_amount,
        assigned_value_milestone,
        fee_already_collected,
        target_payout_fee,
        mtn_flat_fee,
        platform_fee_bps,
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    .and_then(|res| {
        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_milestone_trigger() {
        let res = calculate_flexible_rotate_deposit_pure(
            25_000,
            30_000,
            50_000,
            false,
            1_500,
            500,
            100,
        ).unwrap();

        assert_eq!(res.milestone_triggered_now, true);
        assert_eq!(res.microbond_base_fee, 250);
        assert_eq!(res.hidden_payout_fee, 1_500);
        assert_eq!(res.final_charge_amount, 25_000 + 500 + 250 + 1_500);
    }

    #[test]
    fn test_base_deposit_fee() {
        let res = calculate_base_deposit_fee_pure(10_000).unwrap();
        assert_eq!(res.group_target_amount, 10_000);
        assert_eq!(res.psychological_offset, 16);
        assert_eq!(res.mtn_fee, 150); // 1.5% of 10,000 = 150
        assert_eq!(res.platform_fee, 150 - 16); // 134
        assert_eq!(res.charge_amount, 10_000 + 150 + 134);
    }

    #[test]
    fn test_target_deposit_fee() {
        let res = calculate_target_deposit_fee_pure(
            20_000,
            35_000,
            100_000,
            0.50,
            false,
            979,
        ).unwrap();
        // new_cumulative = 55_000 >= 50_000 -> triggers
        assert_eq!(res.is_fee_milestone, true);
        assert_eq!(res.hidden_payout_fee, 979);
        assert_eq!(res.final_charge_amount, res.base_charge_amount + 979);
    }

    #[test]
    fn test_investment_deposit_fee() {
        let res = calculate_investment_deposit_fee_pure(
            50_000,
            3, // this is deposit #4
            4,
            false,
            979,
        ).unwrap();
        assert_eq!(res.this_deposit_number, 4);
        assert_eq!(res.is_fee_milestone, true);
        assert_eq!(res.hidden_payout_fee, 979);
    }

    #[test]
    fn test_emergency_deposit_fee() {
        let res = calculate_emergency_deposit_fee_pure(
            20_000,
            2, // 2 queued emergency fees
            979,
        ).unwrap();
        assert_eq!(res.cleared_pending_fee, true);
        assert_eq!(res.fees_cleared, 2);
        assert_eq!(res.hidden_payout_fee, 2 * 979);
    }
}
