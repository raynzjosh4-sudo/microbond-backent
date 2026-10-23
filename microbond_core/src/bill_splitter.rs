use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EqualBillSplitResult {
    pub total_bill: i64,
    pub member_count: usize,
    pub base_share: i64,
    pub remainder_units: i64,
    pub member_shares: Vec<i64>,
    pub invariant_verified: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustomSplitValidationResult {
    pub is_valid: bool,
    pub total_bill: i64,
    pub allocated_sum: i64,
    pub discrepancy: i64,
    pub error_message: Option<String>,
}

pub fn calculate_equal_split_pure(total_bill: i64, member_count: usize) -> Result<EqualBillSplitResult, String> {
    if total_bill <= 0 {
        return Err("total_bill must be positive".to_string());
    }
    if member_count == 0 {
        return Err("member_count cannot be zero".to_string());
    }

    let count_i64 = member_count as i64;
    let base_share = total_bill / count_i64;
    let remainder = total_bill % count_i64;

    let mut shares = Vec::with_capacity(member_count);
    for i in 0..member_count {
        if (i as i64) < remainder {
            shares.push(base_share + 1);
        } else {
            shares.push(base_share);
        }
    }

    let sum_shares: i64 = shares.iter().sum();
    let invariant_verified = sum_shares == total_bill;

    Ok(EqualBillSplitResult {
        total_bill,
        member_count,
        base_share,
        remainder_units: remainder,
        member_shares: shares,
        invariant_verified,
    })
}

pub fn validate_custom_split_pure(total_bill: i64, shares: &[i64]) -> CustomSplitValidationResult {
    if total_bill <= 0 {
        return CustomSplitValidationResult {
            is_valid: false,
            total_bill,
            allocated_sum: 0,
            discrepancy: -total_bill,
            error_message: Some("total_bill must be positive".to_string()),
        };
    }

    for (idx, &s) in shares.iter().enumerate() {
        if s < 0 {
            return CustomSplitValidationResult {
                is_valid: false,
                total_bill,
                allocated_sum: shares.iter().sum(),
                discrepancy: shares.iter().sum::<i64>() - total_bill,
                error_message: Some(format!("Share at index {} cannot be negative ({})", idx, s)),
            };
        }
    }

    let allocated_sum: i64 = shares.iter().sum();
    let discrepancy = allocated_sum - total_bill;
    let is_valid = discrepancy == 0;

    let error_message = if !is_valid {
        Some(format!(
            "Total bill is {} UGX but allocated shares sum to {} UGX (discrepancy: {} UGX)",
            total_bill, allocated_sum, discrepancy
        ))
    } else {
        None
    };

    CustomSplitValidationResult {
        is_valid,
        total_bill,
        allocated_sum,
        discrepancy,
        error_message,
    }
}

#[pyfunction]
#[pyo3(signature = (total_bill, member_count))]
pub fn calculate_equal_split(total_bill: i64, member_count: usize) -> PyResult<String> {
    calculate_equal_split_pure(total_bill, member_count)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
        .and_then(|res| {
            serde_json::to_string(&res)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
        })
}

#[pyfunction]
#[pyo3(signature = (total_bill, shares))]
pub fn validate_custom_split(total_bill: i64, shares: Vec<i64>) -> PyResult<String> {
    let res = validate_custom_split_pure(total_bill, &shares);
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_equal_split_with_remainder() {
        // 100,000 UGX split across 3 members -> 33,333 * 3 = 99,999 + 1 remainder
        let res = calculate_equal_split_pure(100_000, 3).unwrap();
        assert_eq!(res.base_share, 33_333);
        assert_eq!(res.remainder_units, 1);
        assert_eq!(res.member_shares, vec![33_334, 33_333, 33_333]);
        assert!(res.invariant_verified);
    }

    #[test]
    fn test_custom_split_validation() {
        assert!(validate_custom_split_pure(100_000, &[40_000, 30_000, 30_000]).is_valid);
        assert!(!validate_custom_split_pure(100_000, &[40_000, 30_000, 20_000]).is_valid);
    }
}
