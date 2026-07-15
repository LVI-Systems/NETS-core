
# NETS Data Protocol

## Types of data to be broadcasted
- Account-level Data
  - Order placement/modification/cancellation success/failure
  - Order filled notification incl. counterparty MPID

- Exchange-level Data
  - Order book snapshot
  - Order book diff (from order placement/cancellation)
  -  Order book diff + trade (from trade execution))

## Specific Data
- Order placement
 - On successful order placement
  - New order status is emitted to the person who placed the order: **(order_qty, fill_qty, fill_cost_norm)**
  - Order book changes emitted:
    - Book liquidity removed (can be different order books if the market facilitates cross-matching)
    - Book liquidity added (if the new order contains an unfilled resting quantity)
    
- Order cancellation
  - On successful order cancellation
    - True is emitted to the person who cancelled the order
    - Order book change (rmv liquidity from relevant level) is emitted
  - On unsuccessful order cancellation
    - False is emitted to the person who cancelled the order
    - No order book change is emitted as there is no manipulation of any order conducted

- Order fill
 - To maker order: (order_qty, fill_qty, taker_mpid) **this may be transmitted on a per tick basis**

## Data format
- Exchange-level trade messages
  - [10, market_id, [price, qty, aggressing_side]]
    - Values of aggressing_side: 0 and 1 for buyer-aggressing and seller-aggressing cases in normal matching, and 2 and 3 for buyer-aggressing and seller aggressing cases in cross-matching. 

- Orderbook updates
  Orderbook updates either show the entire book, or the portion of the book that was changed by a particular operation (diffs).  
  For updates of the full book, an ordered format is used, though this is not necessary for diffs.
  - Diff: [20, market_id, [[price, side, qty], ...]]
  - Snapshot: [21, market_id, [[bid_price, bid_qty], ...], [offer_price, offer_qty]]

## How market data is emitted on the return of functions
 - Data assosciated with the person who called the function **comes first**
 - All other pieces of data, such as those used to update the orderbook state, **comes second**
