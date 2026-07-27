from weakref import proxy


class positions:
    def __init__(self, _exchange_data, serialized_data: dict):
        self.contractNotional = serialized_data["notional"]
        # [[long, short], [bid_qty, offer_qty], [bid_collateral, offer_collateral], collateral_taken]
        # where the margin used by orders are contractNotional * (min(long, offer_qty) + min(short, bid_qty)) - bid_collateral - offer_collateral
        self.acctPositions = {}
        if "positions" in serialized_data:
            self.acctPositions = serialized_data.get("positions", {})
        self.exchangePosition = serialized_data.get("exchange_position", [0, 0])
        self.exchangeCollateralUsed = serialized_data.get("exchange_collateral_used", 0)
        self.acctBalance = proxy(_exchange_data.acctBalance)
        self.acctAvbl = proxy(_exchange_data.acctAvailable)

    def serialize(self):
        return {
            "notional": int(self.contractNotional),
            "positions": self.acctPositions,
            "exchange_positions": self.exchangePosition,
            "exchange_collateral_used": self.exchangeCollateralUsed,
        }

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

    def _update_orders(self, mpid, price, side, qty):
        '''
        Adds or subtracts orders from collateral.
        Args:
            mpid (int): Market Participant ID
            price (int): Order price
            side (int): Order side
            qty(int): Order quantity (positive for adding and vice versa)
        '''
        opposite_side = [1, 0][side]
        mpid_present = mpid in self.acctPositions
        acct_state = self.acctPositions[mpid] if mpid_present else [[0, 0], [0, 0], [0, 0], 0]
        acct_positions, acct_order_qtys, acct_collateral, collateral_taken = acct_state
        nettable_position = acct_positions[opposite_side] - acct_order_qtys[side]
        prev_nettable_position = 0 if nettable_position < 0 else nettable_position
        nettable_position -= qty
        nettable_position = 0 if nettable_position < 0
        # Adding order which increases netting qty
        # nettable_position (smaller) - prev_nettable_position(larger)
        # vice versa
        nettable_position_delta = nettable_position - prev_nettable_position
        order_collateral_delta = self.order_collateral(price, side, qty)
        net_collateral_delta = self.contractNotional * nettable_position_delta + order_collateral_delta

        new_collateral = acct_collateral[side] + net_collateral_delta
        opposite_collateral = acct_collateral[opposite_side]
        new_max_collateral = new_collateral if new_collateral > opposite_collateral else opposite_collateral
        if new_max_collateral < 0:
            raise Exception("Fatal error: Both sides contain net positive collateral deltas")
        collateral_change = new_max_collateral - collateral_taken
        if collateral_change > 0 and qty < 0:
            raise Exception("Fatal boundary violation: Collateral usage increases on order removal")
        if self.acctBalance[mpid] < collateral_change:
            return False, 'InsufficiantCollateral'

        self.acctBalance[mpid] += collateral_change
        acct_order_qtys[side] += qty
        acct_collateral[side] = new_collateral
        acct_state[3] = new_max_collateral
        if not mpid_present:
            self.acctPositions[mpid] = acct_state
        return True, 'Success'

    def post_order(self, mpid, price, side, qty):
        return self._update_orders(mpid, price, side, qty)

    def cancel_order(self, mpid, price, side, qty):
        return self._update_orders(mpid, price, side, -qty)

    def fill_order(self, mpid, order_price, order_side, fill_price, fill_qty):
        opposite_side = [1, 0][order_side]
        self._update_orders(mpid, order_price, order_side, -fill_qty)
        acct_positions = self.acctPositions[mpid][0]
        opposite_position = acct_positions[opposite_side]
        position_closed = opposite_position if fill_qty > opposite_position else fill_qty
        position_opened = fill_qty - position_closed
        collateral_used = self.order_collateral(fill_price, order_side, fill_qty)
        self.acctBalance[mpid] += self.contractNotional * position_closed - collateral_used
        acct_positions[order_side] += position_opened
        acct_positions[opposite_side] -= position_closed
        self.exchange_fill(fill_price, opposite_side, fill_qty)

    def get_position_settlement_value(self, position, settlement_price):
        """
        Get the settlement value of a position given the position and settlement price.
        Args:
            position (list[long, short]): position used to compute settlement value.
            settlement_price (int): settlement value of the position.
        """
        return position[0] * settlement_price + position[1] * (
            self.contractNotional - settlement_price
        )

    def settle_outcome(self, settlement_value):
        """
        Settles all open positions in the outcome to a specified value.
        WARNING: This function MUST be used in conjunction with clearing all open orders on the outcome contract.
        Args:
            settlement_value (int): Settlement value, denominated in the long side.
        """
        if not isinstance(settlement_value, int):
            return False, "Settlement value must be an integer"
        if settlement_value < 0 or settlement_value > self.contractNotional:
            return (
                False,
                f"Settlement value must lie between 0 and {self.contractNotional} (inclusive)",
            )

        exchange_balance_delta = (
            self.get_position_settlement_value(self.exchangePosition, settlement_value)
            - self.exchangeCollateralUsed
        )

        self.acctBalance[0] += exchange_balance_delta
        self.acctAvbl[0] += exchange_balance_delta

        cumulative_settled = 0
        for mpid, user_position in self.acctPositions.values():
            mpid = int(mpid)
            user_market_position = user_position[0]
            user_position_settlement_value = self.get_position_settlement_value(
                user_market_position, settlement_value
            )
            self.acctBalance[mpid] += user_position_settlement_value
            self.acctAvbl[mpid] += user_position_settlement_value
            cumulative_settled += sum(user_market_position)

        return True, f"Settled {cumulative_settled} contracts."

    def remove_all_orders(self):
        """
        Log the removal of all orders assosciated with the outcome.
        WARNING: This function does not modify order data and only frees their collateral.
        """
        for mpid, user_position in self.acctPositions.values():
            mpid = int(mpid)
            user_collateral_usage = user_position[2]
            collateral_freed = sum(
                [max(0, side_collateral) for side_collateral in user_collateral_usage]
            )
            self.acctAvbl[mpid] += collateral_freed

            # zero the total user side order lot quantity and collateral usage
            user_position[1] = [0, 0]
            user_collateral_usage = [0, 0]
