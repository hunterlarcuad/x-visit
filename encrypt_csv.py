#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
加密CSV文件工具

这个脚本用于加密包含私钥的CSV文件。
主要功能是将明文的add.csv文件加密为encrypted_add.csv。

"""

import pandas as pd
import sys
from pathlib import Path
import getpass
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
from argon2 import PasswordHasher
from argon2.profiles import RFC_9106_HIGH_MEMORY
import json
import argparse

def read_csv_file(file_path: str) -> pd.DataFrame:
    """
    读取CSV文件并返回DataFrame
    
    Args:
        file_path: CSV文件的路径
        
    Returns:
        pd.DataFrame: 包含CSV数据的DataFrame
        
    Raises:
        FileNotFoundError: 当文件不存在时
        pd.errors.EmptyDataError: 当文件为空时
    """
    try:
        # 检查文件是否存在
        if not Path(file_path).exists():
            raise FileNotFoundError(f"文件 {file_path} 不存在")
            
        # 读取CSV文件
        df = pd.read_csv(file_path)
        
        # 检查文件是否为空
        if df.empty:
            raise pd.errors.EmptyDataError("CSV文件是空的")
            
        return df
        
    except Exception as e:
        print(f"读取CSV文件时发生错误: {str(e)}")
        sys.exit(1)

def get_password() -> str:
    """
    安全地获取用户密码
    
    使用getpass模块实现密码输入时不显示字符,
    并进行基本的密码强度验证。
    
    Returns:
        str: 用户输入的密码
        
    Raises:
        ValueError: 当密码不符合要求时
    """
    while True:
        # 使用getpass隐藏密码输入
        password = getpass.getpass("请输入加密密码: ")
        confirm_password = getpass.getpass("请再次输入密码: ")
        
        # 检查密码匹配
        if password != confirm_password:
            print("两次输入的密码不匹配,请重试")
            continue
            
        # 检查密码长度
        if len(password) < 8:
            print("密码长度必须至少为8个字符,请重试")
            continue
            
        return password

def generate_salt_and_nonce() -> tuple[bytes, bytes]:
    """
    生成加密所需的salt和nonce
    
    使用操作系统提供的安全随机数生成器生成:
    - 16字节的salt用于密钥派生
    - 12字节的nonce用于AES-GCM加密
    
    Returns:
        tuple[bytes, bytes]: (salt, nonce)元组
    """
    # 生成16字节的salt
    salt = os.urandom(16)
    
    # 生成12字节的nonce
    nonce = os.urandom(12)
    
    print("已生成加密所需的salt和nonce")
    return salt, nonce

def derive_key(password: str, salt: bytes) -> bytes:
    """
    使用Argon2id从密码派生AES密钥
    
    Args:
        password: 用户输入的密码
        salt: 16字节的随机salt
        
    Returns:
        bytes: 32字节的AES-256密钥
        
    Note:
        使用RFC 9106推荐的高内存参数:
        - 内存大小: 2GB
        - 迭代次数: 3
        - 并行度: 4
    """
    # 创建Argon2id实例,使用高内存配置
    ph = PasswordHasher.from_parameters(RFC_9106_HIGH_MEMORY)
    
    # 使用Argon2id派生密钥
    hash = ph.hash(password)
    
    # 从hash中提取32字节作为AES密钥
    key = hash.encode()[:32]
    
    print("已使用Argon2id派生AES密钥")
    return key

def encrypt_data(data: pd.DataFrame, key: bytes, nonce: bytes) -> bytes:
    """
    使用AES-256-GCM加密DataFrame数据
    
    Args:
        data: 要加密的DataFrame
        key: 32字节的AES-256密钥
        nonce: 12字节的nonce
        
    Returns:
        bytes: 加密后的数据
        
    Note:
        1. 将DataFrame转换为JSON字符串
        2. 使用AES-256-GCM加密
        3. GCM模式会自动生成认证标签
    """
    try:
        # 将DataFrame转换为JSON字符串
        json_data = data.to_json()
        data_bytes = json_data.encode()
        
        # 创建AESGCM实例
        aesgcm = AESGCM(key)
        
        # 加密数据
        ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
        
        print("已使用AES-256-GCM加密数据")
        return ciphertext
        
    except Exception as e:
        print(f"加密数据时发生错误: {str(e)}")
        sys.exit(1)

def save_encrypted_file(salt: bytes, nonce: bytes, ciphertext: bytes, output_file: str):
    """
    将加密结果保存到文件
    
    按照以下格式保存:
    - salt (16 bytes)
    - nonce (12 bytes)
    - ciphertext
    - tag (16 bytes, 包含在ciphertext中)
    
    Args:
        salt: 16字节的salt
        nonce: 12字节的nonce
        ciphertext: 加密后的数据(包含GCM认证标签)
        output_file: 输出文件路径
    """
    try:
        with open(output_file, 'wb') as f:
            # 写入salt
            f.write(salt)
            # 写入nonce
            f.write(nonce)
            # 写入密文(包含tag)
            f.write(ciphertext)
            
        print(f"加密结果已保存到 {output_file}")
        
    except Exception as e:
        print(f"保存加密文件时发生错误: {str(e)}")
        sys.exit(1)

def delete_plaintext_file(file_path: str):
    """
    安全删除明文文件
    
    Args:
        file_path: 要删除的文件路径
    """
    try:
        # 检查文件是否存在
        if not Path(file_path).exists():
            print(f"明文文件 {file_path} 不存在,无需删除")
            return
            
        # 删除文件
        os.remove(file_path)
        print(f"已删除明文文件 {file_path}")
        
    except Exception as e:
        print(f"删除明文文件时发生错误: {str(e)}")
        sys.exit(1)

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="加密CSV文件工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-d", "--delete",
        action="store_true",
        help="加密完成后删除明文文件"
    )
    
    return parser.parse_args()

def main():
    """
    主函数
    """
    # 解析命令行参数
    args = parse_args()
    
    # 设置输入输出文件路径
    input_file = "add.csv"
    output_file = "encrypted_add.csv"
    
    try:
        # 读取CSV文件
        df = read_csv_file(input_file)
        print(f"成功读取CSV文件,共 {len(df)} 行数据")
        
        # 获取加密密码
        password = get_password()
        print("密码验证成功")
        
        # 生成salt和nonce
        salt, nonce = generate_salt_and_nonce()
        
        # 派生AES密钥
        key = derive_key(password, salt)
        
        # 加密数据
        ciphertext = encrypt_data(df, key, nonce)
        print(f"加密后数据大小: {len(ciphertext)} 字节")
        
        # 保存加密结果
        save_encrypted_file(salt, nonce, ciphertext, output_file)
        
        # 如果指定了删除选项,则删除明文文件
        if args.delete:
            delete_plaintext_file(input_file)
        
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 