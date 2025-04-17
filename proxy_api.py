import sys
import logging # noqa
import argparse
import requests
import pdb # noqa
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from conf import DEF_CLASH_API_PORT
from conf import DEF_CLASH_API_SECRETKEY
from conf import logger

"""
# noqa

2025.04.11
# Clash Verge
# 获取所有代理
curl -X GET http://127.0.0.1:9097/proxies -H "Authorization: Bearer {API_SecretKey}"

# 获取当前使用的代理模式
curl -X GET http://127.0.0.1:9097/configs -H "Authorization: Bearer {API_SecretKey}"

Sample:
{
  "port": 7890,
  "socks-port": 7891,
  "redir-port": 0,
  "mode": "Rule",  // 👈 当前的代理模式
  ...
}

🛠️ 当前支持的代理模式包括：
"Global"：全局代理
"Rule"：规则分流（默认）
"Direct"：不使用代理
"Script"：脚本控制（部分高级配置中使用）

2025.04.07

# ClashX API 端口和密钥配置
在 macOS 上，启动 ClashX
点击屏幕右上角的 ClashX 图标，然后选择“更多设置”
在“通用”标签页中，设置端口和密钥

# 获取所有代理
curl -X GET http://127.0.0.1:9090/proxies -H "Authorization: Bearer {API_SecretKey}"
# 切换代理
curl -X PUT http://127.0.0.1:9090/proxies/节点选择 \
-H "Authorization: Bearer {API_SecretKey}" \
-H "Content-Type: application/json" \
-d '{"name": "gcp-g03-kr"}'
"""


def get_proxy_config(session: requests.Session):
    """
    获取配置
    例如，代理模式
    """
    url = f'http://127.0.0.1:{DEF_CLASH_API_PORT}/configs'
    headers = {
        'Authorization': f'Bearer {DEF_CLASH_API_SECRETKEY}'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        data = response.json()
        if isinstance(data, dict):
            return data
        else:
            logger.info('Unexpected data format')
            return None
    except requests.exceptions.RequestException as e:
        logger.info(f'Failed to fetch data due to {str(e)}')
        return None


def fetch_proxis(session: requests.Session):
    """
    Function to fetch data from API
    """
    url = f'http://127.0.0.1:{DEF_CLASH_API_PORT}/proxies'
    headers = {
        'Authorization': f'Bearer {DEF_CLASH_API_SECRETKEY}'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        data = response.json()
        if isinstance(data, dict):
            return data
        else:
            logger.info('Unexpected data format')
            return None
    except requests.exceptions.RequestException as e:
        logger.info(f'Failed to fetch data due to {str(e)}')
        return None


def get_mode(session):
    try:
        data = get_proxy_config(session)
        s_mode = data['mode']
    except: # noqa
        s_mode = None

    if s_mode == 'rule':
        s_mode = '节点选择'
    elif s_mode == 'global':
        s_mode = 'GLOBAL'
    else:
        # ERROR
        pass
    return s_mode


def put_proxy(s_mode, proxy_dest, session: requests.Session):
    """
    Function to set proxy

    mode:
        global: 全局模式，url 后缀为 GLOBAL
        rule: 规则模式，url 后缀为 节点选择
    proxy_dest: 目标代理
    """
    # url = f'http://127.0.0.1:{DEF_CLASH_API_PORT}/proxies/节点选择'
    url = f'http://127.0.0.1:{DEF_CLASH_API_PORT}/proxies/{s_mode}'
    headers = {
        'Authorization': f'Bearer {DEF_CLASH_API_SECRETKEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'name': proxy_dest
    }

    try:
        response = session.put(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        return True
    except requests.exceptions.RequestException as e:
        logger.info(f'Failed to change proxy due to {str(e)}')
        return False


def get_proxy_current():
    """
    Return:
        获取当前的代理名称

    proxy_now:
        string
    """
    # Set up a session with retries
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504]) # noqa
    session.mount('http://', HTTPAdapter(max_retries=retries))

    data = fetch_proxis(session)
    d_proxies = data.get('proxies', {})

    d_selector = d_proxies['Proxy']
    proxy_now = d_selector['now']

    return proxy_now


def get_proxy_list(s_mode):
    """
    Return:
        (proxy_now, lst_available)

    proxy_now:
        string
    lst_available:
        [[proxy_name, mean_delay], [proxy_name, mean_delay]]
    """
    # Set up a session with retries
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504]) # noqa
    session.mount('http://', HTTPAdapter(max_retries=retries))

    data = fetch_proxis(session)
    if data is None:
        return (None, [])

    d_proxies = data.get('proxies', {})
    d_selector = d_proxies['GLOBAL']
    # proxy_now = d_proxies['节点选择']['now']
    proxy_now = d_proxies[s_mode]['now']
    lst_proxy = d_selector['all']

    lst_available = []
    for proxy_name in lst_proxy:
        if proxy_name == 'Auto':
            continue
        if proxy_name.startswith('Valid until'):
            continue
        if proxy_name in d_proxies:
            lst_history = d_proxies[proxy_name]['history']
            if len(lst_history) >= 1:
                # ClashX API
                # mean_delay = lst_history[-1]['meanDelay']

                # Clash Verge
                mean_delay = lst_history[-1]['delay']

                # 过滤延迟是0的记录
                if mean_delay < 1:
                    continue
                lst_available.append([proxy_name, mean_delay])
            else:
                # print(proxy_name)
                pass

    # 使用列表的 sort 方法进行排序
    lst_available.sort(key=lambda x: x[1])

    # 打印排序后的列表
    logger.info(f'proxy_now: {proxy_now}')
    for proxy_name, mean_delay in lst_available:
        logger.info(f'{proxy_name} mean_delay:{mean_delay}')

    return (proxy_now, lst_available)


def set_proxy(proxy_dest):
    """
    proxy_dest: destination proxy_name
    """
    # Set up a session with retries
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504]) # noqa
    session.mount('http://', HTTPAdapter(max_retries=retries))

    s_mode = get_mode(session)

    (proxy_now, lst_available) = get_proxy_list(s_mode)
    if proxy_now == proxy_dest:
        logger.info(f'Not change. proxy_old:{proxy_now}, proxy_new:{proxy_dest}') # noqa
    else:
        b_success = put_proxy(s_mode, proxy_dest, session)
        if b_success:
            logger.info(f'Set proxy success. From {proxy_now} to {proxy_dest}')
            return True
        else:
            logger.info(f'Set proxy fail. From {proxy_now} to {proxy_dest}')
            return False

    return True


def change_proxy(black_list=[]):
    """
    black_list: proxy_name black list
    切换成功，返回新的切换后的代理名称
    切换失败，返回当前未切换的代理名称
    """
    # Set up a session with retries
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504]) # noqa
    session.mount('http://', HTTPAdapter(max_retries=retries))

    proxy_dest = ''

    s_mode = get_mode(session)

    (proxy_now, lst_available) = get_proxy_list(s_mode)
    for (s_proxy, mean_delay) in lst_available:
        if s_proxy == proxy_now:
            continue
        if s_proxy in black_list:
            continue
        proxy_dest = s_proxy
        break

    b_success = put_proxy(s_mode, proxy_dest, session)
    logger.info(f'proxy_old:{proxy_now}, proxy_new:{proxy_dest}')

    if b_success:
        return proxy_dest
    else:
        return proxy_now


def main(args):
    """
    """
    if args.get_proxy_list:
        get_proxy_list()
    elif args.set_proxy:
        set_proxy(args.proxy_name)
    elif args.change_proxy:
        change_proxy()
    else:
        print('Usage: python {} -h'.format(sys.argv[0]))


if __name__ == '__main__':
    """
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--get_proxy_list', required=False, action='store_true',
        help='获取 proxy 列表及延迟'
    )
    parser.add_argument(
        '--change_proxy', required=False, action='store_true',
        help='选择 proxy'
    )
    parser.add_argument(
        '--set_proxy', required=False, action='store_true',
        help='Set proxy'
    )
    parser.add_argument(
        '--proxy_name', required=False, default='',
        help='Destination proxy_name'
    )

    args = parser.parse_args()
    main(args)
