from ib_insync import *
import sys, os
import matplotlib.pyplot as plt
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..'))
from greeks import *
from datetime import date, datetime


def currentRiskprofile(self):
    #THIS FUNCTION CAN GENERATE THE RISK PROFILE FOR THE BWB AS WELL AS A BWB WITH UPWARDS CALENDAR ADJUSTMENT. FURTHERMORE, IT CAN GENERATE THE RISK PROFILE POSSIBLE ADJUSTMENTS(MOVING LEGS).
    #AFTER THE CALENDAR ADJUSTMENT IS DONE, THIS FUNCTION CAN THUS BE USED TO GENERATE ALL T-LINES OF THE TRADE AND ALSO THE ONES AFTER ANY LEGS HAVE BEEN MOVED. ANOTHER FUNCTION THEN CHECKS IF THERE IS A DEADZONE PRESENT AND IF ANY LEGS NEED TO BE MOVED.    
    BWBcontracts = [self.upperContract, self.shortContract, self.lowerContract]
    BWBcontracts = self.ib.qualifyContracts(*BWBcontracts)
    data = [self.ib.reqMktData(c, '', False, False) for c in BWBcontracts]
    tickers = [self.ib.ticker(c) for c in BWBcontracts]
    while any(d.midpoint() != d.midpoint() for d in data):
                self.ib.sleep(0.01)

    prices = [(tickers[c].midpoint()) for c in range(len(BWBcontracts))]
    prices.sort(reverse=True)
    currentUpperPrice, currentShortPrice, currentLowerPrice = prices[0], prices[1], prices[2]
    
    expiry_date = datetime.strptime(self.BWBexpiry, '%Y%m%d').date()
    daysLeftToExpiry = (expiry_date - self.today).days
    T = (daysLeftToExpiry)/365

    upperLong_IV = IV_calc(currentUpperPrice, self.market_price, self.upperStrike, T, self.TNX)
    short_IV = IV_calc(currentShortPrice, self.market_price, self.shortStrike, T, self.TNX)
    lowerLong_IV = IV_calc(currentLowerPrice, self.market_price, self.lowerStrike, T, self.TNX)

    if self.adjusted == 'Calendar':
        frontMonth_date, backMonth_date = datetime.strptime(self.frontCalendarContract.lastTradeDateOrContractMonth, '%Y%m%d').date(), datetime.strptime(self.backCalendarContract.lastTradeDateOrContractMonth, '%Y%m%d').date()
        frontMonth_daystoExpiry, backMonth_daystoExpiry  = (frontMonth_date - self.today).days, (backMonth_date - self.today).days

        calendarContracts = [self.frontCalendarContract, self.backCalendarContract]
        calendarContracts = self.ib.qualifyContracts(*calendarContracts)
        data = [self.ib.reqMktData(c, '', False, False) for c in calendarContracts]
        tickers = [self.ib.ticker(c) for c in calendarContracts]
        while any(d.midpoint() != d.midpoint() for d in data):
            self.ib.sleep(0.01)

        prices = [(tickers[c].midpoint()) for c in range(len(calendarContracts))]
        prices.sort(reverse=True)
        currentFrontCalendarPrice, currentBackCalendarPrice = prices[1], prices[0]
        
        Tfront = frontMonth_daystoExpiry/365
        Tback = backMonth_daystoExpiry/365
        frontMonth_IV = IV_calc(currentFrontCalendarPrice, self.market_price, self.calendarStrike, Tfront, self.TNX)
        backMonth_IV = IV_calc(currentBackCalendarPrice, self.market_price, self.calendarStrike, Tback, self.TNX)
        
        if hasattr(self, 'movedContract'):
            #MOVED CONTRACT DETAILS
            self.backMovedContract = Option('SPX', self.backCalendarContract.lastTradeDateOrContractMonth, self.upperStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
            movedContractData = self.ib.reqMktData(self.backMovedContract, '', False, False)
            movedContractTicker = self.ib.ticker(self.backMovedContract)
            while movedContractTicker.midpoint() != movedContractTicker.midpoint():
                self.ib.sleep(0.01)          
            movedContractPrice = movedContractTicker.midpoint()
            movedContract_IV = IV_calc(movedContractPrice, self.market_price, self.upperStrike, Tback, self.TNX)

    #DEFINE GRAPH SIZE
    strikeRange = 450
    steps = 5 #5, 10, 15, etc...
    
    #GENERATE ALL T-LINES
    self.currentTline = {}
    for i in range(0, daysLeftToExpiry+1, 1):
        T = (daysLeftToExpiry - i+0.001)/365
        upperStrike = self.market_price+strikeRange
        lowerStrike = self.market_price-strikeRange
        self.strikes = [S for S in range(lowerStrike, upperStrike, steps)]
        upper_optPrices = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
        short_optPrices = [blackScholes(self.TNX, S, self.shortStrike, T, short_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
        lower_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, T, lowerLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
        butterflyPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 - self.commissionAfterClose for x, y, z in zip(upper_optPrices, short_optPrices, lower_optPrices)]        
        self.currentTline[i] = butterflyPnL
        
        if self.adjusted == 'Calendar':
            #BROKEN WING BUTTERFLY
            Tback = (backMonth_daystoExpiry - i+0.001)/365
            upper_optPrices = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            short_optPrices = [blackScholes(self.TNX, S, self.shortStrike, T, short_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            lower_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, T, lowerLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            butterflyPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 for x, y, z in zip(upper_optPrices, short_optPrices, lower_optPrices)]        

            #CALENDAR SPREAD
            front_optPrices = [blackScholes(self.TNX, S, self.calendarStrike, T, frontMonth_IV, 'P') for S in range(int(self.calendarStrike), upperStrike, steps)]
            back_optPrices = [blackScholes(self.TNX, S, self.calendarStrike, Tback, backMonth_IV, 'P') for S in range(int(self.calendarStrike), upperStrike, steps)]
            calendarPnL =  [(self.backCalendarPremium-self.frontCalendarPremium + d-e)*-100 for d, e in zip(front_optPrices, back_optPrices)]   
            calendarPnLReversed = calendarPnL[::-1]   
            totalCalendarPnL = calendarPnLReversed + calendarPnL
            totalCalendarPnL =  [calendarPnLReversed[0]]*(len(butterflyPnL)-len(totalCalendarPnL)) + totalCalendarPnL
            
            #T LINES FOR CALENDAR UPWARDS ADJUSTMENT
            rolloverCalendarPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a - self.commissionAfterClose for x, y, z, a in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL)]        
            self.currentTline[i] = rolloverCalendarPnL

            if hasattr(self, 'movedContract'):
                #MOVED UPPER STRIKE LEGS
                upper_optPrices2 = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
                movedContract_optPrices = [blackScholes(self.TNX, S, self.upperStrike, Tback, movedContract_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
                movedCalendarPnL =  [(movedContractPrice-currentUpperPrice + d-e)*-100 for d, e in zip(upper_optPrices2, movedContract_optPrices)]   
                movedCalendarPnLReversed = movedCalendarPnL[::-1]   
                totalMovedCalendarPnL = (movedCalendarPnLReversed + movedCalendarPnL)
                totalMovedCalendarPnL = totalMovedCalendarPnL[(len(totalMovedCalendarPnL)-180):]

                #T LINES FOR CALENDAR UPWARDS ADJUSTMENT WITH MOVED LEGS
                movedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a + self.movedContractQty*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalMovedCalendarPnL)]        
                self.currentTline[i] = movedLegsPnL
        
        strikes = [S for S in range(lowerStrike, upperStrike, steps)]
        plt.plot(strikes, rolloverCalendarPnL, label=f"T+{i}")

    #SLOPE(DELTA) CALCULATION
    marketpriceIndex = self.strikes.index(self.market_price)
    slopeRange = self.standardDeviation/2
    self.zerodteSlope = (self.currentTline[0][int(marketpriceIndex+(slopeRange/5))]-self.currentTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)

    #PLOT RESULTS
    plt.xlabel('Underlying Asset Price')
    plt.ylabel('Profit/Loss')
    plt.title('Payoff')
    plt.grid(True)
    plt.legend()
    plt.show()


def PnL(self):
    positions_df = util.df(self.ib.portfolio())
    BWBPortfolio = positions_df.loc[positions_df['contract'].astype(str).str.contains(f'{self.upperContract.conId}') | positions_df['contract'].astype(str).str.contains(f'{self.shortContract.conId}') | positions_df['contract'].astype(str).str.contains(f'{self.lowerContract.conId}')]
    BWBunrealizedPnL = sum(BWBPortfolio['unrealizedPNL'].tolist())
    totalPnL = BWBunrealizedPnL - self.commissionAfterClose
    self.PnLpercentage = (totalPnL/self.margin)*100

    if self.adjusted == 'Calendar':
        calendarPortfolio = positions_df.loc[positions_df['contract'].astype(str).str.contains(f'{self.frontCalendarContract.conId}') | positions_df['contract'].astype(str).str.contains(f'{self.backCalendarContract.conId}')]
        calendarUnrealizedPnL = sum(calendarPortfolio['unrealizedPNL'].tolist())
        totalPnL = BWBunrealizedPnL + calendarUnrealizedPnL - self.commissionAfterClose
        self.PnLpercentage = (totalPnL/self.margin)*100

        if hasattr(self, 'movedContract'):
            movedLegPortfolio = positions_df.loc[positions_df['contract'].astype(str).str.contains(f'{self.frontMovedContract.conId}')]
            movedLegPnL = sum(movedLegPortfolio['unrealizedPNL'].tolist())
            totalPnL = totalPnL + movedLegPnL - self.commissionAfterClose
            self.PnLpercentage = (totalPnL/self.margin)*100

    if self.adjusted == 'Downwards':
        calendarPortfolio = positions_df.loc[positions_df['contract'].astype(str).str.contains(f'{self.frontCalendarContract.conId}') | positions_df['contract'].astype(str).str.contains(f'{self.backCalendarContract.conId}')]
        calendarUnrealizedPnL = sum(calendarPortfolio['unrealizedPNL'].tolist())
        totalPnL = BWBunrealizedPnL + calendarUnrealizedPnL
        self.PnLpercentage = (totalPnL/self.margin)*100
    
    self.totalPnL = totalPnL


def greeks(self):
    BWBcontracts = [self.upperContract, self.shortContract, self.lowerContract]
    BWBcontracts = self.ib.qualifyContracts(*BWBcontracts)
    data = [self.ib.reqMktData(c, '', False, False) for c in BWBcontracts]
    tickers = [self.ib.ticker(c) for c in BWBcontracts]
    while any(d.midpoint() != d.midpoint() for d in data):
                self.ib.sleep(0.01)

    prices = [(tickers[c].midpoint()) for c in range(len(BWBcontracts))]
    prices.sort(reverse=True)
    currentUpperPrice, currentShortPrice, currentLowerPrice = prices[0], prices[1], prices[2]
    
    daysLeftToExpiry = (datetime.strptime(self.upperContract.lastTradeDateOrContractMonth, '%Y%m%d')-datetime.strptime(self.today.strftime("%Y%m%d"), '%Y%m%d')).days
    T = (daysLeftToExpiry)/365
    
    upperLong_IV = IV_calc(currentUpperPrice, self.market_price, self.upperStrike, T, self.TNX)
    short_IV = IV_calc(currentShortPrice, self.market_price, self.shortStrike, T, self.TNX)
    lowerLong_IV = IV_calc(currentLowerPrice, self.market_price, self.lowerStrike, T, self.TNX)
    upperLong_Delta = delta_calc(self.TNX, self.market_price, self.upperStrike, T, upperLong_IV, 'P')
    short_Delta = delta_calc(self.TNX, self.market_price, self.shortStrike, T, short_IV, 'P')
    lowerLong_Delta = delta_calc(self.TNX, self.market_price, self.lowerStrike, T, lowerLong_IV, 'P')

    self.totalDelta = round(((upperLong_Delta*self.long_quantity - short_Delta*self.short_quantity + lowerLong_Delta*self.long_quantity)*100), 2)

    if self.adjusted == 'Calendar':
        calendarContracts = [self.frontCalendarContract, self.backCalendarContract]
        calendarContracts = self.ib.qualifyContracts(*calendarContracts)
        data = [self.ib.reqMktData(c, '', False, False) for c in calendarContracts]
        tickers = [self.ib.ticker(c) for c in calendarContracts]
        while any(d.midpoint() != d.midpoint() for d in data):
            self.ib.sleep(0.01)

        prices = [(tickers[c].midpoint()) for c in range(len(calendarContracts))]
        prices.sort(reverse=True)
        currentFrontCalendarPrice, currentBackCalendarPrice = prices[1], prices[0]

        frontMonth_date, backMonth_date = datetime.strptime(self.frontCalendarContract.lastTradeDateOrContractMonth, '%Y%m%d').date(), datetime.strptime(self.backCalendarContract.lastTradeDateOrContractMonth, '%Y%m%d').date()
        frontMonth_daystoExpiry, backMonth_daystoExpiry  = (frontMonth_date - today).days, (backMonth_date - today).days
        Tfront = frontMonth_daystoExpiry/365
        Tback = backMonth_daystoExpiry/365

        frontMonth_IV = IV_calc(currentFrontCalendarPrice, self.market_price, self.calendarStrike, Tfront, self.TNX)
        backMonth_IV = IV_calc(currentBackCalendarPrice, self.market_price, self.calendarStrike, Tback, self.TNX)
        frontMonth_Delta = delta_calc(self.TNX, self.market_price, self.market_price, Tfront, frontMonth_IV, 'P')
        backMonth_Delta = delta_calc(self.TNX, self.market_price, self.market_price, Tback, backMonth_IV, 'P')
        
        self.totalDelta = round(((upperLong_Delta*self.long_quantity - short_Delta*self.short_quantity + lowerLong_Delta*self.long_quantity - frontMonth_Delta*self.calendarQty + backMonth_Delta*self.calendarQty)*100), 2)
        if hasattr(self, 'movedContract'):
            movedContracts = [self.frontMovedContract, self.backMovedContract]
            movedContracts = self.ib.qualifyContracts(*movedContracts)
            data = [self.ib.reqMktData(c, '', False, False) for c in movedContracts]
            tickers = [self.ib.ticker(c) for c in movedContracts]
            while any(d.midpoint() != d.midpoint() for d in data):
                self.ib.sleep(0.01)
            
            prices = [(tickers[c].midpoint()) for c in range(len(movedContracts))]
            prices.sort(reverse=True)
            currentFrontMovedPrice, currentBackMovedPrice = prices[1], prices[0]

            frontMoved_IV = IV_calc(currentFrontMovedPrice, self.market_price, self.calendarStrike, Tfront, self.TNX)
            backMoved_IV = IV_calc(currentBackMovedPrice, self.market_price, self.calendarStrike, Tback, self.TNX)
            frontMoved_Delta = delta_calc(self.TNX, self.market_price, self.market_price, Tfront, frontMoved_IV, 'P')
            backMoved_Delta = delta_calc(self.TNX, self.market_price, self.market_price, Tback, backMoved_IV, 'P')

            self.totalDelta = round(((upperLong_Delta*self.long_quantity - short_Delta*self.short_quantity + lowerLong_Delta*self.long_quantity + (backMonth_Delta - frontMonth_Delta)*self.calendarQty + (backMoved_Delta - frontMoved_Delta)*self.movedContractQty)*100, 2))
    if self.adjusted == 'Downwards':
        print('not available yet')