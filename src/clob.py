from sortedcontainers import SortedDict as sd

from exchange_data import exchange_data as exchg_data
from positions import positions
from question import question


class clob:
    """Central Limit Order Book (CLOB) implementation.

    Manages order books (bids and asks), top-of-book tracking,
    order placement/cancellation, and partial fills against the
    best available liquidity.
    """

    def __init__(self, exchange_data: exchg_data, market_config):
        """Initialize the CLOB with exchange data and market configuration.

        Args:
            exchange_data: Shared exchange state object.
            market_config: Dict containing notional, question_id,
                outcome_id, and selection_id for the market.
        """
        self.tob = [None, None]
        self.books = [sd(), sd()]
        self.priceLevels = [self.books[0].keys(), self.books[1].keys()]
        self.contractNotional = market_config["notional"]
        self.userPositions = positions(
            _exchange_data=exchange_data, market_ticks=self.contractNotional
        )

        # TODO Pending removal of acctOrderLimit in this class
        self.acctOrderLimit = exchange_data.acctMaxOrders
        self.questionSlot = market_config["question_id"]
        self.outcomeSlot = market_config["outcome_id"]

        self.questionEnabled = self.questionSlot != -1
        if self.questionEnabled:
            question: question = exchange_data.questions[self.questionSlot]
            self.tobSum = question.tob_sum
            self.linkedOutcomes = question.outcomeSlots

        self._alloc_order = exchange_data._get_order_slot
        self._dealloc_order = exchange_data._release_order_slot
        self.orderID = exchange_data.orderID
        self.orderMPID = exchange_data.orderMPID
        self.orderOutcome = exchange_data.orderOutcome
        self.orderPrice = exchange_data.orderPrice
        self.orderSide = exchange_data.orderSide
        self.orderQty = exchange_data.orderQty
        self.orderAcctHead = exchange_data.orderAcctHead
        self.orderAcctTail = exchange_data.orderAcctTail
        self.orderClobHead = exchange_data.orderClobHead
        self.orderClobTail = exchange_data.orderClobTail

        self.outcomeCLOBs = exchange_data.outcomes

    def initialize(self, head_orders):
        """
        Initialise the order book given head and tail orders.
        To be called after initializing all questions and outcomes.

        Args:
            head_orders: [bid_head_idx, offer_head_idx]
            -1 for no order.
        """

        for book in self.books:
            book.clear()

        for side, head_order_idx in head_orders:
            if head_order_idx == -1:
                continue

            current_order = head_order_idx
            order_list = []
            while True:
                order_list.append(current_order)
                current_order = self.orderClobTail[current_order]
                if current_order == -1:
                    break

            for order in order_list:
                self.post_order(current_order)

    def best_executable_quote(self, side):
        """Return the best executable price for the given side.

        Args:
            side: 0 for bid, 1 for ask.

        Returns:
            A tuple of (is_real, real_tob_price).
            For bids we return the real best price if executable,
            otherwise a virtual price; for asks we do the opposite.
        """
        # real_tob: actual best price in book for this side
        real_tob = self.tob[side]
        if not self.questionEnabled:
            return True, real_tob

        # virtual_tob: derived price based on notional and opposite side sum
        virtual_tob = self.contractNotional - (
            self.tobSum[1 - side] - (0 if real_tob is None else real_tob)
        )
        if real_tob == 0:
            return False, virtual_tob

        if side == 0:
            # bid: return real if higher than virtual, else virtual
            return (True, real_tob) if real_tob > virtual_tob else (False, virtual_tob)
        # ask: return real if lower than virtual, else virtual
        return (False, virtual_tob) if real_tob > virtual_tob else (True, real_tob)

    def tob_qty(self, side):
        tob = self.tob[side]
        if tob is None:
            return -1
        return self.books[side][tob][5]

    def place_order(self, mpid, price, side, qty):
        """
        Add a new order into the book, clear its crossing quantities,
        and post any unfilled quantity into the book.

        Collateral checks are done by this function.

        Args:
            mpid: Market participant ID.
            price: Order price.
            side: 0 for bid, 1 for ask.
            qty: Order quantity.

        Returns:
            A tuple of (success: bool, message: str).
        """
        price = int(price)
        qty = int(qty)
        if price < 0 or price > self.contractNotional:
            return False, "Order price is out of bounds"
        if qty < 1:
            return False, "Quantity must be larger than 0"

        new_order_idx = self._alloc_order(mpid)
        if new_order_idx is False:
            return False, "Account-wide order limit has been reached"

        post_order_success, return_msg = self.userPositions.post_order(
            mpid, price, side, qty
        )
        if not post_order_success:
            return False, return_msg

        self.orderOutcome[new_order_idx] = self.outcomeSlot

        # Filling the incoming order.
        # For every step that the incoming order takes,
        # 1. Check if the order has an unfilled quantity
        #
        # 2. Check if the order crosses the best opposing quote (the
        # best of the opposite top of book price and the cross-matching
        # price against same-question orders on the same side)
        #
        # 3. Execute the taker orders, either via normal matching or
        # (lifting the top-of-book normally) cross-matching (lifting
        # the top-of-book of all populated books in the question, for
        # the minimum quantity between the aggressing order and all top
        # of books that are involved in the match
        #
        # 4. Execute the incoming order, and repeat until exhaustion.

        matching_side = 1 - side
        while True:
            tob_real, tob_price = self.best_executable_quote(matching_side)
            # exit the matching loop if the top of book is not crossing the new order
            if qty == 0:
                break
            if (side == 0 and price < tob_price) or (side == 1 and price > tob_price):
                break
            if tob_real:
                qty_matched = self.lift_tob(side=matching_side, qty=qty, stp_mpid=mpid)
            else:
                avl_outcomes: list[clob] = []
                qty_matched = -1
                for outcome_id in self.linkedOutcomes:
                    if outcome_id == self.outcomeSlot:
                        continue
                    outcome: clob = self.outcomeCLOBs[outcome_id]
                    outcome_quote_qty = outcome.tob_qty(matching_side)
                    if outcome_quote_qty == -1:
                        continue
                    if qty_matched == -1:
                        qty_matched = outcome_quote_qty
                    else:
                        if outcome_quote_qty < qty_matched:
                            qty_matched = outcome_quote_qty

                    avl_outcomes.append(outcome)

                qty_matched = min(qty, qty_matched)
                for outcome_clob in avl_outcomes:
                    outcome_clob.lift_tob(side=side, qty=qty_matched)

            self.userPositions.fill_order(
                mpid=mpid,
                order_price=price,
                order_side=side,
                fill_price=tob_price,
                fill_qty=qty_matched,
            )

        if qty == 0:
            self._dealloc_order(mpid=mpid, order_slot=new_order_idx)
        else:
            self.orderMPID[new_order_idx] = mpid
            self.orderOutcome[new_order_idx] = self.outcomeSlot
            self.orderPrice[new_order_idx] = price
            self.orderSide[new_order_idx] = side
            self.orderQty[new_order_idx] = qty
            self.post_order(new_order_idx=new_order_idx)

    def post_order(self, new_order_idx):
        """Post an allocated order to the appropriate order book.

        Inserts the order into the sorted price levels, updates
        top-of-book if needed, and links the order into the
        cross-price order chain.

        Args:
            new_order_idx: Index of the pre-allocated order.
        """
        price = self.orderPrice[new_order_idx]
        side = self.orderSide[new_order_idx]
        qty = self.orderQty[new_order_idx]

        book_price = price * [-1, 1][side]
        side_book = self.books[side]
        current_tob = self.tob[side]

        # Adjust top of book and the sum thereof if necessary.
        if self.questionEnabled:
            if current_tob is None:
                self.tob[side] = book_price
                self.tobSum[side] += -self.contractNotional * side == 1 + price
            elif book_price < current_tob:
                self.tob[side] = book_price
                self.tobSum[side] += (current_tob - book_price) * ([1, -1][side])

        # price:[h_price, t_price, h_order, t_order, tot_orders, tot_qty]
        if book_price not in side_book:
            side_book_price_levels = self.priceLevels[side]

            price_level = [None, None, new_order_idx, new_order_idx, 1, qty]
            side_book[book_price] = price_level
            price_idx = side_book_price_levels.index(book_price)
            tail_price_level_idx = len(side_book_price_levels) - 1

            new_order_clob_head, new_order_clob_tail = -1, -1
            # handle head of new order
            if price_idx > 0:
                head_price = side_book_price_levels[price_idx - 1]
                head_price_tail_order = side_book[head_price][3]
                new_order_clob_head = head_price_tail_order
                self.orderClobTail[head_price_tail_order] = new_order_idx
                price_level[0] = head_price
            # handle tail of new order
            if price_idx < tail_price_level_idx:
                tail_price = side_book_price_levels[price_idx + 1]
                tail_price_head_order = side_book[tail_price][2]
                new_order_clob_tail = tail_price_head_order
                self.orderClobHead[tail_price_head_order] = new_order_idx
                price_level[1] = tail_price

            self.orderClobHead[new_order_idx] = new_order_clob_head
            self.orderClobTail[new_order_idx] = new_order_clob_tail
            side_book[book_price] = price_level
        else:
            price_level = side_book[book_price]
            price_level[4] += 1
            price_level[5] += self.orderQty[new_order_idx]

            new_order_clob_head = price_level[3]
            self.orderClobHead[new_order_idx] = new_order_clob_head
            self.orderClobTail[new_order_clob_head] = new_order_idx
            price_level[3] = new_order_idx
            tail_price = price_level[1]
            if tail_price is None:
                self.orderClobTail[new_order_idx] = -1
            else:
                tail_price_head_order = side_book[tail_price]
                self.orderClobTail[new_order_idx] = tail_price_head_order
                self.orderClobHead[tail_price_head_order] = new_order_idx

    def cancel_order(self, order_idx):
        """Cancel an order and remove it from the order book.

        Unlinks the order from price levels and cross-price chains,
        updates top-of-book if the cancelled order was at the best,
        and releases the order slot.

        Args:
            order_idx: Index of the order to cancel.

        Returns:
            A tuple of (success: bool, message: str).
        """
        order_mpid = self.orderMPID[order_idx]
        order_price = self.orderPrice[order_idx]
        order_side = self.orderSide[order_idx]
        order_qty = self.orderQty[order_idx]

        if order_qty != 0:
            self.userPositions.cancel_order(
                order_mpid, order_price, order_side, order_qty
            )

        order_head = self.orderClobHead[order_idx]
        order_tail = self.orderClobTail[order_idx]
        if order_head != -1:
            self.orderClobTail[order_head] = order_tail
        if order_tail != -1:
            self.orderClobHead[order_tail] = order_head

        self._dealloc_order(order_mpid, order_idx)

        side_book = self.books[order_side]
        book_price = order_price * [-1, 1][order_side]
        price_lvl = side_book[book_price]

        if book_price == self.tob[order_side]:
            self.tob[order_side] = price_lvl[1]

        price_lvl[4] -= 1
        price_lvl[5] -= order_qty
        if price_lvl[4] == 0:
            head_price, tail_price = price_lvl[0:2]
            if head_price is not None:
                side_book[head_price][1] = tail_price
            if tail_price is not None:
                side_book[tail_price][0] = head_price
            del side_book[book_price]

        return True, "Order Cancelled"

    def lift_tob(self, side, qty, stp_mpid=-1):
        """Lift bid (0) or ask (1) — intended to be used with the main fill function.

        Args:
            side: 0 for bid, 1 for ask.
            qty: Quantity to lift.
            stp_mpid: Optional market participant ID to self-trade against
                and cancel.

        Returns:
            The total quantity lifted.
        """

        side_tob = self.tob[side]
        side_tob = self.tob[side]
        if side_tob is None:
            return False

        price_lvl = self.books[side][side_tob]
        head_order = price_lvl[2]
        lvl_orders = price_lvl[4]
        filled_qty = 0

        for i in range(0, lvl_orders):
            order_mpid = self.orderMPID[head_order]
            order_price = self.orderPrice[head_order]
            order_qty = self.orderQty[head_order]

            fill_qty = min(qty, order_qty)
            if fill_qty == 0:
                break

            if order_mpid == stp_mpid:
                self.cancel_order(order_mpid)
                continue

            self.userPositions.fill_order(
                order_mpid, order_price, side, order_price, fill_qty
            )
            order_qty -= fill_qty
            if order_qty == 0:
                self.cancel_order(head_order)

            qty -= fill_qty
            filled_qty += fill_qty
            head_order = self.orderClobTail[head_order]

        return filled_qty

    def cancel_all_orders(self):
        """Cancel every order across all price levels on all sides.

        Releases all order slots and clears the books in-place.

        Returns:
            A tuple of (success: bool, message: str) with the count
            of cancelled orders.
        """

        cumulative_orders_cancelled = 0
        for side, book in enumerate(self.books):
            price_levels = self.priceLevels[side]
            if not len(price_levels):
                continue
            top_of_book = price_levels[0]
            top_order_idx = book[top_of_book][2]
            while top_order_idx != -1:
                top_order_mpid = self.orderMPID[top_order_idx]
                self._dealloc_order(top_order_mpid, top_order_idx)
                top_order_idx = self.orderClobTail[top_order_idx]
                cumulative_orders_cancelled += 1
        return True, f"Cancelled {cumulative_orders_cancelled} orders"
