from ib_insync import *
import sys, os
import matplotlib.pyplot as plt
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..'))
from greeks import *
from datetime import datetime, timedelta


def upwardsRiskprofile(self):
    #THIS FUNCTION GENERATES THE RISK PROFILE FOR THE BWB AS WELL AS A BWB WITH UPWARDS CALENDAR ADJUSTMENT. FURTHERMORE, IT CAN GENERATE THE RISK PROFILE POSSIBLE ADJUSTMENTS(MOVING LEGS).
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
    self.oneThirdMovedLegsTline = {}
    self.twoThirdMovedLegsTline = {}
    self.allMovedLegsTline = {}
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
        
        # if self.adjusted == 'No':
        #     strikes = [S for S in range(lowerStrike, upperStrike, steps)]
        #     plt.plot(strikes, butterflyPnL, label=f"T+{i}")
            
        if self.adjusted == 'Calendar':
            #BROKEN WING BUTTERFLY
            Tback = (backMonth_daystoExpiry - i+0.001)/365
            upper_optPrices = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            short_optPrices = [blackScholes(self.TNX, S, self.shortStrike, T, short_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            lower_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, T, lowerLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            butterflyPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 - self.commissionAfterClose for x, y, z in zip(upper_optPrices, short_optPrices, lower_optPrices)]        

            #CALENDAR SPREAD
            front_optPrices = [blackScholes(self.TNX, S, self.calendarStrike, T, frontMonth_IV, 'P') for S in range(self.calendarStrike, upperStrike, steps)]
            back_optPrices = [blackScholes(self.TNX, S, self.calendarStrike, Tback, backMonth_IV, 'P') for S in range(self.calendarStrike, upperStrike, steps)]
            calendarPnL =  [(self.backCalendarPremium-self.frontCalendarPremium + d-e)*-100 for d, e in zip(front_optPrices, back_optPrices)]   
            calendarPnLReversed = calendarPnL[::-1]   
            totalCalendarPnL = calendarPnLReversed + calendarPnL
            totalCalendarPnL =  [calendarPnLReversed[0]]*(len(butterflyPnL)-len(totalCalendarPnL)) + totalCalendarPnL
            
            #MOVING UPPER STRIKE LEGS
            upper_optPrices2 = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            movedContract_optPrices = [blackScholes(self.TNX, S, self.upperStrike, Tback, movedContract_IV, 'P') for S in range(lowerStrike, upperStrike, steps)]
            movedCalendarPnL =  [(movedContractPrice-currentUpperPrice + d-e)*-100 for d, e in zip(upper_optPrices2, movedContract_optPrices)]   
            movedCalendarPnLReversed = movedCalendarPnL[::-1]   
            totalMovedCalendarPnL = (movedCalendarPnLReversed + movedCalendarPnL)
            totalMovedCalendarPnL = totalMovedCalendarPnL[(len(totalMovedCalendarPnL)-180):]

            #INCLUDE MOVING UPPER STRIKE-10 AS WELL FOR A HIGH NEGATIVE DELTA?
            
            #COMBINED STRATEGIES(JUST LOOK AT THIS ONLY)
            rolloverCalendarPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a - self.commissionAfterClose for x, y, z, a in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL)]        
            oneThirdMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a + round((self.long_quantity)/3)*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalMovedCalendarPnL)]        
            twoThirdMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a + round(((self.long_quantity)/3)*2)*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalMovedCalendarPnL)]        
            allMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.calendarQty*a + self.long_quantity*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalMovedCalendarPnL)]        

            
            self.strikes = [S for S in range(lowerStrike, upperStrike, steps)]
            self.currentTline[i] = rolloverCalendarPnL
            self.oneThirdMovedLegsTline[i] = oneThirdMovedLegsPnL
            self.twoThirdMovedLegsTline[i] = twoThirdMovedLegsPnL
            self.allMovedLegsTline[i] = allMovedLegsPnL

            strikes = [S for S in range(lowerStrike, upperStrike, steps)]
            plt.plot(strikes, rolloverCalendarPnL, label=f"T+{i}")
            
    #SLOPE(DELTA) CALCULATION
    marketpriceIndex = self.strikes.index(self.market_price)
    slopeRange = self.standardDeviation/2
    self.zerodteSlope = (self.currentTline[0][int(marketpriceIndex+(slopeRange/5))]-self.currentTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.oneThirdMovedLegsSlope = (self.oneThirdMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.oneThirdMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.twoThirdMovedLegsSlope = (self.twoThirdMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.twoThirdMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.allMovedLegsSlope = (self.allMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.allMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)

    print(f'{self.zerodteSlope}, {self.oneThirdMovedLegsSlope}, {self.twoThirdMovedLegsSlope}, {self.allMovedLegsSlope}')
    print('Riskprofile set up.')
    self.telegram_bot_sendtext('Riskprofile set up')
            
    #PLOT RESULTS
    plt.xlabel('Underlying Asset Price')
    plt.ylabel('Profit/Loss')
    plt.title('Payoff')
    plt.grid(True)
    plt.legend()
    plt.show()


def downwardsRiskprofile(self):
    #THIS FUNCTION CHECKS ALL POSSIBLE ADJUSTMENTS BEFORE ADJUSTING TO THE DOWNSIDE WHEN NEEDED. IT RETURNS MULTIPLE T-LINES. ANOTHER FUNCTION THEN DECIDES WHICH ONE IS MOST SUITABLE AND SUBMITS THE TRADE.
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

    #CREATE IMAGINARY MOVED CONTRACTS (SETTING UP CALENDAR AT SELF.LOWERSTRIKE)
    short_expiry = self.BWBexpiry
    long_expiry = datetime.strptime(self.BWBexpiry, "%Y%m%d") + timedelta(days=7)
    long_expiry = long_expiry.strftime("%Y%m%d")
    self.frontCalendarContract = Option('SPX', short_expiry, self.lowerStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
    short_conId = self.ib.qualifyContracts(self.frontCalendarContract)[0].conId

    try:
        self.backCalendarContract = Option('SPX', long_expiry, self.lowerStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')  
        long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
    except Exception as e:
        try:
            long_expiry = datetime.strptime(short_expiry, "%Y%m%d") + timedelta(days=8)
            long_expiry = long_expiry.strftime("%Y%m%d")
            self.backCalendarContract = Option('SPX', long_expiry, self.lowerStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')   
            long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
        except Exception as e:
            try:
                long_expiry = datetime.strptime(short_expiry, "%Y%m%d") + timedelta(days=6)
                long_expiry = long_expiry.strftime("%Y%m%d")
                self.backCalendarContract = Option('SPX', long_expiry, self.lowerStrike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')   
                long_conId = self.ib.qualifyContracts(self.backCalendarContract)[0].conId
            except Exception as e:
                print("No contracts available 6, 7 or 8 days after BWB expiry. Downwards riskprofile cannot be setup. Please adjust manually.")

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
    
    self.frontNewCalendarContract = Option('SPX', short_expiry, self.lowerStrike-20, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
    self.backNewCalendarContract = Option('SPX', long_expiry, self.lowerStrike-20, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')   
    newCalendarContracts = [self.frontNewCalendarContract, self.backNewCalendarContract]
    newCalendarContracts = self.ib.qualifyContracts(*newCalendarContracts)
    data = [self.ib.reqMktData(c, '', False, False) for c in newCalendarContracts]
    tickers = [self.ib.ticker(c) for c in newCalendarContracts]
    while any(d.midpoint() != d.midpoint() for d in data):
        self.ib.sleep(0.01)

    prices = [(tickers[c].midpoint()) for c in range(len(newCalendarContracts))]
    prices.sort(reverse=True)
    currentFrontNewCalendarPrice, currentBackNewCalendarPrice = prices[1], prices[0]

    Tfront = frontMonth_daystoExpiry/365
    Tback = backMonth_daystoExpiry/365
    frontMonth_IV = IV_calc(currentFrontCalendarPrice, self.market_price, self.lowerStrike, Tfront, self.TNX)
    backMonth_IV = IV_calc(currentBackCalendarPrice, self.market_price, self.lowerStrike, Tback, self.TNX)
    newCalendarFrontMonth_IV = IV_calc(currentFrontCalendarPrice, self.market_price, self.lowerStrike-20, Tfront, self.TNX)
    newCalendarBackMonth_IV = IV_calc(currentBackCalendarPrice, self.market_price, self.lowerStrike-20, Tback, self.TNX)
    #DEFINE GRAPH SIZE
    self.strikeRange = 450
    self.steps = 5 #5, 10, 15, etc...

    #GENERATE ALL T-LINES
    self.currentTline = {}
    self.oneThirdMovedLegsTline = {}
    self.twoThirdMovedLegsTline = {}
    self.allMovedLegsTline = {}
    self.twoMovedoneNewCalendarTline = {}
    self.oneMovedtwoNewCalendarTline = {}
    self.allNewCalendarTline = {}
    for i in range(0, daysLeftToExpiry+1, 1):
        T = (daysLeftToExpiry - i+0.001)/365
        upperStrike = self.market_price+self.strikeRange
        lowerStrike = self.market_price-self.strikeRange

        Tback = (backMonth_daystoExpiry - i+0.001)/365
        upper_optPrices = [blackScholes(self.TNX, S, self.upperStrike, T, upperLong_IV, 'P') for S in range(lowerStrike, upperStrike, self.steps)]
        short_optPrices = [blackScholes(self.TNX, S, self.shortStrike, T, short_IV, 'P') for S in range(lowerStrike, upperStrike, self.steps)]
        lower_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, T, lowerLong_IV, 'P') for S in range(lowerStrike, upperStrike, self.steps)]
        butterflyPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 - self.commissionAfterClose for x, y, z in zip(upper_optPrices, short_optPrices, lower_optPrices)]        

        #MOVED LEG
        front_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, T, frontMonth_IV, 'P') for S in range(int(self.lowerStrike), upperStrike, self.steps)]
        back_optPrices = [blackScholes(self.TNX, S, self.lowerStrike, Tback, backMonth_IV, 'P') for S in range(int(self.lowerStrike), upperStrike, self.steps)]
        calendarPnL =  [(currentBackCalendarPrice-currentFrontCalendarPrice + d-e)*-100 for d, e in zip(front_optPrices, back_optPrices)]   
        calendarPnLReversed = calendarPnL[::-1]   
        totalCalendarPnL = calendarPnLReversed + calendarPnL
        totalCalendarPnL = totalCalendarPnL[(len(totalCalendarPnL)-len(butterflyPnL)):]

        #NEW CALENDAR
        newCalendarFront_optPrices = [blackScholes(self.TNX, S, self.lowerStrike-20, T, newCalendarFrontMonth_IV, 'P') for S in range(int(self.lowerStrike), upperStrike, self.steps)]
        newCalendarBack_optPrices = [blackScholes(self.TNX, S, self.lowerStrike-20, Tback, newCalendarBackMonth_IV, 'P') for S in range(int(self.lowerStrike), upperStrike, self.steps)]
        newCalendarPnL =  [(currentBackNewCalendarPrice-currentFrontNewCalendarPrice + d-e)*-100 for d, e in zip(newCalendarFront_optPrices, newCalendarBack_optPrices)]   
        newCalendarPnLReversed = newCalendarPnL[::-1]   
        totalNewCalendarPnL = newCalendarPnLReversed + newCalendarPnL
        totalNewCalendarPnL = totalNewCalendarPnL[(len(totalNewCalendarPnL)-len(butterflyPnL)):]
        
        #COMBINED STRATEGIES(JUST LOOK AT THIS ONLY)
        oneThirdMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + round((self.long_quantity)/3)*a - self.commissionAfterClose for x, y, z, a in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL)]        
        twoThirdMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + round(((self.long_quantity)/3)*2)*a - self.commissionAfterClose for x, y, z, a in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL)]        
        allMovedLegsPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.long_quantity*a - self.commissionAfterClose for x, y, z, a in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL)]        
        twoMovedoneNewCalendarPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + round(((self.long_quantity)/3)*2)*a + round((self.long_quantity)/3)*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalNewCalendarPnL)]       
        oneMovedtwoNewCalendarPnL =  [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + round((self.long_quantity)/3)*a + round(((self.long_quantity)/3)*2)*b - self.commissionAfterClose for x, y, z, a, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalCalendarPnL, totalNewCalendarPnL)]       
        allNewCalendarPnL = [((self.upperPremium-x)*self.long_quantity + (self.shortPremium-y)*-self.short_quantity + (self.lowerPremium-z)*self.long_quantity)*-100 + self.long_quantity*b - self.commissionAfterClose for x, y, z, b in zip(upper_optPrices, short_optPrices, lower_optPrices, totalNewCalendarPnL)]       
        
        self.strikes = [S for S in range(lowerStrike, upperStrike, self.steps)]
        self.currentTline[i] = butterflyPnL
        self.oneThirdMovedLegsTline[i] = oneThirdMovedLegsPnL
        self.twoThirdMovedLegsTline[i] = twoThirdMovedLegsPnL
        self.allMovedLegsTline[i] = allMovedLegsPnL
        self.twoMovedoneNewCalendarTline[i] = twoMovedoneNewCalendarPnL
        self.oneMovedtwoNewCalendarTline[i] = oneMovedtwoNewCalendarPnL
        self.allNewCalendarTline[i] = allNewCalendarPnL


    #SLOPE(DELTA) CALCULATION
    marketpriceIndex = self.strikes.index(self.market_price)
    slopeRange = self.standardDeviation/2
    self.zerodteSlope = (self.currentTline[0][int(marketpriceIndex+(slopeRange/5))]-self.currentTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.oneThirdMovedLegsSlope = (self.oneThirdMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.oneThirdMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.twoThirdMovedLegsSlope = (self.twoThirdMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.twoThirdMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.allMovedLegsSlope = (self.allMovedLegsTline[0][int(marketpriceIndex+(slopeRange/5))]-self.allMovedLegsTline[0][int(marketpriceIndex-(slopeRange/5))])/(slopeRange*2)
    self.twoMovedoneNewCalendarSlope = 1
    self.oneMovedtwoNewCalendarSlope = 1
    self.allNewCalendarSlope = 1

    print(self.zerodteSlope, self.oneThirdMovedLegsSlope, self.twoThirdMovedLegsSlope, self.allMovedLegsSlope)
    print('Riskprofile set up.')
    self.telegram_bot_sendtext('Riskprofile set up')

    # strikes = [S for S in range(lowerStrike, upperStrike, self.steps)]
    # plt.plot(strikes, self.currentTline[0], label='current')
    # plt.plot(strikes, self.oneThirdMovedLegsTline[0], label='one')
    # plt.plot(strikes, self.twoThirdMovedLegsTline[0], label='two')
    # plt.plot(strikes, self.allMovedLegsTline[0], label='all')
    # plt.plot(strikes, self.twoMovedoneNewCalendarTline[0], label='all')
    # plt.plot(strikes, self.oneMovedtwoNewCalendarTline[0], label='all')
    # plt.plot(strikes, self.allNewCalendarTline[0], label='all')

    # #PLOT RESULTS
    # plt.xlabel('Underlying Asset Price')
    # plt.ylabel('Profit/Loss')
    # plt.title('Payoff')
    # plt.grid(True)
    # plt.legend()
    # plt.show()