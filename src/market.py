from clob import clob


class Market:
    def __init__(self, _exchange_data, market_slot, n_outcomes, contract_notional):
        self._exchange_data = _exchange_data

        self.marketSlot = market_slot
        self.nOutcomes = n_outcomes
        self.contractNotional = contract_notional

        self.markets = [
            clob(_market=self, clob_slot_idx=i) for i in range(0, self.nOutcomes)
        ]
        self.tob_sum = [0, self.nOutcomes * self.contractNotional]
        self.head_clobs = [-1, -1]
        self.tail_clobs = [-1, -1]
