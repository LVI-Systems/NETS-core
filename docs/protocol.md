
# NETS Data Protocol

## Types of data to be broadcasted
- Account-level Data
  - Order placement/modification/cancellation success/failure
  - Order filled notification incl. counterparty MPID

- Exchange-level Data
  - Order book snapshot
  - Order book diff (from order placement/cancellation)
  -  Order book diff + trade (from trade execution))

## Native data protocol
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
