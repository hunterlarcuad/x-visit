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
from fun_utils import generate_password
from fun_utils import get_index_from_header

from fun_encode import decrypt
from fun_gmail import get_verify_code_from_gmail

from fun_glm import gene_repeal_msg

from proxy_api import set_proxy

from fun_dp import DpUtils

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
DEF_FILE_X_CREATE = f'{DEF_PATH_DATA_ACCOUNT}/x_create.csv'


class XUtils():
    def __init__(self) -> None:
        self.args = None
        self.browser = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}
        self.dic_account = {}

        # Create account
        self.dic_create = {}

        self.inst_dp = DpUtils()

        self.dic_account = load_file(
            file_in=DEF_FILE_X_ENCRIYPT,
            idx_key=0,
            header=DEF_HEADER_ACCOUNT
        )

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
        self.DEF_STATUS_EXCEED_ATTEMPT = 'EXCEED_ATTEMPT'

        # create account output
        self.DEF_HEADER_CREATE = 'account,x_username,x_pwd,x_verifycode,proxy,x_backupcode,x_email,birthday' # noqa
        self.IDX_C_ACCOUNT = 0
        self.IDX_C_USERNAME = 1
        self.IDX_C_PWD = 2
        self.IDX_C_VERIFYCODE = 3
        self.IDX_C_PROXY = 4
        self.IDX_C_BACKUPCODE = 5
        self.IDX_C_EMAIL = 6
        self.IDX_C_BIRTHDAY = 7
        self.IDX_C_UPDATE = 8
        self.C_FIELD_NUM = self.IDX_C_UPDATE + 1

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def set_browser(self, browser):
        self.browser = browser

    def __del__(self):
        self.status_save()

    # def account_load(self):
    #     self.file_account = DEF_FILE_X_ENCRIYPT
    #     self.dic_account = load_file(
    #         file_in=self.file_account,
    #         idx_key=0,
    #         header=DEF_HEADER_ACCOUNT
    #     )

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

    def create_save(self):
        self.file_status = DEF_FILE_X_CREATE
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=self.DEF_HEADER_CREATE
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

    def init_dict(self, dic_para, n_field):
        dic_para[self.args.s_profile] = [
            self.args.s_profile,
        ]
        for i in range(1, n_field):
            dic_para[self.args.s_profile].append('')
        return dic_para

    def update_create(self, idx_status, s_value):
        update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        if self.args.s_profile not in self.dic_create:
            self.dic_create = self.init_dict(self.dic_create, self.C_FIELD_NUM)
        if len(self.dic_create[self.args.s_profile]) != self.C_FIELD_NUM:
            self.dic_create = self.init_dict(self.dic_create, self.C_FIELD_NUM)
        if self.dic_create[self.args.s_profile][idx_status] == s_value:
            return

        self.dic_create[self.args.s_profile][idx_status] = s_value
        self.dic_create[self.args.s_profile][self.IDX_C_UPDATE] = update_time

        save2file(
            file_ot=DEF_FILE_X_CREATE,
            dic_status=self.dic_create,
            idx_key=0,
            header=self.DEF_HEADER_CREATE
        )

        self.is_update = True

    def update_status(self, idx_status, s_value):
        update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        if self.args.s_profile not in self.dic_status:
            self.dic_status = self.init_dict(self.dic_status, self.FIELD_NUM)
        if len(self.dic_status[self.args.s_profile]) != self.FIELD_NUM:
            self.dic_status = self.init_dict(self.dic_status, self.FIELD_NUM)
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
            # s_msg = f'[{self.args.s_profile}]Verify you are human by completing the action' # noqa
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
                if ele_info.wait.clickable(timeout=60) is not False:
                    ele_info.click(by_js=True)
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

    def should_sign_in(self):
        tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Sign in to X', timeout=2) # noqa
        if not isinstance(ele_info, NoneElement):
            self.logit(None, 'Sign in to X ...')
            return True
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
            if ele_btn.wait.clickable(timeout=15) is not False:
                ele_btn.click()

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
                if tab.ele(s_path).wait.clickable(timeout=30) is not False:
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
                if tab.ele(s_path).wait.clickable(timeout=30) is not False:
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
            if self.enter_verification_code() is False:
                continue

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

    def extract_between_at_and_com(self, text):
        # 使用正则表达式匹配 @ 和 ***.com 之间的内容
        pattern = r"@([a-zA-Z]+)\*\*\*\.com"
        match = re.search(pattern, text)
        if match:
            return match.group(1)  # 返回匹配到的内容
        else:
            return None  # 如果没有匹配到，返回 None

    def register_verification_code(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=h1@@id=modal-header', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}')
            if s_info in ['xxx', 'We sent you a code']:
                ele_input = tab.ele('@@tag()=input@@name=verfication_code', timeout=1) # noqa
                if not isinstance(ele_input, NoneElement):
                    # s_code = input('Enter Verification Code:')

                    s_code = None
                    max_wait_sec = 10
                    i = 0
                    while i < max_wait_sec:
                        i += 1
                        self.browser.wait(1)
                        s_in_title = 'is your X verification code'
                        s_code = get_verify_code_from_gmail(s_in_title)
                        if s_code is not None:
                            break
                        self.logit(None, f'Try to get verification code from gmail ... {i}/{max_wait_sec}') # noqa
                        # 查看z***@p***.com获取验证码，然后输入以验证这是你的电子邮件地址。
                        ele_info = tab.ele('@@tag()=div@@class=css-175oi2r r-knv0ih', timeout=1) # noqa
                        if not isinstance(ele_info, NoneElement):
                            s_info = ele_info.text
                            self.logit(None, f'Register code in email: {s_info}') # noqa
                            # s_mail_prefix = self.extract_between_at_and_com(s_info) # noqa
                            # if s_mail_prefix is None:
                            #     continue
                            # if s_mail_prefix == 'g':
                            #     pass
                            # else:
                            #     self.logit(None, 'Not Gmail ? Please check!')

                    if s_code is None:
                        self.logit(None, 'Fail to get verification code from gmail') # noqa
                        return False
                    else:
                        self.logit(None, f'verification code is {s_code}')

                    tab.actions.move_to(ele_input).click().type(s_code)
                    tab.wait(2)

                    ele_btn = tab.ele('@@tag()=div@@class=css-175oi2r r-b9tw7p', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        btn_text = ele_btn.value
                        self.logit(None, f'Button text: {btn_text}')
                        if ele_btn.wait.clickable(timeout=30) is not False:
                            ele_btn.click()
                        tab.wait(2)
                        return True
                    else:
                        self.logit(None, 'Verify Button not found.')
                        return False
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
                        s_in_title = 'confirm your email address to access all of X'
                        s_code = get_verify_code_from_gmail(s_in_title)
                        if s_code is not None:
                            break
                        self.logit(None, f'Try to get verification code from gmail ... {i}/{max_wait_sec}') # noqa
                        # 查看z***@p***.com获取验证码，然后输入以验证这是你的电子邮件地址。
                        ele_info = tab.ele('@@tag()=div@@class=TextGroup-text', timeout=1) # noqa
                        if not isinstance(ele_info, NoneElement):
                            s_info = ele_info.text
                            self.logit(None, f'TextGroup-text: {s_info}')
                            s_mail_prefix = self.extract_between_at_and_com(s_info) # noqa
                            if s_mail_prefix is None:
                                continue
                            if s_mail_prefix == 'g':
                                pass
                            else:
                                self.logit(None, 'Not Gmail ? Please check!')

                    if s_code is None:
                        self.logit(None, 'Fail to get verification code from gmail') # noqa
                        return False
                    else:
                        self.logit(None, f'verification code is {s_code}')

                    tab.actions.move_to(ele_input).click().type(s_code)
                    tab.wait(2)

                    ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        btn_text = ele_btn.value
                        self.logit(None, f'Button text: {btn_text}')
                        if ele_btn.wait.clickable(timeout=30) is not False:
                            ele_btn.click(by_js=True)
                        tab.wait(2)
                        return True
                    else:
                        self.logit(None, 'Verify Button not found.')
                        return False
        return True

    def verify_email(self):
        tab = self.browser.latest_tab
        ele_input = tab.ele('@@tag()=div@@class=PageHeader Edge', timeout=2)
        if not isinstance(ele_input, NoneElement):
            s_info = ele_input.text
            self.logit(None, f'{s_info}') # noqa
            if s_info in ['请验证你的邮件地址。', 'Please verify your email address.']:
                ele_btn = tab.ele('@@tag()=input@@type=submit@@class:EdgeButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
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
                try:
                    ele_btn = random.choice(ele_btns)
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        tab.actions.move_to(ele_btn)
                        ele_btn.click(by_js=True)
                    tab.wait(2)
                    return True
                except Exception as e: # noqa
                    self.logit('click_like', f'Error: {e}')
                    pdb.set_trace()
            else:
                self.logit(None, 'Fail to load posts ...')
                if self.wrong_retry():
                    self.wait_loading()
            tab.wait(2)

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
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
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
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
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
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
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
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(3)
                    return True
            elif s_info in ['Something went wrong.', '发生了错误。']:
                ele_info = tab.ele('@@tag()=div@@class=TextGroup-text', timeout=1) # noqa
                if not isinstance(ele_info, NoneElement):
                    s_info = ele_info.text
                    self.logit(None, f'TextGroup-text: {s_info}')
                    if s_info in ['You have exceeded the number of allowed attempts. Please try again later.', '你已超过允许尝试次数，请稍后再试。']: # noqa
                        self.update_status(self.IDX_STATUS, self.DEF_STATUS_EXCEED_ATTEMPT) # noqa
                    return False

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
                    is_appeal = 'n'
                    # is_appeal = input('Your account is suspended. Will you appeal now ? [y/n]') # noqa

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
            ele_btn = tab.ele('@@tag()=button@@data-testid=confirmationSheetCancel', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Click Cancel button [{s_info}]') # noqa
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)

            ele_btn = tab.ele(f'@@tag()=button@@data-testid:follow@@aria-label:{name}', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                tab.actions.move_to(ele_btn)
                s_info = ele_btn.text
                self.logit(None, f'Follow Button Text: {s_info}')

                # data-testid="1649307142871212032-unfollow"
                s_attr = ele_btn.attr('data-testid').split('-')[-1]
                # Status: following
                if s_attr == 'unfollow':
                    self.logit(None, 'Follow Success ✅')
                    return True
                self.logit(None, 'Try to Click Follow Button')
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(1)
        return False

    def jump_to_new_tweet(self):
        tab = self.browser.latest_tab
        # See the latest post
        # 这个帖子有新的版本。查看最新帖子
        lst_path = [
            '@@tag()=a@@aria-describedby:id@@text():See the latest post',  # en
            '@@tag()=a@@aria-describedby:id@@text():查看最新帖子'  # zh
        ]
        ele_btn = self.inst_dp.get_ele_btn(self.browser.latest_tab, lst_path)
        if ele_btn is not NoneElement:
            if ele_btn.wait.clickable(timeout=5) is not False:
                ele_btn.click(by_js=True)
            tab.wait(2)
            return True
        return False

    def x_retweet(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_retweet', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            tab.wait.doc_loaded()

            # Cancel
            ele_btn = tab.ele('@@tag()=button@@data-testid=confirmationSheetCancel', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit('x_retweet', f'Click Cancel button [{s_info}]') # noqa
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)

            # See the latest post
            if self.jump_to_new_tweet():
                continue

            # ele_btn = tab.ele('@@tag()=button@@data-testid:retweet@@aria-label:Repost', timeout=2) # noqa
            ele_btn = tab.ele('@@tag()=button@@data-testid:retweet', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'reposts num: {s_info}')

                # data-testid="retweet"
                s_attr = ele_btn.attr('data-testid')
                # Status: retweet / unretweet
                if s_attr == 'unretweet':
                    self.logit(None, 'Retweet Success ✅')
                    return True
                self.logit(None, 'Try to Click Retweet Button')
                try:
                    tab.actions.move_to(ele_btn)
                    if ele_btn.wait.clickable(timeout=1) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(1)

                    ele_btn = tab.ele('@@tag()=div@@data-testid=retweetConfirm', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        s_info = ele_btn.text
                        self.logit(None, f'Click Cancel button [{s_info}]') # noqa
                        if ele_btn.wait.clickable(timeout=5) is not False:
                            ele_btn.click(by_js=True)
                except Exception as e: # noqa
                    self.logit('click_like', f'Error: {e}')

        return False

    def x_like(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_like', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            tab.wait.doc_loaded()

            # Cancel
            ele_btn = tab.ele('@@tag()=button@@data-testid=confirmationSheetCancel', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit('x_like', f'Click Cancel button [{s_info}]') # noqa
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)

            # See the latest post
            if self.jump_to_new_tweet():
                continue

            ele_btn = tab.ele('@@tag()=button@@data-testid=like', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Likes num: {s_info}')

                # data-testid="retweet"
                s_attr = ele_btn.attr('data-testid')
                # Status: like / unlike
                if s_attr == 'unlike':
                    self.logit(None, 'Like Success ✅')
                    return True
                self.logit(None, 'Try to Click Like Button')
                tab.actions.move_to(ele_btn)
                if ele_btn.wait.clickable(timeout=1) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(1)

            ele_btn = tab.ele('@@tag()=button@@data-testid=unlike', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Already liked. Likes num: {s_info}')
                return True

        return False

    def x_reply(self, s_text):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_reply', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            tab.wait.doc_loaded()

            # Cancel
            ele_btn = tab.ele('@@tag()=button@@data-testid=confirmationSheetCancel', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit('x_reply', f'Click Cancel button [{s_info}]') # noqa
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)

            # See the latest post
            if self.jump_to_new_tweet():
                continue

            ele_btn = tab.ele('@@tag()=div@@data-testid=tweetTextarea_0_label', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Try to input reply text ...')
                tab.actions.move_to(ele_btn)
                if ele_btn.text.replace('\n', ' ') != s_text.replace('\n', ' '):
                    ele_btn.input(s_text)
                    tab.wait(2)

                if ele_btn.text.replace('\n', ' ') != s_text.replace('\n', ' '):
                    self.logit(None, 'reply ele_btn.text != s_text')
                    self.logit(None, '-- ele_btn.text: {ele_btn.text}')
                    self.logit(None, '-- s_text: {s_text}')
                    continue
            else:
                continue

            ele_btn = tab.ele('@@tag()=button@@data-testid=tweetButtonInline', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Try to click reply button ...')
                tab.actions.move_to(ele_btn)
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)

                tab.wait(1)

                ele_info = tab.ele('@@tag()=div@@aria-live=assertive', timeout=2)
                if not isinstance(ele_info, NoneElement):
                    self.logit(None, f'reply assertive: {ele_info.text}')

                self.logit(None, 'Reply Success ✅')
                return True

        self.logit(None, 'Fail to reply [ERROR]')
        return False

    def x_authorize_app(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('x_authorize_app', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btn = tab.ele('@@tag()=button@@data-testid=OAuth_Consent_Button', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_info = ele_btn.text
                self.logit(None, f'Click Authorize app button [{s_info}]') # noqa
                if ele_btn.wait.clickable(timeout=5) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(1)
                return True
        return False

    def get_create_account_btn(self):
        tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=a@@data-testid=signupButton', timeout=2) # noqa
        return ele_info

    def wait_create_account_button(self, max_wait_sec=30):
        i = 0
        while i < max_wait_sec:
            # tab = self.browser.latest_tab
            # ele_info = tab.ele('@@tag()=a@@data-testid=signupButton', timeout=2) # noqa
            ele_info = self.get_create_account_btn()
            if not isinstance(ele_info, NoneElement):
                self.logit(None, 'load create account button success ...')
                if ele_info.wait.clickable(timeout=60) is not False:
                    ele_info.click(by_js=True)
                # ele_info.click(by_js=True)
                return True
            i += 1
            self.browser.wait(1)
            self.logit(None, f'Wait to load create account button ... {i}/{max_wait_sec}') # noqa

        self.logit(None, 'Fail to load create account button ...') # noqa
        return False

    def wait_create_account_to_x(self, max_wait_sec=30):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_info = tab.ele('@@tag()=span@@class=css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3@@text()=Create your account', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                self.logit(None, 'Success to load popup x window ...')
                return True

            self.browser.wait(1)
            self.logit(None, f'Wait to load popup x window ... {i}/{max_wait_sec}') # noqa

            self.wrong_retry()

        self.logit(None, 'Fail to load popup x window ...') # noqa
        return False

    def create_account_input(self):
        def select_birth(s_id, s_val):
            tab = self.browser.latest_tab
            ele_input = tab.ele(f'@@tag()=select@@id={s_id}', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                ele_input.select.by_value(s_val)
                tab.wait(1)
                return True
            return False

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('create_account_input', f'try_i={i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            # Name
            ele_input = tab.ele('@@tag()=input@@name=name', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                if not self.args.name:
                    s_name = self.args.email.split('@')[0]
                else:
                    s_name = self.args.name
                tab.actions.move_to(ele_input).click().type(s_name)
                tab.wait(1)

            # Email
            ele_btn = tab.ele('@@tag()=button@@dir=ltr@@type=button', timeout=1) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.text in ['Use email instead']:
                    ele_btn.click(by_js=True)
                    tab.wait(1)
            ele_input = tab.ele('@@tag()=input@@name=email', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                if not self.args.email:
                    self.logit(None, 'email can not be empty. [ERROR]') # noqa
                    return False
                else:
                    s_email = self.args.email
                tab.actions.move_to(ele_input).click().type(s_email)
                self.update_create(self.IDX_C_EMAIL, s_email)
                tab.wait(1)

            # Date of birth
            n_year = random.randint(1985, 2005)
            n_month = random.randint(1, 12)
            n_day = random.randint(1, 26)
            select_birth('SELECTOR_1', n_month)
            select_birth('SELECTOR_2', n_day)
            select_birth('SELECTOR_3', n_year)
            s_birth = f'{n_year}-{n_month}-{n_day}'
            self.logit(None, f's_birth: {s_birth}')
            self.update_create(self.IDX_C_BIRTHDAY, s_birth)

            # Next
            ele_btn = tab.ele('@@tag()=button@@data-testid=ocfSignupNextLink', timeout=1) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.enabled(timeout=3):
                    ele_btn.click(by_js=True)
                    tab.wait(1)
                    return True

            self.browser.wait(1)

        self.logit(None, 'Fail to create_account_input ...') # noqa
        return False

    def set_password(self, max_wait_sec=60):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            # Password
            ele_input = tab.ele('@@tag()=input@@name=password', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                self.s_pwd = generate_password(20)
                self.update_create(self.IDX_C_PWD, self.s_pwd)
                self.logit(None, f's_pwd: {self.s_pwd}')
                tab.actions.move_to(ele_input).click().type(self.s_pwd)
                tab.wait(1)

                ele_div = tab.ele('@@tag()=div@@class=css-175oi2r r-b9tw7p', timeout=2) # noqa
                if not isinstance(ele_div, NoneElement):
                    ele_btn = ele_div.ele('@@tag()=button', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        btn_text = ele_btn.text
                        self.logit(None, f'Button text: {btn_text}')
                        ele_btn.wait.enabled(timeout=10)

                        if ele_btn.wait.clickable(timeout=10) is not False:
                            ele_btn.click(by_js=True)

                        tab.wait(3)
                        return True
                else:
                    self.logit(None, 'Password input element not found.')
            self.browser.wait(1)
        self.logit(None, 'Fail to input password.')
        return False

    def set_profile(self, max_wait_sec=10):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            # Pick a profile picture
            ele_btn = tab.ele('@@tag()=div@@class=css-175oi2r r-b9tw7p', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text
                self.logit(None, f'Button text: {btn_text}')
                if ele_btn.wait.clickable(timeout=2) is not False:
                    ele_btn.click()
                tab.wait(3)
                return True
            self.browser.wait(1)
        self.logit(None, 'Fail to set profile.')
        return False

    def set_username(self, max_wait_sec=10):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_input = tab.ele('@@tag()=input@@name=username', timeout=2) # noqa
            if not isinstance(ele_input, NoneElement):
                s_username = ele_input.value
                self.logit(None, f'username: {s_username}')
                self.update_create(self.IDX_C_USERNAME, s_username)

                ele_btn = tab.ele('@@tag()=button@@data-testid=ocfEnterUsernameSkipButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    btn_text = ele_btn.text
                    self.logit(None, f'set_username Button text: {btn_text}')
                    if ele_btn.wait.clickable(timeout=2) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(8)
                    return True
            self.browser.wait(1)
        self.logit(None, 'Fail to set profile.')
        return False

    def set_interest(self, max_wait_sec=6):
        # What do you want to see on X?
        # Select at least 1 interest to personalize your X experience. It will be visible on your profile.
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_items = tab.eles('@@tag()=li@@role=listitem@@id:verticalGridItem', timeout=2) # noqa
            if not ele_items:
                continue
            n_to_select = random.randint(2, 5)
            self.logit(None, f'Select {n_to_select} interest from {len(ele_items)}')
            for i in range(0, n_to_select):
                ele_item = random.choice(ele_items)
                tab.actions.move_to(ele_item)
                # if ele_item.wait.clickable(timeout=3) is not False:
                #     ele_item.click(by_js=True)

                ele_item.wait.clickable(timeout=3)
                # ele_item.click(by_js=True)
                ele_item.click()

                self.logit(None, 'select a interest')
                tab.wait(2)
                if ele_item in ele_items:
                    ele_items.remove(ele_item)

            ele_btn = tab.ele('x://*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div/div/button', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text
                self.logit(None, f'set_interest Button text: {btn_text}')
                if ele_btn.wait.clickable(timeout=3) is not False:
                    ele_btn.click()
                tab.wait(8)
                return True
        self.logit(None, 'Fail to set interest ...') # noqa
        return False

    def follow_some_accounts(self, max_wait_sec=120):
        # Don’t miss out
        # When you follow someone, you’ll see their posts in your Timeline. You’ll also get more relevant recommendations.
        # Follow 1 or more accounts
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_items = tab.eles('@@tag()=div@@data-testid=cellInnerDiv@@text():Click', timeout=2) # noqa
            if not ele_items:
                continue
            n_to_follow = random.randint(3, 6)
            self.logit(None, f'Follow {n_to_follow} accounts from {len(ele_items)}')
            for i in range(0, n_to_follow):
                ele_item = random.choice(ele_items)
                tab.actions.move_to(ele_item)
                if ele_item.wait.clickable(timeout=30) is not False:
                    # ele_item.click(by_js=True)
                    ele_item.click()
                tab.wait(2)
                if ele_item in ele_items:
                    ele_items.remove(ele_item)

            ele_btn = tab.ele('x://*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div/div/div/button', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text
                self.logit(None, f'follow_some_accounts Button text: {btn_text}')
                if ele_btn.wait.clickable(timeout=30) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(8)
                return True
        self.logit(None, 'Fail to set interest ...') # noqa
        return False

    def popup_password_window(self, max_wait_sec=5):
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            # Password
            ele_input = tab.ele('@@tag()=input@@name=password', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit(None, 'Password window is loaded')
                return True

            self.browser.wait(1)
            self.logit(None, f'Wait to load password window ... {i}/{max_wait_sec}') # noqa

        self.logit(None, 'No password window')
        return False

    def enter_password(self, max_wait_sec=5):
        """
        Enter your password
        To get started, first enter your X password to confirm it’s really you.
        """
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            # Password
            ele_input = tab.ele('@@tag()=input@@name=password', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit(None, f's_pwd: {self.s_pwd}')
                tab.actions.move_to(ele_input).click().type(self.s_pwd)
                tab.wait(2)

                ele_btn = tab.ele('@@tag()=button@@data-testid=LoginForm_Login_Button', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    btn_text = ele_btn.text
                    self.logit(None, f'Button text: {btn_text}')
                    ele_btn.wait.enabled(timeout=10)
                    if ele_btn.wait.clickable(timeout=10) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(5)
                    return True
                else:
                    self.logit(None, 'Confirm button is not found.')
            self.browser.wait(1)
        self.logit(None, 'Fail to enter password.')
        return False

    def enter_confirmation_code(self, max_wait_sec=60):
        """
        Enter the confirmation code
        Follow the instructions on the authentication app to link your X account. Once the authentication app generates a confirmation code, enter it here. 
        """
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_input = tab.ele('@@tag()=input@@data-testid=ocfEnterTextTextInput', timeout=1) # noqa
            if not isinstance(ele_input, NoneElement):
                s_2fa_show = pyotp.TOTP(self.qr_code).now()
                self.logit(None, f's_2fa_show: {s_2fa_show}')
                ele_input.input(s_2fa_show)
                tab.wait(1)

                ele_btn = tab.ele('@@tag()=button@@data-testid=ocfEnterTextNextButton', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    btn_text = ele_btn.text
                    self.logit(None, f'Button text: {btn_text}')
                    ele_btn.wait.enabled(timeout=30)
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(5)
                    return True
                else:
                    self.logit(None, 'Confirm button is not found.')
            self.browser.wait(1)
        self.logit(None, 'Fail to enter password.')
        return False

    def save_backup_code(self, max_wait_sec=60):
        """
        Save this single-use backup code in a safe place.
        """
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab

            ele_info = tab.ele('@@tag()=span@@text():Save this single-use backup code in a safe place', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text.replace('\n', ' ')
                self.logit(None, f'backup code: {s_info}')
                self.backup_code = s_info.split(' ')[29]
                self.update_create(self.IDX_C_BACKUPCODE, self.backup_code)


                ele_btn = tab.ele('@@tag()=button@@data-testid=OCF_CallToAction_Button', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    btn_text = ele_btn.text
                    self.logit(None, f'Button text: {btn_text}')
                    ele_btn.wait.enabled(timeout=30)
                    if ele_btn.wait.clickable(timeout=30) is not False:
                        ele_btn.click(by_js=True)
                    tab.wait(8)
                    return True
                else:
                    self.logit(None, 'Done button is not found.')
            self.browser.wait(1)
        self.logit(None, 'Fail to save backup code.')
        return False

    def set_confirmation_code(self, max_wait_sec=120):
        # More -> Settings and privacy
        # Select at least 1 interest to personalize your X experience. It will be visible on your profile.
        i = 0
        while i < max_wait_sec:
            i += 1
            tab = self.browser.latest_tab

            # More
            ele_btn = tab.ele('@@tag()=button@@data-testid=AppTabBar_More_Menu', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=30) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Settings and privacy
            ele_btn = tab.ele('@@tag()=a@@data-testid=settings', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Security and account access
            ele_btn = tab.ele('@@tag()=a@@data-testid=accountAccessLink', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Security / Manage your account’s security
            ele_btn = tab.ele('@@tag()=a@@href:security@@data-testid=pivot', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Two-factor authentication
            ele_btn = tab.ele('@@tag()=a@@href:login_verification@@data-testid=pivot', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Authentication app
            ele_btn = tab.ele('@@tag()=div@@class:css-175oi2r r-1awozwy r-18u37iz@@text():Authentication app', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Click Authentication app checkbox')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Enter your password
            if self.popup_password_window() is True:
                self.enter_password()

            # Protect your account in just
            ele_btn = tab.ele('@@tag()=button@@data-testid=ActionListNextButton', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Link the app to your X account
            # Can’t scan the QR code?
            ele_btn = tab.ele('x://*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div[2]/div/div/button', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                btn_text = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Click Button: {btn_text}')
                if ele_btn.wait.clickable(timeout=10) is not False:
                    ele_btn.click(by_js=True)
                tab.wait(5)
            else:
                continue

            # Can’t scan the QR code?
            ele_info = tab.ele('@@tag()=h1@@text():Can’t scan the QR code', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                ele_btn = tab.ele('x://*[@id="layers"]/div[2]/div/div/div/div/div/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div/div[2]', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    self.qr_code = ele_btn.text.replace('\n', ' ')
                    self.logit(None, f'qr_code: {self.qr_code}')
                    self.update_create(self.IDX_C_VERIFYCODE, self.qr_code)

                    ele_btn = tab.ele('@@tag()=button@@data-testid=ocfShowCodeNextLink', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        btn_text = ele_btn.text.replace('\n', ' ')
                        self.logit(None, f'Click Button: {btn_text}')
                        if ele_btn.wait.clickable(timeout=10) is not False:
                            ele_btn.click(by_js=True)
                        tab.wait(3)
                else:
                    continue

            # Enter the confirmation code
            if self.enter_confirmation_code():
                # Save this single-use backup code in a safe place.
                self.save_backup_code()
                return True

        self.logit(None, 'Fail to set confirmation code ...') # noqa
        return False

    def wait_email_verification_code(self):
        i = 0
        while i < DEF_NUM_TRY:
            i += 1
            if self.register_verification_code() is True:
                self.logit(None, 'Success to get email verification code ...')
                return True

            self.browser.wait(1)
            self.logit(None, f'Wait to get email verification code ... {i}/{DEF_NUM_TRY}') # noqa

        self.logit(None, 'Fail to email verification code ...') # noqa
        return False

    def twitter_create(self):
        # self.update_num_visit()
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('xutils_login', f'try_i={i}/{DEF_NUM_TRY}')

            tab = self.browser.latest_tab

            s_url = 'https://x.com'
            tab.get(s_url, timeout=60, retry=1)

            self.browser.wait(3)

            if self.wait_create_account_button() is False:
                continue
            if self.wait_create_account_to_x() is False:
                continue
            if self.create_account_input() is False:
                continue

            self.browser.wait(5)

            # 图形验证码
            max_wait_sec = 120
            i = 0
            while i < max_wait_sec:
                i += 1
                self.browser.wait(1)
                ele_input = tab.ele('@@tag()=h1@@id=modal-header', timeout=2)
                if not isinstance(ele_input, NoneElement):
                    s_info = ele_input.text
                    self.logit(None, f'{s_info}')
                    if s_info in ['xxx', 'We sent you a code']:
                        break
                self.logit(None, f'Wait YesCaptcha to verify ... {i}/{max_wait_sec}') # noqa

            if self.wait_email_verification_code() is False:
                continue
            if self.set_password() is False:
                continue
            # Verify you are human by completing the action below

            # Pick a profile picture
            self.set_profile()

            # Get username
            self.set_username()
            self.set_interest()
            self.follow_some_accounts()

            n_like = random.randint(3, 6)
            self.logit(None, f'Like {n_like} posts.')
            for i in range(0, n_like):
                self.x_like()

            # set 2fa
            self.set_confirmation_code()

            # Your account has been locked
            if self.x_locked():
                self.verify_email()
                self.enter_verification_code()
                # 图形验证码
                self.x_unlocked()

            s_msg = 'Press any key to continue ! ⚠️' # noqa
            input(s_msg)
            # pdb.set_trace()
            return True

        return False


if __name__ == '__main__':
    """
    Twitter utils
    """
    pass
