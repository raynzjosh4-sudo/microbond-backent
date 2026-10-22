use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupHealthInput {
    pub group_id: String,
    pub on_time_count: i64,
    pub late_count: i64,
    pub default_count: i64,
    pub total_defaulted_amount_minor: i64,
    pub total_expected_amount_minor: i64,
    pub members_in_arrears_count: i32,
    pub total_active_members: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupHealthScoreResult {
    pub group_id: String,
    pub on_time_repayment_rate_pct: f64,
    pub default_rate_pct: f64,
    pub arrears_member_ratio_pct: f64,
    pub composite_score: i32,
    pub grade: String, // "A+" | "A" | "B" | "C" | "D" | "F"
    pub risk_tier: String, // "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
}

/// Pure evaluation of a group's financial health score and letter grade.
pub fn calculate_single_health_grade_pure(input: &GroupHealthInput) -> GroupHealthScoreResult {
    let completed = input.on_time_count + input.late_count + input.default_count;

    let (on_time_pct, default_pct) = if completed > 0 {
        let otp = (input.on_time_count as f64 / completed as f64) * 100.0;
        let def = (input.default_count as f64 / completed as f64) * 100.0;
        (otp, def)
    } else {
        (100.0, 0.0)
    };

    let arrears_ratio_pct = if input.total_active_members > 0 {
        (input.members_in_arrears_count as f64 / input.total_active_members as f64) * 100.0
    } else {
        0.0
    };

    // Composite scoring (0-100 scale):
    // 60% on-time rate + 20% absence of default + 20% member solvency
    let on_time_pts = (on_time_pct * 0.60).round() as i32;
    let default_pts = ((100.0 - default_pct).max(0.0) * 0.20).round() as i32;
    let solvency_pts = ((100.0 - arrears_ratio_pct).max(0.0) * 0.20).round() as i32;

    let composite_score = (on_time_pts + default_pts + solvency_pts).clamp(0, 100);

    let (grade, risk_tier) = match composite_score {
        95..=100 => ("A+", "LOW"),
        85..=94 => ("A", "LOW"),
        75..=84 => ("B", "MODERATE"),
        60..=74 => ("C", "MODERATE"),
        45..=59 => ("D", "HIGH"),
        _ => ("F", "CRITICAL"),
    };

    GroupHealthScoreResult {
        group_id: input.group_id.clone(),
        on_time_repayment_rate_pct: (on_time_pct * 10.0).round() / 10.0,
        default_rate_pct: (default_pct * 10.0).round() / 10.0,
        arrears_member_ratio_pct: (arrears_ratio_pct * 10.0).round() / 10.0,
        composite_score,
        grade: grade.to_string(),
        risk_tier: risk_tier.to_string(),
    }
}

pub fn calculate_batch_health_grades_pure(
    groups: &[GroupHealthInput],
) -> Vec<GroupHealthScoreResult> {
    groups.iter().map(calculate_single_health_grade_pure).collect()
}

// ---------------------------------------------------------------------------
// PyO3 Bindings
// ---------------------------------------------------------------------------

#[pyfunction]
pub fn calculate_batch_health_grades(
    groups_json: &str,
) -> PyResult<String> {
    let inputs: Vec<GroupHealthInput> = serde_json::from_str(groups_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid batch JSON: {}", e)))?;

    let results = calculate_batch_health_grades_pure(&inputs);
    serde_json::to_string(&results)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e)))
}
