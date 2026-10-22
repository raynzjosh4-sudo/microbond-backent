use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObligationItem {
    pub cycle_number: i32,
    pub user_id: String,
    pub amount_due: i64,
    pub amount_paid: i64,
    pub due_date: i64,
    pub status: String,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PayoutItem {
    pub cycle_number: i32,
    pub user_id: Option<String>,
    pub amount_expected: i64,
    pub amount_collected: i64,
    pub status: String,
    pub payout_date: i64,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CycleMatrixResult {
    pub num_cycles: i32,
    pub member_count: usize,
    pub gross_pool_minor: i64,
    pub reserve_held_minor: i64,
    pub net_payout_minor: i64,
    pub obligations: Vec<ObligationItem>,
    pub payouts: Vec<PayoutItem>,
}

pub fn generate_cycle_matrix_pure(
    member_user_ids: &[String],
    group_type: &str,
    contribution_minor: i64,
    payouts_per_cycle: i32,
    reserve_fund_bps: i32,
    collection_frequency_days: i32,
    start_epoch_seconds: i64,
    created_at_epoch_seconds: i64,
) -> Result<CycleMatrixResult, String> {
    if member_user_ids.is_empty() {
        return Err("Member list cannot be empty".to_string());
    }
    if contribution_minor <= 0 {
        return Err("Contribution amount must be greater than zero".to_string());
    }
    if payouts_per_cycle <= 0 {
        return Err("Payouts per cycle must be greater than zero".to_string());
    }
    if collection_frequency_days <= 0 {
        return Err("Collection frequency days must be positive".to_string());
    }

    let member_count = member_user_ids.len();
    let num_cycles = (member_count as i32 + payouts_per_cycle - 1) / payouts_per_cycle;

    let gross_pool_minor = contribution_minor
        .checked_mul(member_count as i64)
        .ok_or_else(|| "Gross pool calculation caused integer overflow".to_string())?;

    let reserve_held_minor = (gross_pool_minor
        .checked_mul(reserve_fund_bps as i64)
        .ok_or_else(|| "Reserve calculation caused overflow".to_string())?)
        / 10_000;

    let net_payout_minor = gross_pool_minor.saturating_sub(reserve_held_minor);

    let seconds_per_interval = (collection_frequency_days as i64) * 86_400;

    let mut obligations = Vec::with_capacity(member_count * (num_cycles as usize));
    let mut payouts = Vec::with_capacity(num_cycles as usize * (payouts_per_cycle as usize));

    let is_bidding = group_type.eq_ignore_ascii_case("BIDDING");

    let mut member_idx = 0;

    for cycle_idx in 0..num_cycles {
        let cycle_number = cycle_idx + 1;
        let due_date = start_epoch_seconds + (cycle_idx as i64 * seconds_per_interval);

        // Obligations: Cartesian product of this cycle across all members
        for user_id in member_user_ids {
            obligations.push(ObligationItem {
                cycle_number,
                user_id: user_id.clone(),
                amount_due: contribution_minor,
                amount_paid: 0,
                due_date,
                status: "PENDING".to_string(),
                created_at: created_at_epoch_seconds,
                updated_at: created_at_epoch_seconds,
            });
        }

        // Payouts for this cycle
        for _ in 0..payouts_per_cycle {
            let recipient_id = if is_bidding {
                None
            } else if member_idx < member_count {
                let rec = Some(member_user_ids[member_idx].clone());
                member_idx += 1;
                rec
            } else {
                None
            };

            let status = if is_bidding {
                "AUCTION_PENDING".to_string()
            } else {
                "PENDING".to_string()
            };

            payouts.push(PayoutItem {
                cycle_number,
                user_id: recipient_id,
                amount_expected: net_payout_minor,
                amount_collected: 0,
                status,
                payout_date: due_date,
                created_at: created_at_epoch_seconds,
                updated_at: created_at_epoch_seconds,
            });
        }
    }

    Ok(CycleMatrixResult {
        num_cycles,
        member_count,
        gross_pool_minor,
        reserve_held_minor,
        net_payout_minor,
        obligations,
        payouts,
    })
}

#[pyfunction]
#[pyo3(signature = (
    member_user_ids,
    group_type,
    contribution_minor,
    payouts_per_cycle=1,
    reserve_fund_bps=0,
    collection_frequency_days=7,
    start_epoch_seconds=0,
    created_at_epoch_seconds=0
))]
pub fn generate_cycle_matrix(
    member_user_ids: Vec<String>,
    group_type: String,
    contribution_minor: i64,
    payouts_per_cycle: i32,
    reserve_fund_bps: i32,
    collection_frequency_days: i32,
    start_epoch_seconds: i64,
    created_at_epoch_seconds: i64,
) -> PyResult<String> {
    generate_cycle_matrix_pure(
        &member_user_ids,
        &group_type,
        contribution_minor,
        payouts_per_cycle,
        reserve_fund_bps,
        collection_frequency_days,
        start_epoch_seconds,
        created_at_epoch_seconds,
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
    fn test_fixed_matrix_generation() {
        let members: Vec<String> = (1..=10).map(|i| format!("user_{}", i)).collect();
        let result = generate_cycle_matrix_pure(
            &members,
            "STANDARD",
            50_000_00,
            1,
            500, // 5% reserve
            7,
            1_700_000_000,
            1_700_000_000,
        ).unwrap();

        assert_eq!(result.num_cycles, 10);
        assert_eq!(result.member_count, 10);
        assert_eq!(result.gross_pool_minor, 500_000_00);
        assert_eq!(result.reserve_held_minor, 25_000_00); // 5% of 500,000 = 25,000
        assert_eq!(result.net_payout_minor, 475_000_00);
        assert_eq!(result.obligations.len(), 100); // 10 members x 10 cycles
        assert_eq!(result.payouts.len(), 10);
        assert_eq!(result.payouts[0].user_id.as_deref(), Some("user_1"));
        assert_eq!(result.payouts[9].user_id.as_deref(), Some("user_10"));
    }

    #[test]
    fn test_bidding_matrix_has_no_recipient() {
        let members: Vec<String> = (1..=5).map(|i| format!("user_{}", i)).collect();
        let result = generate_cycle_matrix_pure(
            &members,
            "BIDDING",
            50_000_00,
            1,
            0,
            7,
            1_700_000_000,
            1_700_000_000,
        ).unwrap();

        assert_eq!(result.num_cycles, 5);
        for payout in result.payouts {
            assert!(payout.user_id.is_none());
            assert_eq!(payout.status, "AUCTION_PENDING");
        }
    }
}
