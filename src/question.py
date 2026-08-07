from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import proxy

if TYPE_CHECKING:
    from core import Core as core

# SCHEMA
# {
#   'questionSlot': int
#   'outcomeSlots': list[ints]
#   'contractNotional': int
# }


class Question:
    def __init__(self, _core: core, serialized_data: dict):
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
        self.outcomes = proxy(_core.outcomes)

    def serialize(self):
        return {
            "question_slot": self.questionSlot,
            "outcome_slots": [str(slot) for slot in self.outcomeSlots],
            "contract_notional": self.contractNotional,
            "question_description": self.questionDescription,
        }

    def get_consolidated_l2(self, max_price_lvls=100, max_scans_lmt=10_000):
        # TODO: Split this up into a function to get the bid side and the offer side.
        individual_l2s = [
            self.outcomes[outcome_idx].get_depth(max_price_lvls)
            for outcome_idx in self.outcomeSlots
        ]

        total_outcomes = len(self.outcomeSlots)
        consolidated_books = [{"b": [], "o": []} for l2book in individual_l2s]

        # iterating through all outcomes in the question
        for outcome_idx in range(total_outcomes):
            # populating L2book for a single question
            for side_idx, representative_side in enumerate(["b", "o"]):
                cumulative_cost = (
                    -self.contractNotional * (total_outcomes - 1) if side_idx else 0
                )
                accessed_depth = [[0, 0] for i in range(total_outcomes)]
                virtual_level_qty = -1
                # scanning through all other L2books in the same question
                for book_idx, book in enumerate(individual_l2s):
                    if book_idx == outcome_idx:
                        continue
                    side_book = book[representative_side]
                    tob_idx = access_idx[book_idx]
                    if tob_idx >= len(side_book):
                        continue
                    # at this point we have confirmed that this specific contract which
                    # we are scanning has orders
                    tob_price, tob_qty = book[tob_idx]
                    if side_idx:
                        cumulative_cost -= self.contractNotional
                    cumulative_cost +=
                    if max_qty == -1 or tob_qty < max_qty:
                        max_qty = tob_qty
                virtual_level_price, virtual_level_qty = self.contractNotional - cumulative_cost
