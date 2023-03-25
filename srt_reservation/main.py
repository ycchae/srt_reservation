# -*- coding: utf-8 -*-
import os
import time
from random import randint

from datetime import datetime
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, WebDriverException

from srt_reservation.exceptions import InvalidStationNameError, InvalidDateError, InvalidDateFormatError, InvalidTimeFormatError
from srt_reservation.validation import station_list

import requests
from collections import defaultdict

CHROMEDRIVER_PATH = "/usr/bin/chromedriver"

SRT_BOT_TOKEN = ""
SRT_BOT_CHANNEL = "srt-reservation-bot"
try:
    token_path = f"{os.path.dirname(os.path.abspath(__file__))}/my_slack_token.txt"
    os.stat(token_path)
    with open(token_path, "r") as f:
        SRT_BOT_TOKEN = f.read().strip()
except:
    pass


def send_srt_bot_msg(token, channel, msg):
    if token == "" or channel == "": return
    if msg == "": msg = "Empty msg"

    requests.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {token}"}, data={"channel": channel, "text": msg})


def get_now_str():
    return datetime.now().strftime('%Y-%m-%d %a %H:%M:%S')
        
class Train:
    def __init__(self, train_type, train_num, dpt, arr):
        self.train_type = train_type
        self.train_num = train_num
        self.dpt_stn, self.dpt_time = dpt.split()
        self.arr_stn, self.arr_time = arr.split()

        self.hash_value = ''.join([self.train_type, self.train_num, self.dpt_stn, self.dpt_time, self.arr_stn, self.arr_time])

    def hash(self):
        return self.hash_value
    
    def to_string(self):
        return f"{self.train_type}({self.train_num})\n{self.dpt_stn} {self.dpt_time} ▶ {self.arr_stn} {self.arr_time}"
        
class SRT:
    def __init__(self, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check=2, want_reserve=False):
        """
        :param dpt_stn: SRT 출발역
        :param arr_stn: SRT 도착역
        :param dpt_dt: 출발 날짜 YYYYMMDD 형태 ex) 20220115
        :param dpt_tm: 출발 시간 hh 형태, 반드시 짝수 ex) 06, 08, 14, ...
        :param num_trains_to_check: 검색 결과 중 예약 가능 여부 확인할 기차의 수 ex) 2일 경우 상위 2개 확인
        :param want_reserve: 예약 대기가 가능할 경우 선택 여부
        """
        self.login_id = None
        self.login_psw = None

        self.dpt_stn = dpt_stn if not str.isdigit(dpt_stn) else num_station_list[int(dpt_stn)] 
        self.arr_stn = arr_stn if not str.isdigit(arr_stn) else num_station_list[int(arr_stn)]

        self.dpt_dt = dpt_dt
        self.dpt_tm = dpt_tm if int(dpt_tm) % 2 == 0 else str(int(dpt_tm) + 1)

        self.num_trains_to_check = num_trains_to_check
        self.want_reserve = want_reserve
        self.driver = None

        self.cnt_refresh = 0  # 새로고침 회수 기록

        self.check_input()

    def check_input(self):
        if self.dpt_stn not in station_list:
            raise InvalidStationNameError(f"출발역 오류. '{self.dpt_stn}' 은/는 목록에 없습니다.")
        if self.arr_stn not in station_list:
            raise InvalidStationNameError(f"도착역 오류. '{self.arr_stn}' 은/는 목록에 없습니다.")
        if not str(self.dpt_dt).isnumeric():
            raise InvalidDateFormatError("날짜는 숫자로만 이루어져야 합니다.")
        try:
            datetime.strptime(str(self.dpt_dt), '%Y%m%d')
        except ValueError:
            raise InvalidDateError("날짜가 잘못 되었습니다. YYYYMMDD 형식으로 입력해주세요.")

    def set_log_info(self, login_id, login_psw):
        self.login_id = login_id
        self.login_psw = login_psw

    def run_driver(self):
        try:
            self.driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH)
        except WebDriverException:
            self.driver = webdriver.Chrome(ChromeDriverManager().install())

    def login(self):
        self.driver.get('https://etk.srail.co.kr/cmc/01/selectLoginForm.do')
        self.driver.implicitly_wait(15)
        self.driver.find_element(By.ID, 'srchDvNm01').send_keys(str(self.login_id))
        self.driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(str(self.login_psw))
        self.driver.find_element(By.XPATH, '//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input').click()
        self.driver.implicitly_wait(5)
        return self.driver

    def check_login(self):
        menu_text = self.driver.find_element(By.CSS_SELECTOR, "#wrap > div.header.header-e > div.global.clear > div").text
        if "환영합니다" in menu_text:
            return True
        else:
            return False

    def go_search(self):
        # 기차 조회 페이지로 이동
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        self.driver.implicitly_wait(5)

        # 출발지 입력
        elm_dpt_stn = self.driver.find_element(By.ID, 'dptRsStnCdNm')
        elm_dpt_stn.clear()
        elm_dpt_stn.send_keys(self.dpt_stn)

        # 도착지 입력
        elm_arr_stn = self.driver.find_element(By.ID, 'arvRsStnCdNm')
        elm_arr_stn.clear()
        elm_arr_stn.send_keys(self.arr_stn)

        # 출발 날짜 입력
        elm_dpt_dt = self.driver.find_element(By.ID, "dptDt")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_dt)
        Select(self.driver.find_element(By.ID, "dptDt")).select_by_value(self.dpt_dt)

        # 출발 시간 입력
        elm_dpt_tm = self.driver.find_element(By.ID, "dptTm")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_tm)
        Select(self.driver.find_element(By.ID, "dptTm")).select_by_visible_text(self.dpt_tm)

        print("기차를 조회합니다")
        print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
        print(f"예약 대기 사용: {self.want_reserve}")

        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        self.driver.implicitly_wait(5)
        time.sleep(1)

    def book_ticket(self, standard_seat, i):
        # standard_seat는 일반석 검색 결과 텍스트
        
        if "예약하기" in standard_seat:
            # Error handling in case that click does not work
            try:
                print("예약 가능 클릭")
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").click()
            except ElementClickInterceptedException as err:
                print(err)
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").send_keys(
                    Keys.ENTER)
            finally:
                self.driver.implicitly_wait(5)

            # 예약이 성공하면
            if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                print("예약 성공")
                return True
            else:
                print("잔여석 없음. 다시 검색")
                self.driver.back()  # 뒤로가기
                self.driver.implicitly_wait(5)

    def refresh_result(self):
        submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
        self.driver.execute_script("arguments[0].click();", submit)
        self.cnt_refresh += 1
        print(f"새로고침 {self.cnt_refresh}회")
        self.driver.implicitly_wait(10)
        time.sleep(0.5)

    def reserve_ticket(self, reservation, i):
        print("예약 대기 완료")
        self.driver.find_element(By.CSS_SELECTOR,
                                    f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8) > a").click()

    def get_train(self, i):
        # 열차종류
        train_type = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(2)").text
        # 열차번호
        train_num = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(3)").text
        # 출발
        dpt = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(4)").text
        # 도착
        arr = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(5)").text
        return Train(train_type, train_num, dpt, arr)

    def check_result(self):
        send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"{get_now_str()}\n*예매조건*\n열차: {self.dpt_stn}▶{self.arr_stn}\n시간: {datetime.strptime(self.dpt_dt, '%Y%m%d').strftime('%Y-%m-%d %a')} {self.dpt_tm}시 이후\n범위: {self.num_trains_to_check}개 대기: {self.want_reserve}")

        booked = defaultdict(lambda: False)
        reserved = defaultdict(lambda: False)

        while True:
            for i in range(1, self.num_trains_to_check+1):
                try:
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text
                    cur_train = self.get_train(i)

                except StaleElementReferenceException:
                    standard_seat = "매진"
                    reservation = "매진"

                if not booked[cur_train.hash()]:
                    if self.book_ticket(standard_seat, i):
                        send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"{get_now_str()}\n*{i}번째 순위 예약성공!*\n{cur_train.to_string()}")
                        booked[cur_train.hash()] = True
                        if i == 1: return

                if self.want_reserve and not booked[cur_train.hash()] and not reserved[cur_train.hash()] and "신청하기" in reservation:
                    send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"*{get_now_str()}{i}번째 순위 예약대기!*\n{cur_train.to_string()}")
                    reserved[cur_train.hash()] = True
                    self.reserve_ticket(reservation, i)

            time.sleep(randint(2, 4))
            self.refresh_result()

    def run(self, login_id, login_psw):
        self.run_driver()
        self.set_log_info(login_id, login_psw)
        self.login()
        self.go_search()
        self.check_result()

#
# if __name__ == "__main__":
#     srt_id = os.environ.get('srt_id')
#     srt_psw = os.environ.get('srt_psw')
#
#     srt = SRT("동탄", "동대구", "20220917", "08")
#     srt.run(srt_id, srt_psw)

