from datetime import datetime

class Train:
    def __init__(self, dpt_dt, train_type, train_num, dpt, arr):
        self.dpt_dt = datetime.strptime(dpt_dt, '%Y%m%d')
        self.train_type = train_type
        self.train_num = train_num
        self.dpt_stn, self.dpt_time = dpt.split()
        self.arr_stn, self.arr_time = arr.split()

        self.hash_value = ''.join([self.train_type, self.train_num, self.dpt_stn, self.dpt_time, self.arr_stn, self.arr_time])

    def hash(self):
        return self.hash_value
    
    def to_string(self):
        return f"{self.dpt_dt.strftime('%Y-%m-%d(%a)')} {self.train_type}({self.train_num})\n{self.dpt_stn} {self.dpt_time} ▶ {self.arr_stn} {self.arr_time}"
    