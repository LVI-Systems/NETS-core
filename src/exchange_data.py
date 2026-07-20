import array

from clob import clob
from question import question


class exchange_data:
    def __init__(self, max_accounts, serialized_data: dict):
        """
        Manages global exchange state including order slots, account lifecycle,
        and outcome/question data structures.

        Args:
            max_accounts (int): number of account slots to allocate.
            serialized_data (dict): configuration values for the exchange.
                - 'maxGlobalOrders': total orders allowed across all accounts.
                - 'maxAccountOrders': per-account order limit.
                - 'maxOutcomes': maximum outcome CLOBs.
                - 'maxQuestions': maximum question groups.
        """
        max_orders = serialized_data["max_orders"]
        self.acctMaxOrders = int(max_orders["account"])
        self.maxOrders = int(max_orders["global"])
        self.maxQuestions = int(serialized_data["max_questions"])
        self.maxOutcomes = int(serialized_data["max_outcomes"])

        acct_default = [-1 for i in range(0, max_accounts)]
        # account status
        # -1 = no account at this slot
        # 1 = activated trading account at this slot
        self.acctStatus = array.array("b", acct_default)
        # account balance/avbl.balance, head order (for tracking the list of orders in an account)
        self.acctBalance = array.array("i", acct_default)
        self.acctAvailable = array.array("i", acct_default)
        self.acctHeadOrder = array.array("i", acct_default)
        self.acctTailOrder = array.array("i", acct_default)
        self.acctTotalOrders = array.array("i", acct_default)

        self.orderID = array.array("i", [i for i in range(0, self.acctMaxOrders)])
        self.vacantOrderID = array.array("i", [i for i in range(0, self.acctMaxOrders)])

        order_default = [-1 for i in range(0, self.acctMaxOrders)]
        self.orderMPID = array.array("i", order_default)
        self.orderOutcome = array.array("i", order_default)
        self.orderPrice = array.array("i", order_default)
        self.orderSide = array.array("b", order_default)
        self.orderQty = array.array("i", order_default)
        self.orderAcctHead = array.array("i", order_default)
        self.orderAcctTail = array.array("i", order_default)
        self.orderClobHead = array.array("i", order_default)
        self.orderClobTail = array.array("i", order_default)

        self.outcomes = [None for i in range(0, self.maxOutcomes)]
        self.questions = [None for i in range(0, self.maxQuestions)]
        self.usedOrders = 0

    def load_exchange_objects(self, serialized_data):
        for account_idx, account_data in serialized_data["accounts"]:
            self.acctStatus[account_idx] = account_data[0]
            self.acctBalance[account_idx] = account_data[1]
            self.acctAvailable[account_idx] = account_data[2]
            self.acctHeadOrder[account_idx] = account_data[3]
            self.acctTailOrder[account_idx] = account_data[4]
            self.acctTotalOrders[account_idx] = account_data[5]

        for order_idx, order_data in serialized_data["orders"]:
            self.orderMPID[order_idx] = order_data[0]
            self.orderOutcome[order_idx] = order_data[1]
            self.orderPrice[order_idx] = order_data[2]
            self.orderSide[order_idx] = order_data[3]
            self.orderQty[order_idx] = order_data[4]
            self.orderAcctHead[order_idx] = order_data[5]
            self.orderAcctTail[order_idx] = order_data[6]
            self.orderClobHead[order_idx] = order_data[7]
            self.orderClobTail[order_idx] = order_data[8]

        for outcome_idx, outcome_data in serialized_data["outcomes"]:
            self.outcomes[outcome_idx] = clob(
                exchange_data=self, serialized_data=outcome_data
            )

        for question_idx, question_data in serialized_data["questions"]:
            self.questions[question_idx] = question(
                exchange_data=self, serialized_data=question_data
            )

    def serialize(self):
        """
        Serialize all class attributes to a dictionary.

        Returns:
            dict: A JSON-serializable representation of the exchange state.
        """
        serialized_accounts = {}
        for account_idx, account_status in enumerate(self.acctStatus):
            if account_status == -1:
                continue
            serialized_accounts[account_idx] = [
                account_status,
                self.acctBalance[account_idx],
                self.acctAvailable[account_idx],
                self.acctHeadOrder[account_idx],
                self.acctTailOrder[account_idx],
                self.acctTotalOrders[account_idx],
            ]

        serialized_orders = {}
        for order_idx, order_mpid in enumerate(self.orderMPID):
            if order_mpid == -1:
                continue
            serialized_orders[order_idx] = [
                order_mpid,
                self.orderOutcome[order_idx],
                self.orderPrice[order_idx],
                self.orderSide[order_idx],
                self.orderQty[order_idx],
                self.orderAcctHead[order_idx],
                self.orderAcctTail[order_idx],
                self.orderClobHead[order_idx],
                self.orderClobTail[order_idx],
            ]

        serialized_outcomes = {
            outcome_idx: outcome.serialize()
            for outcome_idx, outcome in enumerate(self.outcomes)
            if outcome is not None
        }

        serialized_questions = {
            question_idx: question.serialize()
            for question_idx, question in enumerate(self.questions)
            if question is not None
        }

        return {
            "max_orders": {
                "global": int(self.maxOrders),
                "account": int(self.acctMaxOrders),
            },
            "max_questions": self.maxQuestions,
            "max_orders": self.maxOrders,
            "accounts": serialized_accounts,
            "orders": serialized_orders,
            "questions": serialized_questions,
            "outcomes": serialized_outcomes,
        }

    def create_acct(self, acct_slot, initial_balance):
        """
        Create a trading account at the specified slot.

        Args:
            acct_slot (int): index of the account slot to activate.
                Slot 0 is reserved for system use and cannot be used.
            initial_balance (int|float): starting balance for the account.

        Returns:
            tuple: (success, message)
                - success: True if account was created, False otherwise.
                - message: descriptive string explaining the result.
        """
        if acct_slot == 0:
            return False, "Cannot create account at system account slot"

        if self.acctStatus[acct_slot] == -1:
            initial_balance = int(initial_balance)
            self.acctBalance[acct_slot] = initial_balance
            self.acctAvailable[acct_slot] = initial_balance
            self.acctTotalOrders[acct_slot] = 0
            self.acctHeadOrder[acct_slot] = -1
            self.acctTailOrder[acct_slot] = -1
            self.acctStatus[acct_slot] = 1
            return True, "Account created successfully"

        return False, "This account slot is already taken"

    def _get_order_slot(self, mpid):
        """
        Allocate a free order slot for the given account.

        Args:
            mpid (int): Market Participant ID of the account requesting an order.

        Returns:
            int|False: index of the allocated order slot, or False if no slot is available.
                Raises Exception if global order limit has been reached.
        """
        if self.usedOrders == self.maxOrders:
            raise Exception(
                "Exchange out of memory: global order limit has been reached"
            )

        if self.acctTotalOrders[mpid] == self.acctMaxOrders:
            return False

        alloc_order_slot = self.vacantOrderID[self.usedOrders]
        self.usedOrders += 1

        self.acctTotalOrders[mpid] += 1
        self.orderMPID[alloc_order_slot] = mpid

        if self.acctHeadOrder[mpid] == -1:
            self.acctHeadOrder[mpid] = alloc_order_slot
        self.acctTailOrder[mpid] = alloc_order_slot

        old_tail = self.acctTailOrder[mpid]
        if old_tail != -1:
            self.orderAcctTail[old_tail] = alloc_order_slot
        self.orderAcctHead[alloc_order_slot] = old_tail
        self.orderAcctTail[alloc_order_slot] = -1
        return alloc_order_slot

    def _release_order_slot(self, mpid, order_slot):
        """
        Deallocate an order slot back to the pool.

        Args:
            mpid (int): Market Participant ID of the account releasing the order.
            order_slot (int): index of the order slot to free.

        Returns:
            bool: always True on success.
        """
        self.usedOrders -= 1
        self.vacantOrderID[self.usedOrders] = order_slot
        self.acctTotalOrders[mpid] -= 1

        self.orderMPID[order_slot] = -1
        order_acct_head = self.orderAcctHead[order_slot]
        order_acct_tail = self.orderAcctTail[order_slot]
        if order_acct_head != -1:
            self.orderAcctTail[order_acct_head] = order_acct_tail
        if order_acct_tail != -1:
            self.orderAcctHead[order_acct_tail] = order_acct_head

        if order_acct_head == -1:
            self.acctHeadOrder[mpid] = order_acct_tail
        if order_acct_tail == -1:
            self.acctTailOrder[mpid] = order_acct_head

        order_clob_head = self.orderClobHead[order_slot]
        order_clob_tail = self.orderClobTail[order_slot]
        if order_clob_head != -1:
            self.orderClobTail[order_clob_head] = order_clob_tail
        if order_clob_tail != -1:
            self.orderClobHead[order_clob_tail] = order_clob_head

        return True
