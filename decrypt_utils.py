#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
解密CSV文件工具

这个模块提供了解密加密CSV文件的功能。
主要用于解密encrypted_add.csv文件,返回原始DataFrame数据。

"""

import pandas as pd
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2 import PasswordHasher
from argon2.profiles import RFC_9106_HIGH_MEMORY
import json
from cryptography.exceptions import InvalidTag
from io import StringIO


def read_encrypted_file(file_path: str) -> tuple[bytes, bytes, bytes]:
    """
    读取加密文件,提取salt、nonce和密文
    
    Args:
        file_path: 加密文件的路径
        
    Returns:
        tuple[bytes, bytes, bytes]: (salt, nonce, ciphertext)元组
        
    Raises:
        ValueError: 当文件格式不正确时
    """
    try:
        with open(file_path, 'rb') as f:
            # 读取16字节的salt
            salt = f.read(16)
            if len(salt) != 16:
                raise ValueError("文件格式错误: salt长度不正确")
                
            # 读取12字节的nonce
            nonce = f.read(12)
            if len(nonce) != 12:
                raise ValueError("文件格式错误: nonce长度不正确")
                
            # 读取剩余的密文(包含GCM认证标签)
            ciphertext = f.read()
            if len(ciphertext) < 16:  # 至少要包含16字节的认证标签
                raise ValueError("文件格式错误: 密文长度不正确")
                
        print("已读取加密文件中的salt和nonce")
        return salt, nonce, ciphertext
        
    except Exception as e:
        print(f"读取加密文件时发生错误: {str(e)}")
        raise

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
    try:
        # 创建Argon2id实例,使用高内存配置
        ph = PasswordHasher.from_parameters(RFC_9106_HIGH_MEMORY)
        
        # 使用Argon2id派生密钥
        hash = ph.hash(password)
        
        # 从hash中提取32字节作为AES密钥
        key = hash.encode()[:32]
        
        print("已使用Argon2id派生AES密钥")
        return key
        
    except Exception as e:
        print(f"密钥派生过程发生错误: {str(e)}")
        raise

def decrypt_data(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """
    使用AES-256-GCM解密数据
    
    Args:
        key: 32字节的AES-256密钥
        nonce: 12字节的nonce
        ciphertext: 加密的数据(包含GCM认证标签)
        
    Returns:
        bytes: 解密后的数据
        
    Raises:
        InvalidTag: 当密码错误或数据被篡改时
    """
    try:
        # 创建AESGCM实例
        aesgcm = AESGCM(key)
        
        # 解密数据(GCM模式会自动验证认证标签)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        print("已使用AES-256-GCM解密数据")
        return plaintext
        
    except InvalidTag:
        print("解密失败: 密码错误或数据被篡改")
        raise
    except Exception as e:
        print(f"解密过程发生错误: {str(e)}")
        raise

def bytes_to_dataframe(data: bytes) -> pd.DataFrame:
    """
    将解密后的二进制数据转换为DataFrame
    
    Args:
        data: 解密后的二进制数据
        
    Returns:
        pd.DataFrame: 转换后的DataFrame
        
    Raises:
        ValueError: 当数据格式不正确或转换失败时
    """
    try:
        # 将二进制数据解码为JSON字符串
        json_str = data.decode()
        
        # 将JSON字符串转换为DataFrame
        df = pd.read_json(StringIO(json_str))
        
        if df.empty:
            raise ValueError("解密后的数据为空")
            
        print("已将解密数据转换为DataFrame")
        return df
        
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {str(e)}")
        raise ValueError("解密后的数据不是有效的JSON格式")
    except Exception as e:
        print(f"数据转换过程发生错误: {str(e)}")
        raise

def decrypt_csv(file_path: str, password: str) -> pd.DataFrame:
    """
    解密加密的CSV文件并返回DataFrame
    
    Args:
        file_path: 加密文件的路径
        password: 解密密码
        
    Returns:
        pd.DataFrame: 解密后的DataFrame数据
        
    Raises:
        FileNotFoundError: 当文件不存在时
        ValueError: 当密码错误或文件格式不正确时
        Exception: 其他解密错误
    """
    try:
        # 检查文件是否存在
        if not Path(file_path).exists():
            raise FileNotFoundError(f"文件 {file_path} 不存在")
            
        # 读取salt和nonce
        salt, nonce, ciphertext = read_encrypted_file(file_path)
            
        # 派生密钥
        key = derive_key(password, salt)
        
        # 解密数据
        plaintext = decrypt_data(key, nonce, ciphertext)
            
        # 转换为DataFrame
        df = bytes_to_dataframe(plaintext)
        
        return df
        
    except InvalidTag:
        raise ValueError("解密失败: 密码错误或数据被篡改")
    except Exception as e:
        print(f"解密文件时发生错误: {str(e)}")
        raise 