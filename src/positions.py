# TODO: Add contract resolution function


class positions:
    def __init__(self, _exchange_data, market_ticks):
        self.contractNotional = market_ticks
        # [[long, short], [bid_qty, offer_qty], [bid_collateral, offer_collateral]]
        # where the margin used by orders are contractNotional * (min(long, offer_qty) + min(short, bid_qty)) - bid_collateral - offer_collateral
        self.acctPositions = {}
        self.exchangePosition = [0, 0]
        self.exchangeCollateralUsed = 0
        self.acctBalance = _exchange_data.balance
        self.acctAvbl = _exchange_data.available

    def exchange_fill(self, price, side, qty):
        """
        Log order execution of the exchange.
        Args:
            price (int): Execution price
            side (int): Execution side (0=buy, 1=sell)
            qty (int): Execution quantity
        """
        self.exchangePosition[side == 0] += qty
        self.exchangeCollateralUsed += (
            price if side == 0 else self.contractNotional - price
        ) * qty

    def order_collateral(self, price, side, qty):
        """
        Get the collateral used by an order.
        Args:
            price (int): Order price
            side (int): Order direction (0=buy, 1=sell)
            qty (int): Order quantity
        """
        return qty * (price if side == 0 else self.contractNotional - price)

    def post_order(self, mpid, price, side, qty):
        """
        Log the placement of an order by any account.
        Args:
            mpid (int): Market Participant ID of the involved account
            price (int): Order price
            side (int): Order direction (0=buy, 1=sell)
            qty (int): Order quantity
        """

        # The position data of the account
        # [[long, short], [bid_qty, offer_qty], [bid_collateral, offer_collateral]]
        acct_position = self.acctPositions.get(mpid, [[0, 0], [0, 0], [0, 0]])
        # Get the collateral usage/surplus on the side of order placement
        side_collateral_usage = acct_position[2][side]
        # Get the fully-collateralised value of the new order
        raw_order_collateral = self.order_collateral(price, side, qty)

        # The change in side_collateral_usage incurred by the new order
        collateral_usage_delta = 0
        # Position available for the new order to net = total opposite positions - total quantity of existing orders of the same side as new order
        nettable_position = acct_position[0][1 - side] - acct_position[1][side]
        # The margin usage is deducted by the notional value of the positions netted by the new order
        if nettable_position > 0:
            collateral_usage_delta = -self.contractNotional * (
                nettable_position if qty > nettable_position else qty
            )
        # The margin usage is increased by the fully-collaterallised value of the new order
        collateral_usage_delta += raw_order_collateral

        # If the order does not incur a positive fully-filled cost, no balance is to be deducted
        if collateral_usage_delta < 0:
            collateral_used = 0
        else:
            # There is no margin credit (negative fully-filled cost of existing orders) to deduct from
            if side_collateral_usage > 0:
                collateral_used = collateral_usage_delta
            # There is margin credit to deduct from
            else:
                collateral_used = collateral_usage_delta + side_collateral_usage
                # Avoid negative margin consumption value
                if collateral_used < 0:
                    collateral_used = 0

        # Sufficient collateral case
        if self.acctAvbl[mpid] >= collateral_used:
            # Deduct collateral
            self.acctAvbl[mpid] -= collateral_used  # Deduct collateral
            # Update margin usage/surplus of the order side by its delta incurred by the new order
            acct_position[2][side] += collateral_usage_delta
            # Update total side order quantity
            acct_position[1][side] += qty
            # Update account position statement used for margin calculations
            self.acctPositions[mpid] = acct_position
            return True, None
        return False, "Insufficient Margin"

    def cancel_order(self, mpid, price, side, qty):
        """
        Log the partial or full cancellation of an order by any account.
        Args:
            mpid (int): Market Participant ID of the involved account
            price (int): Order price
            side (int): Order direction (0=buy, 1=sell)
            qty (int): Order quantity to be cancelled
        """

        # Get the account position data and collateral use on the operating side
        acct_position = self.acctPositions[mpid]
        side_collateral_usage = acct_position[2][side]
        # Get the raw collateral freed by the operation
        raw_order_collateral = self.order_collateral(price, side, qty)

        # Get the position netting quantity that were decreased by the operation and clamp to >=0
        # total opposite position - current total order quantity + cancellation quantity
        unnetted_qty = acct_position[0][1 - side] - acct_position[1][side] + qty
        if unnetted_qty < 0:
            unnetted_qty = 0

        # Netting deducts from collateral usage, so unnetting does the opposite
        collateral_usage_delta = self.contractNotional * unnetted_qty
        # Adding an order adds order collateral to collateral usage, so cancelling it does the opposite
        collateral_usage_delta -= raw_order_collateral

        # Calculate old collateral debit, then update the collateral usage on operation side
        old_debit = 0 if side_collateral_usage < 0 else side_collateral_usage
        side_collateral_usage += collateral_usage_delta
        # Calculate new collateral debit
        new_debit = 0 if side_collateral_usage < 0 else side_collateral_usage
        # Free collateral amounting to the delta between above two values
        collateral_freed = old_debit - new_debit
        self.acctAvbl[mpid] += collateral_freed

        # Update total order quantity and collateral usage on the operation side
        acct_position[1][side] -= qty
        acct_position[2][side] = side_collateral_usage
        return True

    def fill_order(self, mpid, order_price, order_side, fill_price, fill_qty):
        """
        Log the partial or full execution of an order by any account.
        Args:
            mpid (int): Market Participant ID of the involved account
            order_price (int): Order price
            order_side (int): Order direction (0=buy, 1=sell)
            fill_price (int): Execution price
            fill_qty (int): Execution quantity
        """

        # Get the account position and specifically the actual position
        acct_position = self.acctPositions[mpid]
        market_position = acct_position[0]
        opposite_side = 1 - order_side

        order_side_position, opposite_position = (
            market_position[order_side],
            market_position[opposite_side],
        )

        # Position quantity closed by the fill
        position_size_closed = (
            opposite_position
            if order_side_position > opposite_position
            else order_side_position
        )

        # Calculate the returns caused by closing out positions
        position_closure_credit = position_size_closed * self.contractNotional
        # Calculate balance used from excuting the order
        order_execution_debit = self.order_collateral(fill_price, order_side, fill_qty)

        # Calculate the change in the collateral usage of the execution side
        # Identical logic to order cancellation:
        # collateral usage delta = returns from closing position - operation order collateral
        side_collateral_usage = acct_position[2][order_side]
        prev = side_collateral_usage
        side_collateral_usage -= self.order_collateral(
            order_price, order_side, fill_qty
        )
        side_collateral_usage += position_closure_credit

        if prev > 0 and side_collateral_usage > prev:
            raise Exception(
                "Fatal error: order execution resulted in increased collateral usage\nExchange has been halted."
            )

        # Update account balance, order cumulative quantity/net collateral usage and user position
        self.acctBalance[mpid] += position_closure_credit - order_execution_debit
        acct_position[2][order_side] = side_collateral_usage
        acct_position[1][order_side] -= fill_qty
        market_position[order_side] += fill_qty - position_size_closed
        market_position[opposite_side] -= position_size_closed

        # Exchange takes the opposite side of the user's fill.
        self.exchange_fill(fill_price, opposite_side, fill_qty)
