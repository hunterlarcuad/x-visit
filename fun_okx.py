"""
2025.03.31
okx utils
"""
import os  # noqa
import sys  # noqa
import argparse
import random
import time
import copy
import pdb  # noqa
import shutil
import math
import re  # noqa
import getpass
from datetime import datetime  # noqa

from DrissionPage import ChromiumOptions
from DrissionPage import Chromium
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import load_file

from decrypt_utils import decrypt_csv

from conf import logger

from conf import DEF_PATH_DATA_PURSE
from conf import DEF_FILE_PURSE_ENCRIPT
# from conf import DEF_HEADER_PURSE
from conf import DEF_COL_PURSE_KEY

from conf import DEF_NUM_TRY
from conf import EXTENSION_ID_OKX
from conf import DEF_OKX_PWD


class OkxUtils():

    def __init__(self) -> None:
        self.INFO_NOT_ENOUGH_TO_COVER_FEE = 'You don’t have enough ETH to cover the potential network fee.'
        self.FEE_TOO_HIGH = 'Network fee is greater than max fee'

        self.args = None
        self.dic_purse = {}

    def set_args(self, args):
        self.args = args
        self.is_update = False
        # self.purse_load(self.args.decrypt_pwd)

    def set_browser(self, browser):
        self.browser = browser

    def purse_load(self, s_decrypt_pwd=None):
        """
        self.args.decrypt_pwd
        """
        self.file_purse = f'{DEF_PATH_DATA_PURSE}/{DEF_FILE_PURSE_ENCRIPT}'
        # self.dic_purse = load_file(
        #     file_in=self.file_purse,
        #     idx_key=0,
        #     header=DEF_HEADER_PURSE
        # )

        # 解密文件并获取 DataFrame
        if not s_decrypt_pwd:
            s_decrypt_pwd = getpass.getpass(
                'Please input the decrypt password:')

        df = decrypt_csv(self.file_purse, s_decrypt_pwd)
        self.dic_purse = {
            row['account']: row
            for row in df.to_dict(orient='records')
        }  # noqa
        self.logit('purse_load',
                   f'Success to load purse: {len(self.dic_purse)}')  # noqa

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

    def okx_secure_wallet(self):
        tab = self.browser.latest_tab
        # Secure your wallet
        ele_info = tab.ele('Secure your wallet')
        if not isinstance(ele_info, NoneElement):
            self.logit('okx_secure_wallet', 'Secure your wallet')
            ele_btn = tab.ele('Password', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                ele_btn.click(by_js=True)
                self.browser.wait(1)
                self.logit('okx_secure_wallet', 'Select Password')

                # Next
                ele_btn = tab.ele('@@tag()=button@@data-testid=okd-button',
                                  timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.click(by_js=True)
                    self.browser.wait(1)
                    self.logit('okx_secure_wallet', 'Click Next')
                    return True
        return False

    def okx_set_pwd(self):
        tab = self.browser.latest_tab
        # Set password
        ele_info = tab.ele('Set password', timeout=2)
        if not isinstance(ele_info, NoneElement):
            self.logit('okx_set_pwd', 'Set Password')
            ele_input = tab.ele(
                '@@tag()=input@@data-testid=okd-input@@placeholder:Enter',
                timeout=2)  # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit('okx_set_pwd', 'Input Password')
                tab.actions.move_to(ele_input).click().type(DEF_OKX_PWD)
            self.browser.wait(1)
            ele_input = tab.ele(
                '@@tag()=input@@data-testid=okd-input@@placeholder:Re-enter',
                timeout=2)  # noqa
            if not isinstance(ele_input, NoneElement):
                tab.actions.move_to(ele_input).click().type(DEF_OKX_PWD)
                self.logit('okx_set_pwd', 'Re-enter Password')
            self.browser.wait(1)
            ele_btn = tab.ele(
                '@@tag()=button@@data-testid=okd-button@@text():Confirm',
                timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.click(by_js=True)
                self.logit('okx_set_pwd', 'Password Confirmed [OK]')
                self.browser.wait(10)
                return True
        return False

    def okx_bulk_import_private_key(self, s_key):
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=div@@class:_typography@@text():Bulk import private key',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            ele_btn.click(by_js=True)
            self.logit('okx_bulk_import_private_key', 'Click ...')

            tab = self.browser.get_tab(self.browser.latest_tab.tab_id)

            ele_btn = tab.ele('@@tag()=i@@id=okdDialogCloseBtn',
                              timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Close pwd input box ...')
                ele_btn.click(by_js=True)

            ele_btn = tab.ele(
                '@@tag()=div@@data-testid=okd-select-reference-value-box',
                timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Select network ...')
                ele_btn.click(by_js=True)

            ele_btn = tab.ele(
                '@@tag()=div@@class:_typography@@text()=EVM networks',
                timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                self.logit(None, 'Select EVM networks ...')
                ele_btn.click(by_js=True)

            ele_input = tab.ele(
                '@@tag()=textarea@@id:pk-input@@placeholder:private',
                timeout=2)  # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit(None, 'Input EVM key ...')
                tab.actions.move_to(ele_input).click().type(s_key)  # noqa
                self.browser.wait(5)

    def init_okx(self, is_bulk=False):
        """
        chrome-extension://jiofmdifioeejeilfkpegipdjiopiekl/popup/index.html
        """
        s_url = f'chrome-extension://{EXTENSION_ID_OKX}/home.html'

        for i in range(1, DEF_NUM_TRY + 1):
            tab = self.browser.new_tab(s_url)
            tab.wait.doc_loaded()
            self.browser.wait(1)
            if not tab.html:
                input(
                    'Press Check Addon is installed, Press Enter to continue ...'
                )
                continue

            self.browser.close_tabs(tab, others=True)
            self.browser.wait(1)

            self.logit('init_okx', f'tabs_count={self.browser.tabs_count}')

            if self.browser.tabs_count == 1:
                break

        self.save_screenshot(name='okx_1.jpg')

        # tab = self.browser.latest_tab
        ele_info = tab.ele('@@tag()=div@@class:balance', timeout=2)  # noqa
        if not isinstance(ele_info, NoneElement):
            s_info = ele_info.text
            self.logit('init_okx', f'Account balance: {s_info}')  # noqa
            return True

        ele_btn = tab.ele('Import wallet', timeout=2)
        if not isinstance(ele_btn, NoneElement):
            # Import wallet
            self.logit('init_okx', 'Import wallet ...')
            ele_btn.click(by_js=True)

            self.browser.wait(1)
            ele_btn = tab.ele('Seed phrase or private key', timeout=2)
            if not isinstance(ele_btn, NoneElement):
                # Import wallet
                self.logit('init_okx',
                           'Select Seed phrase or private key ...')  # noqa
                ele_btn.click(by_js=True)
                self.browser.wait(1)

                s_key = self.dic_purse[self.args.s_profile][DEF_COL_PURSE_KEY]

                if len(s_key.split()) == 1:
                    # Private key
                    self.logit('init_okx', 'Import By Private key')
                    ele_btn = tab.ele('Private key', timeout=2)
                    if not isinstance(ele_btn, NoneElement):
                        # 点击 Private key Button
                        self.logit('init_okx', 'Select Private key')
                        ele_btn.click(by_js=True)
                        self.browser.wait(1)
                        ele_input = tab.ele(
                            '@class:okui-input-input input-textarea ta',
                            timeout=2)  # noqa
                        if not isinstance(ele_input, NoneElement):
                            # 使用动作，输入完 Confirm 按钮才会变成可点击状态
                            tab.actions.move_to(ele_input).click().type(
                                s_key)  # noqa
                            self.browser.wait(5)
                            self.logit('init_okx', 'Input Private key')
                    is_bulk = True
                    if is_bulk:
                        self.okx_bulk_import_private_key(s_key)
                else:
                    # Seed phrase
                    self.logit('init_okx', 'Import By Seed phrase')
                    words = s_key.split()

                    # 输入助记词需要最大化窗口，否则最后几个单词可能无法输入
                    (width, height) = tab.rect.window_size  # 保存原始窗口大小
                    tab.set.window.max()

                    ele_inputs = tab.eles(
                        '.mnemonic-words-inputs__container__input',
                        timeout=2)  # noqa
                    if not isinstance(ele_inputs, NoneElement):
                        self.logit('init_okx', 'Input Seed phrase')
                        for i in range(len(ele_inputs)):
                            ele_input = ele_inputs[i]
                            tab.actions.move_to(ele_input).click().type(
                                words[i])  # noqa
                            self.logit(
                                None,
                                f'Input word [{i+1}/{len(words)}]')  # noqa
                            self.browser.wait(1)

                        # 恢复原来的窗口大小
                        tab.set.window.size(width, height)

                # Confirm
                max_wait_sec = 10
                i = 1
                while i < max_wait_sec:
                    tab = self.browser.latest_tab
                    ele_btn = tab.ele(
                        '@@tag()=button@@data-testid=okd-button@@text():Confirm',
                        timeout=2)  # noqa
                    self.logit('init_okx',
                               f'To Confirm ... {i}/{max_wait_sec}')  # noqa
                    if not isinstance(ele_btn, NoneElement):
                        if ele_btn.states.is_enabled is False:
                            self.logit(None, 'Confirm Button is_enabled=False')
                        else:
                            if ele_btn.states.is_clickable:
                                ele_btn.click(by_js=True)
                                self.logit('init_okx',
                                           'Confirm Button is clicked')  # noqa
                                self.browser.wait(1)
                                break
                            else:
                                self.logit(None,
                                           'Confirm Button is_clickable=False'
                                           )  # noqa

                    i += 1
                    self.browser.wait(1)
                # 未点击 Confirm
                if i >= max_wait_sec:
                    self.logit('init_okx',
                               'Confirm Button is not found [ERROR]')  # noqa

                # 导入私钥有此选择页面，导入助记词则没有此选择过程
                # Select network and Confirm
                ele_info = tab.ele('Select network', timeout=2)
                if not isinstance(ele_info, NoneElement):
                    self.logit('init_okx', 'Select network ...')
                    ele_btn = tab.ele('@@tag()=button@@data-testid=okd-button',
                                      timeout=2)  # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.click(by_js=True)
                        self.browser.wait(1)
                        self.logit('init_okx', 'Select network finish')

                self.okx_secure_wallet()

                # Set password
                is_success = self.okx_set_pwd()

                # Import successful
                tab = self.browser.latest_tab
                ele_info = tab.ele('@@tag()=div@@text():Import successful',
                                   timeout=2)  # noqa
                if not isinstance(ele_info, NoneElement):
                    s_info = ele_info.text.replace('\n', ';')
                    self.logit(None, f'[Info] {s_info}')  # noqa

                    # Don't click OK button, or chrome will exit.
                    # ele_btn = tab.ele('@@tag()=button@@data-testid=okd-button@@text()=OK', timeout=2) # noqa
                    # if not isinstance(ele_btn, NoneElement):
                    #     ele_btn.click(by_js=True)
                    #     self.browser.wait(1)

                # Start your Web3 journey
                self.browser.wait(1)
                self.save_screenshot(name='okx_2.jpg')
                tab = self.browser.latest_tab
                ele_btn = tab.ele(
                    '@@tag()=button@@data-testid=okd-button@@text():Start',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.click(by_js=True)
                    self.logit('init_okx', 'import wallet success')
                    self.save_screenshot(name='okx_3.jpg')
                    self.browser.wait(2)

                if is_success:
                    return True
        else:
            ele_info = tab.ele('Your portal to Web3', timeout=2)
            if not isinstance(ele_info, NoneElement):
                self.logit('init_okx', 'Input password to unlock ...')
                s_path = '@@tag()=input@@data-testid=okd-input@@placeholder:Enter'  # noqa
                ele_input = tab.ele(s_path, timeout=2)  # noqa
                if not isinstance(ele_input, NoneElement):
                    tab.actions.move_to(ele_input).click().type(DEF_OKX_PWD)
                    if ele_input.value != DEF_OKX_PWD:
                        self.logit('init_okx',
                                   '[ERROR] Fail to input passwrod !')  # noqa
                        tab.set.window.max()
                        return False

                    self.browser.wait(1)
                    ele_btn = tab.ele(
                        '@@tag()=button@@data-testid=okd-button@@text():Unlock',
                        timeout=2)  # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.click(by_js=True)
                        self.browser.wait(1)

                        self.logit('init_okx', 'login success')
                        self.save_screenshot(name='okx_2.jpg')

                        while True:
                            if self.okx_cancel() is False:
                                break
                            self.browser.wait(1)

                        return True
            else:
                ele_btn = tab.ele(
                    '@@tag()=button@@data-testid=okd-button@@text()=Approve',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    ele_btn.click(by_js=True)
                    self.browser.wait(1)
                else:
                    ele_btn = tab.ele(
                        '@@tag()=button@@data-testid=okd-button@@text()=Connect',
                        timeout=2)  # noqa
                    if not isinstance(ele_btn, NoneElement):
                        ele_btn.click(by_js=True)
                        self.browser.wait(1)
                    else:
                        self.logit('init_okx',
                                   '[ERROR] What is this ... [quit]')  # noqa
                        self.browser.quit()

        self.logit('init_okx', 'login failed [ERROR]')
        return False

    def wait_popup(self, n_tab_dest, max_wait_sec=30):
        """
        n_tab_dest
            目标数值
            n_tab_dest = self.browser.tabs_count + 1
            n_tab_dest = self.browser.tabs_count - 1
        """
        i = 0
        while i < max_wait_sec:
            i += 1
            self.browser.wait(1)
            if self.browser.tabs_count == n_tab_dest:
                self.browser.wait(1)
                self.logit('wait_popup',
                           f'Success n_tab_dest={n_tab_dest}')  # noqa
                return True
            self.logit('wait_popup', f'{i}/{max_wait_sec}')  # noqa
        return False

    def okx_connect(self):
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button@@text()=Connect',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            if ele_btn.wait.clickable(timeout=5):
                ele_btn.click(by_js=True)
                self.logit(None, 'Success to Click Connect Button')  # noqa
                return True
            self.logit(None, 'Fail to Click Connect Button')  # noqa
        else:
            self.logit(None, 'Fail to load Connect Button')  # noqa

        return False

    def okx_cancel(self):
        tab = self.browser.latest_tab
        tab.wait.doc_loaded()

        # Unknown transaction
        # Signature request
        # ele_info = tab.ele('@@tag()=div@@text():Signature request', timeout=1) # noqa
        # if isinstance(ele_info, NoneElement):
        #     return False

        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button@@text():Cancel',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            ele_btn.wait.clickable(timeout=5).click(by_js=True)
            self.logit(None, 'Success to Click Cancel Button')  # noqa
            return True
        else:
            # self.logit(None, 'No Cancel Button') # noqa
            return False

    def okx_approve(self):
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button@@text():Approve',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            if ele_btn.wait.clickable(timeout=5):
                ele_btn.click(by_js=True)
                self.logit(None, 'Success to Click Approve Button')  # noqa
                return True
            self.logit(None, 'Fail to Click Approve Button')  # noqa
        else:
            self.logit(None, 'No Approve Button')  # noqa

        return False

    def okx_confirm_by_fee(self, max_fee):
        """
        Return:
            (True/False, f_fee, s_info)
            s_info:
                [self.INFO_NOT_ENOUGH_TO_COVER_FEE] You don’t have enough ETH to cover the potential network fee
                [self.FEE_TOO_HIGH] Network fee is greater than max fee
        """
        f_fee = -1
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button@@text():Confirm',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            # Get network fee
            ele_blk = tab.ele('@@tag()=div@@class:_networkFee__wrap_',
                              timeout=2)  # noqa
            if not isinstance(ele_blk, NoneElement):
                ele_info = ele_blk.text.replace('\n', ' ')
                self.logit(None, f'Network fee text: {ele_info}')  # noqa

                # Est RARI Mainnet network fee\nE\n0.000185 ETH
                s_fee = ele_blk.text.split('\n')[-1].split()[0]
                self.logit(None, f'Network fee value: {s_fee} ...')  # noqa
                f_fee = float(s_fee)

                s_max_fee = f"{max_fee:.8f}"

                if f_fee > max_fee:
                    self.logit(
                        None,
                        f'Network fee is greater than max fee: {s_fee} > {s_max_fee} [ERROR]'
                    )  # noqa
                    self.okx_cancel()
                    return (False, f_fee, self.FEE_TOO_HIGH)
                self.logit(
                    None,
                    f'Network fee is lower than max fee: {s_fee} <= {s_max_fee} [OK]'
                )  # noqa

            ele_blk = tab.ele('@@tag()=div@@class:_tip-message',
                              timeout=2)  # noqa
            if not isinstance(ele_blk, NoneElement):
                ele_info = ele_blk.text.replace('\n', ' ')
                self.logit(None, f'tip message text: {ele_info}')  # noqa
                self.okx_cancel()
                # You don’t have enough ETH to cover the potential network fee
                return (False, f_fee, ele_info)

            if ele_btn.states.is_enabled is False:
                self.logit(None, 'Confirm Button is_enabled=False')
                self.okx_cancel()
                return (False, f_fee, '')

            if ele_btn.wait.clickable(timeout=5):
                ele_btn.click(by_js=True)
                self.logit(None, 'Success to Click Confirm Button')  # noqa
                return (True, f_fee, '')
            self.logit(None, 'Fail to Click Confirm Button')  # noqa
        else:
            self.logit(None, 'Fail to load Confirm Button')  # noqa

        return (False, f_fee, '')

    def okx_confirm(self):
        tab = self.browser.latest_tab
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button@@text():Confirm',
            timeout=2)  # noqa
        if not isinstance(ele_btn, NoneElement):
            if ele_btn.wait.clickable(timeout=5):
                ele_btn.click(by_js=True)
                self.logit(None, 'Success to Click Confirm Button')  # noqa
                return True
            self.logit(None, 'Fail to Click Confirm Button')  # noqa
        else:
            self.logit(None, 'Fail to load Confirm Button')  # noqa

        return False

    def get_addr_by_chain(self, s_chain, s_coin):
        tab = self.browser.latest_tab
        n_max_try = 3

        for i in range(1, n_max_try + 1):
            self.logit(None, f'get_addr_by_chain try_i={i}/{n_max_try}')

            s_url = f'chrome-extension://{EXTENSION_ID_OKX}/home.html'
            tab.get(s_url)
            # tab.wait.load_start()
            tab.wait(3)

            # Click Icon in the upper right corner
            ele_btn = tab.ele('@@tag()=div@@class=_container_1eikt_1',
                              timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.enabled(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

            # Search network name
            ele_input = tab.ele('@@tag()=input@@data-testid=okd-input',
                                timeout=2)  # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit(None, f'Change network to {s_chain} ...')  # noqa
                tab.actions.move_to(ele_input).click().type(s_chain)
                tab.wait(3)
                ele_btn = tab.ele(
                    f'@@tag()=div@@class:_title@@text()={s_chain}',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    self.logit(None,
                               f'Select network: {ele_btn.text} ...')  # noqa
                    ele_btn.wait.enabled(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(3)

                # Crypto list
                ele_btn = tab.ele(
                    f'@@tag()=div@@class:_wallet-list__item@@text():{s_coin}',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    s_info = ele_btn.text.replace('\n', ' ')
                    self.logit(None, f'Select network: {s_info} ...')  # noqa
                    ele_btn.wait.enabled(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(3)

                # address
                ele_btn = tab.ele(
                    f'@@tag()=div@@class=new-coin-detail-address-content',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    s_info = ele_btn.text
                    self.logit(None, f'address: {s_info}')  # noqa
                    tab.wait(1)
                    return s_info
            else:
                self.logit(None, 'Fail to search network name')  # noqa

        self.logit(None, 'Fail to get address')  # noqa
        return None

    def add_crypto(self, s_coin):
        tab = self.browser.latest_tab
        ele_info = tab.ele(
            '@@tag()=div@@text()=No added crypto for this network',
            timeout=2)
        if isinstance(ele_info, NoneElement):
            return False

        s_info = ele_info.text
        self.logit(None, 'Info: {}'.format(s_info))

        # button data-testid="okd-button"
        ele_btn = tab.ele(
            '@@tag()=button@@data-testid=okd-button',
            timeout=2)
        if not isinstance(ele_btn, NoneElement):
            ele_btn.click(by_js=True)
            tab.wait(5)

        ele_blk = tab.ele(
            f'@@tag()=div@@class:_wallet-list__item@@text():{s_coin}',
            timeout=2)
        if not isinstance(ele_blk, NoneElement):
            s_info = ele_blk.text.replace('\n', ' ')
            self.logit(None, 'Info: {}'.format(s_info))

            ele_btn = tab.ele(
                '@@tag()=i@@class:icon iconfont okx-wallet-plugin-add',
                timeout=2)
            if not isinstance(ele_btn, NoneElement):
                ele_btn.click(by_js=True)
                tab.wait(5)

                ele_back_btn = tab.ele(
                    '@@tag()=i@@class:icon iconfont okds-arrow-chevron-left-centered',
                    timeout=2)
                if not isinstance(ele_back_btn, NoneElement):
                    ele_back_btn.click(by_js=True)
                    tab.wait(2)

                return True

        return False

    def get_balance_by_chain_coin(self, s_chain, s_coin):
        s_balance_coin = '-1'
        s_balance_usd = '-1'

        tab = self.browser.latest_tab
        n_max_try = 3

        for i in range(1, n_max_try + 1):
            self.logit(None, f'get_addr_by_chain try_i={i}/{n_max_try}')

            s_url = f'chrome-extension://{EXTENSION_ID_OKX}/home.html'
            tab.get(s_url)
            # tab.wait.load_start()
            tab.wait(3)

            # Click Icon in the upper right corner
            ele_btn = tab.ele('@@tag()=div@@class=_container_1eikt_1',
                              timeout=2)  # noqa
            if not isinstance(ele_btn, NoneElement):
                ele_btn.wait.enabled(timeout=3)
                ele_btn.click(by_js=True)
                tab.wait(1)

            # Search network name
            ele_input = tab.ele('@@tag()=input@@data-testid=okd-input',
                                timeout=2)  # noqa
            if not isinstance(ele_input, NoneElement):
                self.logit(None, f'Change network to {s_chain} ...')  # noqa
                tab.actions.move_to(ele_input).click().type(s_chain)
                tab.wait(3)
                ele_btn = tab.ele(
                    f'@@tag()=div@@class:_title@@text()={s_chain}',
                    timeout=2)  # noqa
                if not isinstance(ele_btn, NoneElement):
                    self.logit(None,
                               f'Select network: {ele_btn.text} ...')  # noqa
                    ele_btn.wait.enabled(timeout=3)
                    ele_btn.click(by_js=True)
                    tab.wait(3)

                self.add_crypto(s_coin)

                # Hidden (1)
                lst_path = [
                    '@@tag()=div@@class:root@@text():Hidden',
                    '@@tag()=div@@class:root@@text():Small assets'
                ]
                for s_path in lst_path:
                    ele_blk = tab.ele(s_path, timeout=2)
                    if not isinstance(ele_blk, NoneElement):
                        s_text = ele_blk.text
                        self.logit(None, f'Hidden: {s_text} ...')  # noqa
                        # 提取 () 中的数字
                        s_num = re.search(r'\((.*?)\)', s_text).group(1)
                        self.logit(None, f'Hidden: {s_num} ...')  # noqa
                        if int(s_num) > 0:
                            ele_btn = ele_blk.ele('@@tag()=i@@class:icon',
                                                  timeout=2)  # noqa
                            if not isinstance(ele_btn, NoneElement):
                                # icon iconfont okds-arrow-chevron-up-md _icon_1e5k7_12
                                # icon iconfont okds-arrow-chevron-down-md _icon_1e5k7_12
                                if ele_btn.attr('class').find(
                                        'okds-arrow-chevron-down-md') != -1:
                                    ele_btn.click(by_js=True)
                                    tab.wait(1)
                        break
            else:
                self.logit(None, 'Fail to search network name')  # noqa

            # Crypto list
            lst_ele_btn = tab.eles(
                f'@@tag()=div@@class:_wallet-list__item@@text():{s_coin}',
                timeout=2)  # noqa
            if not lst_ele_btn:
                continue

            for ele_btn in lst_ele_btn:
                s_info = ele_btn.text.replace('\n', ' ')
                self.logit(None, f'Select network: {s_info} ...')  # noqa
                # ARB_ETH $2,480.9 -5.66% 0.000017 $0.04285
                fields = s_info.split()
                if len(fields) == 5:
                    if fields[0] == s_coin:
                        s_balance_coin = fields[-2]
                        s_balance_usd = fields[-1]
                        # s_balance_usd 去掉 $
                        s_balance_usd = s_balance_usd.replace('$', '')
                        break
                    else:
                        self.logit(
                            None,
                            f'balance fields is {len(fields)} != 5')  # noqa
                else:
                    self.logit(None,
                               f'balance fields is {len(fields)} != 5')  # noqa
                tab.wait(1)

            break

        return (s_balance_coin, s_balance_usd)


if __name__ == "__main__":
    """
    """
    sys.exit(0)


"""
# noqa
"""
