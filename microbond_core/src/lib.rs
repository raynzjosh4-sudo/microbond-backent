use pyo3::prelude::*;

pub mod join_rules;
pub mod payout;
pub mod audit;
pub mod matrix_generator;
pub mod surplus_allocator;
pub mod fee_amortizer;

#[pymodule]
fn microbond_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 1. Group Join & Eligibility
    m.add_function(wrap_pyfunction!(join_rules::check_join_rules, m)?)?;

    // 2. Financial Arithmetic & Penalties
    m.add_function(wrap_pyfunction!(payout::calculate_rotating_payout, m)?)?;
    m.add_function(wrap_pyfunction!(payout::calculate_penalty, m)?)?;

    // 3. Cryptographic Audit Hashing
    m.add_function(wrap_pyfunction!(audit::canonical_audit_hash, m)?)?;

    // 4. Matrix & Obligation Generation
    m.add_function(wrap_pyfunction!(matrix_generator::generate_cycle_matrix, m)?)?;

    // 5. Surplus Waterfall Allocation
    m.add_function(wrap_pyfunction!(surplus_allocator::allocate_surplus_waterfall, m)?)?;

    // 6. Milestone Fee Amortization
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_flexible_rotate_deposit, m)?)?;

    Ok(())
}
