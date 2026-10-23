use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuctionBidValidationResult {
    pub is_valid: bool,
    pub rejection_reason: Option<String>,
    pub clock_extended: bool,
    pub new_end_time: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuctionSettlementResult {
    pub gross_pool: i64,
    pub reserve_holdback: i64,
    pub winning_bid_discount: i64,
    pub net_winner_payout: i64,
    pub dividend_pool: i64,
    pub non_winning_members_count: usize,
    pub dividend_per_member: i64,
    pub dividend_remainder: i64,
    pub invariant_verified: bool,
}

pub fn validate_auction_bid_pure(
    auction_status: &str,
    current_time_ms: i64,
    auction_end_time_ms: i64,
    new_bid_amount: i64,
    current_highest_bid_amount: Option<i64>,
    anti_sniping_threshold_ms: i64,
    clock_extension_ms: i64,
) -> AuctionBidValidationResult {
    if auction_status != "ACTIVE" {
        return AuctionBidValidationResult {
            is_valid: false,
            rejection_reason: Some(format!("Auction is currently {}.", auction_status)),
            clock_extended: false,
            new_end_time: auction_end_time_ms,
        };
    }

    if current_time_ms >= auction_end_time_ms {
        return AuctionBidValidationResult {
            is_valid: false,
            rejection_reason: Some("The bidding window has closed.".to_string()),
            clock_extended: false,
            new_end_time: auction_end_time_ms,
        };
    }

    if new_bid_amount <= 0 {
        return AuctionBidValidationResult {
            is_valid: false,
            rejection_reason: Some("Bid amount must be positive.".to_string()),
            clock_extended: false,
            new_end_time: auction_end_time_ms,
        };
    }

    if let Some(highest) = current_highest_bid_amount {
        if new_bid_amount <= highest {
            return AuctionBidValidationResult {
                is_valid: false,
                rejection_reason: Some(format!(
                    "A bid of {} or higher already exists. Please submit a higher bid.",
                    highest
                )),
                clock_extended: false,
                new_end_time: auction_end_time_ms,
            };
        }
    }

    let time_remaining = auction_end_time_ms - current_time_ms;
    let (clock_extended, new_end) = if time_remaining < anti_sniping_threshold_ms {
        (true, current_time_ms + clock_extension_ms)
    } else {
        (false, auction_end_time_ms)
    };

    AuctionBidValidationResult {
        is_valid: true,
        rejection_reason: None,
        clock_extended,
        new_end_time: new_end,
    }
}

pub fn settle_auction_payout_pure(
    gross_pool: i64,
    winning_bid: i64,
    member_count: usize,
    reserve_fund_bps: i64,
) -> Result<AuctionSettlementResult, String> {
    if gross_pool <= 0 {
        return Err("gross_pool must be positive".to_string());
    }
    if winning_bid < 0 || winning_bid > gross_pool {
        return Err("winning_bid cannot be negative or exceed gross_pool".to_string());
    }
    if member_count < 2 {
        return Err("member_count must be at least 2".to_string());
    }

    let reserve_holdback = (gross_pool * reserve_fund_bps) / 10_000;
    let net_winner_payout = gross_pool - reserve_holdback - winning_bid;
    let dividend_pool = winning_bid;

    let non_winning_members_count = member_count - 1;
    let dividend_per_member = dividend_pool / (non_winning_members_count as i64);
    let dividend_remainder = dividend_pool % (non_winning_members_count as i64);

    let total_reconciled = net_winner_payout
        + reserve_holdback
        + (dividend_per_member * non_winning_members_count as i64)
        + dividend_remainder;

    let invariant_verified = total_reconciled == gross_pool;

    Ok(AuctionSettlementResult {
        gross_pool,
        reserve_holdback,
        winning_bid_discount: winning_bid,
        net_winner_payout,
        dividend_pool,
        non_winning_members_count,
        dividend_per_member,
        dividend_remainder,
        invariant_verified,
    })
}

#[pyfunction]
#[pyo3(signature = (
    auction_status,
    current_time_ms,
    auction_end_time_ms,
    new_bid_amount,
    current_highest_bid_amount=None,
    anti_sniping_threshold_ms=60000,
    clock_extension_ms=60000
))]
pub fn validate_auction_bid(
    auction_status: &str,
    current_time_ms: i64,
    auction_end_time_ms: i64,
    new_bid_amount: i64,
    current_highest_bid_amount: Option<i64>,
    anti_sniping_threshold_ms: i64,
    clock_extension_ms: i64,
) -> PyResult<String> {
    let res = validate_auction_bid_pure(
        auction_status,
        current_time_ms,
        auction_end_time_ms,
        new_bid_amount,
        current_highest_bid_amount,
        anti_sniping_threshold_ms,
        clock_extension_ms,
    );
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (
    gross_pool,
    winning_bid,
    member_count,
    reserve_fund_bps=0
))]
pub fn settle_auction_payout(
    gross_pool: i64,
    winning_bid: i64,
    member_count: usize,
    reserve_fund_bps: i64,
) -> PyResult<String> {
    settle_auction_payout_pure(gross_pool, winning_bid, member_count, reserve_fund_bps)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
        .and_then(|res| {
            serde_json::to_string(&res)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_anti_sniping_popcorn_extension() {
        let now = 1_000_000;
        let end = now + 30_000; // 30s left (< 60s)
        let res = validate_auction_bid_pure("ACTIVE", now, end, 50_000, Some(40_000), 60_000, 60_000);
        assert!(res.is_valid);
        assert!(res.clock_extended);
        assert_eq!(res.new_end_time, now + 60_000);
    }

    #[test]
    fn test_auction_settlement_dividend_invariant() {
        let res = settle_auction_payout_pure(500_000, 50_000, 10, 500).unwrap();
        assert_eq!(res.reserve_holdback, 25_000);
        assert_eq!(res.net_winner_payout, 500_000 - 25_000 - 50_000);
        assert_eq!(res.non_winning_members_count, 9);
        assert_eq!(res.dividend_per_member, 50_000 / 9);
        assert_eq!(res.dividend_remainder, 50_000 % 9);
        assert!(res.invariant_verified);
    }
}
