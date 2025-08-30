import sys
import logging # noqa
import argparse
import requests
import pdb # noqa
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from conf import DEF_CLASH_API_PORT
from conf import DEF_CLASH_API_SECRETKEY
from conf import logger

# IP检测API配置
IP_DETECTION_APIS = [
    {
        'name': 'ip.sb',
        'url': 'https://api.ip.sb/geoip',
        'timeout': 5,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json'
        },
        'parser': lambda data: {
            'country': data.get('country', 'Unknown'),
            'country_code': data.get('country_code', 'Unknown'),
            'ip': data.get('ip', 'Unknown'),
            'city': data.get('city', 'Unknown'),
            'region': data.get('region', 'Unknown')
        }
    },
    {
        'name': 'ip-api.com',
        'url': 'http://ip-api.com/json/',
        'timeout': 10,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        },
        'parser': lambda data: {
            'country': data.get('country', 'Unknown'),
            'country_code': data.get('countryCode', 'Unknown'),
            'ip': data.get('query', 'Unknown'),
            'city': data.get('city', 'Unknown'),
            'region': data.get('regionName', 'Unknown')
        }
    },
    {
        'name': 'ipapi.co',
        'url': 'https://ipapi.co/json/',
        'timeout': 8,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        },
        'parser': lambda data: {
            'country': data.get('country_name', 'Unknown'),
            'country_code': data.get('country_code', 'Unknown'),
            'ip': data.get('ip', 'Unknown'),
            'city': data.get('city', 'Unknown'),
            'region': data.get('region', 'Unknown')
        }
    },
    {
        'name': 'freegeoip.app',
        'url': 'https://freegeoip.app/json/',
        'timeout': 12,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        },
        'parser': lambda data: {
            'country': data.get('country_name', 'Unknown'),
            'country_code': data.get('country_code', 'Unknown'),
            'ip': data.get('ip', 'Unknown'),
            'city': data.get('city', 'Unknown'),
            'region': data.get('region_name', 'Unknown')
        }
    }
]


def get_ip_location(session=None, max_retries=2):
    """
    获取当前IP所在的国家或地区信息
    使用多接口备用方案，按优先级顺序尝试

    Args:
        session: requests.Session对象，如果为None则创建新的
        max_retries: 每个接口的最大重试次数

    Returns:
        tuple: (success, result_dict, api_used)
        - success: bool, 是否成功获取
        - result_dict: dict, 包含IP位置信息
        - api_used: str, 使用的API名称
    """
    if session is None:
        session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1, 
            status_forcelist=[502, 503, 504]
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

    for api_config in IP_DETECTION_APIS:
        api_name = api_config['name']
        api_url = api_config['url']
        timeout = api_config['timeout']
        parser = api_config['parser']

        logger.info(f'Trying IP detection API: {api_name}')

        for attempt in range(max_retries):
            try:
                # 使用配置中的请求头
                headers = api_config.get('headers', {})
                response = session.get(api_url, headers=headers, timeout=timeout)
                response.raise_for_status()

                # 检查响应类型
                content_type = response.headers.get('content-type', '').lower()

                if 'application/json' in content_type:
                    # JSON响应
                    data = response.json()
                    if not isinstance(data, dict):
                        logger.warning(f'{api_name}: Invalid JSON response format')
                        continue
                elif 'text/plain' in content_type or api_name == 'ip.sb-simple':
                    # 纯文本响应，尝试解析
                    text_content = response.text.strip()
                    logger.info(f'{api_name}: Got text response: {text_content}')

                    # 对于ip.sb-simple，直接使用国家名
                    if api_name == 'ip.sb-simple':
                        data = {'country': text_content, 'country_code': 'Unknown'}
                    else:
                        # 尝试解析其他可能的文本格式
                        data = {'country': text_content, 'country_code': 'Unknown'}
                else:
                    # 尝试JSON解析
                    try:
                        data = response.json()
                        if not isinstance(data, dict):
                            logger.warning(f'{api_name}: Invalid JSON response format')
                            continue
                    except:
                        logger.warning(f'{api_name}: Cannot parse response as JSON or text')
                        continue

                # 使用对应的解析器解析数据
                result = parser(data)

                # 验证必要字段
                if result['country'] == 'Unknown' or result['ip'] == 'Unknown':
                    logger.warning(f'{api_name}: Missing required fields')
                    continue

                logger.info(f'Successfully got IP location from {api_name}')
                return True, result, api_name

            except requests.exceptions.Timeout:
                logger.warning(
                    f'{api_name}: Timeout on attempt {attempt + 1}/{max_retries}'
                )
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f'{api_name}: Request failed on attempt '
                    f'{attempt + 1}/{max_retries}: {str(e)}'
                )
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

            except Exception as e:
                logger.warning(
                    f'{api_name}: Unexpected error on attempt '
                    f'{attempt + 1}/{max_retries}: {str(e)}'
                )
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

    # 所有API都失败了
    error_msg = 'All IP detection APIs failed'
    logger.error(error_msg)
    return False, {'error': error_msg}, 'none'


def get_country_info(session=None):
    """
    获取当前IP所在国家的简化版本
    只返回国家名称和代码

    Returns:
        tuple: (success, result_tuple)
        - success: bool, 是否成功
        - result_tuple: tuple, 格式为 (国家名, 国家代码, IP地址)
    """
    success, result, api_used = get_ip_location(session)

    if success:
        result_tuple = (result['country'], result['country_code'], result['ip'])
        logger.info(f'IP Country Info: [{result["country"]}] [{result["country_code"]}] [{result["ip"]}] [via {api_used}]')
        return True, result_tuple
    else:
        error_info = (
            f"Failed to get IP location: {result.get('error', 'Unknown error')}"
        )
        logger.error(error_info)
        return False, error_info


def check_proxy_location(proxy_name=None, session=None):
    """
    检查代理切换后的IP位置
    如果指定了proxy_name，会先切换到该代理再检测
    
    Args:
        proxy_name: 要切换到的代理名称，如果为None则使用当前代理
        session: requests.Session对象
        
    Returns:
        tuple: (success, location_info, proxy_used)
    """
    if session is None:
        session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1, 
            status_forcelist=[502, 503, 504]
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
    
    # 如果指定了代理名称，先切换代理
    if proxy_name:
        logger.info(f'Switching to proxy: {proxy_name}')
        if not set_proxy(proxy_name):
            return False, f"Failed to switch to proxy: {proxy_name}", None
        
        # 等待代理生效
        time.sleep(3)
    
    # 获取当前代理名称
    current_proxy = get_proxy_current()
    
    # 检测IP位置
    success, result, api_used = get_ip_location(session)
    
    if success:
        location_info = {
            'proxy': current_proxy,
            'country': result['country'],
            'country_code': result['country_code'],
            'ip': result['ip'],
            'city': result['city'],
            'region': result['region'],
            'api_used': api_used
        }
        logger.info(
            f'Proxy Location Check: {current_proxy} -> '
            f'{result["country"]}({result["country_code"]}) - {result["ip"]}'
        )
        return True, location_info, current_proxy
    else:
        return False, f"Failed to get location for proxy: {current_proxy}", current_proxy

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
        try:
            (proxy_now, lst_available) = get_proxy_list(s_mode)
        except:
            s_mode = 'Proxy'
            (proxy_now, lst_available) = get_proxy_list(s_mode)

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


def get_proxy_list(s_mode=None):
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

    if s_mode is None:
        s_mode = get_mode(session)

    data = fetch_proxis(session)
    if data is None:
        return (None, [])

    d_proxies = data.get('proxies', {})
    d_selector = d_proxies['GLOBAL']
    proxy_now = d_proxies[s_mode]['now']
    lst_proxy = d_selector['all']

    lst_available = []
    for proxy_name in lst_proxy:
        if proxy_name in ['Auto', 'DIRECT', 'REJECT', '节点选择']:
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
                mean_delay = -1
                lst_available.append([proxy_name, mean_delay])
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
    elif args.check_ip:
        # 检测当前IP位置
        success, result = get_country_info()
        if success:
            country_name, country_code, ip = result
            print(f"Current IP Location: {country_name}({country_code}) - IP: {ip}")
        else:
            print(f"Failed to get IP location: {result}")
    elif args.check_proxy_location:
        # 检测代理位置
        if args.proxy_name:
            success, location_info, proxy_used = check_proxy_location(args.proxy_name)
        else:
            success, location_info, proxy_used = check_proxy_location()
        
        if success:
            print(f"Proxy: {location_info['proxy']}")
            print(f"Country: {location_info['country']}({location_info['country_code']})")
            print(f"IP: {location_info['ip']}")
            print(f"City: {location_info['city']}")
            print(f"Region: {location_info['region']}")
            print(f"API Used: {location_info['api_used']}")
        else:
            print(f"Failed to check proxy location: {location_info}")
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
    parser.add_argument(
        '--check_ip', required=False, action='store_true',
        help='检查当前IP位置'
    )
    parser.add_argument(
        '--check_proxy_location', required=False, action='store_true',
        help='检查代理位置'
    )

    args = parser.parse_args()
    main(args)
