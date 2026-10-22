use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CycleCoverageDetail {
    pub cycle_number: i32,
    pub amount_required: i64,
    pub amount_allocated: i64,
    pub shortfall: i64,
    pub status: String, // "FULLY_COVERED" | "PARTIALLY_COVERED"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurplusAllocationResult {
    pub total_surplus: i64,
    pub cycles_fully_covered_count: usize,
    pub fully_covered_cycles: Vec<i32>,
    pub partially_covered_cycle: Option<i32>,
    pub unallocated_residual: i64,
    pub next_cycle_requiring_payment: i32,
    pub coverage_details: Vec<CycleCoverageDetail>,
    pub summary_label: String,
}

pub fn allocate_surplus_pure(
    surplus_amount: i64,
    current_cycle_number: i32,
    standard_contribution: i64,
    cycle_overrides: &HashMap<i32, i64>,
    max_cycles: Option<i32>,
) -> SurplusAllocationResult {
    if surplus_amount <= 0 {
        return SurplusAllocationResult {
            total_surplus: 0,
            cycles_fully_covered_count: 0,
            fully_covered_cycles: vec![],
            partially_covered_cycle: None,
            unallocated_residual: 0,
            next_cycle_requiring_payment: current_cycle_number + 1,
            coverage_details: vec![],
            summary_label: "No advance surplus to allocate.".to_string(),
        };
    }

    let mut remaining = surplus_amount;
    let mut target_cycle = current_cycle_number + 1;
    let mut fully_covered = vec![];
    let mut partial_cycle = None;
    let mut details = vec![];

    while remaining > 0 {
        if let Some(max_c) = max_cycles {
            if target_cycle > max_c {
                break;
            }
        }

        let required = cycle_overrides
            .get(&target_cycle)
            .copied()
            .unwrap_or(standard_contribution);

        if remaining >= required {
            remaining -= required;
            fully_covered.push(target_cycle);
            details.push(CycleCoverageDetail {
                cycle_number: target_cycle,
                amount_required: required,
                amount_allocated: required,
                shortfall: 0,
                status: "FULLY_COVERED".to_string(),
            });
            target_cycle += 1;
        } else {
            // Partial coverage
            let shortfall = required - remaining;
            details.push(CycleCoverageDetail {
                cycle_number: target_cycle,
                amount_required: required,
                amount_allocated: remaining,
                shortfall,
                status: "PARTIALLY_COVERED".to_string(),
            });
            partial_cycle = Some(target_cycle);
            remaining = 0;
            break;
        }
    }

    let next_due_cycle = if partial_cycle.is_some() {
        target_cycle
    } else {
        target_cycle
    };

    let summary = if fully_covered.is_empty() && partial_cycle.is_some() {
        format!("Surplus partially covers Round {}.", target_cycle)
    } else if !fully_covered.is_empty() && partial_cycle.is_none() {
        format!("Surplus fully covers {} upcoming rounds.", fully_covered.len())
    } else if !fully_covered.is_empty() && partial_cycle.is_some() {
        format!(
            "Surplus fully covers {} rounds and partially covers Round {}.",
            fully_covered.len(),
            target_cycle
        )
    } else {
        "Surplus held as group reserve credit.".to_string()
    };

    SurplusAllocationResult {
        total_surplus: surplus_amount,
        cycles_fully_covered_count: fully_covered.len(),
        fully_covered_cycles: fully_covered,
        partially_covered_cycle: partial_cycle,
        unallocated_residual: remaining,
        next_cycle_requiring_payment: next_due_cycle,
        coverage_details: details,
        summary_label: summary,
    }
}

#[pyfunction]
#[pyo3(signature = (
    surplus_amount,
    current_cycle_number,
    standard_contribution,
    cycle_overrides_json=None,
    max_cycles=None
))]
pub fn allocate_surplus_waterfall(
    surplus_amount: i64,
    current_cycle_number: i32,
    standard_contribution: i64,
    cycle_overrides_json: Option<String>,
    max_cycles: Option<i32>,
) -> PyResult<String> {
    let overrides: HashMap<i32, i64> = match cycle_overrides_json {
        Some(s) if !s.trim().is_empty() => serde_json::from_str(&s).unwrap_or_default(),
        _ => HashMap::new(),
    };

    let result = allocate_surplus_pure(
        surplus_amount,
        current_cycle_number,
        standard_contribution,
        &overrides,
        max_cycles,
    );

    serde_json::to_string(&result)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exact_two_cycles_coverage() {
        let overrides = HashMap::new();
        // 50,000 per cycle, surplus is 100,000 -> covers cycle 2 and 3
        let res = allocate_surplus_pure(100_000, 1, 50_000, &overrides, Some(10));
        assert_eq!(res.cycles_fully_covered_count, 2);
        assert_eq!(res.fully_covered_cycles, vec![2, 3]);
        assert_eq!(res.partially_covered_cycle, None);
        assert_eq!(res.unallocated_residual, 0);
        assert_eq!(res.next_cycle_requiring_payment, 4);
    }

    #[test]
    fn test_partial_coverage() {
        let overrides = HashMap::new();
        // 50,000 per cycle, surplus is 70,000 -> covers cycle 2 fully, cycle 3 partially (20k allocated, 30k shortfall)
        let res = allocate_surplus_pure(70_000, 1, 50_000, &overrides, Some(10));
        assert_eq!(res.cycles_fully_covered_count, 1);
        assert_eq!(res.fully_covered_cycles, vec![2]);
        assert_eq!(res.partially_covered_cycle, Some(3));
        assert_eq!(res.coverage_details[1].amount_allocated, 20_000);
        assert_eq!(res.coverage_details[1].shortfall, 30_000);
    }
}
