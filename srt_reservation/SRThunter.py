# -*- coding: utf-8 -*-
import time
from random import randint
from datetime import datetime

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import WebDriverException

from srt_reservation.srt import SRT
from srt_reservation.train import Train
from srt_reservation.card import Card
from srt_reservation.slackbot import SlackBot

CHROMEDRIVER_PATH = "/usr/bin/chromedriver"

IMPLICIT_WAIT_SEC = 60

def get_now_str():
    return datetime.now().strftime('%Y-%m-%d %a %H:%M:%S')

class SRThunter:
    def __init__(self, cli_args):
        self.srt = srt = SRT(cli_args.dpt, cli_args.arr, cli_args.dt, cli_args.tm, cli_args.num)
        srt.set_user_info(cli_args.user, cli_args.psw) \
            .set_adult(cli_args.adult) \
            .set_kid(cli_args.kid) \
            .set_elder(cli_args.elder) \
            .set_exact_tms(cli_args.exact_times) \
            .set_want_reserve(cli_args.reserve) \
            .set_greedy(cli_args.greedy)
        
        token, channel = cli_args.slack.strip().split(' ')
        self.bot = SlackBot(token, channel)
        self.card = Card(cli_args.checkout)

        self.cnt_tried = 0  # Timeout 횟수 기록
        self.cnt_refresh = 0  # 새로고침 횟수 기록
        self.success = False

    def run(self):
        self.srt.init_results()
        while not self.success:
            try:
                self.cnt_tried += 1
                self.run_driver()
                self.login(self.srt.login_id, self.srt.login_pwd)
                self.go_search(self.srt)
                self.check_result(self.srt)
            except Exception as e:
                print(e)
                pass

    def run_driver(self):
        try:
            self.driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH)
        except WebDriverException:
            self.driver = webdriver.Chrome(ChromeDriverManager().install())

    def login(self, login_id, login_psw):
        self.driver.get('https://etk.srail.co.kr/cmc/01/selectLoginForm.do')
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)
        self.driver.find_element(By.ID, 'srchDvNm01').send_keys(str(login_id))
        self.driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(str(login_psw))
        self.driver.find_element(By.XPATH, '//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input').click()
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)
        return self.driver

    def check_login(self):
        menu_text = self.driver.find_element(By.CSS_SELECTOR, "#wrap > div.header.header-e > div.global.clear > div").text
        if "환영합니다" in menu_text:
            return True
        else:
            return False

    def go_search(self, srt):
        # 기차 조회 페이지로 이동
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)

        # 출발지 입력
        elm_dpt_stn = self.driver.find_element(By.ID, 'dptRsStnCdNm')
        elm_dpt_stn.clear()
        elm_dpt_stn.send_keys(srt.dpt_stn)

        # 도착지 입력
        elm_arr_stn = self.driver.find_element(By.ID, 'arvRsStnCdNm')
        elm_arr_stn.clear()
        elm_arr_stn.send_keys(srt.arr_stn)

        # 출발 날짜 입력
        elm_dpt_dt = self.driver.find_element(By.ID, "dptDt")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_dt)
        Select(elm_dpt_dt).select_by_value(srt.dpt_dt)

        # 출발 시간 입력
        elm_dpt_tm = self.driver.find_element(By.ID, "dptTm")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_tm)
        Select(elm_dpt_tm).select_by_visible_text(srt.dpt_tm)

        # 인원 수 입력
        if srt.adult != 1:
            elm_adult_num = self.driver.find_element(By.NAME, "psgInfoPerPrnb1")
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_adult_num)
            Select(elm_adult_num).select_by_visible_text(f"어른(만 13세 이상) {srt.adult}명")
        
        if srt.kid > 0:
            elm_kid_num = self.driver.find_element(By.NAME, "psgInfoPerPrnb5")
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_kid_num)
            Select(elm_kid_num).select_by_visible_text(f"어린이(만 6~12세) {srt.kid}명")
        
        if srt.elder > 0:
            elm_elder_num = self.driver.find_element(By.NAME, "psgInfoPerPrnb4")
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_elder_num)
            Select(elm_elder_num).select_by_visible_text(f"경로(만 65세 이상) {srt.elder}명")

        # print("기차를 조회합니다")
        # print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
        # print(f"예약 대기 사용: {self.want_reserve}")
        start_msg = f"{get_now_str()}\n" \
                    f"*예약 시작! ({'자동' if self.card.want_checkout else '수동'} 결제)*\n" \
                    f"열차: {srt.dpt_stn}▶{srt.arr_stn}\n" \
                    f"시간: {datetime.strptime(srt.dpt_dt, '%Y%m%d').strftime('%Y-%m-%d %a')} {srt.dpt_tm}시{'(auto)' if srt.is_dpt_tm_auto_set else ''} 이후\n" \
                    f"범위: {srt.num_trains_to_check}개{'(auto)' if srt.is_num_auto_set else ''}\n" \
                    f"인원: 성인({srt.adult}명) 어린이({srt.kid}명) 경로({srt.elder}명)\n" \
                    f"대기: {srt.want_reserve}\n" \
                    f"고른 시간: {srt.exact_tms if len(srt.exact_tms) != 0 else '-'}" 
        print(start_msg)
        self.bot.send_slack_bot_msg(start_msg)

        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)
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
                self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)

            # 예약이 성공하면
            if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                print("예약 성공")
                return True
            else:
                print("잔여석 없음. 다시 검색")
                self.driver.back()  # 뒤로가기
                self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)

    def refresh_result(self):
        submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
        self.driver.execute_script("arguments[0].click();", submit)
        self.cnt_refresh += 1
        print(f"새로고침 {self.cnt_tried}-{self.cnt_refresh}회")
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)
        time.sleep(0.5)

    def reserve_ticket(self, i):
        self.driver.find_element(By.CSS_SELECTOR,
                                    f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8) > a").click()
        print("예약 대기 완료")

    def get_train(self, dpt_dt, i):
        # 열차종류
        train_type = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(2)").text
        # 열차번호
        train_num = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(3)").text
        # 출발
        dpt = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(4)").text
        # 도착
        arr = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(5)").text
        return Train(dpt_dt, train_type, train_num, dpt, arr)

    def alert_ok(self, print_trace=True):
        time.sleep(2)

        try:
            self.driver.switch_to_alert().accept()
        except:
            try:
                from selenium.webdriver.common.alert import Alert
                Alert(self.driver).accept()
            except Exception as e:
                if print_trace:
                    print(e)
                return False
        return True

    def checkout_ticket(self, my_card, cur_train):
        self.driver.find_element(By.CSS_SELECTOR, f".tal_c > a:nth-child(1)").click()
        self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)

        # 보안키패드 Off
        self.driver.find_element(By.CSS_SELECTOR, f"#Tk_stlCrCrdNo14_checkbox").click()
        self.driver.find_element(By.CSS_SELECTOR, f"#Tk_vanPwd1_checkbox").click()
        # Card Numbers
        for i in range(1, 5):
            cn = self.driver.find_element(By.CSS_SELECTOR, f"#stlCrCrdNo1{i}")
            cn.send_keys(my_card.card_numbers[i-1])

        # Valid date
        Select(self.driver.find_element(By.ID, 'crdVlidTrm1M')).select_by_value(my_card.valid_mon)
        Select(self.driver.find_element(By.ID, 'crdVlidTrm1Y')).select_by_value(my_card.valid_year)

        # Password first 2
        pw = self.driver.find_element(By.CSS_SELECTOR, f"#vanPwd1")
        pw.send_keys(my_card.pw)

        # 인증번호 (주민등록번호 앞 6자리)
        bd = self.driver.find_element(By.CSS_SELECTOR, f"#athnVal1")
        bd.send_keys(my_card.my_number)

        # 스마트폰 발권
        self.driver.find_element(By.CSS_SELECTOR, f"div.tab.tab3 > ul > li:nth-child(2)").click()
        self.alert_ok()

        # 결제버튼
        self.driver.find_element(By.CSS_SELECTOR, f"#requestIssue1").click()
        self.alert_ok()

        self.bot.send_slack_bot_msg(f"{get_now_str()}\n*결제 성공!*\n{cur_train.to_string()}")

    def check_result(self, srt):
        cur_exact_tms_cache = dict()

        while True:
            # 예상하지 못한 alert 넘기기
            while True:
                try:
                    if not self.alert_ok(print_trace=False): break
                except:
                    pass

            for i in range(1, srt.num_trains_to_check+1):
                try:
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text
                    cur_train = self.get_train(srt.dpt_dt, i)

                except Exception as e:
                    print(e)
                    standard_seat = "매진"
                    reservation = "매진"
                    continue

                if cur_exact_tms_cache.get(cur_train.dpt_time) is None:
                    cur_exact_tms_cache[cur_train.dpt_time] = tuple(map(int, cur_train.dpt_time.split(":")))
                if len(srt.exact_tms) != 0 and cur_train.dpt_time not in srt.exact_tms:
                    if srt.max_exact_tm < cur_exact_tms_cache[cur_train.dpt_time]: break
                    continue

                if not srt.booked[cur_train.hash()]:
                    if self.book_ticket(standard_seat, i):
                        self.bot.send_slack_bot_msg(f"{get_now_str()}\n*{i}번째 순위 예약성공!*\n{cur_train.to_string()}")
                        srt.booked[cur_train.hash()] = True
                        srt.gotcha += 1
                        if self.card.want_checkout:
                            try:
                                self.checkout_ticket(self.card, cur_train)
                            except Exception as e:
                                self.bot.send_slack_bot_msg(f"{get_now_str()}\n*결제중 오류!*\n*처리 요망!*\n{cur_train.to_string()}")
                                print(e)
                                exit(1)

                        if not srt.greedy or srt.gotcha == srt.num_trains_to_check:
                            self.success = True
                        return

                if srt.want_reserve and not srt.booked[cur_train.hash()] and not srt.reserved[cur_train.hash()] and "신청하기" in reservation:
                    self.bot.send_slack_bot_msg(f"*{get_now_str()}{i}번째 순위 예약대기!*\n{cur_train.to_string()}")
                    srt.reserved[cur_train.hash()] = True
                    self.reserve_ticket(reservation, i)

            time.sleep(randint(2, 4))
            self.refresh_result()
            self.driver.implicitly_wait(IMPLICIT_WAIT_SEC)