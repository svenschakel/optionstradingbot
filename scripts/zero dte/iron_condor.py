#imports
from ib_insync import *
from datetime import date, datetime, time, timedelta
import pandas as pd
import sys
import os
import requests
import pickle
import configparser


#ACCESS VALUES FROM CONFIG.INI FILE
config = configparser.ConfigParser()
script_directory = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_directory, '..', '..', 'config.ini')
config.read(config_file_path)
socket_port = config.getint('General', 'socket_port')
live_trading = True
availableMargin = float(config.getint('Iron Condor', 'margin'))
submit_time_str = config.get('Iron Condor', 'submit_time')
ironCondor_askPrice = config.getfloat('Iron Condor', 'ironCondor_askPrice')
bid_price = config.getint('Iron Condor', 'bid_price')
telegram_token = config.get('Iron Condor', 'telegram_token')
telegram_chatID = config.get('Iron Condor', 'telegram_chatID')

#BID PRICE RANGE
min_bid_price = bid_price*0.8
max_bid_price = bid_price*1.2

#DATE AND TIME
today = date.today()
datetoday = int(today.strftime("%Y%m%d"))
dateDMY = str(today.strftime("%d/%m/%Y"))
submit_time = time.fromisoformat(submit_time_str)
current_time = int(datetime.now().strftime("%H%M%S"))
target_time = int(submit_time.strftime("%H%M%S"))
print_target_time = str(submit_time.strftime("%H:%M:%S"))


target_datetime = datetime.strptime(str(target_time), "%H%M%S")
minSubmitTime = target_datetime - timedelta(minutes=30)
maxSubmitTime = target_datetime + timedelta(minutes=30)
minSubmitTime = int(minSubmitTime.strftime("%H%M%S"))
maxSubmitTime = int(maxSubmitTime.strftime("%H%M%S"))


class bot():
    def __init__(self, *args, **kwargs):
        print("iron condor script starting up, connecting to IB and fetching market data...")
        self.telegram_bot_sendtext(f"iron condor script starting up...")

        #connect to IB
        try:
            self.ib = IB()
            self.ib.connect("127.0.0.1", socket_port, clientId=1)
           
            self.fetch_marketdata()
            self.ib.run()
        except Exception as e:
            print(str(e))
            self.telegram_bot_sendtext(str(e))


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
        
        self.telegram_bot_sendtext(f"running live.\nMarket price: {self.market_price}; VIX: {self.VIX} \nDate: {dateDMY}")
        if minSubmitTime < current_time < maxSubmitTime:
            print('finding contracts...')
            self.find_contracts()
        else:
            print('Python script started not close enough to submit time. Please set up Windows task scheduler correctly or adjust the submit_time in config file. Exiting program...')
            self.telegram_bot_sendtext('Python script started not close enough to submit time. Please set up Windows task scheduler correctly or adjust the submit_time in config file. Exiting program...')
            self.exit_program()


    def find_contracts(self):
        try:
            strike_price_range = 150
            min_strike_price = self.market_price - strike_price_range
            max_strike_price = self.market_price + strike_price_range
            call_strikePrices = [strike for strike in range(self.market_price, max_strike_price, 5)]
            put_strikePrices = [strike for strike in range(min_strike_price, self.market_price, 5)]

            #FIND CALL CONTRACT
            call_contracts = [Option('SPX', datetoday, strike, 'C', 'SMART', '100', 'USD', tradingClass='SPXW') for strike in range(self.market_price, max_strike_price, 5)]
            call_contracts = self.ib.qualifyContracts(*call_contracts)
            call_data = [self.ib.reqMktData(c, '', False, False) for c in call_contracts]
            tickers = [self.ib.ticker(c) for c in call_contracts]
            while any(d.close != d.close for d in call_data):
                self.ib.sleep(0.01)         

            call_bidPrices = [(tickers[c].bid) for c in range(len(call_contracts))]
            call_askPrices = [(tickers[c].ask) for c in range(len(call_contracts))]
            self.call_bidPrice = min(call_bidPrices, key=lambda x:abs(x-bid_price))
            self.call_contract = call_contracts[call_bidPrices.index(self.call_bidPrice)]
            self.call_strikePrice = self.call_contract.strike
         
            #IRON CONDOR CALL CONTRACT
            self.CallIronCondor_contract = None
            if 0.1 in call_askPrices:
                highest_index = min(i for i, value in enumerate(call_askPrices) if value == 0.1)
                self.CallIronCondor_contract = call_contracts[highest_index]
                self.CallIronCondor_strike = self.CallIronCondor_contract.strike

            #FIND PUT CONTRACT
            put_contracts = [Option('SPX', datetoday, strike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW') for strike in range(min_strike_price, self.market_price, 5)]
            put_contracts = self.ib.qualifyContracts(*put_contracts)
            put_data = [self.ib.reqMktData(c, '', False, False) for c in put_contracts]
            tickers = [self.ib.ticker(c) for c in put_contracts]
            while any(d.close != d.close for d in put_data):
                self.ib.sleep(0.01) 

            put_bidPrices = [(tickers[c].bid) for c in range(len(put_contracts))]
            put_askPrices = [(tickers[c].ask) for c in range(len(put_contracts))]
            self.put_bidPrice = min(put_bidPrices, key=lambda x:abs(x-bid_price))
            self.put_contract = put_contracts[put_bidPrices.index(self.put_bidPrice)]
            self.put_strikePrice = self.put_contract.strike

            #IRON CONDOR PUT CONTRACT
            self.PutIronCondor_contract = None
            if 0.1 in put_askPrices:
                highest_index = max(i for i, value in enumerate(put_askPrices) if value == 0.1)
                self.PutIronCondor_contract = put_contracts[highest_index]
                self.PutIronCondor_strike = self.PutIronCondor_contract.strike

            #CHECK IF THE CONTRACT FULFILLS ALL REQUIREMENTS
            if min_bid_price < self.call_bidPrice < max_bid_price and min_bid_price < self.put_bidPrice < max_bid_price and self.CallIronCondor_contract != None and self.PutIronCondor_contract != None:
                print("call and put contract found for the desired bid price.")

                #CALCULATE MARGIN REQUIREMENTS AND DECIDE ON AMOUNT OF CONTRACTS
                limitPrice = -(self.call_bidPrice + self.put_bidPrice - 2*ironCondor_askPrice)
                Widths = [(self.put_strikePrice-self.PutIronCondor_strike), (self.CallIronCondor_strike-self.call_strikePrice)]
                maxWidth = max(Widths)
                self.reqMargin = (maxWidth-limitPrice)*100
                self.contract_quantity = availableMargin//self.reqMargin

                self.submit_order()
            else:
                print("currently no call and/or put contract available for the desired bid price. trying again...")
                self.ib.sleep(5)
                self.find_contracts()
        except Exception as e:
            print(str(e))
            self.telegram_bot_sendtext(str(e))


    def submit_order(self):
        now = datetime.now().time()
        current_time = int(now.strftime("%H%M%S"))

        if current_time >= target_time:
            #RETRIEVE CONTRACT IDS
            call_contract = Option('SPX', datetoday, self.call_strikePrice, 'C', 'SMART', '100', 'USD', tradingClass='SPXW')
            call_conId = self.ib.qualifyContracts(call_contract)[0].conId
            CallIronCondor_contract = Option('SPX', datetoday, self.CallIronCondor_strike, 'C', 'SMART', '100', 'USD', tradingClass='SPXW')
            CallIronCondor_conId = self.ib.qualifyContracts(CallIronCondor_contract)[0].conId
            put_contract = Option('SPX', datetoday, self.put_strikePrice, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
            put_conId = self.ib.qualifyContracts(put_contract)[0].conId
            PutIronCondor_contract = Option('SPX', datetoday, self.PutIronCondor_strike, 'P', 'SMART', '100', 'USD', tradingClass='SPXW')
            PutIronCondor_conId = self.ib.qualifyContracts(PutIronCondor_contract)[0].conId
            while call_conId and put_conId and CallIronCondor_conId and PutIronCondor_conId == None: 
                self.ib.sleep(0.01) 

            #SUBMIT COMBO ORDER
            combo_contract = Contract(symbol='SPX', secType='BAG', currency='USD', exchange='SMART', tradingClass='SPXW', comboLegs=[ComboLeg(conId=call_conId, ratio=1, action='SELL'), ComboLeg(conId=put_conId, ratio=1, action='SELL'), ComboLeg(conId=CallIronCondor_conId, ratio=1, action='BUY'), ComboLeg(conId=PutIronCondor_conId, ratio=1, action='BUY')])
            combo_order = LimitOrder('BUY', self.contract_quantity, -(self.call_bidPrice + self.put_bidPrice - 2*ironCondor_askPrice), transmit=live_trading)
            combo_trade = self.ib.placeOrder(combo_contract, combo_order)
            print("limit order submitted. waiting for fill...")
            self.telegram_bot_sendtext("limit order submitted. waiting for fill...")
            
            self.ib.sleep(20)
            if combo_trade.orderStatus.status == "Filled":
                print(f"limit order filled.")
                self.telegram_bot_sendtext(f"limit order filled.\ncontracts: {self.contract_quantity}; margin: {round(self.reqMargin * self.contract_quantity)}\nCALL strike: {self.call_strikePrice}; bid: {self.call_bidPrice}\nPUT strike: {self.put_strikePrice}; bid: {self.put_bidPrice}\n")
                
                self.stopPrice = (abs(combo_trade.orderStatus.avgFillPrice)+2*ironCondor_askPrice) * 2
                self.combo_orderId = combo_trade.orderStatus.orderId
                
                #SUBMIT STOP ORDERS
                call_stopOrder = StopOrder('BUY', self.contract_quantity, self.stopPrice, transmit=live_trading)
                put_stopOrder = StopOrder('BUY', self.contract_quantity, self.stopPrice, transmit=live_trading)
                call_stopTrade = self.ib.placeOrder(call_contract, call_stopOrder)
                put_stopTrade = self.ib.placeOrder(put_contract, put_stopOrder)
               
                while call_stopTrade.orderStatus.orderId and put_stopTrade.orderStatus.orderId == None: 
                    self.ib.sleep(0.01)          
                self.callStop_orderId = call_stopTrade.orderStatus.orderId
                self.putStop_orderId = put_stopTrade.orderStatus.orderId
                self.telegram_bot_sendtext("trade successful.")
                self.tradelog()
            else:
                print("limit order not filled. trying again...")
                self.telegram_bot_sendtext("limit order not filled. trying again...")
                self.ib.cancelOrder(combo_order)
                self.find_contracts()
        else:
            print(f"waiting to submit order at {print_target_time}...")
            self.telegram_bot_sendtext(f"waiting to submit order at {print_target_time}...")            
            self.ib.sleep(60)
            self.find_contracts()


    def tradelog(self):  
        #CREATE DICTIONARY AND SAVE TO .PKL FILE
        values_dictIC = {
            'Date': dateDMY,
            'Strategy': 'Iron Condor',
            'value1': self.combo_orderId,
            'value2': self.callStop_orderId,
            'value3': self.putStop_orderId,
            'value4': dateDMY,
            'value5': self.market_price,
            'value6': self.VIX,   
            'value7': self.stopPrice      
        }

        script_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_directory, '..', '..', 'tradelogs', 'ironcondor.pkl')
        with open(file_path, 'wb') as fileIC:
            pickle.dump(values_dictIC, fileIC)

        print("trade successful. exiting program...")
        self.telegram_bot_sendtext("trade successful. exiting program...")
        self.ib.sleep(5)
        self.exit_program()


    def telegram_bot_sendtext(self, bot_message):

        bot_token = telegram_token
        bot_chatID = telegram_chatID
        send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

        response = requests.get(send_text)


        return response.json()


    def exit_program(self):
        self.ib.disconnect()
        sys.exit(0)


bot()
