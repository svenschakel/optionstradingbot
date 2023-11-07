from ib_insync import *
from datetime import date
import numpy as np
import pandas as pd
import os
import sys
import configparser
import requests
import pickle
import configparser

#ACCESS VALUES FROM CONFIG.INI FILE
config = configparser.ConfigParser()
script_directory = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_directory, '..', '..', 'config.ini')
config.read(config_file_path)
socket_port = config.getint('General', 'socket_port')
client_id = config.getint('General', 'client_id')
currentSSMargin = config.get('Short Strangle', 'margin')
SScompounding = config.getboolean('Short Strangle', 'compounding')
currentICMargin = config.get('Iron Condor', 'margin')
ICcompounding = config.getboolean('Iron Condor', 'compounding')
telegram_token = config.get('Iron Condor', 'telegram_token')
telegram_chatID = config.get('Iron Condor', 'telegram_chatID')

#DATE
today = date.today()
datetoday = int(today.strftime("%Y%m%d"))
dateDMY = str(today.strftime("%d/%m/%Y"))

#PATHS
script_directory = os.path.dirname(os.path.abspath(__file__))
shortstranglepklpath = os.path.join(script_directory, '..', '..', 'tradelogs', 'shortstrangle.pkl')
ironcondorpklpath = os.path.join(script_directory, '..', '..', 'tradelogs', 'ironcondor.pkl')
shortstranglecsvpath = os.path.join(script_directory, '..', '..', 'tradelogs', 'shortstrangle.csv')
ironcondorcsvpath = os.path.join(script_directory, '..', '..', 'tradelogs', 'ironcondor.csv')


class bot():
    def __init__(self, *args, **kwargs):
        print('tradelog script running. connecting to IB...')
        self.telegram_bot_sendtext('tradelog script running. connecting to IB...')
        try:
            self.ib = IB()
            self.ib.connect("127.0.0.1", socket_port, clientId=client_id)

            self.find_strategies()
            self.ib.run()
        except Exception as e:
            print(str(e))
            self.telegram_bot_sendtext(str(e))


    def find_strategies(self):
        self.shortstrangleflag = False
        self.ironcondorflag = False

        #load pickle files of all strategies
        if os.path.exists(shortstranglepklpath) and os.path.exists(ironcondorpklpath):
            with open(shortstranglepklpath, 'rb') as fileSS:
                values_dictSS = pickle.load(fileSS)
            with open(ironcondorpklpath, 'rb') as fileIC:
                values_dictIC = pickle.load(fileIC)
            if values_dictSS['Date'] == dateDMY and values_dictSS['Strategy'] == 'Short Strangle' and \
                    values_dictIC['Date'] == dateDMY and values_dictIC['Strategy'] == 'Iron Condor':
                        print("Updating both short strangle and iron condor tradelogs")
                        self.telegram_bot_sendtext("Updating both short strangle and iron condor tradelogs")
                        self.shortstrangle()
                        self.ironcondor()
                        while not self.shortstrangleflag and not self.ironcondorflag:
                            self.ib.sleep(0.1)
                        print("exiting program")
                        self.exit_program()
            else:
                print("No orders submitted today.")
                self.telegram_bot_sendtext("No orders submitted today.")
                self.exit_program
        if os.path.exists(shortstranglepklpath):
            with open(shortstranglepklpath, 'rb') as fileSS:
                values_dictSS = pickle.load(fileSS)
                if values_dictSS['Date'] == dateDMY and values_dictSS['Strategy'] == 'Short Strangle':
                    print("Updating short strangle tradelog...")
                    self.telegram_bot_sendtext("Updating short strangle tradelog...")
                    self.shortstrangle()
                    while not self.shortstrangleflag:
                        self.ib.sleep(0.1)
                    print("exiting program")
                    self.exit_program()
                else:
                    print("No orders submitted today.")
                    self.telegram_bot_sendtext("No orders submitted today.")
                    self.exit_program()
        if os.path.exists(ironcondorpklpath):
            with open(ironcondorpklpath, 'rb') as fileIC:
                values_dictIC = pickle.load(fileIC)
                if values_dictIC['Date'] == dateDMY and values_dictIC['Strategy'] == 'Iron Condor':
                    print("updating iron condor tradelog...")
                    self.telegram_bot_sendtext("updating iron condor tradelog...")
                    self.ironcondor()
                    while not self.ironcondorflag:
                        self.ib.sleep(0.1)
                    print("exiting program")
                    self.exit_program()
                else:
                    print("no orders submitted today.")
                    self.telegram_bot_sendtext("no orders submitted today.")
                    self.exit_program()
        else:
            print("no orders submitted today.")
            self.telegram_bot_sendtext("no orders submitted today.")
            self.exit_program()
        

    def shortstrangle(self):
        # Load the dictionary from the pickle file
        with open(shortstranglepklpath, 'rb') as fileSS:
            values_dictSS = pickle.load(fileSS)
        
        self.combo_orderId = values_dictSS['value1']
        self.callStop_orderId = values_dictSS['value2']
        self.putStop_orderId = values_dictSS['value3']
        dateDMY = values_dictSS['value4']
        self.market_price = values_dictSS['value5']
        self.VIX = values_dictSS['value6']
        self.stopPrice = values_dictSS['value7']   

        #request all filled orders and convert it into a nice dataframe
        fills = self.ib.fills()
        self.ib.sleep(5)

        fills_2_df = util.df([fi.contract for fi in fills])
        fills_3_df = util.df([fi.execution for fi in fills])
        fills_4_df = util.df([fi.commissionReport for fi in fills])
        fills_df = pd.concat([fills_2_df, fills_3_df, fills_4_df], sort=False, axis=1)

        fills_filtered_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.combo_orderId}')]
        fills_filtered_df = fills_filtered_df.loc[fills_filtered_df['secType'].astype(str).str.contains('OPT')]
        row_count = len(fills_filtered_df)
       
        #check for stop order fills
        if not fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.callStop_orderId}')].empty:
            callStop_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.callStop_orderId}')]
            callStop = callStop_df['avgPrice'].values[0]
            callStopCommission = callStop_df['commission'].values[0]
        else:
            callStop = 0
            callStopCommission = 0

        if not fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.putStop_orderId}')].empty:
            putStop_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.putStop_orderId}')]
            putStop = putStop_df['avgPrice'].values[0]
            putStopCommission = putStop_df['commission'].values[0]
        else:
            putStop = 0
            putStopCommission = 0

        #stuff to assign the right values to the right order legs
        shares = fills_filtered_df['cumQty'].tolist()
        shares = float(shares[0])
        actions = fills_filtered_df['side'].tolist()
        rights = fills_filtered_df['right'].tolist()
        action_to_sign = [float(-1) if action == 'BOT' else float(1) for action in actions]
        action_to_stopprice = [f'{round(self.stopPrice, 3)}' if action == 'SLD' else '' for action in actions]
        action_to_putstop = [f'{putStop}' if action == 'SLD' and right == 'P' else 0 for action, right in zip(actions, rights)]
        action_to_callstop = [f'{callStop}' if action == 'SLD' and right == 'C' else 0 for action, right in zip(actions, rights)]
        stopFills = [putstop + callstop for putstop, callstop in zip(action_to_putstop, action_to_callstop)]
        action_to_putStopComission = [putStopCommission if action == 'SLD' and right == 'P' else 0 for action, right in zip(actions, rights)]
        action_to_callStopComission = [callStopCommission if action == 'SLD' and right == 'C' else 0 for action, right in zip(actions, rights)]
        stopFillsCommissions = [(putStopCommission + callStopCommission) for putStopCommission, callStopCommission in zip(action_to_putStopComission, action_to_callStopComission)]
        
        #ROUND EVERYTHING
        commission = fills_filtered_df['commission'].tolist()
        commission = [round(elem, 3) for elem in commission]
        credit = fills_filtered_df['avgPrice'].tolist()
        credit = [round(int(elem), 3) for elem in credit]

        #SUM, TOTAL P/L. THEN ADD TOTAL P/L TO MARGIN CONFIG.INI FILE
        closingDebit = [0] * row_count
        sum = [stopFills[i] + closingDebit[i] for i in range(len(stopFills))]
        totalPnL = (np.array(action_to_sign)*(np.array(credit)*100 - np.array(sum)*100))*shares - np.array(commission) - np.array(stopFillsCommissions)

        log_df = pd.DataFrame({
            'Date': [f'{dateDMY}'] + [''] * (row_count - 1),
            'Expiry': fills_filtered_df['lastTradeDateOrContractMonth'].tolist(),
            'Underlying': fills_filtered_df['symbol'].tolist(),
            'Market price': [f'{self.market_price}'] * row_count,
            'Right': fills_filtered_df['right'].tolist(),
            'Action': fills_filtered_df['side'].tolist(),
            'Quantity': fills_filtered_df['shares'].tolist(),
            'Action Signs': action_to_sign,
            'Strike': fills_filtered_df['strike'].tolist(),
            'VIX': [f'{self.VIX}%'] * row_count,
            'Credit': fills_filtered_df['avgPrice'].tolist(),
            'Commission': fills_filtered_df['commission'].tolist(),
            'Stop Commission': stopFillsCommissions,
            'Stoploss': action_to_stopprice,
            'Stoploss Fill': stopFills,
            'Closing Debit': '',
            'Sum': stopFills,
            'Total P/L': totalPnL,})


        #write to csv file
        log_df.to_csv(shortstranglecsvpath, mode='a', header=False, index=False)

        if SScompounding == True:
            #update margin in config.ini file
            dailyPnL = float(round(np.sum(totalPnL), 2))
            newMargin = float(currentSSMargin) + dailyPnL
            newMargin = round(newMargin)
            config.set('IRON CONDOR', 'margin', f'{newMargin}')
            with open(config_file_path, 'w') as configfile:
                config.write(configfile)      
                  
        self.shortstrangleflag = True
        self.telegram_bot_sendtext(f"Short strangle tradelog updated.\nDaily PnL: {round(np.sum(totalPnL))}")


    def ironcondor(self):
        # Load the dictionary from the pickle file
        with open(ironcondorpklpath, 'rb') as fileIC:
            values_dictIC = pickle.load(fileIC)
        
        self.combo_orderId = values_dictIC['value1']
        self.callStop_orderId = values_dictIC['value2']
        self.putStop_orderId = values_dictIC['value3']
        dateDMY = values_dictIC['value4']
        self.market_price = values_dictIC['value5']
        self.VIX = values_dictIC['value6']
        self.stopPrice = values_dictIC['value7']   
    
        #request all filled orders and convert it into a nice dataframe
        fills = self.ib.fills()
        self.ib.sleep(5)
        
        fills_2_df = util.df([fi.contract for fi in fills])
        fills_3_df = util.df([fi.execution for fi in fills])
        fills_4_df = util.df([fi.commissionReport for fi in fills])
        fills_df = pd.concat([fills_2_df, fills_3_df, fills_4_df], sort=False, axis=1)

        fills_filtered_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.combo_orderId}')]
        fills_filtered_df = fills_filtered_df.loc[fills_filtered_df['secType'].astype(str).str.contains('OPT')]
        row_count = len(fills_filtered_df)

        #check for stop order fills
        if not fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.callStop_orderId}')].empty:
            callStop_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.callStop_orderId}')]
            callStop = callStop_df['avgPrice'].values[0]
            callStopCommission = callStop_df['commission'].values[0]
        else:
            callStop = 0
            callStopCommission = 0

        if not fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.putStop_orderId}')].empty:
            putStop_df = fills_df.loc[fills_df['orderId'].astype(str).str.contains(f'{self.putStop_orderId}')]
            putStop = putStop_df['avgPrice'].values[0]
            putStopCommission = putStop_df['commission'].values[0]
        else:
            putStop = 0
            putStopCommission = 0
        
        #stuff to assign the right values to the right order legs
        actions = fills_filtered_df['side'].tolist()
        rights = fills_filtered_df['right'].tolist()
        action_to_sign = [float(-1) if action == 'BOT' else float(1) for action in actions]
        action_to_stopprice = [f'{round(self.stopPrice, 2)}' if action == 'SLD' else '' for action in actions]
        action_to_putstop = [float(putStop) if action == 'SLD' and right == 'P' else 0 for action, right in zip(actions, rights)]
        action_to_callstop = [float(callStop) if action == 'SLD' and right == 'C' else 0 for action, right in zip(actions, rights)]
        stopFills = [float(putstop+callstop) for putstop, callstop in zip(action_to_putstop, action_to_callstop)]
        action_to_putStopComission = [putStopCommission if action == 'SLD' and right == 'P' else 0 for action, right in zip(actions, rights)]
        action_to_callStopComission = [callStopCommission if action == 'SLD' and right == 'C' else 0 for action, right in zip(actions, rights)]
        stopFillsCommissions = [round(float(putStopCommission+callStopCommission), 1) for putStopCommission, callStopCommission in zip(action_to_putStopComission, action_to_callStopComission)]

        #ROUND EVERYTHING
        shares = fills_filtered_df['shares'].tolist()
        shares = [round(float(elem), 1) for elem in shares]
        commission = fills_filtered_df['commission'].tolist()
        commission = [round(float(elem), 1) for elem in commission]
        credit = fills_filtered_df['avgPrice'].tolist()
        credit = [round(float(elem), 2) for elem in credit]

        #SUM, TOTAL P/L. THEN ADD TOTAL P/L TO MARGIN CONFIG.INI FILE
        closingDebit = [float(0)] * row_count
        sum = [round(float(stopFills[i]+closingDebit[i]), 1) for i in range(len(stopFills))]
        totalPnL = ((np.array(action_to_sign)*(np.array(credit) - np.array(stopFills))*100))*np.array(shares) - np.array(commission) - np.array(stopFillsCommissions)
        totalPnL = [round(float(elem), 2) for elem in totalPnL]
        dailyPnL = float(round(np.sum(totalPnL), 2))

        log_df = pd.DataFrame({
            'Date': [f'{dateDMY}'] + [''] * (row_count - 1),
            'Expiry': fills_filtered_df['lastTradeDateOrContractMonth'].tolist(),
            'Underlying': fills_filtered_df['symbol'].tolist(),
            'Market price': [f'{self.market_price}'] * row_count,
            'Right': fills_filtered_df['right'].tolist(),
            'Action': fills_filtered_df['side'].tolist(),
            'Quantity': fills_filtered_df['shares'].tolist(),
            'Action Signs': action_to_sign,
            'Strike': fills_filtered_df['strike'].tolist(),
            'VIX': [f'{self.VIX}%'] * row_count,
            'Credit': credit,
            'Commission': commission,
            'Stop Commission': stopFillsCommissions,
            'Stoploss': action_to_stopprice,
            'Stoploss Fill': stopFills,
            'Closing Debit': closingDebit,
            'Sum': sum,
            'Total P/L': totalPnL,
            'Daily P/L': [f'{dailyPnL}'] + [''] * (row_count - 1),})

        #write to csv file
        log_df.to_csv(ironcondorcsvpath, mode='a', header=False, index=False)

        if ICcompounding == True:
            #update margin in config.ini file
            newMargin = float(currentICMargin) + dailyPnL
            newMargin = round(newMargin)
            config.set('Iron Condor', 'margin', f'{newMargin}')
            with open(config_file_path, 'w') as configfile:
                config.write(configfile)

        self.ironcondorflag = True
        self.telegram_bot_sendtext(f"iron condor tradelog updated.\ndaily PnL: {round(np.sum(totalPnL))}")


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
