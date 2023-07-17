import os
from datetime import datetime

class Card:
    def __init__(self, card_filename):
        self.want_checkout = False

        try:
            card_filepath = f"{os.path.dirname(os.path.abspath(__file__))}/{card_filename}"

            with open(card_filepath, "r") as f:
                self.card_numbers = f.readline().strip().split('-')
                self.valid_mon, self.valid_year = f.readline().strip().split('/')
                self.pw = f.readline().strip()
                self.my_number = f.readline().strip()
            self.validate()
            self.want_checkout = True
        except:
            pass
        
    def validate(self):
        if len(self.card_numbers) != 4:
            raise Exception(f"Invalid card numbers. Should be 4 sets but {len(self.card_numbers)}")
        
        if not 1 <= int(self.valid_mon) <= 12:
            raise Exception(f"Invalid card validate month {self.valid_mon}")
        
        cur_year = datetime.today().year
        cur_year -= (cur_year // 100) * 100
        if not cur_year <= int(self.valid_year) <= cur_year+12:
            raise Exception(f"Invalid card validate year {self.valid_year}")
        
        if len(self.pw) != 2:
            raise Exception(f"Password should be 2 digits {self.pw}")
        try:
            int(self.pw)
        except:
            raise Exception(f"Password should be number {self.pw}")

        if len(self.my_number) != 6:
            raise Exception(f"My number should be 6 digits {self.my_number}")
        try:
            int(self.my_number)
        except:
            raise Exception(f"My number should be number {self.my_number}")