import os
import sys
import configparser
import csv

#==================================================================================
#=====CREATE CONFIG.INI============================================================
#==================================================================================

config = configparser.ConfigParser(allow_no_value=True)

config['General'] = {
    'socket_port': '7497'
}

config['Short Strangle'] = {
    'margin': '25000',
    'compounding': 'True',
    'contract_quantity': '2',
    'bid_price': '1',
    'submit_time': '15:45:00',
    'telegram_token': '5900483573:AAH8O9ERGkkHBDuZCtQdaw3o3kkBKj4AkgU',
    'telegram_chatID': '5959794128'
}

config['Iron Condor'] = {
    'compounding': 'True',
    'margin': '25000',
    'ironCondor_Delta': '10',
    'bid_price': '1',
    'ironCondor_askPrice': '0.1',
    'submit_time': '15:45:00',
    'telegram_token': '6188374997:AAEPvvTLo34tXF1fCneMXg7r7J_Jz-HAhlM',
    'telegram_chatID': '5959794128'
}

config['A14'] = {
    'margin': '30000',
    'compounding': 'True',
    'max_spread': '1',
    'telegram_token': '6016792408:AAGg3qe9BR3ojSPK8vyDDIUQ6Gz4z2k8o5g',
    'telegram_chatID': '5959794128'
}


pathTo_main = str(os.path.dirname(os.path.realpath(__file__)))
pathTo_config = pathTo_main + '/config.ini'

if not os.path.exists(pathTo_config):
    with open(pathTo_config, 'w') as config_file:
        config.write(config_file)

#==================================================================================
#=====CREATE .BAT FILES============================================================
#==================================================================================

zerodtescripts = ['short_strangle', 'iron_condor', 'iron_condorDELTA', 'tradelog']

pathTo_executable = sys.executable
pathTo_batFiles = pathTo_main + '/bat files'
pathTo_scripts = pathTo_main + '/scripts'
pathTo_A14 = pathTo_scripts + '/A14'
pathTo_timezone = pathTo_scripts + '/timezone'
pathTo_zerodte = pathTo_scripts + '/zero dte'

if not os.path.exists(pathTo_batFiles):
    os.makedirs(pathTo_batFiles)


for i in zerodtescripts:
    myBat = open(f'{pathTo_batFiles}/start_{i}.bat','w+')
    myBat.write(f'''@echo off
"{pathTo_executable}" "{pathTo_zerodte}\{i}.py"''')
    myBat.close() 

#A14 BAT FILE
    myBat = open(f'{pathTo_batFiles}/start_A14.bat','w+')
    myBat.write(f'''@echo off
"{pathTo_executable}" "{pathTo_A14}/A14.py"''')
    myBat.close() 

#TIMEZONE BAT FILE
    myBat = open(f'{pathTo_batFiles}/start_timezone.bat','w+')
    myBat.write(f'''@echo off
"{pathTo_executable}" "{pathTo_timezone}/timezone.py"''')
    myBat.close() 


#==================================================================================
#=====CREATE TRADELOGS=============================================================
#==================================================================================

pathTo_tradelogs = pathTo_main + '/tradelogs'
pathTo_shortstranglecsv = pathTo_tradelogs + '/shortstrangle.csv'
pathTo_ironcondorcsv = pathTo_tradelogs + '/ironcondor.csv'

if not os.path.exists(pathTo_tradelogs):
    os.makedirs(pathTo_tradelogs)

if not os.path.exists(pathTo_shortstranglecsv):
    header = [
        'Date', 'Expiry', 'Underlying', 'Market Price', 'Right', 'Action', 'Quantity', 'Sign',
        'Strike', 'VIX', 'Credit', 'Commission', 'Stop Commission', 'Stoploss', 'Stoploss Fill',
        'Closing Debit', 'Sum', 'Total P/L', 'Net Premium', 'Gross Premium', 'Net Percentage'
    ]

    with open(pathTo_shortstranglecsv, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)

if not os.path.exists(pathTo_ironcondorcsv):
    header = [
        'Date', 'Expiry', 'Underlying', 'Market Price', 'Right', 'Action', 'Quantity', 'Sign',
        'Strike', 'VIX', 'Credit', 'Commission', 'Stop Commission', 'Stoploss', 'Stoploss Fill',
        'Closing Debit', 'Sum', 'Total P/L', 'Net Premium', 'Gross Premium', 'Net Percentage'
    ]

    with open(pathTo_ironcondorcsv, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
