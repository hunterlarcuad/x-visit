from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

app = Flask(__name__)

# 全局变量存储进程信息
current_process: Optional[subprocess.Popen] = None
process_logs = []
process_status = "stopped"
process_start_time = None
current_config = {}
last_used_config = {}  # 记录最后使用的配置

# 配置文件路径
CONFIGS_DIR = "configs"
CONFIG_FILE = os.path.join(CONFIGS_DIR, "xwool-configs.json")

# 确保配置目录存在
os.makedirs(CONFIGS_DIR, exist_ok=True)

# 从配置文件加载最后使用的配置
def load_last_used_config():
    """从配置文件加载最后使用的配置"""
    global last_used_config
    try:
        configs = load_configs()
        if 'last_used_config' in configs:
            last_used_config = configs['last_used_config'].get('config', {})
            app.logger.info(f"已从配置文件加载最后使用的配置: {last_used_config}")
        else:
            app.logger.info("配置文件中没有找到最后使用的配置")
    except Exception as e:
        app.logger.error(f"加载最后使用的配置失败: {e}")

# 保存最后使用的配置到文件
def save_last_used_config(config):
    """保存最后使用的配置到文件"""
    try:
        configs = load_configs()
        configs['last_used_config'] = {
            'name': 'last_used_config',
            'config': config,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        save_configs(configs)
        app.logger.info(f"已保存最后使用的配置到文件: {config}")
    except Exception as e:
        app.logger.error(f"保存最后使用的配置失败: {e}")


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """保存配置"""
    try:
        data = request.get_json()
        config_name = data.get('name', f'config_{int(time.time())}')
        
        # 保存配置到文件
        configs = load_configs()
        configs[config_name] = {
            'name': config_name,
            'config': data.get('config', {}),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        save_configs(configs)
        return jsonify({'success': True, 'message': '配置保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500

@app.route('/api/config/list', methods=['GET'])
def list_configs():
    """获取配置列表"""
    try:
        configs = load_configs()
        return jsonify({'success': True, 'configs': configs})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'}), 500

@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    """获取特定配置"""
    try:
        configs = load_configs()
        if config_name in configs:
            return jsonify({'success': True, 'config': configs[config_name]})
        else:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'}), 500

@app.route('/api/script/start', methods=['POST'])
def start_script():
    """启动脚本"""
    global current_process, process_status, process_start_time, current_config, last_used_config
    
    try:
        data = request.get_json()
        app.logger.info(f"接收到的启动请求数据: {data}")
        config = data.get('config', {})
        app.logger.info(f"提取的配置: {config}")
        
        if current_process and current_process.poll() is None:
            return jsonify({'success': False, 'message': '脚本已在运行中'}), 400
        
        # 构建命令
        cmd = ['python', 'xwool.py']
        app.logger.info(f"初始命令: {cmd}")
        
        # 添加参数
        for key, value in config.items():
            if value is not None and value != '':
                if isinstance(value, bool):
                    if value:
                        cmd.append(f'--{key}')
                        app.logger.info(f"添加布尔参数: --{key}")
                else:
                    cmd.append(f'--{key}')
                    cmd.append(str(value))
                    app.logger.info(f"添加参数: --{key} {value}")
        
        app.logger.info(f"最终命令: {cmd}")
        
        # 启动进程
        current_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 记录启动时间和配置
        process_start_time = datetime.now()
        current_config = config
        process_status = "running"
        process_logs.clear()
        last_used_config = config # 记录最后使用的配置
        
        # 保存最后使用的配置到文件
        save_last_used_config(config)
        
        # 启动日志收集线程
        threading.Thread(target=collect_logs, daemon=True).start()
        
        return jsonify({'success': True, 'message': '脚本启动成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'}), 500

@app.route('/api/script/stop', methods=['POST'])
def stop_script():
    """停止脚本"""
    global current_process, process_status
    
    try:
        if current_process and current_process.poll() is None:
            # 终止主进程
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_process.kill()
            
            # 终止相关的Chromium进程
            import psutil
            try:
                # 读取配置文件中的端口号
                import importlib.util
                spec = importlib.util.spec_from_file_location("conf", "conf.py")
                conf = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(conf)
                debug_port = conf.DEF_LOCAL_PORT
                
                # 查找并终止Chromium进程
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info['cmdline']
                        if cmdline and any('chromium' in arg.lower() or 'chrome' in arg.lower() for arg in cmdline):
                            # 检查是否是我们的调试端口
                            if any(f'--remote-debugging-port={debug_port}' in arg for arg in cmdline):
                                app.logger.info(f"终止Chromium进程: {proc.info['pid']}")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception as e:
                app.logger.error(f"终止Chromium进程时出错: {e}")
            
            process_status = "stopped"
            return jsonify({'success': True, 'message': '脚本已停止'})
        else:
            return jsonify({'success': False, 'message': '没有运行中的脚本'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'}), 500

@app.route('/api/script/status', methods=['GET'])
def get_status():
    """获取脚本状态"""
    global current_process, process_status
    
    try:
        if current_process:
            if current_process.poll() is None:
                process_status = "running"
            else:
                process_status = "stopped"
        
        return jsonify({
            'success': True,
            'status': process_status,
            'pid': current_process.pid if current_process else None
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取状态失败: {str(e)}'}), 500

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    try:
        import csv
        accounts = []
        account_data = {}
        csv_file = 'datas/account/x_account.csv'
        
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    account = row['account']
                    # 避免重复添加账号
                    if account not in accounts:
                        accounts.append(account)
                        # 保存账号的完整信息
                        account_data[account] = {
                            'account': account,
                            'x_username': row.get('x_username', ''),
                            'x_pwd': row.get('x_pwd', ''),
                            'x_verifycode': row.get('x_verifycode', ''),
                            'proxy': row.get('proxy', '')
                        }
        
        return jsonify({
            'success': True,
            'accounts': accounts,
            'account_data': account_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取账号列表失败: {str(e)}'}), 500

@app.route('/api/account-status', methods=['GET'])
def get_account_status():
    """获取账号状态列表"""
    try:
        import csv
        from datetime import datetime
        import pytz
        
        status_data = []
        csv_file = 'datas/status/x_status.csv'
        account_file = 'datas/account/x_account.csv'
        
        # 读取账号信息（包含代理）
        account_proxies = {}
        if os.path.exists(account_file):
            with open(account_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    account_proxies[row.get('account', '')] = row.get('proxy', '')
        
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    account_name = row.get('account', '')
                    
                    # 解析更新时间
                    update_time_str = row.get('update_time', '')
                    days_ago = '未知'
                    
                    if update_time_str and update_time_str != 'None':
                        try:
                            # 解析时间字符串
                            if '+' in update_time_str:
                                # 格式: 2025-08-31T14:23:46+0800
                                dt = datetime.strptime(update_time_str, '%Y-%m-%dT%H:%M:%S%z')
                            else:
                                # 格式: 2025-08-31 14:23:46
                                dt = datetime.strptime(update_time_str, '%Y-%m-%d %H:%M:%S')
                                # 假设是本地时间
                                dt = pytz.timezone('Asia/Shanghai').localize(dt)
                            
                            # 计算天数差
                            now = datetime.now(pytz.timezone('Asia/Shanghai'))
                            delta = now - dt
                            days = delta.days
                            
                            if days == 0:
                                days_ago = '今天'
                            elif days == 1:
                                days_ago = '1天前'
                            elif days < 7:
                                days_ago = f'{days}天前'
                            elif days < 30:
                                days_ago = f'{days//7}周前'
                            else:
                                days_ago = f'{days//30}个月前'
                                
                        except Exception as e:
                            app.logger.error(f"解析时间失败: {update_time_str}, 错误: {e}")
                            days_ago = '时间解析错误'
                    
                    status_data.append({
                        'account': account_name,
                        'status': row.get('status', ''),
                        'update_time': update_time_str,
                        'days_ago': days_ago,
                        'visit_date': row.get('visit_date', ''),
                        'num_visit': row.get('num_visit', ''),
                        'auth_token': row.get('auth_token', ''),
                        'proxy': account_proxies.get(account_name, '')
                    })
        
        return jsonify({
            'success': True,
            'status_data': status_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取账号状态失败: {str(e)}'}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    try:
        return jsonify({
            'success': True,
            'logs': process_logs[-100:],  # 只返回最近100条日志
            'last_log': process_logs[-1] if process_logs else '',
            'waiting_for_input': process_logs[-1].find('Please select vpn') != -1 if process_logs else False
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取日志失败: {str(e)}'}), 500

@app.route('/api/logs/server', methods=['GET'])
def get_server_logs():
    """获取server.log内容"""
    try:
        log_file = 'server.log'
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 返回最近100行
                return jsonify({
                    'success': True,
                    'logs': lines[-100:]
                })
        else:
            return jsonify({
                'success': True,
                'logs': ['server.log文件不存在']
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取server.log失败: {str(e)}'}), 500


@app.route('/api/script/input-status', methods=['GET'])
def get_input_status():
    """检查脚本是否需要输入"""
    try:
        # 检查run.log文件的最后一行
        run_log_file = 'run.log'
        if os.path.exists(run_log_file):
            with open(run_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # 严格检查是否包含 "Please select vpn"
                    waiting_for_input = 'Please select vpn' in last_line
                    
                    # 只在等待输入时记录日志，避免日志污染
                    if waiting_for_input:
                        app.logger.info(f"检测到脚本等待输入 - 最后一行: '{last_line}'")
                    
                    return jsonify({
                        'success': True,
                        'waiting_for_input': waiting_for_input,
                        'last_line': last_line,
                        'debug_info': {
                            'contains_vpn_prompt': 'Please select vpn' in last_line,
                            'line_length': len(last_line)
                        }
                    })
        
        return jsonify({
            'success': True,
            'waiting_for_input': False,
            'last_line': '',
            'debug_info': {
                'contains_vpn_prompt': False,
                'line_length': 0
            }
        })
    except Exception as e:
        app.logger.error(f"检查输入状态失败: {e}")
        return jsonify({'success': False, 'message': f'检查输入状态失败: {str(e)}'}), 500

@app.route('/api/logs/run', methods=['GET'])
def get_run_logs():
    """获取run.log内容"""
    try:
        log_file = 'run.log'
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 返回最近100行
                return jsonify({
                    'success': True,
                    'logs': lines[-100:]
                })
        else:
            return jsonify({
                'success': True,
                'logs': ['run.log文件不存在']
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取run.log失败: {str(e)}'}), 500

@app.route('/api/script/input', methods=['POST'])
def send_input():
    """向脚本发送输入"""
    global current_process
    
    try:
        data = request.get_json()
        user_input = data.get('input', '')
        
        if current_process and current_process.poll() is None:
            # 发送输入到进程
            current_process.stdin.write(user_input + '\n')
            current_process.stdin.flush()
            return jsonify({'success': True, 'message': '输入已发送'})
        else:
            return jsonify({'success': False, 'message': '没有运行中的脚本'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'发送输入失败: {str(e)}'}), 500

@app.route('/api/script/cleanup', methods=['POST'])
def cleanup_processes():
    """清理残留的Chromium进程"""
    try:
        import psutil
        killed_count = 0
        
        # 读取配置文件中的端口号
        import importlib.util
        spec = importlib.util.spec_from_file_location("conf", "conf.py")
        conf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conf)
        debug_port = conf.DEF_LOCAL_PORT
        
        # 查找并终止Chromium进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('chromium' in arg.lower() or 'chrome' in arg.lower() for arg in cmdline):
                    # 检查是否是我们的调试端口
                    if any(f'--remote-debugging-port={debug_port}' in arg for arg in cmdline):
                        app.logger.info(f"清理Chromium进程: {proc.info['pid']}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return jsonify({
            'success': True, 
            'message': f'清理完成，终止了 {killed_count} 个Chromium进程'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'清理失败: {str(e)}'}), 500

@app.route('/api/script/chromium-count', methods=['GET'])
def get_chromium_count():
    """获取当前Chromium进程数量"""
    try:
        import psutil
        
        # 读取配置文件中的端口号
        import importlib.util
        spec = importlib.util.spec_from_file_location("conf", "conf.py")
        conf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conf)
        debug_port = conf.DEF_LOCAL_PORT
        
        count = 0
        # 查找Chromium进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('chromium' in arg.lower() or 'chrome' in arg.lower() for arg in cmdline):
                    # 检查是否是我们的调试端口
                    if any(f'--remote-debugging-port={debug_port}' in arg for arg in cmdline):
                        count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取进程数量失败: {str(e)}'}), 500

@app.route('/api/script/running-info', methods=['GET'])
def get_running_info():
    """获取当前运行脚本的详细信息"""
    global current_process, process_status, process_start_time, current_config
    
    try:
        if current_process and current_process.poll() is None:
            # 计算运行时长
            if process_start_time:
                runtime = datetime.now() - process_start_time
                # 格式化运行时长
                total_seconds = int(runtime.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                if hours > 0:
                    runtime_str = f"{hours}小时{minutes}分钟{seconds}秒"
                elif minutes > 0:
                    runtime_str = f"{minutes}分钟{seconds}秒"
                else:
                    runtime_str = f"{seconds}秒"
            else:
                runtime_str = "未知"
            
            # 构建完整命令
            cmd = ['python', 'xwool.py']
            for key, value in current_config.items():
                if value is not None and value != '':
                    if isinstance(value, bool):
                        if value:
                            cmd.append(f'--{key}')
                    else:
                        cmd.append(f'--{key}')
                        cmd.append(str(value))
            
            # 参数说明映射
            param_descriptions = {
                'profile': '账号',
                'max_interactions': '最大互动次数',
                'headless': '无头模式',
                'force': '强制运行',
                'water': '浇水模式',
                'ad_user': '追星模式',
                'vpn_auto': '自动切换VPN',
                'no_auto_vpn': '跳过VPN设置',
                'vpn_manual': '手动设置VPN',
                'loop_interval': '循环间隔(秒)',
                'sleep_sec_min': '最小休眠时间(秒)',
                'sleep_sec_max': '最大休眠时间(秒)',
                'auto_like': '自动点赞',
                'auto_follow': '自动关注',
                'auto_retweet': '自动转发',
                'auto_reply': '自动回复'
            }
            
            # 生成参数说明
            param_explanations = []
            for key, value in current_config.items():
                if value is not None and value != '':
                    desc = param_descriptions.get(key, key)
                    if isinstance(value, bool):
                        if value:
                            param_explanations.append(f"{desc}: 启用")
                    else:
                        param_explanations.append(f"{desc}: {value}")
            
            return jsonify({
                'success': True,
                'data': {
                    'status': 'running',
                    'account': current_config.get('profile', '未知'),
                    'full_command': ' '.join(cmd),
                    'parameters': param_explanations,
                    'start_time': process_start_time.isoformat() if process_start_time else None,
                    'runtime': runtime_str,
                    'pid': current_process.pid
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'status': 'stopped',
                    'account': None,
                    'full_command': None,
                    'parameters': [],
                    'start_time': None,
                    'runtime': None,
                    'pid': None
                }
            })
    except Exception as e:
        app.logger.error(f"获取运行信息失败: {e}")
        return jsonify({'success': False, 'message': f'获取运行信息失败: {str(e)}'}), 500

@app.route('/api/config/last-used', methods=['GET'])
def get_last_used_config():
    """获取最后使用的配置"""
    global last_used_config
    
    try:
        return jsonify({
            'success': True, 
            'config': last_used_config
        })
    except Exception as e:
        app.logger.error(f"获取最后使用配置失败: {e}")
        return jsonify({'success': False, 'message': f'获取最后使用配置失败: {str(e)}'}), 500

@app.route('/api/config/update-last-used', methods=['POST'])
def update_last_used_config():
    """更新最后使用的配置"""
    global last_used_config
    
    try:
        data = request.get_json()
        config = data.get('config', {})
        
        # 更新最后使用的配置
        last_used_config = config
        
        # 保存最后使用的配置到文件
        save_last_used_config(config)
        
        app.logger.info(f"更新最后使用配置: {config}")
        
        return jsonify({
            'success': True, 
            'message': '配置已更新'
        })
    except Exception as e:
        app.logger.error(f"更新最后使用配置失败: {e}")
        return jsonify({'success': False, 'message': f'更新最后使用配置失败: {str(e)}'}), 500

@app.route('/api/proxy/current-info', methods=['GET'])
def get_current_proxy_info():
    """获取当前代理信息"""
    try:
        # 导入proxy_api模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("proxy_api", "proxy_api.py")
        proxy_api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proxy_api)
        
        # 调用get_country_info函数
        success, result = proxy_api.get_country_info()
        
        if success:
            country, country_code, ip = result
            return jsonify({
                'success': True,
                'data': {
                    'country': country,
                    'country_code': country_code,
                    'ip': ip
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': str(result)
            }), 500
    except Exception as e:
        app.logger.error(f"获取代理信息失败: {e}")
        return jsonify({'success': False, 'message': f'获取代理信息失败: {str(e)}'}), 500


@app.route('/api/accounts/manage', methods=['GET'])
def get_accounts_for_management():
    """获取所有账号用于管理"""
    try:
        import csv
        account_file = 'datas/account/x_account.csv'
        if not os.path.exists(account_file):
            return jsonify({'accounts': [], 'error': '账号文件不存在'})
        
        accounts = []
        with open(account_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                accounts.append({
                    'account': row.get('account', ''),
                    'x_username': row.get('x_username', ''),
                    'x_pwd': row.get('x_pwd', ''),
                    'x_verifycode': row.get('x_verifycode', ''),
                    'proxy': row.get('proxy', '')
                })
        
        return jsonify({'success': True, 'accounts': accounts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/manage', methods=['POST'])
def add_account():
    """添加新账号"""
    try:
        import csv
        data = request.get_json()
        account = data.get('account', '').strip()
        x_username = data.get('x_username', '').strip()
        x_pwd = data.get('x_pwd', '').strip()
        x_verifycode = data.get('x_verifycode', '').strip()
        proxy = data.get('proxy', '').strip()
        
        if not account:
            return jsonify({'success': False, 'error': '账号名不能为空'})
        
        if not x_username:
            return jsonify({'success': False, 'error': '用户名不能为空'})
        
        account_file = 'datas/account/x_account.csv'
        
        # 检查账号是否已存在
        existing_accounts = []
        if os.path.exists(account_file):
            with open(account_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_accounts = [row['account'] for row in reader]
        
        if account in existing_accounts:
            return jsonify({'success': False, 'error': '账号已存在'})
        
        # 添加新账号
        new_account = {
            'account': account,
            'x_username': x_username,
            'x_pwd': x_pwd,
            'x_verifycode': x_verifycode,
            'proxy': proxy
        }
        
        # 写入文件
        fieldnames = ['account', 'x_username', 'x_pwd', 'x_verifycode', 'proxy']
        file_exists = os.path.exists(account_file)
        
        with open(account_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_account)
        
        return jsonify({'success': True, 'message': '账号添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/manage/<account>', methods=['PUT'])
def update_account(account):
    """更新账号信息"""
    try:
        import csv
        data = request.get_json()
        new_account = data.get('account', '').strip()
        x_username = data.get('x_username', '').strip()
        x_pwd = data.get('x_pwd', '').strip()
        x_verifycode = data.get('x_verifycode', '').strip()
        proxy = data.get('proxy', '').strip()
        
        if not new_account:
            return jsonify({'success': False, 'error': '账号名不能为空'})
        
        if not x_username:
            return jsonify({'success': False, 'error': '用户名不能为空'})
        
        account_file = 'datas/account/x_account.csv'
        if not os.path.exists(account_file):
            return jsonify({'success': False, 'error': '账号文件不存在'})
        
        # 读取所有账号
        accounts = []
        with open(account_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['account'] == account:
                    # 更新账号信息
                    row['account'] = new_account
                    row['x_username'] = x_username
                    row['x_pwd'] = x_pwd
                    row['x_verifycode'] = x_verifycode
                    row['proxy'] = proxy
                accounts.append(row)
        
        # 检查新账号名是否与其他账号冲突
        if new_account != account and any(acc['account'] == new_account for acc in accounts):
            return jsonify({'success': False, 'error': '账号名已存在'})
        
        # 写回文件
        fieldnames = ['account', 'x_username', 'x_pwd', 'x_verifycode', 'proxy']
        with open(account_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(accounts)
        
        return jsonify({'success': True, 'message': '账号更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/manage/<account>', methods=['DELETE'])
def delete_account(account):
    """删除账号"""
    try:
        import csv
        account_file = 'datas/account/x_account.csv'
        if not os.path.exists(account_file):
            return jsonify({'success': False, 'error': '账号文件不存在'})
        
        # 读取所有账号
        accounts = []
        with open(account_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['account'] != account:
                    accounts.append(row)
        
        # 写回文件
        fieldnames = ['account', 'x_username', 'x_pwd', 'x_verifycode', 'proxy']
        with open(account_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(accounts)
        
        return jsonify({'success': True, 'message': '账号删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def collect_logs():
    """收集日志的线程函数"""
    global current_process, process_logs
    
    if not current_process:
        return
    
    for line in iter(current_process.stdout.readline, ''):
        if line:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f'[{timestamp}] {line.strip()}'
            process_logs.append(log_entry)
            # 限制日志数量
            if len(process_logs) > 1000:
                process_logs = process_logs[-500:]

def load_configs():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_configs(configs):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    import logging
    from logging.handlers import RotatingFileHandler
    import sys
    import signal
    from werkzeug.serving import run_simple

    def signal_handler(signum, frame):
        """信号处理函数"""
        print("\n🔄 正在关闭Flask应用...")
        sys.exit(0)

    # 注册信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = RotatingFileHandler('server.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Flask应用启动')
    
    # 在Flask应用启动后加载配置
    load_last_used_config()

    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.propagate = False

    sys.stdout = open('server.log', 'a')
    sys.stderr = open('server.log', 'a')

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False) 