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
from datetime import timedelta

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import format_ts
from fun_utils import get_index_from_header

from fun_okx import OkxUtils
from fun_x import XUtils
from fun_dp import DpUtils

from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_DATA_STATUS

from conf import DEF_WINDOW_LOCATION
from conf import DEF_WINDOW_SIZE

from conf import DEF_HEADER_ACCOUNT

# from conf import TZ_OFFSET
from conf import DEL_PROFILE_DIR

from conf import FILENAME_LOG
from conf import logger

# gm Check-in use UTC Time
TZ_OFFSET = 0

DEF_INSUFFICIENT_ETH = 'Insufficient ETH balance'
DEF_SUCCESS = 'Success'
DEF_FAIL = 'Fail'

"""
2025.05.17
"""


class ClsLayer3():
    def __init__(self) -> None:
        self.args = None

        self.file_status = None

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}
        self.dic_account = {}

        self.inst_okx = OkxUtils()
        self.inst_dp = DpUtils()
        self.inst_x = XUtils()

        self.inst_dp.plugin_yescapcha = True
        self.inst_dp.plugin_capmonster = True
        self.inst_dp.plugin_okx = True

        # output
        self.DEF_HEADER_STATUS = 'account,arb_eth,arb_usd,task_status,complete_date,gm_value,gm_date,update_time' # noqa
        self.IDX_BALANCE_ETH = 1
        self.IDX_BALANCE_USD = 2
        self.IDX_MINT_STATUS = 3
        self.IDX_MINT_DATE = 4
        self.IDX_GM_VALUE = 5
        self.IDX_GM_DATE = 6
        self.IDX_UPDATE = 7
        self.FIELD_NUM = self.IDX_UPDATE + 1

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        pass
        # self.status_save()

    def get_status_file(self):
        if not self.args.url:
            logger.info('Invalid self.args.url')
            sys.exit(-1)
        filename = self.args.url.split('/')[-1]
        self.file_status = f'{DEF_PATH_DATA_STATUS}/layer3/{filename}.csv'

    def status_load(self):
        if self.file_status is None:
            self.get_status_file()

        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=self.DEF_HEADER_STATUS
        )

    def status_save(self):
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

    def get_status_by_idx(self, idx_status, s_profile=None):
        if s_profile is None:
            s_profile = self.args.s_profile

        s_val = ''
        lst_pre = self.dic_status.get(s_profile, [])
        if len(lst_pre) == self.FIELD_NUM:
            try:
                # s_val = int(lst_pre[idx_status])
                s_val = lst_pre[idx_status]
            except: # noqa
                pass

        return s_val

    def update_date(self, idx_status, update_ts=None):
        if not update_ts:
            update_ts = time.time()
        update_time = format_ts(update_ts, 2, TZ_OFFSET)

        claim_date = update_time[:10]

        self.update_status(idx_status, claim_date)

    def set_lang(self):
        for i in range(1, DEF_NUM_TRY+1):
            self.logit('set_lang', f'trying ... {i}/{DEF_NUM_TRY}')
            tab = self.browser.latest_tab
            ele_btn = tab.ele('.nav-item nav-language other-wrap', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Click language setting button ...') # noqa
                if ele_btn.states.is_clickable:
                    ele_btn.click()
                    tab.wait(2)
                else:
                    self.logit(None, 'language setting button is not clickable ...') # noqa

            ele_blk = tab.ele('.oxnv-dialog-container', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                ele_btn = ele_blk.ele('@@tag()=a@@id=language_zh_CN', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    if 'item selected' == ele_btn.attr('class'):
                        ele_close = tab.ele('#okdDialogCloseBtn', timeout=1)
                        if not isinstance(ele_close, NoneElement):
                            ele_close.click(by_js=True)
                    else:
                        self.logit(None, 'Click language setting button ...') # noqa
                        ele_btn.click(by_js=True)
                        tab.wait(1)
                    return True
            self.logit(None, 'Language elements not found [ERROR]') # noqa
            tab.wait(1)

            if i > DEF_NUM_TRY/2:
                tab.set.window.max()
                self.logit(None, 'set.window.max') # noqa

        self.logit(None, 'Fail to set language [ERROR]') # noqa
        return False

    def connect_wallet(self):
        n_tab = self.browser.tabs_count

        for i in range(1, DEF_NUM_TRY+1):
            tab = self.browser.latest_tab
            tab.wait.doc_loaded()
            tab.wait(3)

            ele_blk = tab.ele('@@tag()=div@@class:flex shrink-0 items-center gap-3', timeout=2) # noqa
            if not isinstance(ele_blk, NoneElement):
                ele_btn = ele_blk.ele('@@tag()=button', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    s_info = ele_btn.text
                    self.logit(None, f'Connect Wallet Button Text: {s_info}') # noqa
                    if s_info == 'Sign in':
                        try:
                            ele_btn.wait.enabled(timeout=5)
                            if ele_btn.wait.clickable(timeout=5):
                                ele_btn.click(by_js=True)
                                tab.wait(1)
                        except Exception as e: # noqa
                            # self.logit('connect_wallet', f'Sign in Exception: {e}')
                            continue

                        ele_btn = tab.ele('@@tag()=span@@text()=OKX Wallet', timeout=2)
                        if not isinstance(ele_btn, NoneElement):
                            if ele_btn.wait.clickable(timeout=5):
                                ele_btn.click(by_js=True)

                        if self.inst_okx.wait_popup(n_tab+1, 10):
                            tab.wait(2)
                            self.inst_okx.okx_connect()

                        if self.inst_okx.wait_popup(n_tab+1, 10):
                            tab.wait(2)
                            try:
                                if self.inst_okx.okx_confirm():
                                    self.logit(None, 'Signature request Confirm')
                                    self.inst_okx.wait_popup(n_tab, 15)
                                    tab.wait(3)
                            except Exception as e: # noqa
                                self.logit('connect_wallet', f'[okx_confirm] Error: {e}') # noqa
                                continue

                        # Connect Wallet 弹窗，卡住，刷新页面
                        lst_path = [
                            '@@tag()=div@@class:text-content-primary@@text()=Connect Wallet',
                        ]
                        ele_btn = self.inst_dp.get_ele_btn(tab, lst_path)
                        if ele_btn is not NoneElement:
                            self.logit(None, 'Connect Wallet Stuck, Refresh Page')
                            tab.refresh()
                            tab.wait(3)
                            continue
                    else:
                        self.logit(None, 'Log in success')
                        return True

            # Create a new account
            lst_path = [
                '@@tag()=button@@text()=Create a new account',  # pc
            ]
            ele_btn = self.inst_dp.get_ele_btn(self.browser.latest_tab, lst_path) # noqa
            if ele_btn is not NoneElement:
                self.logit(None, 'Try to Create a new account ...')
                if ele_btn.wait.clickable(timeout=3):
                    ele_btn.click(by_js=True)
                    self.logit(None, 'Create a new account [Success]')
                tab.wait(6)

        return False

    def okx_verify_click(self):
        # geetest_text_tips
        tab = self.browser.latest_tab
        ele_btn = tab.ele('@@tag()=div@@class:geetest_text_tips', timeout=1) # noqa
        if not isinstance(ele_btn, NoneElement):
            s_text = ele_btn.text
            self.logit(None, f'Verify Manual: {s_text}')
            return True
        return False

    def get_task_result(self):
        tab = self.browser.latest_tab
        # tab.get(self.args.url)
        tab.refresh()

        tab.wait.doc_loaded()
        tab.wait(3)

        # Connect wallet
        if self.connect_wallet() is False:
            return 'Fail_to_sign_in'

        s_text = self.wait_continue(wait_sec=10)
        if s_text == 'Not enough ETH':
            return s_text

        # Activation Completed
        ele_info = tab.ele('@@tag()=h1@@class:text-2xl@@text()=Activation Completed', timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            # self.logit(None, f'Task status: {s_text}')
            self.is_update = True
            return s_text

        # Claim Rewards
        if self.is_claim_rewards():
            ele_blk = tab.ele('@@tag()=div@@style:padding-bottom', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                tab.wait(2)
                ele_btn = ele_blk.ele('@@tag()=button@@class:relative', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    self.logit(None, f'Claim Rewards Button: {ele_btn.text}')
                    if ele_btn.text == 'Switch to Arbitrum One':
                        if ele_btn.wait.clickable(timeout=2):
                            ele_btn.click(by_js=True)
                            tab.wait(2)
                            return False
                    elif ele_btn.text == 'Mint CUBE to claim':
                        if ele_btn.wait.clickable(timeout=2):
                            n_tab = self.browser.tabs_count
                            ele_btn.click(by_js=True)
                            tab.wait(2)
                            if self.inst_okx.wait_popup(n_tab+1, 10) is False:
                                return ele_btn.text
                            if self.inst_okx.okx_confirm():
                                self.logit(None, 'transaction Confirm')
                                self.inst_okx.wait_popup(n_tab, 15)
                                self.is_update = True
                                tab.wait(3)
                                return ele_btn.text
                    else:
                        # ele_btn.text: 'Not enough ETH'
                        return ele_btn.text

        return None

    def task_x(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@class:bg-transparent transition-all', timeout=2)
        if not isinstance(ele_blk, NoneElement):
            ele_btn = ele_blk.ele('@@tag()=button@@class:hover:bg-button-secondaryHover@@text()=Open X', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.clickable(timeout=3):
                    ele_btn.click(by_js=True)
                    tab.wait(3)

                    if not self.args.no_x:
                        x_status = self.inst_x.dic_status[self.args.s_profile][self.inst_x.IDX_STATUS] # noqa
                        if x_status == self.inst_x.DEF_STATUS_OK:
                            tab = self.browser.latest_tab
                            if tab.url.find('x.com/intent/follow') >= 0:
                                name = tab.url.split('=')[-1]
                                self.logit(None, f'Try to Follow x: {name}')
                                if self.inst_x.x_follow(name):
                                    tab.wait(1)
                            elif tab.url.find('x.com/intent/retweet') >= 0:
                                self.logit(None, f'Try to retweet x: {tab.url}')
                                if self.inst_x.x_retweet():
                                    tab.wait(1)

                    self.browser.latest_tab.close()
                    return True
        return False

    def wait_continue(self, wait_sec=10):
        i = 0
        while i < wait_sec:
            i += 1
            tab = self.browser.latest_tab
            ele_blk = tab.ele('@@tag()=div@@style:padding-bottom', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                lst_path = [
                    '@@tag()=button@@text()=Continue',
                    '@@tag()=button@@text()=Mint CUBE to claim',
                    '@@tag()=button@@text()=Switch to Arbitrum One',
                    '@@tag()=button@@text()=Not enough ETH',
                    '@@tag()=button@@text()=Verify',
                ]
                ele_btn = self.inst_dp.get_ele_btn(ele_blk, lst_path)
                if ele_btn is not NoneElement:
                    return ele_btn.text
            self.logit(None, f'Wait for continue button ... {i}/{wait_sec}')
            self.browser.wait(1)
        return None

    def click_continue(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@style:padding-bottom', timeout=2)
        if not isinstance(ele_blk, NoneElement):
            ele_btn = ele_blk.ele('@@tag()=button@@text()=Continue', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.clickable(timeout=2):
                    ele_btn.click(by_js=True)
            tab.wait(2)

    def task_quiz(self, lst_answer=None):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@class:bg-transparent transition-all', timeout=2)
        if not isinstance(ele_blk, NoneElement):

            self.click_continue()

            # 4 Questions
            if lst_answer is None:
                lst_answer = ['D', 'B', 'C', 'D']
            # 将 A B C D 转换为 a1 a2 a3 a4
            lst_answer_ids = []
            for ans in lst_answer:
                # 将 A->a1, B->a2, C->a3, D->a4
                idx = ord(ans) - ord('A') + 1
                lst_answer_ids.append(f'a{idx}')

            for i in range(len(lst_answer)):
                ele_info = ele_blk.ele('.body text-sm text-content-secondary', timeout=2)
                if not isinstance(ele_info, NoneElement):
                    s_info = ele_info.text
                    self.logit(None, f'Question info: {s_info}')
                    # Question 1 of 4
                    # 提取 1 of 4 中的 1 ，去掉 Question ，转为数字
                    idx = int(s_info.split('of')[0].strip().replace('Question', ''))
                    idx -= 1
                    self.logit(None, f'Question index: {idx}')
                    if idx != i:
                        self.logit(None, f'Question index is not match, skip [i={i}]')
                        continue

                # ele_btn = ele_blk.ele(f'@@tag()=button@@id={lst_answer_ids[i]}', timeout=2) # noqa
                ele_btn = ele_blk.ele(f'@@tag()=button@@text():{lst_answer[i]})', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=2):
                        ele_btn.click(by_js=True)
                    tab.wait(2)
                    self.click_continue()
                    tab.wait(2)

            return True
        return False

    def get_step_num(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('.absolute right-5 top-5 z-5 flex items-center gap-2', timeout=2)
        if not isinstance(ele_blk, NoneElement):
            ele_info = ele_blk.ele('@@tag()=button@@aria-haspopup=dialog', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text
                # Step 7 of 8
                # 提取 7 of 8 中的 7 ，去掉 Step ，转为数字
                n_step = int(s_info.split('of')[0].strip().replace('Step', ''))
                return n_step
        return -1

    def is_claim_rewards(self):
        tab = self.browser.latest_tab
        ele_info = tab.ele('.text-center text-2xl font-semibold leading-tight text-content-primary', timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit(None, f'Task info: {s_text}')
            if s_text == 'Claim Rewards':
                return True
        return False

    def complete_tasks_week1(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week1', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共8个任务
            task_num = 8

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 4):
                    # 任务 1-4 直接 Continue
                    if self.click_continue():
                        continue
                elif (n_step >= 5) and (n_step <= 7):
                    # 任务 5-7
                    self.task_x()
                    self.click_continue()
                elif n_step == 8:
                    # 第8个 任务 quiz
                    self.task_quiz()
                    break
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def open_bridge(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@class:bg-transparent transition-all', timeout=2)
        if not isinstance(ele_blk, NoneElement):
            ele_btn = ele_blk.ele('@@tag()=button@@class:relative', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                s_text = ele_btn.text
                self.logit(None, f'Jump to new tab: {s_text}')
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait.doc_loaded()
                tab.wait(6)
                return True
        return False

    def bridge_to_rari_mainnet(self):
        n_tab = self.browser.tabs_count
        tab = self.browser.latest_tab

        for i in range(1, DEF_NUM_TRY+1):

            # Agree to Terms and Continue
            ele_btn = tab.ele('@@tag()=span@@class=truncate', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                s_text = ele_btn.text
                self.logit(None, f'Agree button: {s_text}')
                if s_text == 'Agree to Terms and Continue':
                    ele_btn.wait.clickable(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(1)

            # Connect Wallet
            ele_btn = tab.ele('@@tag()=button@@text()=Connect Wallet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

                ele_btn = tab.ele('@@tag()=div@@text()=OKX Wallet', timeout=2)
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=5):
                        ele_btn.click()

                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    self.inst_okx.okx_connect()
                    self.inst_okx.wait_popup(n_tab, 5)

            # Switch to Transaction History Tab
            # ele_btn = tab.ele('@@tag()=button@@aria-label=Switch to Transaction History Tab', timeout=2) # noqa
            # if not isinstance(ele_btn, NoneElement):
            #     ele_btn.wait.clickable(timeout=3)
            #     ele_btn.click(by_js=True)
            #     tab.wait(1)

            # s_path = 'x://*[@id="headlessui-tabs-panel-:r4:"]/div/div[1]/div[1]/div/div[2]/div[2]/div/div/div/div/span[2]'
            # f_eth_amount = self.get_eth_amount(s_path)
            # # Ammount
            # s_path = 'x://*[@id="headlessui-tabs-panel-:r5:"]/div/div[1]/div[1]/div/div[2]/div[2]/div/div/input'
            # ele_input = tab.ele(s_path, timeout=2)
            # if not isinstance(ele_input, NoneElement):
            #     ele_input.wait.clickable(timeout=3)

            #     # 生成一个0.0004到0.0006之间的随机数，保留4位小数   
            #     f_amount = round(random.uniform(0.00791, 0.00822), 5)
            #     if f_amount >= f_eth_amount:
            #         self.logit(None, f'Insufficient ETH balance: {f_eth_amount}')
            #         self.update_status(self.IDX_MINT_STATUS, 'Insufficient ETH balance')
            #         self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
            #         return DEF_INSUFFICIENT_ETH

            #     ele_input.click.multi(times=2)
            #     tab.wait(1)
            #     ele_input.clear(by_js=True)
            #     tab.wait(1)
            #     tab.actions.move_to(ele_input).click().type(f_amount) # noqa
            #     tab.wait(1)
            #     if ele_input.value != str(f_amount):
            #         continue


            # Move funds to RARI Mainnet
            ele_btn = tab.ele('@@tag()=button@@text()=Move funds to RARI Mainnet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    try:
                        if self.inst_okx.okx_confirm():
                            self.logit(None, 'Bridge Confirm')
                            self.inst_okx.wait_popup(n_tab, 15)
                            tab.wait(3)
                    except Exception as e: # noqa
                        self.logit('connect_wallet', f'okx_confirm Exception: {e}') # noqa
                        continue

            # 是否出现 You have 1 pending transaction
            ele_info = tab.ele('@@tag()=span@@text():You have', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_text = ele_info.text
                self.logit(None, f'Transaction result: {s_text}')
                self.update_status(self.IDX_MINT_STATUS, s_text)
                self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                return True

            # 如果出现 Internal Server Error ，则刷新页面
            ele_info = tab.ele('@@tag()=h2@@text():Internal Server Error', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_text = ele_info.text
                self.logit(None, f'Error: {s_text}')
                tab.refresh()
                tab.wait.doc_loaded()
                tab.wait(2)
                continue

        return False

    def verify_bridge(self):
        # 循环等待，最多等5分钟
        n_max_sec = 300
        ts_start = time.time()
        while (time.time() - ts_start) < n_max_sec:
            tab = self.browser.latest_tab
            ele_blk = tab.ele('@@style:padding-bottom', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                ele_btn = ele_blk.ele('@@tag()=button@@text()=Verify', timeout=2) # noqa
                if not isinstance(ele_btn, NoneElement):
                    if ele_btn.wait.clickable(timeout=2):
                        ele_btn.click(by_js=True)
                        self.logit(None, 'Click Verify Button')
                    else:
                        self.logit(None, 'Verify Button is not clickable')
                tab.wait(2)

            n_step = self.get_step_num()
            if n_step == 4:
                self.logit(None, 'Verify bridge success')
                self.update_status(self.IDX_MINT_STATUS, 'Verify bridge success')
                self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                return True

            ele_info = tab.ele('@@tag()=p@@text():No matching transactions found', timeout=2)
            if not isinstance(ele_info, NoneElement):
                s_text = ele_info.text
                self.logit(None, f'Error: {s_text}')
                tab.wait(5)
                continue

            n_elapsed = int(time.time() - ts_start)
            self.logit(None, f'sleep 10 seconds, elapsed seconds: {n_elapsed}/{n_max_sec}')
            time.sleep(10)

        return False

    def complete_tasks_week2_2(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week1', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共4个任务
            task_num = 4

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif n_step == 3:
                    # 任务 3 Bridge to RARI Mainnet
                    # Verify
                    # 如果 mint_status 为 You have 1 pending transaction ，则验证
                    mint_status = self.get_status_by_idx(self.IDX_MINT_STATUS)
                    if mint_status == 'You have 1 pending transaction':
                        self.verify_bridge()
                        continue
                    self.open_bridge()
                    if self.bridge_to_rari_mainnet():
                        self.browser.latest_tab.close()
                        continue
                elif n_step == 4:
                    # 第4个 任务 continue
                    if self.click_continue():
                        break
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def get_glp_amount(self):
        tab = self.browser.latest_tab
        tab.wait(10)
        s_path = 'x://*[@id="root"]/div/div[1]/div/div/div[2]/div[1]/div[2]/form/div[2]/div[2]/div[2]/div/div[3]/div[2]/span[2]'
        ele_info = tab.ele(s_path, timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit('get_glp_amount', f'GLP amount: {s_text}')
            try:
                f_amount = float(s_text)
                return f_amount
            except Exception as e: # noqa
                self.logit('get_glp_amount', f'Exception: {e}')
                return 0
        return 0

    def get_eth_amount(self, s_path):
        tab = self.browser.latest_tab
        tab.wait(10)
        # s_path = 'x://*[@id="root"]/div/div[1]/div/div/div[2]/div[1]/div[2]/form/div[2]/div[1]/div/div[3]/div[2]/span[2]'
        ele_info = tab.ele(s_path, timeout=2)
        if not isinstance(ele_info, NoneElement):
            s_text = ele_info.text
            self.logit('get_eth_amount', f'ETH amount: {s_text}')
            try:
                f_amount = float(s_text)
                return f_amount
            except Exception as e: # noqa
                self.logit('get_eth_amount', f'Exception: {e}')
                return 0
        return 0

    def acquire_gmx(self):
        n_tab = self.browser.tabs_count
        tab = self.browser.latest_tab

        for i in range(1, DEF_NUM_TRY+1):
            self.logit('acquire_gmx', f'trying ... {i}/{DEF_NUM_TRY}')

            # Connect Wallet
            lst_path = [
                'x://*[@id="root"]/div/div[1]/div/header/div/div/div[2]/div/button',
                'x://*[@id="root"]/div/div[1]/div/header/div/div[2]/div/button'
            ]
            ele_btn = tab.ele('x://*[@id="root"]/div/div[1]/div/header/div/div/div[2]/div/button', timeout=2) # noqa
            ele_btn = self.inst_dp.get_ele_btn(self.browser.latest_tab, lst_path) # noqa
            if ele_btn is not NoneElement:
                s_text = ele_btn.text
                self.logit(None, f'Click Connect Wallet Button: {s_text}') # noqa
                
                if s_text in ['Connect', 'Connect Wallet']:
                    ele_btn.wait.clickable(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(3)

                    ele_btn = tab.ele('@@tag()=div@@text()=OKX Wallet', timeout=2)
                    if not isinstance(ele_btn, NoneElement):
                        if ele_btn.wait.clickable(timeout=5):
                            ele_btn.click()

                            if self.inst_okx.wait_popup(n_tab+1, 10):
                                tab.wait(2)
                                self.inst_okx.okx_connect()
                                self.inst_okx.wait_popup(n_tab, 5)
                    elif self.inst_okx.wait_popup(n_tab+1, 3):
                        tab.wait(2)
                        self.inst_okx.okx_connect()
                        self.inst_okx.wait_popup(n_tab, 3)
                continue

            # Buy GLP
            ele_btn = tab.ele('@@tag()=a@@text()=Buy GLP', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(3)

                # if self.inst_okx.wait_popup(n_tab+1, 10):
                #     tab.wait(2)
                #     try:
                #         if self.inst_okx.okx_confirm():
                #             self.logit(None, 'Bridge Confirm')
                #             self.inst_okx.wait_popup(n_tab, 15)
                #             tab.wait(3)
                #     except Exception as e: # noqa
                #         self.logit('connect_wallet', f'okx_confirm Exception: {e}') # noqa
                #         continue

            f_glp_amount = self.get_glp_amount()
            if f_glp_amount > 0:
                self.logit(None, f'[Success] GLP amount: {f_glp_amount}')
                return DEF_SUCCESS

            s_path = 'x://*[@id="root"]/div/div[1]/div/div/div[2]/div[1]/div[2]/form/div[2]/div[1]/div/div[3]/div[2]/span[2]'
            f_eth_amount = self.get_eth_amount(s_path)

            ele_blk = tab.ele('x://*[@id="root"]/div/div[1]/div/div/div[2]/div[1]/div[2]/form/div[2]/div[1]/div', timeout=2)
            if not isinstance(ele_blk, NoneElement):
                ele_input = ele_blk.ele('@@tag()=input@@inputmode=decimal', timeout=2)
                if not isinstance(ele_input, NoneElement):
                    # 生成一个0.0004到0.0006之间的随机数，保留4位小数
                    f_amount = round(random.uniform(0.0004, 0.0006), 6)
                    if f_amount >= f_eth_amount:
                        self.logit(None, f'Insufficient ETH balance: {f_eth_amount}')
                        self.update_status(self.IDX_MINT_STATUS, 'Insufficient ETH balance')
                        self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                        return DEF_INSUFFICIENT_ETH

                    tab.actions.move_to(ele_input).click().type(f_amount) # noqa
                    tab.wait(2)
                    if ele_input.value == str(f_amount):
                        self.logit(None, f'Input amount: {f_amount}')
                        ele_btn = tab.ele('@@tag()=button@@type=submit', timeout=2)
                        if not isinstance(ele_btn, NoneElement):
                            s_text = ele_btn.text
                            self.logit(None, f'Button text: {s_text}')
                            if s_text == 'Insufficient ETH balance':
                                self.update_status(self.IDX_MINT_STATUS, 'Insufficient ETH balance')
                                self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                                return DEF_INSUFFICIENT_ETH
                            else:
                                if ele_btn.wait.clickable(timeout=3) is not False:
                                    ele_btn.click(by_js=True)
                                    tab.wait(1)

                                    if self.inst_okx.wait_popup(n_tab+1, 10):
                                        tab.wait(2)
                                        try:
                                            if self.inst_okx.okx_confirm():
                                                self.logit(None, 'Buy GLP Confirm')
                                                self.inst_okx.wait_popup(n_tab, 15)
                                                tab.wait(3)
                                                return DEF_SUCCESS
                                        except Exception as e: # noqa
                                            self.logit('connect_wallet', f'okx_confirm Exception: {e}') # noqa
                                            continue

        return DEF_FAIL

    def complete_tasks_week2_1(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return DEF_SUCCESS

            self.logit('complete_tasks_week1', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共4个任务
            task_num = 4

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return DEF_FAIL
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif n_step == 3:
                    # 任务 3 答题
                    self.task_quiz(lst_answer=['C', 'C', 'D'])
                elif n_step == 4:
                    # 第4个 任务 Acquire GLP or GLV on GMX
                    # Verify
                    if self.verify_bridge():
                        self.browser.wait(3)
                        is_failed = self.inst_dp.get_tag_info('p', 'No matching transactions found')
                        if is_failed is False:
                            break
                    self.open_bridge()
                    ret = self.acquire_gmx()
                    self.browser.latest_tab.close()
                    if ret == DEF_INSUFFICIENT_ETH:
                        return DEF_INSUFFICIENT_ETH
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return DEF_SUCCESS

        self.logit(None, 'Task elements not found [ERROR]')
        return DEF_FAIL

    def gm_checkin(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('.flex w-full flex-col gap-1', timeout=1) # noqa
        if not isinstance(ele_blk, NoneElement):
            ele_btn = ele_blk.ele('@@tag()=button@@class:relative', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                self.update_status(self.IDX_GM_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                tab.wait(2)
                return True
            ele_info = ele_blk.ele('@@tag()=div@@class=flex w-full items-center', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text
                self.logit(None, f'GM info: {s_info}')
                self.update_status(self.IDX_GM_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                return True
        return False

    def gm_value(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('.flex w-full flex-col gap-1', timeout=1) # noqa
        if not isinstance(ele_blk, NoneElement):
            ele_info = ele_blk.ele('@@tag()=div@@class=flex items-center gap-2', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text
                self.logit(None, f'GM value: {s_info}')
                self.update_status(self.IDX_GM_VALUE, s_info)
                return True
        return False

    def create_glyph_account(self):
        n_tab = self.browser.tabs_count

        n_try = 6
        tab = self.browser.latest_tab
        tab.wait.doc_loaded()
        tab.wait(3)

        for i in range(1, n_try+1):
            self.logit('create_glyph_account', f'trying ... {i}/{n_try}')

            tab = self.browser.latest_tab
            ele_btn = tab.ele('@@tag()=span@@text()=Sign in with Glyph', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(2)

            ele_btn = tab.ele('@@tag()=div@@text()=Continue with a wallet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(2)
            # OKX Wallet
            ele_btn = tab.ele('@@tag()=span@@text()=OKX Wallet', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.clickable(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(2)
                if self.inst_okx.wait_popup(n_tab+1, 10):
                    tab.wait(2)
                    self.inst_okx.okx_connect()
                    tab.wait(3)
                    self.inst_okx.okx_confirm()
                    self.inst_okx.wait_popup(n_tab, 5)
                    return True

            if self.inst_dp.get_tag_info('p', 'You did not pass CAPTCHA'):
                self.logit(None, 'Something went wrong')

            tab.wait(3)

        return False

    def click_verify(self):
        tab = self.browser.latest_tab
        ele_blk = tab.ele('@@style:padding-bottom', timeout=2)
        if not isinstance(ele_blk, NoneElement):
            ele_btn = ele_blk.ele('@@tag()=button@@text()=Verify', timeout=2) # noqa
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.wait.clickable(timeout=2):
                    ele_btn.click(by_js=True)
            tab.wait(2)

    def complete_tasks_week3_1(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week3_1', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共4个任务
            task_num = 3

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif (n_step == 3):
                    # 任务 3
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open Caldera', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        tab.wait(2)
                        self.browser.latest_tab.close()
                        self.click_continue()
                    continue
                elif (n_step == 4):
                    self.task_quiz(lst_answer=['B', 'B', 'C'])
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def complete_tasks_week4(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week4', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共4个任务
            task_num = 4

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif (n_step == 3):
                    # 任务 3
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open Glyph', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        self.create_glyph_account()
                        self.browser.latest_tab.close()
                        self.click_verify()
                    continue
                elif (n_step == 4):
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open Alpine', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        tab.wait(2)
                        self.browser.latest_tab.close()
                        tab.wait(2)
                        self.click_continue()
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def complete_tasks_week5(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week5', f'trying ... {i}/{DEF_NUM_TRY}')
            # 一共4个任务
            task_num = 3

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif n_step == 3:
                    # 第8个 任务 quiz
                    self.task_quiz(lst_answer=['C', 'B', 'D'])
                    break
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def complete_tasks_week6_1(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week6_1', f'trying ... {i}/{DEF_NUM_TRY}')
            # 任务数量
            task_num = 5

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 3):
                    # 任务 1-3 直接 Continue
                    if self.click_continue():
                        continue
                elif n_step == 4:
                    # 第8个 任务 quiz
                    self.task_quiz(lst_answer=['B', 'A', 'C'])
                elif n_step == 5:
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open Nexus', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        tab.wait(2)
                        self.browser.latest_tab.close()
                        tab.wait(2)
                        self.click_continue()
                    break
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def complete_tasks_week6_2(self):
        for i in range(1, DEF_NUM_TRY+1):
            if self.is_claim_rewards():
                return True

            self.logit('complete_tasks_week6_2', f'trying ... {i}/{DEF_NUM_TRY}')
            # 任务数量
            task_num = 5

            for j in range(1, task_num*3):
                self.logit(None, f'Doing task j={j} (Start from 1)')
                n_step = self.get_step_num()
                if n_step == -1:
                    self.logit(None, 'Step number not found')
                    if j >= 3:
                        return False
                    continue

                self.logit(None, f'Step number: {n_step}')

                if (n_step >= 1) and (n_step <= 2):
                    # 任务 1-2 直接 Continue
                    if self.click_continue():
                        continue
                elif n_step == 3:
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open X', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        tab.wait(2)
                        self.browser.latest_tab.close()
                        self.click_continue()
                    continue
                elif n_step == 4:
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele('@@tag()=button@@text()=Open Discord', timeout=2) # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.wait.clickable(timeout=3)
                        ele_btn.click(by_js=True)
                        tab.wait(2)
                        self.browser.latest_tab.close()
                        self.click_continue()
                    continue
                elif n_step == 5:
                    self.click_continue()
                    break
                else:
                    self.logit(None, f'Step number is not processable [n_step={n_step}]')
                    break

            return True

        self.logit(None, 'Task elements not found [ERROR]')
        return False

    def layer3_process(self):
        s_task_name = self.args.url.split('/')[-1]
        # open layer3 url
        # tab = self.browser.latest_tab
        # tab.get(self.args.url)
        tab = self.browser.new_tab(self.args.url)
        tab.wait.doc_loaded()
        # tab.wait(3)
        # tab.set.window.max()

        # Connect wallet
        if self.connect_wallet() is False:
            return False

        n_try = 8
        for i in range(1, n_try+1):
            self.logit('layer3_process', f'trying ... {i}/{n_try}')

            # Query Task Result
            s_status = self.get_task_result()
            self.logit(None, f'Task status: {s_status}')

            if self.args.only_gm:
                is_gm_success = self.gm_checkin()
                self.gm_value()
                if is_gm_success:
                    return True
                else:
                    continue

            if s_status in ['Activation Completed', 'Not enough ETH', DEF_INSUFFICIENT_ETH]:
                self.update_status(self.IDX_MINT_STATUS, s_status)
                self.update_status(self.IDX_MINT_DATE, format_ts(time.time(), style=1, tz_offset=TZ_OFFSET))
                return True
            elif s_status in ['Mint CUBE to claim']:
                continue
            elif s_status in ['Switch to Arbitrum One']:
                continue

            if s_task_name == 'intro-to-espresso':
                self.complete_tasks_week1()
            elif s_task_name == 'brewing-the-future-arbitrum':
                ret = self.complete_tasks_week2_1()
                if ret == DEF_INSUFFICIENT_ETH:
                    return True
            elif s_task_name == 'brewing-the-future-rari':
                self.complete_tasks_week2_2()
            elif s_task_name == 'brewing-the-future-caldera':
                self.complete_tasks_week3_1()
            elif s_task_name == 'brewing-the-future-apechain':
                self.complete_tasks_week4()
            elif s_task_name == 'brewing-the-future-molten-network':
                self.complete_tasks_week5()
            elif s_task_name == 'brewing-the-future-buildn-brew':
                self.complete_tasks_week6_1()
            elif s_task_name == 'brewing-the-future-caffeinated-creators':
                self.complete_tasks_week6_2()

        return False

    def layer3_run(self):
        self.browser = self.inst_dp.get_browser(self.args.s_profile)

        self.inst_okx.set_browser(self.browser)

        tab = self.browser.latest_tab
        if self.args.set_window_size == 'max':
            # 判断窗口是否是最大化
            if tab.rect.window_state != 'maximized':
                # 设置浏览器窗口最大化
                tab.set.window.max()
                self.logit(None, 'Set browser window to maximize')
        if DEF_WINDOW_LOCATION:
            x, y = DEF_WINDOW_LOCATION
            tab.set.window.location(x, y)
        if DEF_WINDOW_SIZE:
            w, h = DEF_WINDOW_SIZE
            tab.set.window.size(w, h)

        if self.inst_okx.init_okx(is_bulk=True) is False:
            return False

        s_chain = 'Arbitrum One'
        s_coin = 'ARB_ETH'
        (s_balance_coin, s_balance_usd) = self.inst_okx.get_balance_by_chain_coin(s_chain, s_coin)
        self.logit(None, f'Balance: {s_balance_coin} {s_balance_usd} [{s_chain}][{s_coin}]')
        self.update_status(self.IDX_BALANCE_ETH, s_balance_coin)
        self.update_status(self.IDX_BALANCE_USD, s_balance_usd)

        if not self.args.no_x:
            if self.inst_dp.init_capmonster() is False:
                return False

            if self.inst_dp.init_yescaptcha() is False:
                return False

            self.inst_x.status_load()
            self.inst_x.set_browser(self.browser)

            idx_vpn = get_index_from_header(DEF_HEADER_ACCOUNT, 'proxy')
            s_vpn = self.inst_x.dic_account[self.args.s_profile][idx_vpn]
            if self.inst_dp.set_vpn(s_vpn) is False:
                return False

            self.inst_x.twitter_run()
            x_status = self.inst_x.dic_status[self.args.s_profile][self.inst_x.IDX_STATUS] # noqa
            if x_status != self.inst_x.DEF_STATUS_OK:
                self.logit('layer3_run', f'x_status is {x_status}')
                # return False

        self.layer3_process()

        if self.args.manual_exit:
            s_msg = 'Manual Exit. Press any key to exit! ⚠️' # noqa
            input(s_msg)

        self.logit('layer3_run', 'Finished!')

        return True


def send_msg(inst_layer3, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            lst_status = None
            if s_profile in inst_layer3.dic_status:
                lst_status = inst_layer3.dic_status[s_profile]

            if lst_status is None:
                lst_status = [s_profile, -1]

            s_info += '- {},{}\n'.format(
                s_profile,
                lst_status[inst_layer3.IDX_MINT_STATUS],
            )
        d_cont = {
            'title': 'Layer3 Task Finished! [layer3]',
            'text': (
                'Layer3 Task\n'
                '- account,task_status\n'
                '{}\n'
                .format(s_info)
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")


def show_msg(args):
    current_directory = os.getcwd()
    FILE_LOG = f'{current_directory}/{FILENAME_LOG}'
    FILE_STATUS = f'{current_directory}/{DEF_PATH_DATA_STATUS}/status.csv'

    print('########################################')
    print('The program is running')
    print(f'headless={args.headless}')
    print('Location of the running result file:')
    print(f'{FILE_STATUS}')
    print('The running process is in the log file:')
    print(f'{FILE_LOG}')
    print('########################################')


def main(args):
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    if DEL_PROFILE_DIR and os.path.exists(DEF_PATH_USER_DATA):
        logger.info(f'Delete {DEF_PATH_USER_DATA} ...')
        shutil.rmtree(DEF_PATH_USER_DATA)
        logger.info(f'Directory {DEF_PATH_USER_DATA} is deleted') # noqa

    inst_layer3 = ClsLayer3()
    inst_layer3.set_args(args)

    args.s_profile = 'ALL'
    inst_layer3.inst_okx.set_args(args)
    inst_layer3.inst_okx.purse_load(args.decrypt_pwd)

    # 检查 profile 参数冲突
    if args.profile and (args.profile_begin is not None or args.profile_end is not None):
        logger.info('参数 --profile 与 --profile_begin/--profile_end 不能同时使用！')
        sys.exit(1)

    if len(args.profile) > 0:
        items = args.profile.split(',')
    elif args.profile_begin is not None and args.profile_end is not None:
        # 生成 profile_begin 到 profile_end 的 profile 列表
        prefix = re.match(r'^[a-zA-Z]+', args.profile_begin).group()
        start_num = int(re.search(r'\d+', args.profile_begin).group())
        end_num = int(re.search(r'\d+', args.profile_end).group())
        num_width = len(re.search(r'\d+', args.profile_begin).group())
        items = [f"{prefix}{str(i).zfill(num_width)}" for i in range(start_num, end_num + 1)]
        logger.info(f'Profile list: {items}')
    else:
        # 从配置文件里获取钱包名称列表
        items = list(inst_layer3.inst_okx.dic_purse.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    def is_complete(lst_status):
        if args.force:
            return False

        b_ret = True
        date_now = format_ts(time.time(), style=1, tz_offset=TZ_OFFSET)

        if lst_status:
            if len(lst_status) < inst_layer3.FIELD_NUM:
                return False

            if args.only_gm:
                if date_now != lst_status[inst_layer3.IDX_GM_DATE]:
                    b_ret = b_ret and False
                elif lst_status[inst_layer3.IDX_GM_VALUE] == '0':
                    b_ret = b_ret and False
            else:
                idx_status = inst_layer3.IDX_MINT_STATUS
                lst_status_ok = ['Activation Completed', 'Not enough ETH']
                if lst_status[idx_status] in lst_status_ok:
                    b_complete = True
                else:
                    b_complete = False
                b_ret = b_ret and b_complete

        else:
            b_ret = False

        return b_ret

    # 将已完成的剔除掉
    inst_layer3.status_load()
    # 从后向前遍历列表的索引
    for i in range(len(profiles) - 1, -1, -1):
        s_profile = profiles[i]
        if s_profile in inst_layer3.dic_status:
            lst_status = inst_layer3.dic_status[s_profile]

            if is_complete(lst_status):
                n += 1
                profiles.pop(i)

        else:
            continue
    logger.info('#'*40)

    percent = math.floor((n / total) * 100)
    logger.info(f'Progress: {percent}% [{n}/{total}]') # noqa

    while profiles:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(profiles)
        percent = math.floor((n / total) * 100)
        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile}]') # noqa

        if percent > args.max_percent:
            logger.info(f'Progress is more than threshold {percent}% > {args.max_percent}% [{n}/{total}] [{s_profile}]')
            break

        profiles.remove(s_profile)

        args.s_profile = s_profile

        if s_profile not in inst_layer3.inst_okx.dic_purse:
            logger.info(f'{s_profile} is not in okx account conf [ERROR]')
            sys.exit(0)

        # 如果出现异常(与页面的连接已断开)，增加重试
        max_try_except = 3
        for j in range(1, max_try_except+1):
            try:
                if j > 1:
                    logger.info(f'⚠️ 正在重试，当前是第{j}次执行，最多尝试{max_try_except}次 [{s_profile}]') # noqa

                inst_layer3.set_args(args)
                inst_layer3.inst_dp.set_args(args)
                inst_layer3.inst_okx.set_args(args)

                if not args.no_x:
                    inst_layer3.inst_x.set_args(args)

                if s_profile in inst_layer3.dic_status:
                    lst_status = inst_layer3.dic_status[s_profile]
                else:
                    lst_status = None

                if is_complete(lst_status):
                    logger.info(f'[{s_profile}] Last update at {lst_status[inst_layer3.IDX_UPDATE]}') # noqa
                    break
                else:
                    b_ret = inst_layer3.layer3_run()
                    inst_layer3.close()
                    if b_ret:
                        lst_success.append(s_profile)
                        break

            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                inst_layer3.close()
                if j < max_try_except:
                    time.sleep(5)

        if inst_layer3.is_update is False:
            continue

        logger.info(f'Progress: {percent}% [{n}/{total}] [{s_profile} Finish]')
        if percent > args.max_percent:
            continue

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))

            # 输出下次执行时间，格式为 YYYY-MM-DD HH:MM:SS
            next_exec_time = datetime.now() + timedelta(seconds=sleep_time)
            logger.info(f'next_exec_time: {next_exec_time.strftime("%Y-%m-%d %H:%M:%S")}')
            time.sleep(sleep_time)

    send_msg(inst_layer3, lst_success)


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
    parser.add_argument(
        '--profile_begin', required=False, default=None,
        help='按指定的 profile 开始后缀(包含) eg: g01'
    )
    parser.add_argument(
        '--profile_end', required=False, default=None,
        help='按指定的 profile 结束后缀(包含) eg: g05'
    )

    parser.add_argument(
        '--decrypt_pwd', required=False, default='',
        help='decrypt password'
    )
    # 不使用 X
    parser.add_argument(
        '--no_x', required=False, action='store_true',
        help='Not use X account'
    )
    parser.add_argument(
        '--auto_like', required=False, action='store_true',
        help='Like a post after login automatically'
    )
    parser.add_argument(
        '--auto_appeal', required=False, action='store_true',
        help='Auto appeal when account is suspended'
    )
    parser.add_argument(
        '--force', required=False, action='store_true',
        help='Run ignore status'
    )
    parser.add_argument(
        '--manual_exit', required=False, action='store_true',
        help='Close chrome manual'
    )
    # 添加 --headless 参数
    parser.add_argument(
        '--headless',
        action='store_true',   # 默认为 False，传入时为 True
        default=False,         # 设置默认值
        help='Enable headless mode'
    )
    # 添加 --no-headless 参数
    parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless',  # 指定与 --headless 参数共享同一个变量
        help='Disable headless mode'
    )
    parser.add_argument(
        '--url', required=False, default='',
        help='okx layer3 url'
    )
    parser.add_argument(
        '--get_task_status', required=False, action='store_true',
        help='Check task result'
    )
    # 添加 --max_percent 参数
    parser.add_argument(
        '--max_percent', required=False, default=100, type=int,
        help='[默认为 100] 执行的百分比'
    )
    parser.add_argument(
        '--only_gm', required=False, action='store_true',
        help='Only do gm checkin'
    )
    parser.add_argument(
        '--set_window_size', required=False, default='normal',
        help='[默认为 normal] 窗口大小，normal 为正常，max 为最大化'
    )

    args = parser.parse_args()
    show_msg(args)

    if args.only_gm:
        args.no_x = True
        logger.info('-'*40)
        logger.info('Only do gm checkin, set no_x=True')

    if args.loop_interval <= 0:
        main(args)
    elif len(args.profile) > 0:
        main(args)
    else:
        while True:
            main(args)

            if args.get_task_status:
                break

            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)

"""
# noqa
python layer3.py --auto_like --auto_appeal --sleep_sec_min=30 --sleep_sec_max=60 --loop_interval=60
python layer3.py --auto_like --auto_appeal --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=180
python layer3.py --auto_like --auto_appeal --sleep_sec_min=60 --sleep_sec_max=180
python layer3.py --auto_like --auto_appeal --sleep_sec_min=120 --sleep_sec_max=360

python layer3.py --auto_like --auto_appeal --profile=g05
python layer3.py --auto_like --auto_appeal --force --profile=g05

2025.05.15
Espresso 奥德赛
https://app.layer3.xyz/campaigns/brewing-the-future

Week 1
python layer3.py --auto_like --url=https://app.layer3.xyz/activations/intro-to-espresso
python layer3.py --auto_like --url=https://app.layer3.xyz/activations/intro-to-espresso --sleep_sec_min=600 --sleep_sec_max=1800 --max_percent=50 --headless

Week 2
Week 2.1 Brewing the Future: Arbitrum
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-arbitrum
Week 2.2 Brewing the Future: RARI
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-rari --profile=g05

Week 3
Week 3.1
https://app.layer3.xyz/activations/brewing-the-future-caldera
B 、B 、C
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-caldera

Week 3.2 (dc + logx)(complete by manual)
https://app.layer3.xyz/activations/brewing-the-future-logx

Week 4
https://app.layer3.xyz/activations/brewing-the-future-apechain
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-apechain --profile=g05

Week 5
https://app.layer3.xyz/activations/brewing-the-future-molten-network
C、B、D
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-molten-network --profile=g05

Week 6.1
https://app.layer3.xyz/activations/brewing-the-future-buildn-brew
B、A、C
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-buildn-brew --profile=g05

Week 6.2
https://app.layer3.xyz/activations/brewing-the-future-caffeinated-creators
python layer3.py --no_x --url=https://app.layer3.xyz/activations/brewing-the-future-caffeinated-creators --profile=g01
"""
