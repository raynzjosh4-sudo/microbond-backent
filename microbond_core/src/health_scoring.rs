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

#[pyfunction]
pub fn calculate_single_health_grade(
    group_id: &str,
    on_time_count: i64,
    late_count: i64,
    default_count: i64,
    total_defaulted_amount_minor: i64,
    total_expected_amount_minor: i64,
    members_in_arrears_count: i32,
    total_active_members: i32,
) -> PyResult<String> {
    let input = GroupHealthInput {
        group_id: group_id.to_string(),
        on_time_count,
        late_count,
        default_count,
        total_defaulted_amount_minor,
        total_expected_amount_minor,
        members_in_arrears_count,
        total_active_members,
    };
    let result = calculate_single_health_grade_pure(&input);
    serde_json::to_string(&result)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e)))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenefitEligibilityResult {
    pub is_eligible: bool,
    pub active_guarantors_count: i32,
    pub required_guarantors_count: i32,
    pub trust_score: i32,
    pub minimum_trust_score: Option<i32>,
    pub status: String,
    pub rejection_reason: Option<String>,
}

pub fn evaluate_benefit_eligibility_pure(
    require_guarantors: bool,
    required_guarantors_count: i32,
    active_guarantors_count: i32,
    trust_score: i32,
    minimum_trust_score: Option<i32>,
) -> BenefitEligibilityResult {
    if let Some(min_score) = minimum_trust_score {
        if trust_score < min_score {
            return BenefitEligibilityResult {
                is_eligible: false,
                active_guarantors_count,
                required_guarantors_count,
                trust_score,
                minimum_trust_score: Some(min_score),
                status: "REJECTED_LOW_TRUST_SCORE".to_string(),
                rejection_reason: Some(format!(
                    "Member Trust Score ({}) is below the required minimum of {}.",
                    trust_score, min_score
                )),
            };
        }
    }

    if require_guarantors && active_guarantors_count < required_guarantors_count {
        return BenefitEligibilityResult {
            is_eligible: false,
            active_guarantors_count,
            required_guarantors_count,
            trust_score,
            minimum_trust_score,
            status: "REQUIRES_GUARANTOR".to_string(),
            rejection_reason: Some(format!(
                "Benefit requires {} active guarantor(s), but only {} verified.",
                required_guarantors_count, active_guarantors_count
            )),
        };
    }

    BenefitEligibilityResult {
        is_eligible: true,
        active_guarantors_count,
        required_guarantors_count,
        trust_score,
        minimum_trust_score,
        status: "APPROVED".to_string(),
        rejection_reason: None,
    }
}

#[pyfunction]
pub fn evaluate_benefit_eligibility(
    require_guarantors: bool,
    required_guarantors_count: i32,
    active_guarantors_count: i32,
    trust_score: i32,
    minimum_trust_score: Option<i32>,
) -> PyResult<String> {
    let result = evaluate_benefit_eligibility_pure(
        require_guarantors,
        required_guarantors_count,
        active_guarantors_count,
        trust_score,
        minimum_trust_score,
    );
    serde_json::to_string(&result)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e)))
}

