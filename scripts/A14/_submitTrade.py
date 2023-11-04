from ib_insync import *
import sys, os
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..'))
from greeks import *
import pandas as pd
from datetime import datetime, timedelta
import itertools


def opening(self):
    print('Opening new trade...')
    self.telegram_bot_sendtext('Opening new trade...')
    #FETCH MIDPRICES OF QUALIFIABLE OPTION CONTRACTS
    upperLong_contracts = [Option('SPX', self.expiry, strike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW') for strike in range(self.market_price, self.market_price+6, 5)]
    short_contracts = [Option('SPX', self.expiry, strike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW') for strike in range(self.market_price-50, self.market_price-29, 5)]
    lowerLong_contracts = [Option('SPX', self.expiry, strike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW') for strike in range(self.market_price-110, self.market_price-89, 5)]
    contracts = upperLong_contracts + short_contracts + lowerLong_contracts
    self.ib.qualifyContracts(*contracts)
    self.ib.reqMarketDataType(2)
    upperData = [self.ib.reqMktData(c, '', False, False) for c in upperLong_contracts]
    upperTickers = [self.ib.ticker(c) for c in upperLong_contracts]
    shortData = [self.ib.reqMktData(c, '', False, False) for c in short_contracts]
    shortTickers = [self.ib.ticker(c) for c in short_contracts]
    lowerData = [self.ib.reqMktData(c, '', False, False) for c in lowerLong_contracts]
    lowerTickers = [self.ib.ticker(c) for c in lowerLong_contracts]
    self.ib.sleep(5)

    upperLong_Prices = [(upperTickers[c].midpoint()) for c in range(len(upperLong_contracts))]
    short_Prices = [(shortTickers[c].midpoint()) for c in range(len(short_contracts))]
    lowerLong_Prices = [(lowerTickers[c].midpoint()) for c in range(len(lowerLong_contracts))]

    T = self.daystoExpiry/365
    #CALCULATE IMPLIED VOLATILITIES AND DELTAS
    upperLong_IVs = [IV_calc(price, self.market_price, K, T, self.TNX) for K, price in zip([K for K in range(self.market_price, self.market_price+6, 5)], upperLong_Prices)]
    short_IVs = [IV_calc(price, self.market_price, K, T, self.TNX) for K, price in zip([K for K in range(self.market_price-50, self.market_price-29, 5)], short_Prices)]
    lowerLong_IVs = [IV_calc(price, self.market_price, K, T, self.TNX) for K, price in zip([K for K in range(self.market_price-110, self.market_price-89, 5)], lowerLong_Prices)]
    upperLong_Deltas = [delta_calc(self.TNX, self.market_price, strike, T, IV, 'P')*100 for strike, IV in zip([strike for strike in range(self.market_price, self.market_price+6, 5)], upperLong_IVs)]
    short_Deltas = [delta_calc(self.TNX, self.market_price, strike, T, IV, 'P')*100*-2 for strike, IV in zip([strike for strike in range(self.market_price-50, self.market_price-29, 5)], short_IVs)]
    lowerLong_Deltas = [delta_calc(self.TNX, self.market_price, strike, T, IV, 'P')*100 for strike, IV in zip([strike for strike in range(self.market_price-110, self.market_price-89, 5)], lowerLong_IVs)]

    #FIND STRATEGY WITH FLATTEST DELTA
    combinations = list(itertools.product(upperLong_Deltas, short_Deltas, lowerLong_Deltas))
    sums = []
    for item in combinations:
        item_sum = sum(item)
        sums.append(item_sum)
    flattestDelta = min(sums, key=lambda x:abs(x-0))
    print(flattestDelta)
        
    if -3 <= flattestDelta <= 1:
        #FIND CORRESPONDING CONTRACTS
        flattestDeltaCombination = [combinations[sums.index(flattestDelta)]]
        value1 = flattestDeltaCombination[0][0]
        value2 = flattestDeltaCombination[0][1]
        value3 = flattestDeltaCombination[0][2]
        for item in upperLong_Deltas:
            if item == value1 or item == value2 or item == value3:
                self.upperContract = upperLong_contracts[upperLong_Deltas.index(item)]
                print(upperLong_contracts[upperLong_Deltas.index(item)])
                break
        for item in short_Deltas:
            if item == value1 or item == value2 or item == value3:
                self.shortContract = short_contracts[short_Deltas.index(item)]
                print(short_contracts[short_Deltas.index(item)])
                break
        for item in lowerLong_Deltas:
            if item == value1 or item == value2 or item == value3:
                self.lowerContract = lowerLong_contracts[lowerLong_Deltas.index(item)]
                print(lowerLong_contracts[lowerLong_Deltas.index(item)])
                break

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
        askPrice = round((marketData[0].ask - marketData[1].bid*2 + marketData[2].ask), 2)
        maxPrice = round((midPrice+(askPrice-midPrice)*self.maxSpread), 2)
        limitPrice = midPrice
        priceStep = round((round(((maxPrice-midPrice)/5), 1))/0.05)*0.05

        #MARGIN AND CONTRACTS
        maxLossOneContract = (((self.shortContract.strike - self.lowerContract.strike)-(self.upperContract.strike - self.shortContract.strike)) + askPrice)*100
        contract_quantity = round(((self.availableMargin*(2/3))/maxLossOneContract))
        self.long_quantity, self.short_quantity = contract_quantity, contract_quantity*2

        if contract_quantity < 3:
            print("The margin too low, the contracts too few,\nThe trade is not possible, I must bid adieu.\n")
            self.exit_program()

        print(f'Contracts found. Available Margin: {self.availableMargin} Margin per contract: {maxLossOneContract} Submitting order for {contract_quantity} contracts...')
        self.telegram_bot_sendtext(f'Contracts found. Available Margin: {self.availableMargin} Margin per contract: {maxLossOneContract} Submitting order for {contract_quantity} contracts...')
        while True:
            combo_contract = Contract(symbol='SPX', secType='BAG', currency='USD', exchange='SMART', tradingClass='SPXW', comboLegs=[ComboLeg(conId=upperLong_conId, ratio=1, action='BUY'), ComboLeg(conId=short_conId, ratio=2, action='SELL'), ComboLeg(conId=lowerLong_conId, ratio=1, action='BUY')])
            combo_order = LimitOrder('BUY', contract_quantity, round(limitPrice, 2), transmit=self.live_trading)
            combo_trade = self.ib.placeOrder(combo_contract, combo_order)
            
            self.ib.sleep(300)
            #CHECK FOR PARTIAL FILL
            filled = combo_trade.orderStatus.filled
            remaining = combo_trade.orderStatus.remaining
            start_time = int(datetime.now().time().strftime("%H%M%S"))
            timeout = 1800 #AMOUNT OF SECONDS TO WAIT BEFORE CONTINUING
            if filled > 0 and remaining > 0:
                print(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
                self.telegram_bot_sendtext(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
                while combo_trade.orderStatus.status != "Filled":
                    print(f'Contracts filled/remaining: {filled}/{remaining}.')
                    self.telegram_bot_sendtext(f'Contracts filled/remaining: {filled}/{remaining}.')
                    current_time = int(datetime.now().time().strftime("%H%M%S"))
                    elapsed_time = current_time - start_time
                    if elapsed_time > timeout:
                        filled = combo_trade.orderStatus.filled
                        self.ib.cancelOrder(combo_order)
                        print(f'waited 30 minutes, cancelling order and continuing trade with currently filled contract amount: {filled}')
                        self.telegram_bot_sendtext(f'waited 30 minutes, cancelling order and continuing trade with currently filled contract amount: {filled}')
                        #TRY TO SAVE THE FILL DATAFRAME AND ADD THE FILL DATAFRAME OF THE MODIFIED ORDER TO IT
                        break
                    self.ib.sleep(10)

            if combo_trade.orderStatus.status == "Filled":
                #SAVE TRADE DETAILS TO PANDAS DATAFRAME
                fill = combo_trade.fills

                fill_2_df = util.df([fi.contract for fi in fill])
                fill_3_df = util.df([fi.execution for fi in fill])
                fill_4_df = util.df([fi.commissionReport for fi in fill])
                fill_df = pd.concat([fill_2_df, fill_3_df, fill_4_df], sort=False, axis=1)
                self.BWBdetails = fill_df.loc[fill_df['secType'].astype(str).str.contains('OPT')]
                self.margin = (((self.shortContract.strike - self.lowerContract.strike)-(self.upperContract.strike - self.shortContract.strike)) + limitPrice)*100*contract_quantity

                print('Order filled. Updating tradelog...')
                print(f"Market Price: {self.market_price}\nLower, Short, and Upper BWB Strike: {self.lowerContract.strike}, {self.shortContract.strike}, {self.upperContract.strike}\nContracts: {contract_quantity}\nDelta: {flattestDelta}\nMargin per contract: {maxLossOneContract}\nMargin Impact: {self.margin}")
                self.telegram_bot_sendtext('Order filled. Updating tradelog...')
                self.telegram_bot_sendtext(f"Market Price: {self.market_price}\nLower, Short, and Upper BWB Strike: {self.lowerContract.strike}, {self.shortContract.strike}, {self.upperContract.strike}\nContracts: {contract_quantity}\nDelta: {flattestDelta}\nMargin per contract: {maxLossOneContract}\nMargin Impact: {self.margin}")

                self.openinglog()
                break

            limitPrice += priceStep
            limitPrice = round(limitPrice, 2)
            if limitPrice > maxPrice:
                print("Limit order not filled, price higher or equal to maximum price. Setting up new BWB and trying again for a better price...")
                self.telegram_bot_sendtext("Limit order not filled, price higher or equal to maximum price. Setting up new BWB and trying again for a better price...")
                self.ib.cancelOrder(combo_order)
                self.ib.sleep(5)
                self.opening()
            else:
                print(f"Limit order not filled. Cancelling order and trying again, increasing the price by 10 cents. Limit Price/Ask Price: {limitPrice}/{askPrice}")
                self.telegram_bot_sendtext(f"Limit order not filled. Cancelling order and trying again, increasing the price by 10 cents. Limit Price/Ask Price: {limitPrice}/{askPrice}")
                self.ib.cancelOrder(combo_order)
                self.ib.sleep(5)
    else:
        print("try 30/40BWB")
        self.opening()


def calendar(self, calendarStrike, Qty):
    short_expiry = self.BWBexpiry 
    long_expiry = datetime.strptime(self.BWBexpiry, "%Y%m%d") + timedelta(days=7)
    long_expiry = long_expiry.strftime("%Y%m%d")
    self.frontCalendarContract = Option('SPX', short_expiry, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
    short_conId = self.ib.qualifyContracts(self.frontCalendarContract)[0].conId

    #OPTION CONTRACTS
    try:
        self.backCalendarContract = Option('SPX', long_expiry, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')  
        long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
    except Exception as e:
        try:
            long_expiry = datetime.strptime(short_expiry, "%Y%m%d") + timedelta(days=8)
            long_expiry = long_expiry.strftime("%Y%m%d")
            self.backCalendarContract = Option('SPX', long_expiry, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')   
            long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
        except Exception as e:
            try:
                long_expiry = datetime.strptime(short_expiry, "%Y%m%d") + timedelta(days=6)
                long_expiry = long_expiry.strftime("%Y%m%d")
                self.backCalendarContract = Option('SPX', long_expiry, calendarStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')   
                long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
            except Exception as e:
                print("no contracts available 6, 7 or 8 days after BWB expiry. Please adjust manually.")

    self.ib.reqMarketDataType(2)
    contracts = [self.frontCalendarContract, self.backCalendarContract]
    marketData = self.ib.reqTickers(*contracts)
    while any(d.midpoint() != d.midpoint() for d in marketData):
            self.ib.sleep(0.01)
    short_price = marketData[0].midpoint()
    long_price = marketData[1].midpoint()

    #PRICES
    midPrice = round((-short_price + long_price), 2)
    askPrice = round((-marketData[0].bid + marketData[1].ask), 2)
    maxPrice = round((midPrice+(askPrice-midPrice)*self.maxSpread), 2)
    limitPrice = midPrice
    priceStep = round((round(((maxPrice-midPrice)/5), 1))/0.05)*0.05

    print(f'Submitting calendar order for {Qty} contracts at {calendarStrike} strike...')
    self.telegram_bot_sendtext(f'Submitting calendar order for {Qty} contracts at {calendarStrike} strike...')
    while True:
        combo_contract = Contract(symbol='SPX', secType='BAG', currency='USD', exchange='SMART', tradingClass='SPXW', comboLegs=[ComboLeg(conId=short_conId, ratio=1, action='SELL'), ComboLeg(conId=long_conId, ratio=1, action='BUY')])
        combo_order = LimitOrder('BUY', Qty, round(limitPrice, 2), transmit=self.live_trading)
        combo_trade = self.ib.placeOrder(combo_contract, combo_order)

        self.ib.sleep(300)
        #CHECK FOR PARTIAL FILL
        filled = combo_trade.orderStatus.filled
        remaining = combo_trade.orderStatus.remaining
        start_time = int(datetime.now().time().strftime("%H%M%S"))
        timeout = 1800 #AMOUNT OF SECONDS TO WAIT BEFORE CONTINUING
        if filled > 0 and remaining > 0:
            print(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            self.telegram_bot_sendtext(f'Order partially filled. Contracts filled/remaining: {filled}/{remaining}. Waiting for the other ones to fill...')
            while combo_trade.orderStatus.status != "Filled":
                print(f'Contracts filled/remaining: {filled}/{remaining}.')
                self.telegram_bot_sendtext(f'Contracts filled/remaining: {filled}/{remaining}.')
                current_time = int(datetime.now().time().strftime("%H%M%S"))
                elapsed_time = current_time - start_time
                if elapsed_time > timeout:
                    filled = combo_trade.orderStatus.filled
                    self.ib.cancelOrder(combo_order)
                    print(f'waited 30 minutes, continuing trade with currently filled contract amount: {filled} MANUALLY CHECK IF THE TRADE IS STILL DOING ALLRIGHT!!!')
                    self.telegram_bot_sendtext(f'waited 30 minutes, continuing trade with currently filled contract amount: {filled} MANUALLY CHECK IF THE TRADE IS STILL DOING ALLRIGHT!!!')
                    #TRY TO SAVE THE FILL DATAFRAME AND ADD THE FILL DATAFRAME OF THE MODIFIED ORDER TO IT
                    break
                self.ib.sleep(20)
                
        if combo_trade.orderStatus.status == "Filled":
            #SAVE TRADE DETAILS TO PANDAS DATAFRAME
            fill = combo_trade.fills

            fill_2_df = util.df([fi.contract for fi in fill])
            fill_3_df = util.df([fi.execution for fi in fill])
            fill_4_df = util.df([fi.commissionReport for fi in fill])
            fill_df = pd.concat([fill_2_df, fill_3_df, fill_4_df], sort=False, axis=1)
            self.calendarDetails = fill_df.loc[fill_df['secType'].astype(str).str.contains('OPT')]
            self.calendarQty = Qty

            #REMOVE THIS. MAKE SURE TO LOAD TRADE AGAIN AFTER CALENDAR IS FILLED AND LOG IS UPDATED. ONLY THEN DO RISK PROFILE
            print('Order filled. Updating tradelog...')
            self.telegram_bot_sendtext(f'Order filled. Current margin: {self.margin}. Updating tradelog...')          
            break
        
        limitPrice += priceStep
        limitPrice = round(limitPrice, 2)
        if limitPrice > maxPrice:
            print("Limit order not filled, price higher or equal to ask price. Setting up new calendar and trying again for a better price...")
            self.telegram_bot_sendtext("Limit order not filled, price higher or equal to ask price. Setting up new calendar and trying again for a better price...")
            self.ib.cancelOrder(combo_order)
            self.ib.sleep(5)
            self.calendar()
            break
        else:
            print(f"Limit order not filled. Cancelling order and trying again, increasing the price by 10 cents. Ask Price/Limit Price: {askPrice}/{limitPrice} ")
            self.telegram_bot_sendtext(f"Limit order not filled. Cancelling order and trying again, increasing the price by 10 cents. Ask Price/Limit Price: {askPrice}/{limitPrice} ")
            self.ib.cancelOrder(combo_order)
            self.ib.sleep(5)