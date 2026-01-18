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

from proxy_api import set_proxy


from conf import DEF_LOCAL_PORT
from conf import DEF_INCOGNITO
from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_NUM_TRY
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_BROWSER

from conf import DEF_HEADER_ACCOUNT

from conf import TZ_OFFSET

from conf import EXTENSION_ID_OKX

from conf import DEF_CAPTCHA_EXTENSION_PATH
from conf import DEF_CAPTCHA_KEY
from conf import EXTENSION_ID_YESCAPTCHA

from conf import DEF_CAPMONSTER_EXTENSION_PATH
from conf import EXTENSION_ID_CAPMONSTER
from conf import DEF_CAPMONSTER_KEY

from conf import DEF_OKX_EXTENSION_PATH

from conf import logger

"""
2025.04.16
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

DEF_OKX = False

# DEF_FILE_X_ENCRIYPT = f'{DEF_PATH_DATA_ACCOUNT}/x_encrypt.csv'
# DEF_FILE_X_STATUS = f'{DEF_PATH_DATA_ACCOUNT}/x_status.csv'


class DpUtils():
    """
    DrissionPage Utils
    """
    def __init__(self) -> None:
        self.args = None
        self.browser = None

        # What plugins should be loaded
        self.plugin_okx = False
        self.plugin_yescapcha = False
        self.plugin_capmonster = False

    def set_args(self, args):
        self.args = args
        self.is_update = False

    def __del__(self):
        pass

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

    def get_browser(self, s_profile):
        """
        s_profile: 浏览器数据用户目录名称
        """
        # Settings.singleton_tab_obj = True

        profile_path = s_profile
        self.args.s_profile = s_profile

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

        def addon(s_name, s_path):
            # 检查目录是否存在
            if os.path.exists(os.path.join(current_directory, s_path)): # noqa
                logger.info(f'{s_name} plugin path: {s_path}')
                co.add_extension(s_path)
            else:
                print("{s_name} plugin directory is not exist. Exit!")
                sys.exit(1)

        if self.plugin_yescapcha:
            addon(s_name='YesCaptcha', s_path=DEF_CAPTCHA_EXTENSION_PATH)
        if self.plugin_capmonster:
            addon(s_name='CapMonster', s_path=DEF_CAPMONSTER_EXTENSION_PATH)
        if self.plugin_okx:
            addon(s_name='okx', s_path=DEF_OKX_EXTENSION_PATH)

        # https://drissionpage.cn/ChromiumPage/browser_opt
        b_headless = DEF_USE_HEADLESS
        try:
            b_headless = self.args.headless
        except: # noqa
            logger.info('self.args.headless is not exist.')
        co.headless(b_headless)
        co.set_user_agent(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36') # noqa

        try:
            self.browser = Chromium(co)
            # input('Manual install Addon ...')

            if self.plugin_okx:
                # Close okx popup window
                self.close_okx_popup()

            return self.browser
        except Exception as e:
            logger.info(f'Error: {e}')
        finally:
            pass
        return None

    def close_okx_popup(self):
        n_tabs_pre = self.browser.tabs_count
        max_wait_sec = 3
        # max_wait_sec = 10
        i = 0
        while i < max_wait_sec:
            i += 1
            self.browser.wait(1)

            n_tabs_cur = self.browser.tabs_count
            if self.browser.tabs_count > n_tabs_pre:
                self.logit(None, f'n_tabs_on_start={n_tabs_pre} n_tabs_now={n_tabs_cur}') # noqa
                break
            self.logit('wait_okx_popup', f'{i}/{max_wait_sec}') # noqa

        tab = self.browser.new_tab()
        self.browser.wait(1)

        self.browser.close_tabs(tab, others=True)
        self.browser.wait(1)
        self.logit(None, f'Closed okx popup. n_tabs_now={self.browser.tabs_count}') # noqa

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
                            try:
                                tab.actions.move_to(btn_save)
                                btn_save.wait.clickable(timeout=10).click()
                                self.logit(None, 'Save button is clicked')
                                break
                            except Exception as e: # noqa
                                self.logit('set_max_try_times', f'Save exception: {e}')

            self.logit(None, f'set_mint_num ... [{i}/{max_try}]')

        self.logit(None, f'Fail to set n_max_times! [n_max_times={n_max_times}] [Error]') # noqa
        return False

    def set_checkbox(self, s_path, is_select=True, s_display=''):
        """
        is_select:
            True / False
        s_display:
            display info
        """
        n_max_times = 5
        self.logit(None, f'To set checkbox try times: {n_max_times}') # noqa

        i = 0
        while i < n_max_times:
            i += 1
            tab = self.browser.latest_tab
            checkbox = tab.ele(s_path, timeout=2)
            if not isinstance(checkbox, NoneElement):
                if checkbox.states.is_checked == is_select:
                    self.logit(None, f'Set {s_display} success! [checked={is_select}]') # noqa
                    return True
                checkbox.click()
                self.logit(None, 'checkbox is clicked')
                tab.wait(1)

        self.logit(None, f'Fail to set {s_display} ! [Error]') # noqa
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
            s_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[6]/div[2]/span/input' # noqa
            self.set_checkbox(s_path, False, 'auto_start')

            # Cloudflare
            s_path = 'x://*[@id="app"]/div/div[2]/div[3]/div/div[5]/label/span[1]/input' # noqa
            self.set_checkbox(s_path, False, 'Cloudflare')

            logger.info('yescaptcha init success')
            self.save_screenshot(name='yescaptcha_2.jpg')
            return True
        else:
            return False

    def init_capmonster(self):
        """
        chrome-extension://jiofmdifioeejeilfkpegipdjiopiekl/popup/index.html
        """
        s_url = f'chrome-extension://{EXTENSION_ID_CAPMONSTER}/popup.html'
        tab = self.browser.latest_tab
        tab.get(s_url)
        tab.wait(3)

        def get_balance():
            """
            Balance: $0.9987
            Balance: Wrong key
            """
            tab.wait(1)
            ele_info = tab.ele('tag:div@@class=sc-bdvvtL dTzMWc', timeout=2) # noqa
            if not isinstance(ele_info, NoneElement):
                s_info = ele_info.text
                logger.info(f'{s_info}')
                self.logit('init_capmonster', f'CapMonster {s_info}')
                if s_info.find('$') >= 0:
                    return True
                if s_info.find('Wrong key') >= 0:
                    return False
            return False

        def click_checkbox(s_value):
            ele_input = tab.ele(f'tag:input@@value={s_value}', timeout=2)
            if not isinstance(ele_input, NoneElement):
                if ele_input.states.is_checked is True:
                    ele_input.click(by_js=True)
                    self.logit(None, f'cancel checkbox {s_value}')
                    return True
            return False

        def cancel_checkbox():
            lst_text = [
                'ReCaptcha2',
                'ReCaptcha3',
                'ReCaptchaEnterprise',
                'GeeTest',
                'ImageToText',
                'BLS',
            ]
            for s_value in lst_text:
                click_checkbox(s_value)

        self.save_screenshot(name='capmonster_1.jpg')

        if get_balance():
            return True

        ele_block = tab.ele('tag:div@@class=sc-bdvvtL ehUtQX', timeout=2)
        if isinstance(ele_block, NoneElement):
            self.logit('init_capmonster', 'API-key block is not found')
            return False
        self.logit('init_capmonster', None)

        ele_input = ele_block.ele('tag:input')
        if not isinstance(ele_input, NoneElement):
            if ele_input.value == DEF_CAPMONSTER_KEY:
                self.logit(None, 'init_capmonster has been initialized before')
                return True
            if len(ele_input.value) > 0 and ele_input.value != DEF_CAPMONSTER_KEY: # noqa
                ele_input.click.multi(times=2)
                ele_input.clear(by_js=True)
                # tab.actions.type('BACKSPACE')
            tab.actions.move_to(ele_input).click().type(DEF_CAPMONSTER_KEY) # noqa
            tab.wait(1)
            ele_btn = ele_block.ele('tag:button')
            if not isinstance(ele_btn, NoneElement):
                if ele_btn.states.is_enabled is False:
                    self.logit(None, 'The Save Button is_enabled=False')
                else:
                    ele_btn.wait.clickable(timeout=5)
                    ele_btn.click(by_js=True)
                    tab.wait(1)
                    self.logit(None, 'Saved capmonster_key [OK]')
                    cancel_checkbox()
                    if get_balance():
                        return True
            else:
                self.logit(None, 'the save button is not found')
                return False
        else:
            self.logit(None, 'the input element is not found')
            return False

        logger.info('capmonster init success')
        self.save_screenshot(name='capmonster_2.jpg')

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

        s_val = self.get_status_by_idx(IDX_NUM_VISIT, s_profile)

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

    def wait_countdown(self, s_info='', max_wait_sec=30):
        i = 0
        while i < max_wait_sec:
            i += 1
            self.browser.wait(1)
            self.logit('wait_countdown', f'{s_info} {i}/{max_wait_sec}') # noqa

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

    def set_vpn(self, s_vpn=None):
        if s_vpn is None:
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
        # ding_msg(d_cont, DEF_DING_opTOKEN, msgtype="markdown")
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

    def get_ele_btn(self, tab, lst_path, n_timeout=2):
        # tab = self.browser.latest_tab
        for s_path in lst_path:
            ele_btn = tab.ele(s_path, timeout=n_timeout) # noqa
            if not isinstance(ele_btn, NoneElement):
                return ele_btn
        return NoneElement

    def is_extension_installed(self, extension_id: str, s_name: str) -> bool:
        """
        检查指定插件（extension_id）是否已正确安装。
        仅支持在非 headless 模式下检测。
        """
        if not self.browser:
            logger.info('Browser 未启动，无法检测插件。')
            return False
        try:
            # chrome://extensions/?id=mcohilncbfahbmgdjkbpemcciiolgcge
            s_url = f'chrome://extensions/?id={extension_id}'
            tab = self.browser.new_tab(s_url)
            tab.wait(2)
            ele_extension = tab.ele('tag=extensions-manager', timeout=2)
            if not isinstance(ele_extension, NoneElement):
                ele_view = ele_extension.sr.ele('tag=cr-view-manager', timeout=2)
                if not isinstance(ele_view, NoneElement):
                    ele_detail = ele_view.ele('tag=extensions-detail-view', timeout=2)
                    if not isinstance(ele_detail, NoneElement):
                        ele_section = ele_detail.sr.ele('@@id=id-section', timeout=2)
                        if not isinstance(ele_section, NoneElement):
                            s_text = ele_section.text
                            if extension_id in s_text:
                                # self.logit(None, f'插件 {s_name} 已安装。')
                                self.browser.close_tabs(tab)
                                return True
            # self.logit(None, f'插件 {s_name} 未安装。')
            self.browser.close_tabs(tab)
            return False
        except Exception as e:
            self.logit(None, f'检查插件异常: {e}')
            return False

    def check_extension(self, n_max_try=3, lst_extension_id=None) -> bool:
        """
        lst_extension_id:
            [(extension_id, s_name), ...]
            None: Use self.args.extension_id
        """
        b_ret = True

        tab = self.browser.new_tab('chrome://extensions/')
        tab.wait(1)
        self.browser.close_tabs(tab, others=True)

        if lst_extension_id is None:
            try:
                id = self.args.extension_id
            except:
                self.args.extension_id = ''

            if self.args.extension_id == '':
                lst_extension_id = [
                    (EXTENSION_ID_OKX, 'okx'),
                    (EXTENSION_ID_YESCAPTCHA, 'yescaptcha'),
                    (EXTENSION_ID_CAPMONSTER, 'capmonster'),
                ]
            else:
                # id 用逗号分隔
                lst_extension_id = [(s_id, 'custom') for s_id in self.args.extension_id.split(',')]
                # lst_extension_id = [(self.args.extension_id, 'custom')]

        for i in range(n_max_try):
            b_ret = True
            self.logit(None, f'Check Extension, try: {i+1}/{n_max_try} ...')

            for extension_id, s_name in lst_extension_id:
                is_installed = self.is_extension_installed(extension_id, s_name)
                if is_installed:
                    self.logit(None, f'插件 {s_name} 已安装 [OK]')
                else:
                    b_ret = b_ret and False
                    self.logit(None, f'插件 {s_name} 未安装或检测失败 [NG]')
                    input('Please Check and Press Enter to continue...')

            if b_ret:
                break

        return b_ret
    
    def check_connection(self):
        """
        检测当前的互联网连接是否可用
        
        Returns:
            bool: True表示连接正常，False表示连接异常
        """
        import time
        
        for attempt in range(3):  # 最多重试3次（初始1次 + 重试2次）
            try:
                # 尝试HTTP请求到Google
                import requests
                response = requests.get("http://www.google.com", timeout=10)
                if response.status_code == 200:
                    logger.info(f"网络连接检测成功 (Google) - 第{attempt + 1}次尝试")
                    return True
                else:
                    logger.warning(f"网络连接检测失败，HTTP状态码: {response.status_code} - 第{attempt + 1}次尝试")
                    if attempt < 2:  # 如果不是最后一次尝试
                        logger.info("等待3秒后重试...")
                        time.sleep(3)
                        continue
                    else:
                        return False
                
            except Exception as e:
                logger.error(f"网络连接检测异常: {e} - 第{attempt + 1}次尝试")
                if attempt < 2:  # 如果不是最后一次尝试
                    logger.info("等待3秒后重试...")
                    time.sleep(3)
                    continue
                else:
                    return False
        
        return False


def main():
    parser = argparse.ArgumentParser(description='DrissionPage 插件检测工具')
    parser.add_argument('--profile', type=str, required=True, help='浏览器用户目录名称')
    parser.add_argument('--extension_id', type=str, required=False, default='', help='需要检测的插件 extension_id')
    parser.add_argument('--check_connection', action='store_true', help='检测网络连接状态')
    args = parser.parse_args()

    dp = DpUtils()
    dp.set_args(args)
    
    # 如果指定了检测网络连接
    if args.check_connection:
        print("正在检测网络连接...")
        if dp.check_connection():
            print("✅ 网络连接正常")
        else:
            print("❌ 网络连接异常")
        return
    
    # 检测浏览器和插件
    browser = dp.get_browser(args.profile)
    if browser is None:
        print('浏览器启动失败')
        return
    dp.check_extension()
    dp.close()


if __name__ == '__main__':
    main()
