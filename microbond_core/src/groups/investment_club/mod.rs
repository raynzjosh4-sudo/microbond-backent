pub mod auction_settlement;

pub use crate::shared::fees::fee_amortizer::{
    calculate_investment_deposit_fee, calculate_investment_deposit_fee_pure,
    InvestmentDepositCalculation,
};
