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
from fun_utils import get_index_from_header

from fun_encode import decrypt
from fun_gmail import get_verify_code_from_gmail

from fun_glm import gene_repeal_msg

from proxy_api import set_proxy

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS
from conf import DEF_ENCODE_HANDLE_X

from conf import DEF_PATH_DATA_ACCOUNT
from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET

from conf import DEF_LIST_APPEAL_DESC

from conf import logger

"""
2025.03.18
"""

DEF_FILE_X_ENCRIYPT = f'{DEF_PATH_DATA_ACCOUNT}/x_encrypt.csv'
DEF_FILE_X_STATUS = f'{DEF_PATH_DATA_STATUS}/x_status.csv'


class XUtils():
    def __init__(self) -> None:
        self.args = None
        self.browser = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}

        self.dic_account = {}

        self.account_load()

        # output
        self.DEF_HEADER_STATUS = 'account,status,visit_date,num_visit,update_time' # noqa
        self.IDX_STATUS = 1
        self.IDX_VISIT_DATE = 2
        self.IDX_NUM_VISIT = 3
        self.IDX_UPDATE = 4
        self.FIELD_NUM = self.IDX_UPDATE + 1

        # X STATUS
        self.DEF_STATUS_OK = 'OK'
        self.DEF_STATUS_SUSPEND = 'SUSPEND'
        self.DEF_STATUS_APPEALED = 'APPEALED'

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def set_browser(self, browser):
        self.browser = browser

    def __del__(self):
        self.status_save()

    def account_load(self):
        self.file_account = DEF_FILE_X_ENCRIYPT
        self.dic_account = load_file(
            file_in=self.file_account,
            idx_key=0,
            header=DEF_HEADER_ACCOUNT
        )

    def status_load(self):
        self.file_status = DEF_FILE_X_STATUS
        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=self.DEF_HEADER_STATUS
        )

    def status_save(self):
        self.file_status = DEF_FILE_X_STATUS
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=self.DEF_HEADER_STATUS
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
            for i in range(1, self.FIELD_NUM):
                self.dic_status[self.args.s_profile].append('')

        if self.args.s_profile not in self.dic_status:
            init_status()
        if len(self.dic_status[self.args.s_profile]) != self.FIELD_NUM:
            init_status()
        if self.dic_status[self.args.s_profile][idx_status] == s_value:
            return

        self.dic_status[self.args.s_profile][idx_status] = s_value
        self.dic_status[self.args.s_profile][self.IDX_UPDATE] = update_time

        self.status_save()
        self.is_update = True

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == self.FIELD_NUM:
            try:
                s_val = int(lst_pre[idx_status])
            except: # noqa
                pass

        return s_val

    def get_pre_num_visit(self, s_profile=None):
        num_visit_pre = 0

        s_val = self.get_status_by_idx(self.IDX_NUM_VISIT, s_profile)

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

        self.update_status(self.IDX_NUM_VISIT, str(num_visit))

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def verify_human(self):
        s_path = '@@tag()=p@@class=h2 spacer-bottom'
        s_text = self.get_text(s_path, 'Verify')
        if s_text is None:
            return False
        return True

    def auto_verify_cloudflare(self):
        if self.verify_human():
            # s_msg = f'[{self.args.s_profile}]Verify you are human by completing the action'
            # ding_msg(s_msg, DEF_DING_TOKEN, msgtype='text')
            # input('Verify you are human by completing the action')

            # Wait CapMonster to verify
            max_wait_sec = 60
            i = 0
            while i < max_wait_sec:
                i += 1
                if self.verify_human() is False:
                    self.logit(None, f'CapMonster verify success !') # noqa
                    return True
                self.logit(None, f'Wait CapMonster to verify ... {i}/{max_wait_sec}') # noqa
                self.browser.wait(1)

            self.logit(None, f'CapMonster failed to verify ! Refresh Page.') # noqa
            tab = self.browser.latest_tab
            tab.refresh()
            return False
        return True

    def wait_log_in_button(self, max_wait_sec=30):
        i = 0
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

            self.x_locked()

            if self.x_unlocked():
                break

            # ERR_CONNECTION_RESET

            self.auto_verify_cloudflare()

            if self.verify_email():
                break

            # Login success
            if self.wait_loading():
                break

            self.logit(None, f'Wait to load login in button ... {i}/{max_wait_sec}') # noqa
        return False

    def wait_sign_in_to_x(self, max_wait_sec=30):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Sign in to X', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                self.logit(None, 'Success to load popup x window ...')
                return True

            self.browser.wait(1)
            self.logit(None, f'Wait to load popup x window ... {i}/{max_wait_sec}') # noqa

            self.wrong_retry()

        return False

    def wait_countdown(self, s_info='', max_wait_sec=30):
        i = 0
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

    def get_tag_info(self, s_tag, s_text):
        """
        s_tag:
            span
            div
        """
        tab = self.browser.latest_tab
        s_path = f'@@tag()={s_tag}@@text():{s_text}'
        ele_info = tab.ele(s_path, timeout=1)
        if not isinstance(ele_info, NoneElement):
            # self.logit(None, f'[html] {s_text}: {ele_info.html}')
            s_info = ele_info.text.replace('\n', ' ')
            self.logit(None, f'[info][{s_tag}] {s_text}: {s_info}')
            return True
        return False

    def get_text(self, s_path, s_msg):
        """
        """
        tab = self.browser.latest_tab
        ele_info = tab.ele(s_path, timeout=1)
        if not isinstance(ele_info, NoneElement):
            # self.logit(None, f'[html] {s_text}: {ele_info.html}')
            s_info = ele_info.text.replace('\n', ' ')
            self.logit(None, f'[info][{s_msg}]: {s_info}')
            return s_info
        return None

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
        s_path = '@@tag()=span@@text():Enter your phone number or email address' # noqa
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
                x_pwd = decrypt(DEF_ENCODE_HANDLE_X, encode_pwd)
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

    def xutils_login(self):
        """
        """
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xutils_login', f'try_i={i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            s_url = 'https://x.com'
            tab.get(s_url, timeout=60, retry=1)

            self.browser.wait(3)

            self.x_locked()

            # if self.verify_email():
            #     self.enter_verification_code()

            self.verify_email()
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
        # d_cont = {
        #     'title': f'Set VPN to {s_vpn} ! [x_login]',
        #     'text': (
        #         '[X] Set VPN [x_login]\n'
        #         f'- profile: {self.args.s_profile}\n'
        #         f'- vpn: {s_vpn}\n'
        #     )
        # }
        # ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")
        # s_msg = f'[{self.args.s_profile}] Set VPN to {s_vpn} and press Enter to continue! ⚠️' # noqa
        # input(s_msg)
        # print('Executing ...')

        if set_proxy(s_vpn):
            self.logit(None, f'Set VPN Success [VPN: {s_vpn}]')
            self.browser.wait(3)
            return True
        else:
            d_cont = {
                'title': f'Fail to set VPN to {s_vpn} ! [x_login]',
                'text': (
                    '[X] Fail to set VPN [x_login]\n'
                    f'- profile: {self.args.s_profile}\n'
                    f'- vpn: {s_vpn}\n'
                )
            }
            ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")
            return False

    def enter_verification_code(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}')
            if s_info in ['我们发送了你的验证码。', 'We sent your verification code.']:

                ele_input = tab.ele('@@tag()=input@@class:Edge-textbox', timeout=1) # noqa
                if not isinstance(ele_input, NoneElement):
                    # s_code = input('Enter Verification Code:')

                    s_code = None
                    max_wait_sec = 120
                    i = 0
                    while i < max_wait_sec:
                        i += 1
                        self.browser.wait(1)
                        s_code = get_verify_code_from_gmail()
                        if s_code is not None:
                            break
                        self.logit(None, f'Try to get verification code from gmail ... {i}/{max_wait_sec}') # noqa

                    if s_code is None:
                        self.logit(None, 'Fail to get verification code from gmail') # noqa
                    else:
                        self.logit(None, f'verification code is {s_code}')

                    tab.actions.move_to(ele_input).click().type(s_code)
                    tab.wait(2)

                    ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        btn_text = ele_btn.value
                        self.logit(None, f'Button text: {btn_text}')
                        ele_btn.wait.clickable(timeout=30).click(by_js=True)
                        tab.wait(2)
                        return True
                    else:
                        self.logit(None, 'Verify Button not found.')
        return False

    def verify_email(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['请验证你的邮件地址。', 'Please verify your email address.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(2)

                    # d_cont = {
                    #     'title': 'verify by email [x_login]',
                    #     'text': (
                    #         '[X] verify by email [x_login]\n'
                    #         f'- profile: {self.args.s_profile}\n'
                    #     )
                    # }
                    # ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")

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
                self.update_status(self.IDX_STATUS, self.DEF_STATUS_SUSPEND)
                return True

        return False

    def do_appeal(self):

        s_cont_default = random.choice(DEF_LIST_APPEAL_DESC)
        s_cont_llm = gene_repeal_msg(s_cont_default)
        if s_cont_llm is None:
            s_cont_appeal = s_cont_default
            self.logit(None, f'Fail to gene appeal cont by llm. cont_default: {s_cont_appeal}') # noqa
        else:
            s_cont_appeal = s_cont_llm

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xutils_login', f'try_i={i}/{DEF_NUM_TRY}')

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

            ele_input = tab.ele('@@tag()=textarea@@name=DescriptionText', timeout=2) # noqa
            if not isinstance(ele_input, NoneElement):
                # s_text = input('Tell us if you’re having a problem accessing your account:') # noqa
                tab.actions.move_to(ele_input).click().type(s_cont_appeal) # noqa
                self.logit(None, f'{s_cont_appeal}') # noqa
                tab.wait(2)

                ele_btn = tab.ele('@@tag()=button@@type=submit@@class:submit', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(2)

                    max_wait_sec = 60
                    i = 0
                    while i < max_wait_sec:
                        i += 1
                        tab = self.browser.latest_tab
                        ele_info = tab.ele('@@tag()=h2@@class:headline@@text()=Thank you!', timeout=2) # noqa
                        if not isinstance(ele_info, NoneElement):
                            self.logit(None, 'We’ve received your request. We’ll review, and take further action if appropriate.') # noqa
                            self.update_status(self.IDX_STATUS, self.DEF_STATUS_APPEALED) # noqa
                            return True

                        self.browser.wait(1)

                        # <span id="feather-form-field-text-173">Your original case is already in the queue. Please wait to hear back from us on the original case.</span> # noqa
                        if self.get_tag_info('span', 'Your original case is already in the queue'): # noqa
                            return True

                        self.logit(None, f'Submiting appeal request ... {i}/{max_wait_sec}') # noqa

        return False

    def wrong_retry(self):
        """
        # noqa
        <span class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3">Something went wrong. Try reloading.</span>
        <span class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3">Retry</span>
        """
        tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=span@@text()=Something went wrong. Try reloading.', timeout=2) # noqa
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
            self.logit(None, f'PageHeader Info: {s_info}') # noqa
            if s_info in ['账号已解锁。', 'Account unlocked.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.wait.clickable(timeout=30).click(by_js=True)
                    tab.wait(3)
                    return True
        return False

    def wait_loading(self, max_wait_sec=60):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=div@@aria-label=Loading@@role=progressbar', timeout=2) # noqa
            if isinstance(ele_info, NoneElement):
                self.logit(None, 'Finished loading ...')
                return True

            self.logit(None, f'Loading ... {i}/{max_wait_sec}') # noqa
            tab.wait(1)

        return False

    def twitter_run(self):
        # if self.set_vpn() is False:
        #     return False

        self.update_num_visit()

        if not self.xutils_login():
            self.logit('twitter_run', 'Fail to login in x')
            return False

        self.x_locked()
        self.x_unlocked()

        self.wait_loading()
        if self.wrong_retry():
            self.wait_loading()

        if self.args.auto_like:
            is_like = 'y'
        else:
            print(f'[{self.args.s_profile}] Success to log in !')
            # s_msg = 'Press any key to continue! ⚠️' # noqa
            s_msg = 'Will you Like a post ? [y/n]' # noqa
            is_like = input(s_msg)

        if is_like == 'y':
            if not self.click_like():
                return False
            if self.is_suspend():
                if self.args.auto_appeal is True:
                    is_appeal = 'y'
                else:
                    is_appeal = input('Your account is suspended. Will you appeal now ? [y/n]') # noqa

                if is_appeal == 'y':
                    self.logit(None, 'appealing ...')
                    self.do_appeal()
                else:
                    self.logit(None, 'Not appeal ...')
            else:
                self.update_status(self.IDX_STATUS, self.DEF_STATUS_OK)

        self.update_date(self.IDX_VISIT_DATE)

        # if self.args.manual_exit:
        #     s_msg = 'Press any key to exit! ⚠️' # noqa
        #     input(s_msg)

        # self.logit('twitter_run', 'Finished!')
        # self.close()

        return True

    def x_follow(self, name):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_follow', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btn = tab.ele('@@tag()=button@@data-testid=confirmationSheetCancel', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Click Cancel button [{s_info}]') # noqa
                ele_btn.click(by_js=True)

            ele_btn = tab.ele(f'@@tag()=button@@data-testid:follow@@aria-label:{name}', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Follow Button Text: {s_info}')

                # data-testid="1649307142871212032-unfollow"
                s_attr = ele_btn.attr('data-testid').split('-')[-1]
                # Status: following
                if s_attr == 'unfollow':
                    self.logit(None, 'Follow Success [OK]')
                    return True
                self.logit(None, 'Try to Click Follow Button')
                ele_btn.click(by_js=True)
                tab.wait(1)
        return False

    def x_authorize_app(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_authorize_app', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btn = tab.ele('@@tag()=button@@data-testid=OAuth_Consent_Button', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Click Authorize app button [{s_info}]') # noqa
                ele_btn.wait.clickable(timeout=5).click(by_js=True)
                tab.wait(1)
                return True
        return False

    def twitter_create(self):
        self.update_num_visit()

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xutils_login', f'try_i={i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            s_url = 'https://x.com'
            tab.get(s_url, timeout=60, retry=1)

            self.browser.wait(3)
            s_msg = 'Press any key to continue ! ⚠️' # noqa
            input(s_msg)

        return False


if __name__ == '__main__':
    """
    Twitter utils
    """
    pass
