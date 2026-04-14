import pymysql
import pymysql.cursors
import time
import json
from datetime import datetime, timezone
from conf import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PWD, MYSQL_DB
from conf import logger

class DBManager:
    def __init__(self):
        self.host = MYSQL_HOST
        self.port = MYSQL_PORT
        self.user = MYSQL_USER
        self.password = MYSQL_PWD
        self.db = MYSQL_DB

    def get_conn(self, use_db=True):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.db if use_db else None,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            init_command='SET time_zone = "+00:00"'
        )

    def init_db(self):
        """初始化数据库和表（支持详细 Schema 和历史记录）"""
        # 1. 创建数据库
        conn = self.get_conn(use_db=False)
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db} CHARACTER SET utf8mb4")
            conn.commit()
        finally:
            conn.close()

        # 2. 创建表
        conn = self.get_conn(use_db=True)
        try:
            with conn.cursor() as cursor:
                # 用户相关记录表（及其对等历史表）
                sql_users_table = '''
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) NOT NULL,
                        user_url VARCHAR(1024),
                        nickname VARCHAR(255),
                        following_count INT DEFAULT -1,
                        follower_count INT DEFAULT -1,
                        description TEXT,
                        last_notice_time TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP NULL,
                        {extra_constraint}
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                '''
                
                # 创建主表和历史表
                cursor.execute(sql_users_table.format(table_name="x_users", extra_constraint="UNIQUE KEY uk_username (username)"))
                cursor.execute(sql_users_table.format(table_name="x_history_users", extra_constraint="INDEX idx_username (username)"))

                # 推文相关记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS x_tweets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tweet_url VARCHAR(1024) NOT NULL,
                        content TEXT,
                        tweet_publish_time TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP NULL,
                        UNIQUE KEY uk_tweet_url (tweet_url(255))
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                ''')

                # 回复相关记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS x_replies (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tweet_url VARCHAR(1024) NOT NULL,
                        reply_username VARCHAR(255),
                        reply_content TEXT,
                        reply_time TIMESTAMP NULL,
                        llm_replies_json TEXT,
                        llm_generated_at TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP NULL,
                        INDEX idx_tweet_url (tweet_url(255))
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                ''')

                # 队列表：用户队列
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS queue_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) NOT NULL,
                        priority INT DEFAULT 0,
                        status VARCHAR(20) DEFAULT 'PENDING',
                        retry_count INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP NULL,
                        INDEX idx_status_priority (status, priority DESC, created_at ASC)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                ''')

                # 队列表：推文队列
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS queue_tweets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tweet_url VARCHAR(1024) NOT NULL,
                        username VARCHAR(255),
                        nickname VARCHAR(255),
                        content TEXT,
                        is_white TINYINT(1) DEFAULT 0,
                        priority INT DEFAULT 0,
                        following_count INT DEFAULT -1,
                        followers_count INT DEFAULT -1,
                        status VARCHAR(20) DEFAULT 'PENDING',
                        retry_count INT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP NULL,
                        INDEX idx_status_priority (status, priority DESC, created_at ASC)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                ''')

            conn.commit()
            logger.info("Database initialized with detailed schema and history tables.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise e
        finally:
            conn.close()

    # --- 数据归档方法（含历史记录追踪逻辑） ---
    def add_user(self, user_data):
        """
        user_data: dict containing username, user_url, nickname, following_count, follower_count, description, last_notice_time
        """
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                # 1. 查找现有数据
                sql_find = "SELECT * FROM x_users WHERE username = %s AND deleted_at IS NULL"
                cursor.execute(sql_find, (user_data['username'],))
                old_data = cursor.fetchone()

                # 如果新简介为空且已有旧数据，则不更新简介字段（按需保留原数据）
                if old_data and not user_data.get('description'):
                    user_data['description'] = old_data.get('description')

                should_append_history = False
                if old_data:
                    # 2. 比对关键字段：昵称、关注数、粉丝数、简介
                    fields_to_compare = ['nickname', 'following_count', 'follower_count', 'description']
                    for field in fields_to_compare:
                        if str(old_data.get(field)) != str(user_data.get(field)):
                            should_append_history = True
                            break
                    
                    if should_append_history:
                        # 3. 产生变更，向 x_history_users 追加旧记录镜像
                        sql_history = """
                        INSERT INTO x_history_users (
                            username, user_url, nickname, following_count, follower_count, 
                            description, last_notice_time, created_at, updated_at, deleted_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_history, (
                            old_data['username'], old_data['user_url'], old_data['nickname'], 
                            old_data['following_count'], old_data['follower_count'], 
                            old_data['description'], old_data['last_notice_time'],
                            old_data['created_at'], old_data['updated_at'], old_data['deleted_at']
                        ))
                
                # 4. 更新或插入主表记录
                sql_main = """
                INSERT INTO x_users (
                    username, user_url, nickname, following_count, follower_count, 
                    description, last_notice_time
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    user_url=%s, nickname=%s, following_count=%s, 
                    follower_count=%s, description=%s, last_notice_time=%s
                """
                cursor.execute(sql_main, (
                    user_data['username'], user_data['user_url'], user_data['nickname'], 
                    user_data['following_count'], user_data['follower_count'], 
                    user_data['description'], user_data['last_notice_time'],
                    user_data['user_url'], user_data['nickname'], 
                    user_data['following_count'], user_data['follower_count'], 
                    user_data['description'], user_data['last_notice_time']
                ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"add_user (with history) error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def add_tweet(self, tweet_data):
        """
        tweet_data: dict containing tweet_url, content, tweet_publish_time
        """
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO x_tweets (tweet_url, content, tweet_publish_time) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE content=%s, tweet_publish_time=%s
                """
                cursor.execute(sql, (
                    tweet_data['tweet_url'], tweet_data['content'], tweet_data['tweet_publish_time'],
                    tweet_data['content'], tweet_data['tweet_publish_time']
                ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"add_tweet error: {e}")
            return False
        finally:
            conn.close()

    def add_reply(self, reply_data):
        """
        reply_data: dict containing tweet_url, reply_username, reply_content, reply_time, llm_replies_json, llm_generated_at
        """
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO x_replies (
                    tweet_url, reply_username, reply_content, reply_time, 
                    llm_replies_json, llm_generated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    reply_data['tweet_url'], reply_data['reply_username'], 
                    reply_data['reply_content'], reply_data['reply_time'], 
                    reply_data['llm_replies_json'], reply_data['llm_generated_at']
                ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"add_reply error: {e}")
            return False
        finally:
            conn.close()

    # --- 队列生产者方法 ---
    def push_user_queue(self, username, priority=0):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                # 1. 检查是否存在正在进行的相同任务
                check_status_sql = "SELECT id FROM queue_users WHERE username=%s AND status IN ('PENDING', 'PROCESSING') AND deleted_at IS NULL"
                cursor.execute(check_status_sql, (username,))
                if cursor.fetchone():
                    return True
                
                # 2. 检查 1 分钟内是否已经插入过（频率限制）
                check_rate_sql = "SELECT id FROM queue_users WHERE username=%s AND created_at > DATE_SUB(NOW(), INTERVAL 1 MINUTE) AND deleted_at IS NULL"
                cursor.execute(check_rate_sql, (username,))
                if cursor.fetchone():
                    logger.info(f"Skip pushing {username} to queue: Rate limit (1 min)")
                    return True
                
                sql = "INSERT INTO queue_users (username, priority) VALUES (%s, %s)"
                cursor.execute(sql, (username, priority))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"push_user_queue error: {e}")
            return False
        finally:
            conn.close()

    def push_tweet_queue(self, tweet_data, priority=0):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                check_sql = "SELECT id FROM queue_tweets WHERE tweet_url=%s AND status IN ('PENDING', 'PROCESSING') AND deleted_at IS NULL"
                cursor.execute(check_sql, (tweet_data['tw_url'],))
                if cursor.fetchone():
                    return True

                sql = """
                INSERT INTO queue_tweets (tweet_url, username, nickname, content, is_white, priority, following_count, followers_count) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    tweet_data['tw_url'], 
                    tweet_data['s_user'], 
                    tweet_data['nickname'], 
                    tweet_data['tw_text'], 
                    1 if tweet_data['is_white'] else 0,
                    priority,
                    tweet_data['n_following'],
                    tweet_data['n_followers']
                ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"push_tweet_queue error: {e}")
            return False
        finally:
            conn.close()

    # --- 队列消费者方法 (原子性) ---
    def pop_user_queue(self):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = """
                SELECT id, username FROM queue_users 
                WHERE status = 'PENDING' AND deleted_at IS NULL
                ORDER BY priority DESC, created_at ASC 
                LIMIT 1 FOR UPDATE SKIP LOCKED
                """
                cursor.execute(sql)
                row = cursor.fetchone()
                if row:
                    update_sql = "UPDATE queue_users SET status = 'PROCESSING' WHERE id = %s"
                    cursor.execute(update_sql, (row['id'],))
                    conn.commit()
                    return row
            return None
        except Exception as e:
            logger.error(f"pop_user_queue error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def pop_tweet_queue(self):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = """
                SELECT * FROM queue_tweets 
                WHERE status = 'PENDING' AND deleted_at IS NULL
                ORDER BY priority DESC, created_at ASC 
                LIMIT 1 FOR UPDATE SKIP LOCKED
                """
                cursor.execute(sql)
                row = cursor.fetchone()
                if row:
                    update_sql = "UPDATE queue_tweets SET status = 'PROCESSING' WHERE id = %s"
                    cursor.execute(update_sql, (row['id'],))
                    conn.commit()
                    return row
            return None
        except Exception as e:
            logger.error(f"pop_tweet_queue error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def finish_task(self, table_name, task_id, status='DONE'):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = f"UPDATE {table_name} SET status = %s WHERE id = %s"
                cursor.execute(sql, (status, task_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"finish_task error on {table_name}: {e}")
            return False
        finally:
            conn.close()

    def recover_stale_tasks(self, timeout_seconds=600):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                for table in ['queue_users', 'queue_tweets']:
                    sql_find = f"""
                    SELECT id, retry_count FROM {table} 
                    WHERE status = 'PROCESSING' AND deleted_at IS NULL
                    AND updated_at < DATE_SUB(NOW(), INTERVAL {timeout_seconds} SECOND)
                    """
                    cursor.execute(sql_find)
                    stale_tasks = cursor.fetchall()
                    
                    for task in stale_tasks:
                        if task['retry_count'] < 1:
                            sql_retry = f"UPDATE {table} SET status = 'PENDING', retry_count = retry_count + 1 WHERE id = %s"
                            cursor.execute(sql_retry, (task['id'],))
                            logger.info(f"Recovered stale task {task['id']} from {table} to PENDING (retry_count={task['retry_count'] + 1})")
                        else:
                            sql_fail = f"UPDATE {table} SET status = 'FAIL' WHERE id = %s"
                            cursor.execute(sql_fail, (task['id'],))
                            logger.warn(f"Stale task {task['id']} from {table} failed permanently after retry.")
                
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"recover_stale_tasks error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def cleanup_done_tasks(self, days=3):
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                for table in ['queue_users', 'queue_tweets']:
                    sql = f"""
                    DELETE FROM {table} 
                    WHERE status IN ('DONE', 'FAIL') 
                    AND updated_at < DATE_SUB(NOW(), INTERVAL {days} DAY)
                    """
                    cursor.execute(sql)
                conn.commit()
                logger.info(f"Cleaned up queue records older than {days} days.")
            return True
        except Exception as e:
            logger.error(f"cleanup_done_tasks error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

if __name__ == "__main__":
    db = DBManager()
    db.init_db()
