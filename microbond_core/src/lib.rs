use pyo3::prelude::*;

pub mod join_rules;
pub mod payout;
pub mod audit;
pub mod matrix_generator;
pub mod surplus_allocator;
pub mod fee_amortizer;
pub mod risk_engine;
pub mod escrow_engine;
pub mod quorum_decay;
pub mod health_scoring;
pub mod turn_swap_engine;
pub mod auction_settlement;
pub mod bill_splitter;
pub mod identity_matching;

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

    // 6. Multi-Product Milestone Fee Amortization
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_base_deposit_fee, m)?)?;
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_target_deposit_fee, m)?)?;
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_investment_deposit_fee, m)?)?;
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_emergency_deposit_fee, m)?)?;
    m.add_function(wrap_pyfunction!(fee_amortizer::calculate_flexible_rotate_deposit, m)?)?;

    // 7. Cross-Group Risk & Anti-Collusion DAG
    m.add_function(wrap_pyfunction!(risk_engine::detect_guarantor_cycle, m)?)?;
    m.add_function(wrap_pyfunction!(risk_engine::evaluate_cross_group_exposure, m)?)?;
    m.add_function(wrap_pyfunction!(risk_engine::evaluate_guarantor_capacity, m)?)?;

    // 8. Escrow Release Formal Predicates
    m.add_function(wrap_pyfunction!(escrow_engine::evaluate_escrow_release, m)?)?;

    // 9. Time-Locked Quorum Decay (TLQD)
    m.add_function(wrap_pyfunction!(quorum_decay::calculate_decayed_quorum, m)?)?;

    // 10. Batch Health Scoring
    m.add_function(wrap_pyfunction!(health_scoring::calculate_batch_health_grades, m)?)?;

    // 11. Turn Swap Invariant Verification
    m.add_function(wrap_pyfunction!(turn_swap_engine::validate_turn_swap_eligibility, m)?)?;

    // 12. Auction Bidding & Dividend Settlement
    m.add_function(wrap_pyfunction!(auction_settlement::validate_auction_bid, m)?)?;
    m.add_function(wrap_pyfunction!(auction_settlement::settle_auction_payout, m)?)?;

    // 13. Bill Split Invariant Engines
    m.add_function(wrap_pyfunction!(bill_splitter::calculate_equal_split, m)?)?;
    m.add_function(wrap_pyfunction!(bill_splitter::validate_custom_split, m)?)?;

    // 14. Identity & Fuzzy Matching
    m.add_function(wrap_pyfunction!(identity_matching::is_name_similar, m)?)?;

    Ok(())
}
