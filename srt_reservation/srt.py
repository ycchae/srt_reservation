import os

from collections import defaultdict
from datetime import datetime

from srt_reservation.validation import station_list, num_station_list

class SRT:
    def __init__(self, dpt, arr, dpt_dt, dpt_tm, num):
        """
        :param dpt_stn: SRT 출발역
        :param arr_stn: SRT 도착역
        :param dpt_dt: 출발 날짜 YYYYMMDD 형태 ex) 20220115
        :param dpt_tm: 출발 시간 hh 형태, 반드시 짝수 ex) 06, 08, 14, ...
        :param num_trains_to_check: 검색 결과 중 예약 가능 여부 확인할 기차의 수 ex) 2일 경우 상위 2개 확인
        :param want_reserve: 예약 대기가 가능할 경우 선택 여부
        """

        self.want_reserve = False
        self.greedy = False

        self.dpt_stn = dpt if not str.isdigit(dpt) else num_station_list[int(dpt)]
        if self.dpt_stn not in station_list:
            raise Exception(f"출발역 오류. '{self.dpt_stn}' 은/는 목록에 없습니다.")
        
        self.arr_stn = arr if not str.isdigit(arr) else num_station_list[int(arr)]
        if self.arr_stn not in station_list:
            raise Exception(f"도착역 오류. '{self.arr_stn}' 은/는 목록에 없습니다.")
        
        self.dpt_dt = dpt_dt
        try:
            datetime.strptime(str(self.dpt_dt), '%Y%m%d')
        except Exception as e:
            print(e)
            raise Exception("날짜가 잘못 되었습니다. YYYYMMDD 형식으로 입력해주세요.")
        if not str(self.dpt_dt).isnumeric():
            raise Exception("날짜는 숫자로만 이루어져야 합니다.")

        self.set_dpt_tm(dpt_tm)
        self.num_trains_to_check = num

        self.is_num_auto_set = False
        self.is_dpt_tm_auto_set = False
               
        self.gotcha = 0

    def set_dpt_tm(self, dpt_tm):
        dpt_tm = str(dpt_tm) if int(dpt_tm) % 2 == 0 else str(int(dpt_tm) - 1)
        self.dpt_tm = dpt_tm.zfill(2)

    
    def init_results(self):
        self.booked = defaultdict(lambda: False)
        self.reserved = defaultdict(lambda: False)

    def set_exact_tms(self, exact_tms):
        self.exact_tms = exact_tms
        if len(self.exact_tms) > 0:
            self.exact_tms = self.exact_tms.split(",")
            self.exact_tms.sort(key = lambda x: tuple(map(int, x.split(":"))))
            self.min_exact_tm = tuple(map(int, self.exact_tms[0].split(":")))
            self.max_exact_tm = tuple(map(int, self.exact_tms[-1].split(":")))
            if self.num_trains_to_check < 10:
                self.num_trains_to_check = 10
                self.is_num_auto_set = True
            if abs(int(self.dpt_tm) - self.min_exact_tm[0]) > 2:
                self.set_dpt_tm(self.min_exact_tm[0])
                self.is_dpt_tm_auto_set = True
        return self

    def set_want_reserve(self, reserve):
        self.want_reserve = reserve
        return self
    
    def set_greedy(self, greedy):
        self.greedy = greedy
        return self
    
    def set_adult(self, adult):
        if adult < 0: adult = 0
        self.adult = adult
        return self

    def set_kid(self, kid):
        if kid < 0: kid = 0
        self.kid = kid
        return self

    def set_elder(self, elder):
        if elder < 0: elder = 0
        self.elder = elder
        return self

    def set_user_info(self, login_id, login_pwd):
        self.login_id = login_id
        self.login_pwd = login_pwd
        return self
