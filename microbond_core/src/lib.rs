use pyo3::prelude::*;

pub mod groups;
pub mod shared;

// Keep the original Rust module paths available to existing crate consumers.
pub use groups::bill_split::bill_splitter;
pub use groups::investment_club::auction_settlement;
pub use groups::rotating_savings::{matrix_generator, payout, surplus_allocator, turn_swap_engine};
pub use groups::welfare_fund::claim_evaluator;
pub use shared::audit;
pub use shared::escrow_engine;
pub use shared::fees::fee_amortizer;
pub use shared::health_scoring;
pub use shared::identity_matching;
pub use shared::join_rules;
pub use shared::quorum_decay;
pub use shared::risk_engine;

#[pymodule]
fn microbond_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 1. Group Join & Eligibility
    m.add_function(wrap_pyfunction!(shared::join_rules::check_join_rules, m)?)?;

    // 2. Financial Arithmetic, Penalties & Liquidity Buffer
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::payout::calculate_rotating_payout,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::payout::calculate_penalty,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::payout::evaluate_liquidity_reserve,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::payout::calculate_escalated_late_fee,
        m
    )?)?;

    // 3. Cryptographic Audit Hashing
    m.add_function(wrap_pyfunction!(shared::audit::canonical_audit_hash, m)?)?;

    // 4. Matrix & Obligation Generation
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::matrix_generator::generate_cycle_matrix,
        m
    )?)?;

    // 5. Surplus Waterfall Allocation
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::surplus_allocator::allocate_surplus_waterfall,
        m
    )?)?;

    // 6. Multi-Product Milestone Fee Amortization
    m.add_function(wrap_pyfunction!(
        shared::fees::fee_amortizer::calculate_base_deposit_fee,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::fees::fee_amortizer::calculate_target_deposit_fee,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::fees::fee_amortizer::calculate_investment_deposit_fee,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::fees::fee_amortizer::calculate_emergency_deposit_fee,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::welfare_fund::claim_evaluator::evaluate_emergency_claim,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::fees::fee_amortizer::calculate_flexible_rotate_deposit,
        m
    )?)?;

    // 7. Cross-Group Risk & Anti-Collusion DAG
    m.add_function(wrap_pyfunction!(
        shared::risk_engine::detect_guarantor_cycle,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::risk_engine::evaluate_cross_group_exposure,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::risk_engine::evaluate_guarantor_capacity,
        m
    )?)?;

    // 8. Escrow Release Formal Predicates
    m.add_function(wrap_pyfunction!(
        shared::escrow_engine::evaluate_escrow_release,
        m
    )?)?;

    // 9. Time-Locked Quorum Decay (TLQD)
    m.add_function(wrap_pyfunction!(
        shared::quorum_decay::calculate_decayed_quorum,
        m
    )?)?;

    // 10. Batch Health Scoring & Benefit Eligibility
    m.add_function(wrap_pyfunction!(
        shared::health_scoring::calculate_batch_health_grades,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::health_scoring::calculate_single_health_grade,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        shared::health_scoring::evaluate_benefit_eligibility,
        m
    )?)?;

    // 11. Turn Swap Invariant Verification
    m.add_function(wrap_pyfunction!(
        groups::rotating_savings::turn_swap_engine::validate_turn_swap_eligibility,
        m
    )?)?;

    // 12. Auction Bidding & Dividend Settlement
    m.add_function(wrap_pyfunction!(
        groups::investment_club::auction_settlement::validate_auction_bid,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::investment_club::auction_settlement::settle_auction_payout,
        m
    )?)?;

    // 13. Bill Split Invariant Engines
    m.add_function(wrap_pyfunction!(
        groups::bill_split::bill_splitter::calculate_equal_split,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        groups::bill_split::bill_splitter::validate_custom_split,
        m
    )?)?;

    // 14. Identity & Fuzzy Matching
    m.add_function(wrap_pyfunction!(
        shared::identity_matching::is_name_similar,
        m
    )?)?;

    Ok(())
}
