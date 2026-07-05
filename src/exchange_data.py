import array


class exchange_data:
    def __init__(self, max_accounts, _config):
        self.maxOrders = _config["maxGlobalOrders"]
        self.maxOutcomes = _config["maxGlobalOutcomes"]
        self.maxQuestions = _config["maxGlobalQuestions"]
        self.acctMaxOrders = _config["maxAccountOrders"]

        acct_default = [-1 for i in range(0, max_accounts)]
        # account status
        # -1 = no account at this slot
        # 1 = activated trading account at this slot
        self.acctStatus = array.array("b", acct_default)
        # account balance/avbl.balance, head order (for tracking the list of orders in an account)
        self.balance = array.array("i", acct_default)
        self.available = array.array("i", acct_default)
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

    def create_acct(self, acct_slot, initial_balance):
        if acct_slot == 0:
            return False, "Cannot create account at system account slot"

        if self.acctStatus[acct_slot] == -1:
            initial_balance = int(initial_balance)
            self.balance[acct_slot] = initial_balance
            self.available[acct_slot] = initial_balance
            self.acctTotalOrders[acct_slot] = 0
            self.acctHeadOrder[acct_slot] = -1
            self.acctTailOrder[acct_slot] = -1
            self.acctStatus[acct_slot] = 1
            return True, "Account created successfully"

        return False, "This account slot is already taken"

    def get_order_slot(self, mpid):
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

    def release_order_slot(self, mpid, order_slot):
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
