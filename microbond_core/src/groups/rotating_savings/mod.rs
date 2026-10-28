pub mod matrix_generator;
pub mod payout;
pub mod surplus_allocator;
pub mod turn_swap_engine;

pub use crate::shared::fees::fee_amortizer::{
    calculate_flexible_rotate_deposit, calculate_flexible_rotate_deposit_pure,
    FlexibleRotateDepositResult,
};
