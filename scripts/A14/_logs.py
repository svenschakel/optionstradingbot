import os
import pickle


def openinglog(self):
    values_dict = {
        'Adjusted': 'No',
        'BWB Details': self.BWBdetails,
        'upperContract': self.upperContract,
        'shortContract': self.shortContract,
        'lowerContract': self.lowerContract,
        'longQty': self.long_quantity,
        'shortQty': self.short_quantity,
        'Margin': self.margin,
    }

    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')
    with open(file_path, 'wb') as file:
        pickle.dump(values_dict, file)

    print("Tradelog updated. Exiting program...")
    self.telegram_bot_sendtext("Tradelog updated. Exiting program...")
    self.ib.sleep(5)
    self.exit_program()


def calendarlog(self):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')
    with open(file_path, 'rb') as file:
        values_dict = pickle.load(file)

    values_dict['Adjusted'] = 'Calendar'
    values_dict['Calendar Details'] = self.calendarDetails
    values_dict['frontCalendarContract'] = self.frontCalendarContract
    values_dict['backCalendarContract'] = self.backCalendarContract
    values_dict['calendarQty'] = self.calendarQty
    values_dict['Margin'] = self.margin

    with open(file_path, 'wb') as file:
        pickle.dump(values_dict, file)

    print("calendar log updated")
    self.telegram_bot_sendtext("calendar log updated")


def movedleglog(self):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')
    with open(file_path, 'rb') as file:
        values_dict = pickle.load(file)
    
    values_dict['movedContract Details'] = self.calendarDetails
    values_dict['frontMovedContract'] = self.frontCalendarContract
    values_dict['backMovedContract'] = self.backCalendarContract
    values_dict['movedContractQuantity'] = values_dict.get('movedContractQuantity', 0) + self.movedContractQty
    values_dict['Margin'] = self.margin

    with open(file_path, 'wb') as file:
        pickle.dump(values_dict, file)

    print("log updated")
    self.telegram_bot_sendtext("log updated")


def downwardslog(self):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')
    with open(file_path, 'rb') as file:
        values_dict = pickle.load(file)

    values_dict['Adjusted'] = 'Downwards'
    values_dict['Calendar Details'] = self.calendarDetails
    values_dict['frontCalendarContract'] = self.frontCalendarContract
    values_dict['backCalendarContract'] = self.backCalendarContract
    values_dict['calendarQty'] = self.calendarQty
    values_dict['Margin'] = self.margin

    with open(file_path, 'wb') as file:
        pickle.dump(values_dict, file)

    print("downwards log updated. Exiting program...")
    self.telegram_bot_sendtext("downwards log updated")
 


def marginlog(self):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')
    with open(file_path, 'rb') as file:
        values_dict = pickle.load(file)
    
    values_dict['Margin'] = self.margin

    with open(file_path, 'wb') as file:
        pickle.dump(values_dict, file)

    print("margin updated")
    self.telegram_bot_sendtext("margin updated")


def deletelog(self):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_directory, 'a14weekly.pkl')

    if os.path.exists(file_path):
        os.remove(file_path)
    
    print('.pkl file deleted')
    self.telegram_bot_sendtext(".pkl file deleted")