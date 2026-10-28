# Rust domain engine

The crate organizes group-specific rules under `src/groups/` and reusable
cross-group rules under `src/shared/`.

| Folder | Responsibility |
| --- | --- |
| `groups/rotating_savings/` | ROSCA payout calculations, cycle matrices, surplus allocation, and turn swaps |
| `groups/goal_savings/` | Goal-savings fee calculations |
| `groups/investment_club/` | Auction bidding, settlement, and investment deposit fees |
| `groups/bill_split/` | Equal and custom bill-split validation |
| `groups/welfare_fund/` | Emergency-fund deposit fees |
| `shared/fees/` | Base fee calculation and shared fee primitives |
| `shared/` | Join eligibility, audit hashing, escrow, risk, quorum, health, and identity helpers |

`src/lib.rs` remains the PyO3 registration point. It preserves the Python
extension's function names and re-exports the former Rust module paths for
compatibility.
