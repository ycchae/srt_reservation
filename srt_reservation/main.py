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
from selenium.common.exceptions import WebDriverException

from srt_reservation.validation import station_list, num_station_list

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
    
class Card:
    def __init__(self, card_filepath):
        with open(card_filepath, "r") as f:
            self.card_numbers = f.readline().strip().split('-')
            self.valid_mon, self.valid_year = f.readline().strip().split('/')
            self.pw = f.readline().strip()
            self.my_number = f.readline().strip()
        self.validate()
    
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

        
class SRT:
    def __init__(self, dpt_stn, arr_stn, dpt_dt, dpt_tm, exact_tms="", num_trains_to_check=2, want_checkout=True, want_reserve=False, greedy=False):
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
        self.is_num_auto_set = False
        self.is_dpt_tm_auto_set = False

        self.dpt_stn = dpt_stn if not str.isdigit(dpt_stn) else num_station_list[int(dpt_stn)] 
        self.arr_stn = arr_stn if not str.isdigit(arr_stn) else num_station_list[int(arr_stn)]

        self.dpt_dt = dpt_dt
        self.dpt_tm = dpt_tm if int(dpt_tm) % 2 == 0 else str(int(dpt_tm) - 1)
        self.exact_tms = exact_tms

        self.num_trains_to_check = num_trains_to_check
        if len(self.exact_tms) > 0:
            self.exact_tms = exact_tms.split(",")
            self.exact_tms.sort(key = lambda x: tuple(map(int, x.split(":"))))
            self.min_exact_tm = tuple(map(int, self.exact_tms[0].split(":")))
            self.max_exact_tm = tuple(map(int, self.exact_tms[-1].split(":")))
            if self.num_trains_to_check < 10:
                self.num_trains_to_check = 10
                self.is_num_auto_set = True
            if(int(dpt_tm) > self.min_exact_tm[0]):
                self.dpt_tm = str(self.min_exact_tm[0]) if self.min_exact_tm[0] % 2 == 0 else str(self.min_exact_tm[0] - 1)
                self.is_dpt_tm_auto_set = True

        self.gotcha = 0

        self.want_checkout = want_checkout
        self.want_reserve = want_reserve
        self.greedy = greedy

        self.driver = None

        self.cnt_tried = 0  # Timeout 횟수 기록
        self.cnt_refresh = 0  # 새로고침 횟수 기록

        self.success = False

        self.check_input()


    def check_input(self):
        if self.dpt_stn not in station_list:
            raise Exception(f"출발역 오류. '{self.dpt_stn}' 은/는 목록에 없습니다.")
        if self.arr_stn not in station_list:
            raise Exception(f"도착역 오류. '{self.arr_stn}' 은/는 목록에 없습니다.")
        if not str(self.dpt_dt).isnumeric():
            raise Exception("날짜는 숫자로만 이루어져야 합니다.")
        
        if self.want_checkout:
            try:
                card_path = f"{os.path.dirname(os.path.abspath(__file__))}/my_card.txt"
                self.my_card = Card(card_path)
            except Exception as e:
                print(e)
                self.want_checkout = False

        try:
            datetime.strptime(str(self.dpt_dt), '%Y%m%d')
        except Exception as e:
            print(e)
            raise Exception("날짜가 잘못 되었습니다. YYYYMMDD 형식으로 입력해주세요.")

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
        self.driver.implicitly_wait(10)

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

        # print("기차를 조회합니다")
        # print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
        # print(f"예약 대기 사용: {self.want_reserve}")
        start_msg = f"{get_now_str()}\n" \
                    f"*예약 시작!*\n" \
                    f"열차: {self.dpt_stn}▶{self.arr_stn}\n" \
                    f"시간: {datetime.strptime(self.dpt_dt, '%Y%m%d').strftime('%Y-%m-%d %a')} {self.dpt_tm}시{'(auto)' if self.is_dpt_tm_auto_set else ''} 이후\n" \
                    f"범위: {self.num_trains_to_check}개{'(auto)' if self.is_num_auto_set else ''}\n" \
                    f"대기: {self.want_reserve}\n" \
                    f"고른 시간: {self.exact_tms if len(self.exact_tms) != 0 else '-'}"
        print(start_msg)
        send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, start_msg)

        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        self.driver.implicitly_wait(10)
        time.sleep(1)

    def book_ticket(self, standard_seat, i):
        # standard_seat는 일반석 검색 결과 텍스트
        if "예약하기" in standard_seat:
            # Error handling in case that click does not work
            try:
                print("예약 가능 클릭")
                b = self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a")
                if "예약하기" in b.text:
                    b.click()
            except Exception as err:
                print(err)
                self.driver.find_element(By.CSS_SELECTOR,
                                         f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7) > a").send_keys(Keys.ENTER)
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
        print(f"새로고침 {self.cnt_tried}-{self.cnt_refresh}회")
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
        return Train(self.dpt_dt, train_type, train_num, dpt, arr)

    def alert_ok(self):
        time.sleep(2)

        try:
            self.driver.switch_to_alert().accept()
        except:
            try:
                from selenium.webdriver.common.alert import Alert
                Alert(self.driver).accept()
            except Exception as e:
                print(e)
                exit(1)

    def checkout_ticket(self, cur_train):
        self.driver.find_element(By.CSS_SELECTOR, f".tal_c > a:nth-child(1)").click()
        self.driver.implicitly_wait(10)

        # 보안키패드 Off
        self.driver.find_element(By.CSS_SELECTOR, f"#Tk_stlCrCrdNo14_checkbox").click()
        self.driver.find_element(By.CSS_SELECTOR, f"#Tk_vanPwd1_checkbox").click()
        # Card Numbers
        for i in range(1, 5):
            cn = self.driver.find_element(By.CSS_SELECTOR, f"#stlCrCrdNo1{i}")
            cn.send_keys(self.my_card.card_numbers[i-1])

        # Valid date
        Select(self.driver.find_element(By.ID, 'crdVlidTrm1M')).select_by_value(self.my_card.valid_mon)
        Select(self.driver.find_element(By.ID, 'crdVlidTrm1Y')).select_by_value(self.my_card.valid_year)

        # Password first 2
        pw = self.driver.find_element(By.CSS_SELECTOR, f"#vanPwd1")
        pw.send_keys(self.my_card.pw)

        # 인증번호 (주민등록번호 앞 6자리)
        bd = self.driver.find_element(By.CSS_SELECTOR, f"#athnVal1")
        bd.send_keys(self.my_card.my_number)

        # 스마트폰 발권
        self.driver.find_element(By.CSS_SELECTOR, f"div.tab.tab3 > ul > li:nth-child(2)").click()
        self.alert_ok()

        # 결제버튼
        self.driver.find_element(By.CSS_SELECTOR, f"#requestIssue1").click()
        self.alert_ok()

        send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"{get_now_str()}\n*결제 성공!*\n{cur_train.to_string()}")

    def check_result(self):
        cur_exact_tms_cache = dict()
        while True:
            for i in range(1, self.num_trains_to_check+1):
                try:
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text
                    cur_train = self.get_train(i)

                except Exception as e:
                    print(e)
                    standard_seat = "매진"
                    reservation = "매진"
                    continue

                if cur_exact_tms_cache.get(cur_train.dpt_time) is None:
                    cur_exact_tms_cache[cur_train.dpt_time] = tuple(map(int, cur_train.dpt_time.split(":")))
                if len(self.exact_tms) != 0 and cur_train.dpt_time not in self.exact_tms:
                    if self.max_exact_tm < cur_exact_tms_cache[cur_train.dpt_time]: break
                    continue

                if not self.booked[cur_train.hash()]:
                    if self.book_ticket(standard_seat, i):
                        send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"{get_now_str()}\n*{i}번째 순위 예약성공!*\n{cur_train.to_string()}")
                        self.booked[cur_train.hash()] = True
                        self.gotcha += 1
                        if self.want_checkout:
                            try:
                                self.checkout_ticket(cur_train)
                            except Exception as e:
                                send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"{get_now_str()}\n*결제중 오류!*\n*처리 요망!*\n{cur_train.to_string()}")
                                print(e)
                                exit(1)

                        if not self.greedy or self.gotcha == self.num_trains_to_check:
                            self.success = True
                        return

                if self.want_reserve and not self.booked[cur_train.hash()] and not self.reserved[cur_train.hash()] and "신청하기" in reservation:
                    send_srt_bot_msg(SRT_BOT_TOKEN, SRT_BOT_CHANNEL, f"*{get_now_str()}{i}번째 순위 예약대기!*\n{cur_train.to_string()}")
                    self.reserved[cur_train.hash()] = True
                    self.reserve_ticket(reservation, i)

            time.sleep(randint(2, 4))
            self.refresh_result()
            self.driver.implicitly_wait(10)

    def run(self, login_id, login_psw):
        self.booked = defaultdict(lambda: False)
        self.reserved = defaultdict(lambda: False)

        while not self.success:
            try:
                self.cnt_tried += 1
                self.run_driver()
                self.set_log_info(login_id, login_psw)
                self.login()
                self.go_search()
                self.check_result()
            except Exception as e:
                print(e)
                pass
                

#
# if __name__ == "__main__":
#     srt_id = os.environ.get('srt_id')
#     srt_psw = os.environ.get('srt_psw')
#
#     srt = SRT("동탄", "동대구", "20220917", "08")
#     srt.run(srt_id, srt_psw)

