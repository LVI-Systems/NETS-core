from exchange_data import exchange_data as exchg_data
from positions import positions as positions
from question import question
from sortedcontainers import SortedDict as sd


class clob:
    def __init__(self, exchange_data: exchg_data, market_config):
        self.tob = [None, None]
        self.books = [sd(), sd()]
        self.priceLevels = [self.books[0].keys, self.books[1].keys]
        self.contractNotional = market_config["notional"]
        self.userPositions = positions(
            _exchange_data=exchange_data, market_ticks=self.contractNotional
        )

        # TODO Pending removal of acctOrderLimit in this class
        self.acctOrderLimit = exchange_data.acctMaxOrders
        self.questionSlot = market_config["question_id"]
        self.outcomeSlot = market_config["outcome_id"]

        if self.questionSlot != -1:
            question: question = exchange_data.questions[self.questionSlot]
            self.tobSum = question.tob_sum
            # [bid, offer]
            self.headClobs = [-1, -1]
            self.tailClobs = [-1, -1]
            # [bid mkt slot, offer mkt slot]
            self.questionHeadClobs = question.head_clobs
            self.questionTailClobs = question.tail_clobs
            # All other outcome markets in the same class
            self.clobList = question.markets

        self._allocOrder = exchange_data.get_order_slot
        self._deallocOrder = exchange_data.release_order_slot
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

    def log_occupied_clob(self, side):
        outcome_slot = self.outcomeSlot
        if self.questionHeadClobs[side] == -1:
            self.questionHeadClobs[side] = outcome_slot
            self.questionTailClobs[side] = outcome_slot
            return
        current_tail = self.questionTailClobs[side]
        if current_tail == outcome_slot:
            return
        self.clobList[current_tail].tailClobs[side] = outcome_slot
        self.tailClobs[side] = -1
        self.headClobs[side] = current_tail

    def log_empty_clob(self, side):
        outcome_head = self.headClobs[side]
        outcome_tail = self.tailClobs[side]

        if outcome_head != -1:
            self.clobList[outcome_head].tailClobs[side] = outcome_tail
        else:
            self.questionHeadClobs[side] = outcome_tail
        if outcome_tail != -1:
            self.clobList[outcome_tail].headClobs[side] = outcome_head
        else:
            self.questionTailClobs[side] = outcome_head

    def deduct_price_lvl(self, side, price, sum_orders, sum_qty):
        side_book = self.books[side]
        book_price = price * [-1, 1][side]
        price_lvl = side_book[book_price]
        price_lvl[4] -= sum_orders
        price_lvl[5] -= sum_qty

        if price_lvl[4] > 0:
            return False

        head_price, tail_price = price_lvl[0:2]
        if head_price is not None:
            side_book[head_price][1] = tail_price
        if tail_price is not None:
            side_book[tail_price][0] = head_price
        del side_book[book_price]
        return True

    def post_order(self, mpid, price, side, qty):
        # Verify that the order can be placed by the account, including the consideration of account order limit, global memory limit
        new_order_idx = self._allocOrder(mpid)
        if new_order_idx is False:
            return False, "Account-wide order limit has been reached"

        post_order_success, return_msg = self.userPositions.post_order(
            mpid, price, side, qty
        )
        if not post_order_success:
            return False, return_msg

        self.orderOutcome[new_order_idx] = self.outcomeSlot

        book_price = price * [-1, 1][side]
        side_book = self.books[side]
        current_tob = self.tob[side]
        if current_tob is None:
            self.tob[side] = book_price
            self.tobSum[side] -= -self.contractNotional * side == 1 + price
        elif book_price < current_tob:
            self.tob[side] = book_price
            self.tobSum[side] += (current_tob - book_price) * ([1, -1][side])

        # remember: sd{price:[head_price, tail_price, head_order, tail_order, sum_orders, sum_qty]}
        if book_price not in side_book:
            side_book_price_levels = self.priceLevels[side]
            price_level = [None, None, new_order_idx, new_order_idx, 1, qty]
            side_book[book_price] = price_level
            price_idx = side_book_price_levels.index(book_price)
            tail_price_level_idx = len(side_book_price_levels)

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
        order_mpid = self.orderMPID[order_idx]
        order_price = self.orderPrice[order_idx]
        order_side = self.orderSide[order_idx]
        order_qty = self.orderQty[order_idx]
        self.userPositions.cancel_order(order_mpid, order_price, order_side, order_qty)

        order_head = self.orderClobHead[order_idx]
        order_tail = self.orderClobTail[order_idx]
        if order_head != -1:
            self.orderClobTail[order_head] = order_tail
        if order_tail != -1:
            self.orderClobHead[order_tail] = order_head

        self.deduct_price_lvl(order_side, order_price, 1, order_qty)
        self._deallocOrder(order_mpid, order_idx)
