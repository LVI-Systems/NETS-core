from this import d

from exchange_data import exchange_data as exchg_data
from market import Market
from sortedcontainers import SortedDict as sd
from user_positions import user_positions as positions


class clob:
    def __init__(self, _market: Market, clob_slot_idx: int):
        exchange_data: exchg_data = _market._exchange_data

        self.tob = [None, None]
        self.books = [sd(), sd()]
        self.priceLevels = [self.books[0].keys, self.books[1].keys]
        self.userPositions = positions(
            _exchange_data=exchange_data, market_ticks=_market.contractNotional
        )

        self.contractNotional = _market.contractNotional
        # TODO Pending removal of acctOrderLimit in this class
        self.acctOrderLimit = exchange_data.acctMaxOrders
        self.marketSlot = _market.marketSlot
        self.outcomeSlot = clob_slot_idx

        self.tobSum = _market.tob_sum
        # [bid, offer]
        self.headClobs = [-1, -1]
        self.tailClobs = [-1, -1]
        self.marketHeadClobs = _market.head_clobs
        self.marketTailClobs = _market.tail_clobs
        self.clobList = _market.markets

        self._allocOrder = exchange_data.get_order_slot
        self._deallocOrder = exchange_data.release_order_slot
        self.orderID = exchange_data.orderID
        self.orderMarket = exchange_data.orderMarket
        self.orderOutcome = exchange_data.orderOutcome
        self.orderPrice = exchange_data.orderPrice
        self.orderSide = exchange_data.orderSide
        self.orderQty = exchange_data.orderQty
        self.orderAcctHead = exchange_data.orderAcctHead
        self.orderAcctTail = exchange_data.orderAcctTail
        self.orderClobHead = exchange_data.orderClobHead
        self.orderClobTail = exchange_data.orderClobTail

    def log_occupied_clob(self, side):
        mkt_slot = self.outcomeSlot
        if self.marketHeadClobs[side] == -1:
            self.marketHeadClobs[side] = mkt_slot
            self.marketTailClobs[side] = mkt_slot
            return
        current_tail = self.marketTailClobs[side]
        if current_tail == mkt_slot:
            return
        self.clobList[current_tail].tailClobs[side] = mkt_slot
        self.tailClobs[side] = -1
        self.headClobs[side] = current_tail

    def log_empty_clob(self, side):
        mkt_head = self.headClobs[side]
        mkt_tail = self.tailClobs[side]

        if mkt_head != -1:
            self.clobList[mkt_head].tailClobs[side] = mkt_tail
        else:
            self.marketHeadClobs[side] = mkt_tail
        if mkt_tail != -1:
            self.clobList[mkt_tail].headClobs[side] = mkt_head
        else:
            self.marketTailClobs[side] = mkt_head

    def post_order(self, mpid, price, side, qty):
        # Verify that the order can be placed by the account, including the consideration of account order limit, global memory limit
        new_order_idx = self._allocOrder(mpid)
        if new_order_idx is False:
            return False, "Account-wide order limit has been reached"
        if not self.userPositions.post_order(mpid, price, side, qty):
            return False, "Insufficient Collateral"

        self.orderMarket[new_order_idx] = self.marketSlot
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
