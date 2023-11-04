from ib_insync import *
from datetime import datetime, time


def tradeExit(self):
    print('checking if the trade should be exited...')
    self.telegram_bot_sendtext("checking if the trade should be exited...")

    #IF PNL>5% AND DELTA <5, WAIT FOR PNL TO RISE. CHECK EVERY HOUR, IF PNL IS FALLING ... TIMES IN A ROW, TAKE PROFIT
    if self.exit == 'True':
        if self.PnLpercentage >= self.previousPnLpercentage:
            print("waiting for PnL to rise, checking again in an hour...")
            self.telegram_bot_sendtext("waiting for PnL to rise, checking again in an hour...")
            self.exit_program()
        elif self.PnLpercentage < self.previousPnLpercentage and self.rising == 'False' or time.fromisoformat('13:00:00') < datetime.now().time() < time.fromisoformat('15:00:00'):
            print("taking profit")
            self.telegram_bot_sendtext("taking profit")
            self.closeBWB()
            if self.adjusted == 'Calendar':
                print('closing calendar')
                self.closeCalendar(self.calendarStrike, self.calendarQty)
                if hasattr(self, 'movedContract'):
                    print('closing moved contract(s)')
                    self.closeCalendar(self.backMovedContract.strike, self.movedContractQty)
            #DELETE .PKL FILE AND EXIT PROGRAM
            self.deletelog()
            self.ib.sleep(5)
            self.telegram_bot_sendtext("The target has been reached, the goal has been won,\n Im a winner today, and Im feeling so fun.\nI'll celebrate my success, and then I'll begin,\nTo look for my next trade, and my next win.")
            self.exit_program()
        elif self.PnLpercentage < self.previousPnLpercentage and self.rising == 'True':
            print("PnL is falling. If PnL is lower again one hour from now I'm taking profit.")
            self.telegram_bot_sendtext("PnL is falling. If PnL is lower again one hour from now I'm taking profit.")

    #IF DOWNWARDS ADJUSTMENT, CHECK IF THE MARKET IS RECOVERING. IF IT DOESNT, TAKE A LOSS INTRADAY. IF IT DOES, AND THEN FALLS AGAIN, TAKE A LOSS INTRADAY.
    #IF IT DOES RECOVER, TAKE PROFIT FOLLOWING DAY.S
    elif self.adjusted == 'Downwards':
        
        print('do the other thing')


def closeBWB(self):
    #RETRIEVE MID PRICES AND CONIDS
    upperLong_conId = self.ib.qualifyContracts(self.upperContract)[0].conId
    short_conId = self.ib.qualifyContracts(self.shortContract)[0].conId
    lowerLong_conId = self.ib.qualifyContracts(self.lowerContract)[0].conId
    self.ib.reqMarketDataType(2)
    contracts = [self.upperContract, self.shortContract, self.lowerContract]
    marketData = self.ib.reqTickers(*contracts)
    while any(d.midpoint() != d.midpoint() for d in marketData):
            self.ib.sleep(0.01)
    upperLong_price = marketData[0].midpoint()
    short_price = marketData[1].midpoint()
    lowerLong_price = marketData[2].midpoint()

    #PRICES
    midPrice = round(((upperLong_price - short_price*2 + lowerLong_price)), 2)
    bidPrice = round((marketData[0].bid - marketData[1].ask*2 + marketData[2].bid), 2)
    minPrice = round((midPrice+(bidPrice-midPrice)*self.maxSpread), 2)
    limitPrice = midPrice
    priceStep = round((round(((midPrice-minPrice)/5), 1))/0.05)*0.05

    print(f'Selling {self.long_quantity} BWB contracts...')
    self.telegram_bot_sendtext(f'Selling {self.long_quantity} BWB contracts...')
    while True:
        Qty = self.long_quantity
        combo_contract = Contract(symbol='SPX', secType='BAG', currency='USD', exchange='SMART', tradingClass='SPXW', comboLegs=[ComboLeg(conId=upperLong_conId, ratio=1, action='BUY'), ComboLeg(conId=short_conId, ratio=2, action='SELL'), ComboLeg(conId=lowerLong_conId, ratio=1, action='BUY')])
        combo_order = LimitOrder('SELL', Qty, round(limitPrice, 2), transmit=self.live_trading)
        combo_trade = self.ib.placeOrder(combo_contract, combo_order)

        self.ib.sleep(300)

        #CHECK FOR PARTIAL FILL
        filled = combo_trade.orderStatus.filled
        remaining = combo_trade.orderStatus.remaining
        start_time = int(datetime.now().time().strftime("%H%M%S"))
        timeout = 900 #AMOUNT OF SECONDS TO WAIT BEFORE CONTINUING
        if filled > 0 and remaining > 0:
            print(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            self.telegram_bot_sendtext(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            while combo_trade.orderStatus.status != "Filled":
                current_time = int(datetime.now().time().strftime("%H%M%S"))
                elapsed_time = current_time - start_time
                if elapsed_time > timeout:
                    filled = combo_trade.orderStatus.filled
                    remaining = combo_trade.orderStatus.remaining
                    Qty = remaining
                    print(f'waited 15 minutes but not all contracts are filled. Trying the remaining contracts again at a different price. Contracts filled/remaining: {filled}/{remaining}')
                    self.telegram_bot_sendtext(f'waited 15 minutes but not all contracts are filled. Trying the remaining contracts again at a different price. Contracts filled/remaining: {filled}/{remaining}')
                    break
                self.ib.sleep(10)

        if combo_trade.orderStatus.status == "Filled":
            print('BWB sold.')
            self.telegram_bot_sendtext(f'BWB sold.')
            break

        limitPrice -= priceStep
        limitPrice = round(limitPrice, 2)
        if limitPrice < minPrice:
            print("The price rose too high, my order did not fly.\nStarting from midprice, again I'll try.")
            self.telegram_bot_sendtext("The price rose too high, my order did not fly.\nFrom midprice again, I will try.")
            self.ib.sleep(5)
            self.closeBWB()
        else:
            print(f"Limit order not filled. Cancelling order and trying again, removing 10 cents from the limit price. Limit Price/Bid Price: {limitPrice}/{bidPrice}")
            self.telegram_bot_sendtext(f"Limit order not filled. Cancelling order and trying again, removing 10 cents from the limit price. Limit Price/Bid Price: {limitPrice}/{bidPrice}")
            self.ib.cancelOrder(combo_order)
            self.ib.sleep(5)   


def closeCalendar(self, calendarStrike, Qty):
    #REMOVE EXISTING CALENDAR
    self.frontCalendarContract = Option('SPX', self.frontCalendarContract.lastTradeDateOrContractMonth, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
    self.backCalendarContract = Option('SPX', self.backCalendarContract.lastTradeDateOrContractMonth, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
    frontCalendarContractId = self.ib.qualifyContracts(self.frontCalendarContract)[0].conId
    backCalendarContractId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId

    self.ib.reqMarketDataType(2)
    contracts = [self.frontCalendarContract, self.backCalendarContract]
    marketData = self.ib.reqTickers(*contracts)
    while any(d.midpoint() != d.midpoint() for d in marketData):
            self.ib.sleep(0.01)
    frontCalendarPrice = marketData[0].midpoint()
    backCalendarPrice = marketData[1].midpoint()

    #PRICES
    midPrice = -frontCalendarPrice + backCalendarPrice
    bidPrice = -marketData[0].ask + marketData[1].bid
    minPrice = round((midPrice+(bidPrice-midPrice)*self.maxSpread), 2)
    limitPrice = midPrice
    priceStep = round((round(((midPrice-minPrice)/5), 1))/0.05)*0.05

    print(f'Selling {Qty} calendar contracts at {calendarStrike} strike...')
    self.telegram_bot_sendtext(f'Selling {Qty} calendar contracts at {calendarStrike} strike...')
    while True:
        combo_contract = Contract(symbol='SPX', secType='BAG', currency='USD', exchange='SMART', tradingClass='SPXW', comboLegs=[ComboLeg(conId=frontCalendarContractId, ratio=1, action='SELL'), ComboLeg(conId=backCalendarContractId, ratio=1, action='BUY')])
        combo_order = LimitOrder('SELL', Qty, round(limitPrice, 2), transmit=self.live_trading)
        combo_trade = self.ib.placeOrder(combo_contract, combo_order)

        self.ib.sleep(300)

        #CHECK FOR PARTIAL FILL
        filled = combo_trade.orderStatus.filled
        remaining = combo_trade.orderStatus.remaining
        start_time = int(datetime.now().time().strftime("%H%M%S"))
        timeout = 900 #AMOUNT OF SECONDS TO WAIT BEFORE CONTINUING
        if filled > 0 and remaining > 0:
            print(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            self.telegram_bot_sendtext(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            while combo_trade.orderStatus.status != "Filled":
                current_time = int(datetime.now().time().strftime("%H%M%S"))
                elapsed_time = current_time - start_time
                if elapsed_time > timeout:
                    filled = combo_trade.orderStatus.filled
                    remaining = combo_trade.orderStatus.remaining
                    Qty = remaining
                    self.calendarStrike = calendarStrike
                    self.calendarQty = Qty
                    self.margin = self.margin + limitPrice*100*Qty
                    print(f'waited 15 minutes but not all contracts are filled. Trying the remaining contracts again at a different price. Contracts filled/remaining: {filled}/{remaining}')
                    self.telegram_bot_sendtext(f'waited 15 minutes but not all contracts are filled. Trying the remaining contracts again at a different price. Contracts filled/remaining: {filled}/{remaining}')
                    break
                self.ib.sleep(10)

        if combo_trade.orderStatus.status == "Filled":
            print('Calendar sold.')
            self.telegram_bot_sendtext(f'Calendar sold.')
            break
        
        limitPrice -= priceStep
        limitPrice = round(limitPrice, 2)
        if limitPrice < minPrice:
            print("Limit order not filled, price higher or equal to ask price. Starting over again from midprice...")
            self.telegram_bot_sendtext("Limit order not filled, price higher or equal to ask price. Starting over again from midprice...")
            self.ib.sleep(5)
            self.closeCalendar()
        else:
            print(f"Limit order not filled. Cancelling order and trying again, removing 10 cents from the limit price. Limit Price/Bid Price: {limitPrice}/{bidPrice}")
            self.telegram_bot_sendtext(f"Limit order not filled. Cancelling order and trying again, removing 10 cents from the limit price. Limit Price/Bid Price: {limitPrice}/{bidPrice}")
            self.ib.cancelOrder(combo_order)
            self.ib.sleep(5)
