class user_positons:
    def __init__(self, _exchange_data, market_ticks):
        self.contractNotional = market_ticks
        # [[long, short], [bid_qty, offer_qty], [bid_collateral, offer_collateral]]
        # where the margin used by orders are contractNotional * (min(long, offer_qty) + min(short, bid_qty)) - bid_collateral - offer_collateral
        self.positions = {}
        self.acctBalance = _exchange_data.balance
        self.acctAvbl = _exchange_data.available

    def order_collateral(self, price, side, qty):
        return qty * (price if side == 0 else self.contractNotional - price)

    def post_order(self, mpid, price, side, qty):
        acct_position = self.positions.get(mpid, [[0, 0], [0, 0], [0, 0]])
        side_margin_debit = acct_position[2][side]
        raw_order_collateral = self.order_collateral(price, side, qty)

        nettable_position = acct_position[1][side] - acct_position[0][1 - side]
        if nettable_position > 0:
            margin_debit_delta = -self.contractNotional * (
                nettable_position if qty > nettable_position else qty
            )

        margin_debit_delta += raw_order_collateral

        # If the order does not incur a positive fully-filled cost, no balance is to be deducted
        if margin_debit_delta < 0:
            margin_used = 0
        else:
            # There is no margin credit (negative fully-filled cost of existing orders) to deduct from
            if side_margin_debit > 0:
                margin_used = margin_debit_delta
            # There is margin credit to deduct from
            else:
                margin_used = margin_debit_delta + side_margin_debit
                # Avoid negative margin consumption value
                if margin_used < 0:
                    margin_used = 0

        if self.acctAvbl[mpid] >= margin_used:
            self.acctAvbl[mpid] -= margin_used
            acct_position[2][side] += margin_debit_delta
            acct_position[1][side] += qty
            return True
        return False

    def cancel_order(self, mpid, price, side, qty):
        acct_position = self.positions[mpid]
        side_margin_debit = acct_position[2][side]
        raw_order_collateral = self.order_collateral(price, side, qty)

        unnetted_qty = acct_position[0][1 - side] - acct_position[1][side] + qty
        if unnetted_qty < 0:
            unnetted_qty = 0

        margin_debit_delta = self.contractNotional * unnetted_qty
        margin_debit_delta -= raw_order_collateral

        old_debit = 0 if side_margin_debit < 0 else side_margin_debit
        side_margin_debit += margin_debit_delta
        new_debit = 0 if side_margin_debit < 0 else side_margin_debit
        margin_freed = old_debit - new_debit

        acct_position[1][side] -= qty
        acct_position[2][side] = side_margin_debit
        self.acctAvbl[mpid] += margin_freed
        return True

    def fill_order(self, mpid, order_price, order_side, fill_price, fill_qty):
        acct_position = self.positions[mpid]
        market_position = acct_position[0]
        opposite_side = 1 - order_side

        order_side_position, opposite_position = (
            market_position[order_side],
            market_position[opposite_side],
        )

        # tokens returned for closure of positions
        position_size_closed = (
            opposite_position
            if order_side_position > opposite_position
            else order_side_position
        )

        position_closure_credit = position_size_closed * self.contractNotional
        order_execution_debit = self.order_collateral(fill_price, order_side, fill_qty)

        # calculate the change in the account side margin credit / debit
        side_margin_debit = acct_position[2][order_side]
        prev = side_margin_debit
        side_margin_debit -= self.order_collateral(order_price, order_side, fill_qty)
        side_margin_debit += position_closure_credit
        if prev > 0 and side_margin_debit > prev:
            raise Exception("Fatal error: order execution resulted in increased")

        self.acctBalance[mpid] += position_closure_credit - order_execution_debit
        acct_position[2][order_side] = side_margin_debit
        market_position[order_side] += fill_qty - position_size_closed
        market_position[opposite_side] -= position_size_closed
