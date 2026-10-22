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
        // Milestone is 50,000. Currently saved: 30,000. Depositing: 25,000 -> cumulative 55,000 (triggers payout fee)
        let res = calculate_flexible_rotate_deposit_pure(
            25_000,
            30_000,
            50_000,
            false,
            1_500,
            500,
            100, // 1% = 250
        ).unwrap();

        assert_eq!(res.milestone_triggered_now, true);
        assert_eq!(res.microbond_base_fee, 250);
        assert_eq!(res.hidden_payout_fee, 1_500);
        assert_eq!(res.final_charge_amount, 25_000 + 500 + 250 + 1_500);
    }
}
