#imports
from ib_insync import *
from datetime import date, datetime, time, timedelta
import numpy as np
import pandas as pd
import sys
import os
import requests
import pickle
import configparser
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '..'))
from greeks import *


class bot():
    from _logs import openinglog, calendarlog, movedleglog, downwardslog, marginlog, deletelog
    from _submitTrade import opening, calendar
    from _tradeStatus import currentRiskprofile, PnL, greeks
    from _riskprofile import upwardsRiskprofile, downwardsRiskprofile
    from _exitTrade import tradeExit, closeBWB, closeCalendar
    def __init__(self, *args, **kwargs):
        #ACCESS VALUES FROM CONFIG.INI FILE
        config = configparser.ConfigParser()
        config_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
        config.read(config_file_path)
        socket_port = config.getint('GENERAL SETTINGS', 'socket_port')
        self.availableMargin = float(config.get('A14', 'margin'))
        self.telegram_token = config.get('A14', 'telegram_token')
        self.telegram_chatID = config.get('A14', 'telegram_chatID')
        self.maxSpread = float(config.get('A14', 'max_spread')) #value of 0-1. If 1, you're willing to buy at the ask price. If 0, you're only willing to buy at mid price.
        print("Connecting to IB...")
        try:
            self.ib = IB()
            self.ib.connect("127.0.0.1", socket_port, clientId=1)

            self.fetch_marketdata()
            self.loadTrade()
            # self.PnL()
            #self.currentRiskprofile()
            # self.profitSpace()

            self.whattodo()
            self.ib.run()
        except Exception as e:
            print(str(e))
            self.telegram_bot_sendtext(str(e))
        

    def whattodo(self):
        if self.inTrade == True:
            self.upwardsRiskprofile()
            self.currentRiskprofile()
            self.PnL()
            #self.greeks()
            print(f'Market Price: {self.market_price} IV: {self.IV} Unrealized PnL: {round(self.totalPnL)}({round(self.PnLpercentage, 2)}%) | SD: {self.standardDeviation}\nSlope within 1SD: {self.zerodteSlope}')
            self.telegram_bot_sendtext(f'Market Price: {self.market_price} | IV: {self.IV} | Unrealized PnL: {round(self.totalPnL)}({round(self.PnLpercentage, 2)}%) | SD: {self.standardDeviation}\nSlope within 1SD: {self.zerodteSlope}')

            if self.PnLpercentage >= 5 or 'Exit' in self.values_dict:
                print('exiting trade soon...')
                self.telegram_bot_sendtext("exiting trade soon...")
                #GET PREVIOUS PNL PERCENTAGE AND SEE IF IT WAS RISING OR NOT
                self.exit = 'True'
                self.currentlyRising = 'True'
                if 'Exit' in self.values_dict:
                    self.previousPnLpercentage = self.values_dict['PnLpercentage']
                    if self.PnLpercentage >= self.previousPnLpercentage:
                        self.currentlyRising = 'True'
                    else:
                        self.currentlyRising = 'False'
                if 'Rising' in self.values_dict:
                    self.rising = self.values_dict['Rising']

                #DUMP CURRENT DATA TO PKL FILE
                script_directory = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(script_directory, 'a14weekly.pkl')
                with open(file_path, 'rb') as file:
                    values_dict = pickle.load(file)
                
                values_dict['Exit'] = self.exit
                values_dict['PnLpercentage'] = self.PnLpercentage
                values_dict['Rising'] = self.currentlyRising

                with open(file_path, 'wb') as file:
                    pickle.dump(values_dict, file)
                self.tradeExit()

            elif self.values_dict['Adjusted'] == 'No' and self.market_price >= self.upperStrike+5 and 21 <= self.currentDatetime.hour < 22:
                print('Adjusting upwards with calendar...')
                self.telegram_bot_sendtext('Adjusting upwards with calendar...')

                self.calendar(self.market_price+20, round((self.long_quantity-0.1)/2))
                self.adjusted = 'Calendar'
                self.calendarlog()

                print('Setting up riskprofiles and checking for deadzone...')
                self.telegram_bot_sendtext('Setting up riskprofiles and checking for deadzone...')
                self.upwardsRiskprofile()
                self.deadzone()
            elif self.values_dict['Adjusted'] == 'Calendar' and self.market_price >= self.calendarStrike+5 and 21 <= self.currentDatetime.hour < 22:
                print('Rolling calendar spread...')
                self.telegram_bot_sendtext("Rolling calendar spread...")
                self.closeCalendar(self.calendarStrike, round((self.long_quantity-0.1)/2))
                self.calendar(self.market_price+20, round((self.long_quantity-0.1)/2))

                self.adjusted = 'Calendar'
                self.calendarlog()

                print('Setting up riskprofiles and checking for deadzone...')
                self.telegram_bot_sendtext('Setting up riskprofiles and checking for deadzone...')
                self.upwardsRiskprofile()
                self.deadzone()
            elif self.values_dict['Adjusted'] == 'No' and self.market_price < (self.lowerStrike +((self.shortStrike-self.lowerStrike)*0.5)) and 16 <= self.currentDatetime.hour < 22:
                print('Doing downwards adjustment. Setting up riskprofiles and checking all possible adjustments...')
                self.telegram_bot_sendtext('Doing downwards adjustment. Setting up riskprofiles and checking all possible adjustments...')
                self.downwardsRiskprofile()
                self.downwards()


            elif self.values_dict['Adjusted'] == 'Calendar' and self.market_price < (self.lowerStrike +((self.shortStrike-self.lowerStrike)*0.5)) and 16 <= self.currentDatetime.hour < 22:
                #CLOSING EXISTING UPPER ADJUSTMENTS
                print('Closing existing calendar and moved legs and doing downwards adjustment...')
                self.telegram_bot_sendtext('Closing existing calendar and moved legs and doing downwards adjustment...')
                self.closeCalendar(self.calendarStrike, round((self.long_quantity-0.1)/2))
                if 'movedContract' in values_dict:
                    self.closeCalendar(self.backMovedContract.strike, self.movedContractQty)

                #SETTING UP RISKPROFILES AND DECIDING ON HOW TO ADJUST
                print('Setting up riskprofiles and checking all possible adjustments...')
                self.telegram_bot_sendtext('Setting up riskprofiles and checking all possible adjustments...')
                self.downwardsRiskprofile()
                self.downwards()    


            elif self.values_dict['Adjusted'] == 'Downwards' or self.values_dict['Adjusted'] == 'Exit':
                print('KEEP AN EYE ON PNL, EXIT TRADE MAXIMALLY ONE DAY AFTER ADJUSTMENT')
                self.tradeExit()
            else:
                self.exit_program()

        elif self.currentDatetime.weekday() == 4 and datetime.now().time() >= time.fromisoformat('16:30:00'):
            print("Opening new trade...")
            self.telegram_bot_sendtext("Opening new trade...")
            self.deletelog()
            self.opening()
        else:
            print("Waiting to open a new trade on Friday...")
            self.telegram_bot_sendtext("Waiting to open a new trade on Friday...")
            self.exit_program()


    def fetch_marketdata(self):
        #fetch market price of underlying contract
        self.underlying = Index('SPX', 'CBOE', 'USD')
        self.ib.qualifyContracts(self.underlying)
        self.ib.reqMarketDataType(2)
        data = self.ib.reqMktData(self.underlying, '', False, False)
        while data.last != data.last:
            self.ib.sleep(0.01) #Wait until data is in.

        self.market_price = 5 * round(data.last/5)
        print(self.market_price)

        #fetch VIX price
        self.VIXIndex = Index('VIX', 'CBOE', 'USD')
        self.ib.qualifyContracts(self.VIXIndex)
        VIX_data = self.ib.reqMktData(self.VIXIndex, '', False, False)
        while VIX_data.last != VIX_data.last:
            self.ib.sleep(0.01) #Wait until data is in.

        self.VIX = round(VIX_data.last)
        self.IV = VIX_data.last/100
        print(self.IV)
        #fetch treasury yield
        self.TNXIndex = Index('TNX', 'CBOE', 'USD')
        self.ib.qualifyContracts(self.TNXIndex)
        TNX_data = self.ib.reqMktData(self.TNXIndex, '', False, False)
        while TNX_data.close != TNX_data.close:
            self.ib.sleep(0.01) #Wait until data is in.
        self.TNX = TNX_data.close/1000
        print(self.TNX)


    def loadTrade(self):
        #DATE & TIME
        self.today, self.currentDatetime = date.today(), datetime.now() 
        datetoday = self.today.strftime("%Y%m%d")
        self.daystoExpiry = 14
        DTE14 = self.today + timedelta(days=self.daystoExpiry)
        self.expiry = DTE14.strftime("%Y%m%d")

        self.live_trading = True
        script_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_directory, 'a14weekly.pkl')

        if os.path.exists(file_path):
            self.inTrade = True
            #FETCH TRADE DETAILS
            with open(file_path, 'rb') as file:
                self.values_dict = pickle.load(file)
            self.adjusted = self.values_dict['Adjusted']
        
            #BWB DETAILS
            BWBdetails = self.values_dict['BWB Details']
            self.upperContract, self.shortContract, self.lowerContract = self.values_dict['upperContract'], self.values_dict['shortContract'], self.values_dict['lowerContract']
            self.upperStrike, self.shortStrike, self.lowerStrike = self.upperContract.strike, self.shortContract.strike, self.lowerContract.strike
            
            upperBWBdetails, shortBWBdetails, lowerBWBdetails = BWBdetails.loc[BWBdetails['strike'].astype(str).str.contains(f'{self.upperStrike}')], BWBdetails.loc[BWBdetails['strike'].astype(str).str.contains(f'{self.shortStrike}')], BWBdetails.loc[BWBdetails['strike'].astype(str).str.contains(f'{self.lowerStrike}')]
            upperPremiums, shortPremiums, lowerPremiums = upperBWBdetails['avgPrice'], shortBWBdetails['avgPrice'], lowerBWBdetails['avgPrice'] 
            self.upperPremium, self.shortPremium, self.lowerPremium = sum(upperPremiums)/len(upperPremiums), sum(shortPremiums)/len(shortPremiums), sum(lowerPremiums)/len(lowerPremiums)
            
            self.BWBexpiry = BWBdetails['lastTradeDateOrContractMonth'].iloc[0]
            self.margin = float(self.values_dict['Margin'])
            self.commission = sum(BWBdetails['commission'])
            self.commissionAfterClose = self.commission*2
            self.allFrontContracts, self.allBackContracts = [self.upperContract, self.shortContract, self.lowerContract], []
            self.long_quantity, self.short_quantity = self.values_dict['longQty'], self.values_dict['shortQty']
            self.daysInTrade = self.daystoExpiry-(datetime.strptime(self.upperContract.lastTradeDateOrContractMonth, '%Y%m%d')-datetime.strptime(self.today.strftime("%Y%m%d"), '%Y%m%d')).days
            daysLeftToExpiry = (self.daystoExpiry - self.daysInTrade)
            self.standardDeviation = (self.market_price * self.IV * (np.sqrt(daysLeftToExpiry/365)))/2
            self.standardDeviation = 5*round(self.standardDeviation/5)  

            #KEEP CALENDAR AND DOWNWARDS SEPARATE. MOVEDCONTRACT DOESN'T GET REMOVED FROM PKL FILE AFTER UPWARDS CALENDAR IS REMOVED
            if self.adjusted == 'Calendar':
                #CALENDAR DETAILS
                calendarDetails = self.values_dict['Calendar Details']
                self.frontCalendarContract, self.backCalendarContract = self.values_dict['frontCalendarContract'], self.values_dict['backCalendarContract']
                self.calendarStrike = int(self.frontCalendarContract.strike)
                self.frontCalendarExpiry, self.backCalendarExpiry = sorted(calendarDetails['lastTradeDateOrContractMonth'], reverse=True)[1], sorted(calendarDetails['lastTradeDateOrContractMonth'], reverse=True)[0]
                
                frontCalendarDetails, backCalendarDetails = calendarDetails.loc[calendarDetails['lastTradeDateOrContractMonth'].astype(str).str.contains(f'{self.frontCalendarExpiry}')], calendarDetails.loc[calendarDetails['lastTradeDateOrContractMonth'].astype(str).str.contains(f'{self.backCalendarExpiry}')]
                frontCalendarPremiums, backCalendarPremiums = frontCalendarDetails['avgPrice'], backCalendarDetails['avgPrice']
                self.frontCalendarPremium, self.backCalendarPremium = sum(frontCalendarPremiums)/len(frontCalendarPremiums), sum(backCalendarPremiums)/len(backCalendarPremiums)

                self.calendarQty = self.values_dict['calendarQty']
                self.commission = sum(BWBdetails['commission']) + sum(calendarDetails['commission'])
                self.commissionAfterClose = self.commission*2
                self.allFrontContracts, self.allBackContracts = [self.upperContract, self.shortContract, self.lowerContract, self.frontCalendarContract], [self.backCalendarContract]

                if 'movedContract' in self.values_dict:
                    self.movedContractDetails = self.values_dict['movedContract Details']
                    self.frontMovedContract, self.backMovedContract = self.values_dict['frontMovedContract'], self.values_dict['backMovedContract']
                    self.movedContractQty = self.values_dict['movedContractQuantity']
                    self.allFrontContracts, self.allBackContracts = [self.upperContract, self.shortContract, self.lowerContract, self.frontCalendarContract, self.frontMovedContract], [self.backCalendarContract, self.backMovedContract]
            
            if self.adjusted == 'Downwards':
                #CALENDAR DETAILS
                calendarDetails = self.values_dict['Calendar Details']
                self.frontCalendarContract, self.backCalendarContract = self.values_dict['frontCalendarContract'], self.values_dict['backCalendarContract']
                self.calendarStrike = self.frontCalendarContract.strike
                self.frontCalendarExpiry, self.backCalendarExpiry = sorted(calendarDetails['lastTradeDateOrContractMonth'], reverse=True)[1], sorted(calendarDetails['lastTradeDateOrContractMonth'], reverse=True)[0]
                
                frontCalendarDetails, backCalendarDetails = calendarDetails.loc[calendarDetails['lastTradeDateOrContractMonth'].astype(str).str.contains(f'{self.frontCalendarExpiry}')], calendarDetails.loc[calendarDetails['lastTradeDateOrContractMonth'].astype(str).str.contains(f'{self.backCalendarExpiry}')]
                frontCalendarPremiums, backCalendarPremiums = frontCalendarDetails['avgPrice'], backCalendarDetails['avgPrice']
                self.frontCalendarPremium, self.backCalendarPremium = sum(frontCalendarPremiums)/len(frontCalendarPremiums), sum(backCalendarPremiums)/len(backCalendarPremiums)

                self.calendarQty = self.values_dict['calendarQty']
                self.commission = sum(BWBdetails['commission']) + sum(calendarDetails['commission'])
                self.commissionAfterClose = self.commission*2
                self.allFrontContracts, self.allBackContracts = [self.upperContract, self.shortContract, self.lowerContract, self.frontCalendarContract], [self.backCalendarContract]

        else:
            self.inTrade = False
    

    def downwards(self):
        print('checking best way to adjust downwards')
        slopes = [self.zerodteSlope, self.oneThirdMovedLegsSlope, self.twoThirdMovedLegsSlope, self.allMovedLegsSlope, self.twoMovedoneNewCalendarSlope, self.oneMovedtwoNewCalendarSlope, self.allNewCalendarSlope]
        minSlope = min(slopes)
        minSlopeIndex = slopes.index(minSlope)
        #SLOPE PER CONTRACTS OR SLOPE AND PERCENTAGE OF MARGIN.

        #LOOK AT ALL T+0 LINES AND FIND THE ONE WITH THE FLATTEST SLOPE. HOWEVER, ALSO TRY TO MOVE THE LEAST AMOUNT OF CONTRACTS.
        minDifference = 2
        differenceWithPreviousElement = slopes[minSlopeIndex] - slopes[minSlopeIndex-1]
        if differenceWithPreviousElement < minDifference:
            minSlopeIndex = minSlopeIndex-1
            differenceWithPreviousElement = slopes[minSlopeIndex] - slopes[minSlopeIndex-1]
            if differenceWithPreviousElement < minDifference:
                print('Found flattest slope but difference not significant compared to moving less legs. Taking less legs...')
        else:
            print('Found flattest slope, difference significant compared to moving less legs.')


        print('adjusted downwards with calendar spread')
        self.telegram_bot_sendtext('adjusted downwards with calendar spread')
        if minSlopeIndex == 0:
            print('Moving legs doesnt have any effect, EXIT THE TRADE MANUALLY.')
        if minSlopeIndex == 1:
            print('moving one third of lower contracts legs...')            
            self.calendar(self.lowerStrike, round(((self.long_quantity)/3)))
        if minSlopeIndex == 2:
            print('moving two third of lower contracts legs...')            
            self.calendar(self.lowerStrike, round(((self.long_quantity)/3)*2))
        if minSlopeIndex == 3:
            print('moving two third of lower contracts legs...')            
            self.calendar(self.lowerStrike, self.long_quantity)
        # if minSlopeIndex == 4:
        #     print('moving two third of lower contracts legs and setting up new calendar 20 points below market price with the remaining contracts...')            
        #     self.calendar(self.lowerStrike, round(((self.long_quantity)/3)*2))  
        #     self.calendar(self.lowerStrike-20, round(((self.long_quantity)/3)))
        # if minSlopeIndex == 5:
        #     print('moving one third of lower contracts legs and setting up new calendar 20 points below market price with the remaining contracts...')            
        #     self.calendar(self.lowerStrike, round(((self.long_quantity)/3)))  
        #     self.calendar(self.lowerStrike-20, round(((self.long_quantity)/3)*2))
        # if minSlopeIndex == 6:
        #     print('setting up new calendar 20 points below market price with all lower leg contracts...')            
        #     self.calendar(self.lowerStrike-20, self.long_quantity)

        self.downwardslog()
        self.exit_program()


    def deadzone(self):
        #CHECK FOR DEADZONE
        daysToDeadzoneTLine = (self.daystoExpiry - self.daysInTrade)-1 

        #LOOK AT LAST DAY. IF IT IS BELOW ZERO, TRY TO ADJUST IT. IF IT WORKS AND GETS THE LINE FLATTER, GREAT. IF IT DOESN'T, KEEP WATCHING THE SPACE FOR PROFIT.
        #ALSO LOOK AT CURRENT DELTA. IF THE SLOPE IS TOO BIG AFTER ADJUSTMENT, DON'T DO IT. GOALS: MAKE SURE LINE IS FLAT ENOUGH(DOESNT DIVE INTO LOSSES WHEN MARKET GOES UP) AND THERE IS ENOUGH ROOM FOR PROFIT LEFT.
        upperStrikeIndex = self.strikes.index(self.upperStrike)
        calendarStrikeIndex = self.strikes.index(self.calendarStrike)
        marketpriceIndex = self.strikes.index(self.market_price)
        deadzoneTline = self.currentTline[daysToDeadzoneTLine]
        deadzoneTline = deadzoneTline[upperStrikeIndex:calendarStrikeIndex+1]

        #IF T+0 SLOPE < -30? AND SELF.MARKET_PRICE+30 < 0, DON'T DO ADJUSTMENT.
        maxSlope = 20
        maxpercentageBelowBreakeven = 0.1
        percentageBelowBreakeven = (len([x for x in deadzoneTline if x < 0])/len(deadzoneTline))
        if percentageBelowBreakeven > maxpercentageBelowBreakeven:
            #TRY MOVING ONE THIRD OF ALL LEGS
            oneThirdMovedLegs = self.oneThirdMovedLegsTline[daysToDeadzoneTLine]
            oneThirdMovedLegs = oneThirdMovedLegs[upperStrikeIndex:calendarStrikeIndex+1]
            oneThirdMovedLegsPercentageBelowBreakeven = (len([x for x in oneThirdMovedLegs if x < 0])/len(oneThirdMovedLegs))
            if oneThirdMovedLegsPercentageBelowBreakeven > 0.1 or abs(self.oneThirdMovedLegsSlope) > maxSlope:
                #TRY MOVING TWO THIRDS OF ALL LEGS
                twoThirdMovedLegs = self.twoThirdMovedLegsTline[daysToDeadzoneTLine]
                twoThirdMovedLegs = twoThirdMovedLegs[upperStrikeIndex:calendarStrikeIndex+1]
                twoThirdMovedLegsPercentageBelowBreakeven = (len([x for x in twoThirdMovedLegs if x < 0])/len(twoThirdMovedLegs))
                if twoThirdMovedLegsPercentageBelowBreakeven > maxpercentageBelowBreakeven or abs(self.twoThirdMovedLegsSlope) > maxSlope:
                    #TRY MOVING ALL LEGS
                    allMovedLegs = self.allMovedLegsTline[daysToDeadzoneTLine]
                    allMovedLegs = allMovedLegs[upperStrikeIndex:calendarStrikeIndex+1]
                    allMovedLegsPercentageBelowBreakeven = (len([x for x in allMovedLegs if x < 0])/len(allMovedLegs))
                    if allMovedLegsPercentageBelowBreakeven > maxpercentageBelowBreakeven or abs(self.allMovedLegsSlope) > maxSlope:
                        print('Deadzone present but moving legs does not fix it or T+0 line gets too steep. Checking the room left for profit every hour and exiting trade when there is not much room left.')
                        self.telegram_bot_sendtext('Deadzone present but moving legs does not fix it or T+0 line gets too steep. Checking the room left for profit every hour and exiting trade when there is not much room left.')
                        self.exit_program()
                    else:
                        print(f"moving all({self.long_quantity}) upper legs")
                        self.telegram_bot_sendtext(f"moving all({self.long_quantity}) upper legs")
                        self.movedContractQty = self.long_quantity
                        self.calendar(self.upperStrike, self.movedContractQty)
                        self.movedleglog()
                        self.exit_program()
                else:
                    print(f"moving {round(((self.long_quantity)/3)*2)} BWB legs")
                    self.telegram_bot_sendtext(f"moving {round(((self.long_quantity)/3)*2)} BWB legs")
                    self.movedContractQty = round(((self.long_quantity)/3)*2)
                    self.calendar(self.upperStrike, self.movedContractQty)
                    self.movedleglog()
                    self.exit_program()
            else:
                print(f"moving {round((self.long_quantity)/3)} BWB legs")
                self.telegram_bot_sendtext(f"moving {round((self.long_quantity)/3)} BWB legs")
                self.movedContractQty = round((self.long_quantity)/3)
                self.calendar(self.upperStrike, self.movedContractQty)
                self.movedleglog()
                self.exit_program()
        else:
            print('No deadzone present.')   
            self.telegram_bot_sendtext('No deadzone present.')
            self.exit_program()



    def profitSpace(self):
        #THIS FUNCTION CHECKS IF THERE IS ENOUGH ROOM LEFT FOR PROFIT. FOR EXAMPLE WHEN IT'S ABOVE THE DEADZONE, YOU DON'T WANNA WAIT TILL EXPIRATION. SO, YOU MIGHT HAVE TO TAKE PROFIT BELOW 5%.
        #CAN YOU APPLY THIS AT ANY TIME??? THE MARKET COULD STILL MOVE. SO, MAYBE JUST CHECK THIS WHEN ABOVE DEADZONE OR WHENEVER APPROPRIATE
        daysToOneDTE = (self.daystoExpiry - self.daysInTrade)-1
        
        strikeRange = 5       
        lowerIndex = self.strikes.index(self.market_price-strikeRange)
        upperIndex = self.strikes.index(self.market_price+strikeRange)
        marketpriceIndex = self.strikes.index(self.market_price)
        oneDTEline = self.currentTline[daysToOneDTE]
        oneDTEline = oneDTEline[lowerIndex:upperIndex+1]
        
        #CHECK IF ABOVE DEADZONE. IF SO, CHECK HOW MUCH ROOM THERE IS LEFT IN A WIDER VICINITY
        #IF SOMEWHERE ELSE, KEEP THE STRIKERANGE SMALLER. ONLY CHECK AFTER AN ADJUSTMENT IS DONE. PERHAPS INCLUDE THIS IN THE RISKPROFILE BEFORE DOING ADJUSTMENT.
        for i in oneDTEline:
            oneDTEpercentage = (i/self.margin)*100
            if oneDTEpercentage < 5:
                print('PnL at expiration not above 5%!')
                self.telegram_bot_sendtext('PnL at expiration not above 5%!')
                break
            else:
                print('')



#================================================================================================================================================================#
###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER###OTHER##
#================================================================================================================================================================#


    def telegram_bot_sendtext(self, bot_message):

        bot_token = self.telegram_token
        bot_chatID = self.telegram_chatID
        send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

        response = requests.get(send_text)

        return response.json()


    def exit_program(self):
        self.ib.disconnect()
        sys.exit(0)


bot()
