from clob import clob
from exchange_data import exchange_data

# SCHEMA
# {
#   'questionSlot': int
#   'outcomeSlots': list[ints]
#   'contractNotional': int
# }


class question:
    def __init__(self, _exchange_data: exchange_data, question_data):
        """
        Initializes a question object.
        A question is a group of markets. Markets cannot simultaneously belong to more than one question.
        """
        self._exchange_data = _exchange_data

        self.questionSlot = question_data["questionSlots"]
        self.outcomeSlots = question_data["outcomeSlots"]
        self.contractNotional = question_data["contractNotional"]

        self.outcomes = []
        for outcome_slot in self.outcomeSlots:
            outcome = self._exchange_data.markets[outcome_slot]
            if outcome is None:
                raise Exception("One or more outcomes in the question is not found")

        self.tob_sum = [0, len(self.outcomes) * self.contractNotional]
        self.head_clobs = [-1, -1]
        self.tail_clobs = [-1, -1]
