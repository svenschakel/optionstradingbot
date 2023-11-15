import pandas as pd
import os

script_directory = os.path.dirname(os.path.realpath(__file__))
tviblog = os.path.join(script_directory, 'tvib.log')

class tradelog:
    def __init__(self, tviblog):
        self.tviblog = tviblog
        self.filter()
        self.totalprofit()


    def filter(self):
        self.tradedict = {}
        with open(self.tviblog, 'r') as log:
            for line in log:
                if 'execDetails: Fill' in line:
                    line = line.split()
                    for i in line:
                        if 'side' in i:
                            side = str(i[6:9])
                        if 'price' in i:
                            price = float(i.split('=')[1].rstrip(','))
                            self.tradedict[price] = side
                        if 'multiplier' in i:
                            self.multiplier = int(i[12:13])
      

    def totalprofit(self):
        total_sld = 0
        total_bot = 0
        for price, side in self.tradedict.items():
            if side == 'SLD':
                total_sld += price
            if side == 'BOT':
                total_bot += price
        totalprofit = (total_sld - total_bot) * self.multiplier
        print(totalprofit)


tradelog(tviblog)