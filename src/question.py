from clob import clob
from exchange_data import exchange_data

# SCHEMA
# {
#   'questionSlot': int
#   'outcomeSlots': list[ints]
#   'contractNotional': int
# }


class question:
    def __init__(self, exchange_data: exchange_data, serialized_data: dict):
        """
        Initializes a question object.
        A question is a group of mutually exclusive markets. Markets cannot
        simultaneously belong to more than one question.

        Questions are to be initialised before initializing outcomes, as the
        initialization of outcomes may involve linking to question objects.

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

        self.questionSlot = serialized_data["question_slot"]
        self.outcomeSlots = serialized_data["outcome_slots"]
        self.contractNotional = serialized_data["contract_notional"]
        self.questionDescription = serialized_data["question_description"]

        self.tob_sum = [0, len(self.outcomeSlots) * self.contractNotional]

    def serialize(self):
        return {
            "question_slot": self.questionSlot,
            "outcome_slots": [str(slot) for slot in self.outcomeSlots],
            "contract_notional": self.contractNotional,
            "question_description": self.questionDescription,
        }
