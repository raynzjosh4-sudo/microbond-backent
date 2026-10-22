use pyo3::prelude::*;

pub mod join_rules;
pub mod payout;
pub mod audit;

#[pymodule]
fn microbond_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(join_rules::check_join_rules, m)?)?;
    m.add_function(wrap_pyfunction!(payout::calculate_rotating_payout, m)?)?;
    m.add_function(wrap_pyfunction!(payout::calculate_penalty, m)?)?;
    m.add_function(wrap_pyfunction!(audit::canonical_audit_hash, m)?)?;
    Ok(())
}
