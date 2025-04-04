import os # noqa
import sys # noqa
import argparse
import random
import time
import copy
import pdb # noqa
import shutil
import math
import re # noqa
from datetime import datetime # noqa
import pyotp

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import format_ts
from fun_utils import time_difference
from fun_utils import seconds_to_hms
from fun_utils import get_index_from_header

from fun_encode import decrypt

from conf import DEF_LOCAL_PORT
from conf import DEF_INCOGNITO
from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import NUM_MAX_TRY_PER_DAY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_BROWSER
from conf import DEF_PATH_DATA_STATUS
from conf import DEF_HEADER_STATUS
from conf import DEF_ENCODE_HANDLE

from conf import DEF_PATH_DATA_ACCOUNT
from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import DEF_CAPTCHA_EXTENSION_PATH
from conf import DEF_CAPTCHA_KEY
from conf import EXTENSION_ID_YESCAPTCHA
from conf import DEF_LIST_APPEAL_DESC

from conf import logger

"""
2025.03.18
"""

# Wallet balance
DEF_INSUFFICIENT = -1
DEF_SUCCESS = 0
DEF_FAIL = 1

# Mint would exceed wallet limit
DEF_EXCEED_LIMIT = 10
# Price too high
DEF_PRICE_TOO_HIGH = 11

# output
IDX_STATUS = 1
IDX_VISIT_DATE = 2
IDX_NUM_VISIT = 3
IDX_UPDATE = 4
FIELD_NUM = IDX_UPDATE + 1

# X STATUS
DEF_STATUS_OK = 'OK'
DEF_STATUS_SUSPEND = 'SUSPEND'
DEF_STATUS_APPEALED = 'APPEALED'


class X():
    def __init__(self) -> None:
        self.args = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}

        self.dic_account = {}

        self.account_load()

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        self.status_save()

    def account_load(self):
        # self.file_account = f'{DEF_PATH_DATA_ACCOUNT}/account.csv'
        self.file_account = f'{DEF_PATH_DATA_ACCOUNT}/encrypt.csv'
        self.dic_account = load_file(
            file_in=self.file_account,
            idx_key=0,
            header=DEF_HEADER_ACCOUNT
        )

    def status_load(self):
        self.file_status = f'{DEF_PATH_DATA_STATUS}/status.csv'
        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def status_save(self):
        self.file_status = f'{DEF_PATH_DATA_STATUS}/status.csv'
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def close(self):
        # 在有头浏览器模式 Debug 时，不退出浏览器，用于调试
        if DEF_USE_HEADLESS is False and DEF_DEBUG:
            pass
        else:
            if self.browser:
                try:
                    self.browser.quit()
                except Exception as e: # noqa
                    # logger.info(f'[Close] Error: {e}')
                    pass

    def initChrome(self, s_profile):
        """
        s_profile: 浏览器数据用户目录名称
        """
        # Settings.singleton_tab_obj = True

        profile_path = s_profile

        # 是否设置无痕模式
        if DEF_INCOGNITO:
            co = ChromiumOptions().incognito(True)
        else:
            co = ChromiumOptions()

        # 设置本地启动端口
        co.set_local_port(port=DEF_LOCAL_PORT)
        if len(DEF_PATH_BROWSER) > 0:
            co.set_paths(browser_path=DEF_PATH_BROWSER)

        co.set_argument('--accept-lang', 'en-US')  # 设置语言为英语（美国）
        co.set_argument('--lang', 'en-US')

        # 阻止“自动保存密码”的提示气泡
        co.set_pref('credentials_enable_service', False)

        # 阻止“要恢复页面吗？Chrome未正确关闭”的提示气泡
        co.set_argument('--hide-crash-restore-bubble')

        # 关闭沙盒模式
        # co.set_argument('--no-sandbox')

        # popups支持的取值
        # 0：允许所有弹窗
        # 1：只允许由用户操作触发的弹窗
        # 2：禁止所有弹窗
        # co.set_pref(arg='profile.default_content_settings.popups', value='0')

        co.set_user_data_path(path=DEF_PATH_USER_DATA)
        co.set_user(user=profile_path)

        # 获取当前工作目录
        current_directory = os.getcwd()

        # 检查目录是否存在
        if os.path.exists(os.path.join(current_directory, DEF_CAPTCHA_EXTENSION_PATH)): # noqa
            logger.info(f'YesCaptcha plugin path: {DEF_CAPTCHA_EXTENSION_PATH}') # noqa
            co.add_extension(DEF_CAPTCHA_EXTENSION_PATH)
        else:
            print("YesCaptcha plugin directory is not exist. Exit!")
            sys.exit(1)

        # https://drissionpage.cn/ChromiumPage/browser_opt
        co.headless(DEF_USE_HEADLESS)
        co.set_user_agent(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36') # noqa

        try:
            self.browser = Chromium(co)
        except Exception as e:
            logger.info(f'Error: {e}')
        finally:
            pass

        # 初始化 YesCaptcha
        self.init_yescaptcha()

    def set_max_try_times(self):
        n_max_times = 3
        self.logit(None, f'To set max try times: {n_max_times}') # noqa

        max_try = 20
        i = 0
        while i < max_try:
            i += 1
            tab = self.browser.latest_tab
            x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[5]/div[2]/div/input' # noqa
            ele_input = tab.ele(x_path, timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                if ele_input.value == str(n_max_times):
                    self.logit(None, f'Set n_max_times success! [n_max_times={n_max_times}]') # noqa
                    return True
                else:
                    ele_input.click.multi(times=2)
                    tab.wait(1)
                    ele_input.clear(by_js=True)
                    tab.wait(1)
                    tab.actions.move_to(ele_input).click().type(n_max_times) # noqa
                    tab.wait(1)
                    if ele_input.value != str(n_max_times):
                        continue

                    for s_text in ['保存', 'save']:
                        btn_save = tab.ele(f'tag:button@@text():{s_text}', timeout=2) # noqa
                        if not isinstance(btn_save, NoneElement):
                            tab.actions.move_to(btn_save)
                            btn_save.wait.clickable(timeout=10).click()
                            self.logit(None, 'Save button is clicked')
                            break

            self.logit(None, f'set_mint_num ... [{i}/{max_try}]')

        self.logit(None, f'Fail to set n_max_times! [n_max_times={n_max_times}] [Error]') # noqa
        return False

    def set_auto_start(self, b_auto_start=True):
        n_max_times = 3
        self.logit(None, f'To set max try times: {n_max_times}') # noqa

        max_try = 20
        i = 0
        while i < max_try:
            i += 1
            tab = self.browser.latest_tab
            x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[6]/div[2]/span/input' # noqa
            checkbox = tab.ele(x_path, timeout=2)
            if not isinstance(checkbox, NoneElement):
                if checkbox.states.is_checked == b_auto_start:
                    self.logit(None, f'Set auto_start success! [auto_start={b_auto_start}]') # noqa
                    return True
                checkbox.click()
                self.logit(None, 'Save button is clicked')
                tab.wait(1)

        self.logit(None, f'Fail to set auto_start! [Error]') # noqa
        return False

    def init_yescaptcha(self):
        """
        chrome-extension://jiofmdifioeejeilfkpegipdjiopiekl/popup/index.html
        """
        # EXTENSION_ID = 'jiofmdifioeejeilfkpegipdjiopiekl'
        s_url = f'chrome-extension://{EXTENSION_ID_YESCAPTCHA}/popup/index.html' # noqa
        tab = self.browser.latest_tab
        tab.get(s_url)
        # tab.wait.load_start()
        tab.wait(3)

        self.save_screenshot(name='yescaptcha_1.jpg')

        x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[2]/div[2]/div/input' # noqa
        ele_input = tab.ele(f'{x_path}', timeout=2)
        if not isinstance(ele_input, NoneElement):
            if ele_input.value == DEF_CAPTCHA_KEY:
                logger.info('yescaptcha key is configured')
            else:
                logger.info('input yescaptcha key ...')
                # ele_input.input(DEF_CAPTCHA_KEY, clear=True, by_js=True)
                # ele_input.click()
                tab = self.browser.latest_tab
                ele_input.clear(by_js=True)
                # ele_input.input(DEF_CAPTCHA_KEY, clear=True, by_js=False)
                tab.actions.move_to(ele_input).click().type(DEF_CAPTCHA_KEY) # noqa
                time.sleep(2)

                is_success = False
                for s_text in ['保存', 'save']:
                    # btn_save = tab.ele(s_text, timeout=2)
                    btn_save = tab.ele(f'tag:button@@text():{s_text}', timeout=2) # noqa
                    if not isinstance(btn_save, NoneElement):
                        # btn_save.click(by_js=True)
                        tab.actions.move_to(btn_save).click()
                        is_success = True
                        break
                if is_success:
                    logger.info('Save Success!')
                else:
                    logger.info('Fail to save!')

            # 次数限制
            self.set_max_try_times()

            # 自动开启
            # self.set_auto_start(b_auto_start=True)
            self.set_auto_start(b_auto_start=False)

        logger.info('yescaptcha init success')
        self.save_screenshot(name='yescaptcha_2.jpg')

    def logit(self, func_name=None, s_info=None):
        s_text = f'{self.args.s_profile}'
        if func_name:
            s_text += f' [{func_name}]'
        if s_info:
            s_text += f' {s_info}'
        logger.info(s_text)

    def save_screenshot(self, name):
        tab = self.browser.latest_tab
        # 对整页截图并保存
        # tab.set.window.max()
        s_name = f'{self.args.s_profile}_{name}'
        tab.get_screenshot(path='tmp_img', name=s_name, full_page=True)

    def is_task_complete(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        if s_profile not in self.dic_status:
            return False

        claimed_date = self.dic_status[s_profile][idx_status]
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET) # noqa
        if date_now != claimed_date:
            return False
        else:
            return True

    def update_status(self, idx_status, s_value):
        update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        def init_status():
            self.dic_status[self.args.s_profile] = [
                self.args.s_profile,
            ]
            for i in range(1, FIELD_NUM):
                self.dic_status[self.args.s_profile].append('')

        if self.args.s_profile not in self.dic_status:
            init_status()
        if len(self.dic_status[self.args.s_profile]) != FIELD_NUM:
            init_status()
        if self.dic_status[self.args.s_profile][idx_status] == s_value:
            return

        self.dic_status[self.args.s_profile][idx_status] = s_value
        self.dic_status[self.args.s_profile][IDX_UPDATE] = update_time

        self.status_save()
        self.is_update = True

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == FIELD_NUM:
            try:
                s_val = int(lst_pre[idx_status])
            except: # noqa
                pass

        return s_val

    def get_pre_num_visit(self, s_profile=None):
        num_visit_pre = 0

        s_val = self.get_status_by_idx(IDX_NUM_TRY, s_profile)

        try:
            num_visit_pre = int(s_val)
        except: # noqa
            pass

        return num_visit_pre

    def update_num_visit(self, s_profile=None):
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)
        s_update = self.get_status_by_idx(-1, s_profile)
        if len(s_update) > 10:
            date_update = s_update[:10]
        else:
            date_update = ''
        if date_now != date_update:
            num_visit = 1
        else:
            num_visit_pre = self.get_pre_num_visit(s_profile)
            num_visit = num_visit_pre + 1

        self.update_status(IDX_NUM_VISIT, str(num_visit))

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def wait_log_in_button(self, max_wait_sec=30):
        i = 1
        while i < max_wait_sec:
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Sign in', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                self.logit(None, 'load login in button success ...')
                ele_info.wait.clickable(timeout=60).click(by_js=True)
                # ele_info.click(by_js=True)
                return True
            i += 1
            self.browser.wait(1)
            self.logit(None, f'Wait to load login in button ... {i}/{max_wait_sec}') # noqa
        return False

    def wait_sign_in_to_x(self, max_wait_sec=30):
        i = 1
        while i < max_wait_sec:
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Sign in to X', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                self.logit(None, 'Success to load popup x window ...')
                return True
            i += 1
            self.browser.wait(1)
            self.logit(None, f'Wait to load popup x window ... {i}/{max_wait_sec}') # noqa

            self.wrong_retry()

        return False

    def wait_countdown(self, s_info='', max_wait_sec=30):
        i = 1
        while i < max_wait_sec:
            i += 1
            self.browser.wait(1)
            self.logit('wait_countdown', f'{s_info} {i}/{max_wait_sec}') # noqa

    def is_login_success(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=a@@href=/home', timeout=2)
        if not isinstance(ele_input, NoneElement):
            self.logit(None, f'Already login !') # noqa
            return True
        return False

    def twitter_login(self):
        if self.is_login_success():
            return True

        if not self.wait_log_in_button():
            return False

        if not self.wait_sign_in_to_x():
            return False

        tab = self.browser.latest_tab
        ele_input = tab.ele('@autocapitalize=sentences', timeout=2)
        if not isinstance(ele_input, NoneElement):
            logger.info('Twitter input username ...')
            idx = get_index_from_header(DEF_HEADER_ACCOUNT, 'x_username')
            x_username = self.dic_account[self.args.s_profile][idx]
            ele_input.input(x_username)
            time.sleep(1)
            logger.info('Twitter Click Next')
            tab.ele('@@role=button@@text():Next').click()
            time.sleep(1)
        else:
            return False

        # There was unusual login activity on your account.
        # Enter your phone number or email address
        s_path = '@@tag()=span@@text():Enter your phone number or email address'
        ele_info = tab.ele(s_path, timeout=2)
        if not isinstance(ele_info, NoneElement):
            logger.info('There was unusual login activity on your account.')
            s_email = input('Input email address and press Enter to continue:')
            ele_input = tab.ele('@@tag()=input@@name=text', timeout=2)
            ele_input.input(s_email)
            ele_btn = tab.ele('@@role=button@@text():Next')
            ele_btn.wait.clickable(timeout=15).click()

            # TODO
            input('Press Enter to continue:')
            return False

        # Enter your password 窗口
        s_path = '@@class:css-1jxf684@@text():Enter your password'
        tab.wait.eles_loaded(s_path, timeout=2)
        ele_info = tab.ele(s_path, timeout=2)
        if isinstance(ele_info, NoneElement):
            logger.info('twitter 没有出现密码输入窗口 ...')
            return False
        else:
            ele_input = tab.ele('@name=password', timeout=2)
            if not isinstance(ele_input, NoneElement):
                logger.info('Twitter input password')
                idx = get_index_from_header(DEF_HEADER_ACCOUNT, 'x_pwd')
                encode_pwd = self.dic_account[self.args.s_profile][idx]
                x_pwd = decrypt(DEF_ENCODE_HANDLE, encode_pwd)
                ele_input.input(x_pwd)
                time.sleep(1)
                logger.info('Twitter Click Log in')
                s_path = '@data-testid=LoginForm_Login_Button'
                tab.ele(s_path).wait.clickable(timeout=30)
                tab.ele(s_path).click()
                time.sleep(1)
            else:
                return False

        # Enter your verification code 窗口
        s_path = '@@class:css-1jxf684@@text():Enter your verification code'
        tab.wait.eles_loaded(s_path, timeout=2)
        ele_info = tab.ele(s_path, timeout=2)
        if isinstance(ele_info, NoneElement):
            logger.info('twitter 没有出现一次性密码输入窗口 ...')
            return False
        else:
            ele_input = tab.ele('@name=text', timeout=2)
            if not isinstance(ele_input, NoneElement):
                logger.info('Twitter Input verification code')
                idx = get_index_from_header(DEF_HEADER_ACCOUNT, 'x_verifycode')
                x_verifycode = self.dic_account[self.args.s_profile][idx]
                ele_input.input(pyotp.TOTP(x_verifycode).now())
                time.sleep(1)
                logger.info('Twitter Click Next Button ...')
                s_path = '@data-testid=ocfEnterTextNextButton'
                tab.ele(s_path).wait.clickable(timeout=30)
                tab.ele(s_path).click()
                time.sleep(1)

        if self.is_login_success():
            return True

        return False

    def xvisit_login(self):
        """
        """
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xvisit_login', f'try_i={i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            s_url = 'https://x.com'
            tab.get(s_url, timeout=60, retry=1)

            self.browser.wait(3)

            self.x_locked()

            if self.verify_email():
                self.enter_verification_code()

            self.x_unlocked()

            if self.twitter_login():
                return True
        return False

    def set_vpn(self):
        idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
        try:
            s_vpn = self.dic_account[self.args.s_profile][idx_vpn]
        except: # noqa
            s_vpn = 'NULL'
        self.logit(None, f'[X] Set VPN to {s_vpn} ...')
        d_cont = {
            'title': f'Set VPN to {s_vpn} ! [x_login]',
            'text': (
                '[X] Set VPN [x_login]\n'
                f'- profile: {self.args.s_profile}\n'
                f'- vpn: {s_vpn}\n'
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")
        s_msg = f'[{self.args.s_profile}] Set VPN to {s_vpn} and press Enter to continue! ⚠️' # noqa
        input(s_msg)

        print('Executing ...')

    def enter_verification_code(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['xxx', 'We sent your verification code.']:

                ele_input = tab.ele('@@tag()=input@@class:Edge-textbox', timeout=1) # noqa
                if not isinstance(ele_input, NoneElement):
                    s_code = input('Enter Verification Code:')
                    tab.actions.move_to(ele_input).click().type(s_code) # noqa


                    ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=30).click(by_js=True)
                        tab.wait(2)
                        return True
        return False

    def verify_email(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['xxx', 'Please verify your email address.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(2)
                    return True
        return False

    def click_like(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('click_like', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btns = tab.eles('@@tag()=button@@data-testid=like', timeout=2) # noqa
            if len(ele_btns) > 0:
                ele_btn = random.choice(ele_btns)
                tab.actions.move_to(ele_btn)
                ele_btn.wait.clickable(timeout=30).click(by_js=True)
                tab.wait(2)
                return True
            else:
                pdb.set_trace()
                self.logit(None, 'Fail to load posts ...')
                if self.wrong_retry():
                    self.wait_loading()

        return False

    def is_suspend(self):
        tab = self.browser.latest_tab

        # <span class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3">Your account is suspended and is not permitted to perform this action.</span> # noqa
        for s_text in ['Your account is suspended', '你的账号已被冻结']:
            ele_input = tab.ele(f'@@tag()=span@@text():{s_text}', timeout=2)
            if not isinstance(ele_input, NoneElement):
                s_info = ele_input.text
                self.logit(None, f'{s_info}') # noqa
                self.update_status(IDX_STATUS, DEF_STATUS_SUSPEND)
                return True

        return False

    def do_appeal(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xvisit_login', f'try_i={i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            s_url = 'https://help.x.com/en/forms/account-access/appeals'
            tab.get(s_url, timeout=60, retry=1)

            self.browser.wait(3)

            ele_info = tab.ele('@@tag()=h2@@class:headline@@text()=Appeal a locked or suspended account', timeout=2) # noqa
            if isinstance(ele_info, NoneElement):
                self.logit(None, 'Wait to load Help Center ...')
                continue

            ele_input = tab.ele('@@tag()=input@@name=Form_Email__c', timeout=2)
            if not isinstance(ele_input, NoneElement):
                s_text = ele_input.value
                if len(s_text) == 0:
                    self.logit(None, 'Fail to load email, retry ...') # noqa
                    continue

            ele_input = tab.ele('@@tag()=textarea@@name=DescriptionText', timeout=2)
            if not isinstance(ele_input, NoneElement):
                # s_text = input('Tell us if you’re having a problem accessing your account:')
                s_text = random.choice(DEF_LIST_APPEAL_DESC)
                tab.actions.move_to(ele_input).click().type(s_text) # noqa
                self.logit(None, f'{s_text}') # noqa
                tab.wait(2)

                ele_btn = tab.ele('@@tag()=button@@type=submit@@class:submit', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(2)

                    max_wait_sec = 60
                    i = 1
                    while i < max_wait_sec:
                        tab = self.browser.latest_tab
                        ele_info = tab.ele('@@tag()=h2@@class:headline@@text()=Thank you!', timeout=2) # noqa
                        if not isinstance(ele_info, NoneElement):
                            self.logit(None, 'We’ve received your request. We’ll review, and take further action if appropriate.')
                            self.update_status(IDX_STATUS, DEF_STATUS_APPEALED)
                            return True
                        i += 1
                        self.browser.wait(1)
                        self.logit(None, f'Submiting appeal request ... {i}/{max_wait_sec}') # noqa

        return False

    def wrong_retry(self):
        """
        # noqa
        <span class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3">Something went wrong. Try reloading.</span>
        <span class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3">Retry</span>
        """
        tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=span@@text()=Something went wrong. Try reloading.', timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_info = ele_info.text
            self.logit(None, f'{s_info}') # noqa
            for s_text in ['重试', 'Retry']:
                ele_btn = tab.ele(f'@@tag()=span@@text()={s_text}', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(1)
                    return True
        return False

    def x_locked(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['你的账号已被封锁。', 'Your account has been locked.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    self.wait_countdown('captcha challenge', 15)
                    return True
        return False

    def x_unlocked(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['账号已解锁。', 'Account unlocked.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(1)
                    return True
        return False

    def wait_loading(self, max_wait_sec=60):
        i = 1
        while i < max_wait_sec:
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=div@@aria-label=Loading@@role=progressbar', timeout=2) # noqa
            if isinstance(ele_info, NoneElement):
                self.logit(None, 'Finished loading ...')
                return True
            i += 1
            self.logit(None, f'Loading ... {i}/{max_wait_sec}') # noqa
            tab.wait(1)

        return False

    def xvisit_run(self):
        self.set_vpn()

        self.update_num_visit()

        if not self.xvisit_login():
            self.logit('xvisit_run', 'Fail to login in x')
            return False

        self.x_locked()
        self.x_unlocked()

        self.wait_loading()
        if self.wrong_retry():
            self.wait_loading()

        print(f'[{self.args.s_profile}] Success to log in !')

        # s_msg = 'Press any key to continue! ⚠️' # noqa
        s_msg = 'Will you Like a post ? [y/n]' # noqa
        is_like = input(s_msg)
        if is_like == 'y':
            self.click_like()
            if self.is_suspend():
                is_appeal = input('Your account is suspended. Will you appeal now ? [y/n]')
                if is_appeal == 'y':
                    self.logit(None, 'appealing ...')
                    self.do_appeal()
                else:
                    self.logit(None, 'Not appeal ...')
            else:
                self.update_status(IDX_STATUS, DEF_STATUS_OK)

        self.update_date(IDX_VISIT_DATE)

        s_msg = 'Press any key to exit! ⚠️' # noqa
        input(s_msg)

        self.logit('xvisit_run', 'Finished!')
        self.close()

        return True


def send_msg(instXVisit, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in instXVisit.dic_status:
                lst_status = instXVisit.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[IDX_VISIT_DATE],
            )
        d_cont = {
            'title': 'Daily Check-In Finished! [xvisit]',
            'text': (
                'Daily Check-In [xvisit]\n'
                '- account,time_next_claim\n'
                '{}\n'
                .format(s_info)
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")


def main(args):
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted') # noqa

    instXVisit = XVisit()

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(instXVisit.dic_account.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []
    lst_wait = []

    def get_sec_wait(lst_status):
        n_sec_wait = 0
        if lst_status:
            avail_time = lst_status[IDX_UPDATE]
            if avail_time:
                n_sec_wait = time_difference(avail_time) + 1

        return n_sec_wait

    # 将已完成的剔除掉
    instXVisit.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in instXVisit.dic_status:
            lst_status = instXVisit.dic_status[s_profile]
            n_sec_wait = get_sec_wait(lst_status)
            if n_sec_wait > 0:
                lst_wait.append([s_profile, n_sec_wait])
                # logger.info(f'[{s_profile}] 还需等待{n_sec_wait}秒') # noqa
                n += 1
                profiles.pop(i)
        else:
            continue
    logger.info('#'*40)
    if len(lst_wait) > 0:
        n_top = 5
        logger.info(f'***** Top {n_top} wait list')
        sorted_lst_wait = sorted(lst_wait, key=lambda x: x[1], reverse=False)
        for (s_profile, n_sec_wait) in sorted_lst_wait[:n_top]:
            logger.info(f'[{s_profile}] 还需等待{seconds_to_hms(n_sec_wait)}') # noqa
    percent = math.floor((n / total) * 100)
    logger.info(f'Progress: {percent}% [{n}/{total}]') # noqa

    while profiles:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(profiles)
        percent = math.floor((n / total) * 100)
        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile}]') # noqa
        profiles.remove(s_profile)

        args.s_profile = s_profile

        if s_profile not in instXVisit.dic_account:
            logger.info(f'{s_profile} is not in account conf [ERROR]')
            sys.exit(0)

        def _run():
            s_directory = f'{DEF_PATH_USER_DATA}/{args.s_profile}'
            if os.path.exists(s_directory) and os.path.isdir(s_directory):
                pass
            else:
                # Create new profile
                # instXVisit.initChrome(args.s_profile)
                # instXVisit.init_okx()
                # instXVisit.close()
                pass

            instXVisit.initChrome(args.s_profile)
            is_claim = instXVisit.xvisit_run()
            return is_claim

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                instXVisit.set_args(args)
                instXVisit.status_load()

                if s_profile in instXVisit.dic_status:
                    lst_status = instXVisit.dic_status[s_profile]
                else:
                    lst_status = None

                n_sec_wait = get_sec_wait(lst_status)
                if n_sec_wait > 0:
                    logger.info(f'[{s_profile}] Last update at {lst_status[IDX_UPDATE]}') # noqa
                    break
                else:
                    if _run():
                        lst_success.append(s_profile)
                        instXVisit.close()
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                instXVisit.close()
                if j < max_try_except:
                    time.sleep(5)

        if instXVisit.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')

        if len(items) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(instXVisit, lst_success)


if __name__ == '__main__':
    """
    每次随机取一个出来，并从原列表中删除，直到原列表为空
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--loop_interval', required=False, default=60, type=int,
        help='[默认为 60] 执行完一轮 sleep 的时长(单位是秒)，如果是0，则不循环，只执行一次'
    )
    parser.add_argument(
        '--sleep_sec_min', required=False, default=3, type=int,
        help='[默认为 3] 每个账号执行完 sleep 的最小时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_max', required=False, default=10, type=int,
        help='[默认为 10] 每个账号执行完 sleep 的最大时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_at_start', required=False, default=0, type=int,
        help='[默认为 0] 在启动后先 sleep 的时长(单位是秒)'
    )
    parser.add_argument(
        '--profile', required=False, default='',
        help='按指定的 profile 执行，多个用英文逗号分隔'
    )
    args = parser.parse_args()
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            main(args)
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python xvisit.py --sleep_sec_min=30 --sleep_sec_max=60 --loop_interval=60
python xvisit.py --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180
python xvisit.py --sleep_sec_min=60 --sleep_sec_max=180
"""
