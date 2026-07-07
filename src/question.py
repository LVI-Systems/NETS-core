from clob import clob
from exchange_data import exchange_data

# SCHEMA
# {
#   'questionSlot': int
#   'outcomeSlots': list[ints]
#   'contractNotional': int
# }


class question:
    def __init__(self, exchange_data: exchange_data, question_config):
        """
        Initializes a question object.
        A question is a group of markets. Markets cannot simultaneously belong to more than one question.

        Questions are to be initialised before initializing order books, as the initialization of the later

        Args:
            exchange_data (exchange_data): global exchange data.
            question_config (dict): configuration of the question:
                {
                    'outcome_slots': the slots containing outcome CLOBs.
                    'question_slot': the slot belonging to the question.
                    'contract_notional': contact notioanl value of all
                    outcomes in the question.
                }
        """

        self._exchange_data = exchange_data

        self.questionSlot = question_config["question_slot"]
        self.outcomeSlots = question_config["outcome_slots"]
        self.contractNotional = question_config["contract_notional"]

        self.tob_sum = [0, len(self.outcomeSlots) * self.contractNotional]
