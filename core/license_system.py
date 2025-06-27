#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频上传助手 - 许可证系统
基于硬件指纹的软件授权机制
"""
import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta
import os
import time
import platform
import subprocess
import uuid

# 可选依赖的导入
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import cpuinfo
    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

class LicenseSystem:
    def __init__(self, secret_key="BILIBILI_UPLOADER_2025"):
        self.secret_key = secret_key.encode('utf-8')
        self._hardware_fp_cache = None  # 硬件指纹缓存
        self._cache_timestamp = 0       # 缓存时间戳
        self._cache_duration = 300      # 缓存5分钟
        
    def get_hardware_fingerprint(self):
        """获取硬件指纹（性能优化版本）- 智能缓存与快速检测"""
        # 检查缓存是否有效
        current_time = time.time()
        if (self._hardware_fp_cache and 
            current_time - self._cache_timestamp < self._cache_duration):
            return self._hardware_fp_cache
        
        hardware_components = []
        
        try:
            # 1. 获取CPU信息 - 性能优化版本
            try:
                cpu_info = platform.processor()
                if cpu_info and len(cpu_info.strip()) > 0:
                    hardware_components.append(f"CPU:{cpu_info[:50]}")
                else:
                    # 备用CPU信息获取 - 仅在必要时使用
                    if HAS_CPUINFO:
                        try:
                            cpu_info = cpuinfo.get_cpu_info().get('brand_raw', 'unknown')
                            hardware_components.append(f"CPU:{cpu_info[:50]}")
                        except:
                            hardware_components.append("CPU:unknown")
                    else:
                        hardware_components.append("CPU:unknown")
            except:
                hardware_components.append("CPU:unknown")
            
            # 2. 获取主板序列号 - 性能优化版本
            try:
                if platform.system() == "Windows":
                    # 使用单个最快的命令
                    try:
                        result = subprocess.run(
                            ['wmic', 'baseboard', 'get', 'serialnumber', '/format:list'],
                            capture_output=True, 
                            text=True, 
                            timeout=2,  # 减少到2秒
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        motherboard_info = "unknown"
                        if result.returncode == 0 and result.stdout:
                            lines = [line.strip() for line in result.stdout.strip().split('\n') 
                                    if line.strip() and '=' in line]
                            for line in lines:
                                if 'SerialNumber=' in line:
                                    value = line.split('=', 1)[1].strip()
                                    if value and value != "To be filled by O.E.M.":
                                        motherboard_info = value[:30]
                                        break
                        hardware_components.append(f"MB:{motherboard_info}")
                    except (subprocess.TimeoutExpired, Exception):
                        hardware_components.append("MB:unknown")
                else:
                    hardware_components.append("MB:unknown")
            except:
                hardware_components.append("MB:unknown")
            
            # 3. 获取硬盘信息 - 简化版本，只获取C盘信息
            try:
                if platform.system() == "Windows":
                    try:
                        result = subprocess.run(
                            ['wmic', 'logicaldisk', 'where', 'DeviceID="C:"', 'get', 'volumeserialnumber', '/format:list'], 
                            capture_output=True, 
                            text=True, 
                            timeout=1.5,  # 进一步减少超时时间
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        disk_info = "unknown"
                        if result.returncode == 0 and result.stdout:
                            lines = [line.strip() for line in result.stdout.strip().split('\n') 
                                    if line.strip() and '=' in line]
                            for line in lines:
                                if 'VolumeSerialNumber=' in line:
                                    value = line.split('=', 1)[1].strip()
                                    if value:
                                        disk_info = value[:20]
                                        break
                        hardware_components.append(f"DISK:{disk_info}")
                    except:
                        hardware_components.append("DISK:unknown")
                else:
                    hardware_components.append("DISK:unknown")
            except:
                hardware_components.append("DISK:unknown")
            
            # 4. 获取MAC地址（性能优化版本）
            try:
                mac = "unknown"
                if HAS_PSUTIL:
                    try:
                        # 快速获取MAC地址，只检查前几个接口
                        interfaces = psutil.net_if_addrs()
                        interface_count = 0
                        for interface, addrs in interfaces.items():
                            interface_count += 1
                            if interface_count > 3:  # 只检查前3个接口，提升性能
                                break
                                
                            # 跳过回环接口
                            if 'loopback' in interface.lower() or 'lo' in interface.lower():
                                continue
                            for addr in addrs:
                                if (hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK) or addr.family == 17:
                                    if addr.address and addr.address != '00:00:00:00:00:00':
                                        mac = addr.address
                                        break
                            if mac != "unknown":
                                break
                    except:
                        pass
                
                # 备用MAC获取方法
                if mac == "unknown":
                    try:
                        node = uuid.getnode()
                        mac = ':'.join(['{:02x}'.format((node >> elements) & 0xff) 
                                       for elements in range(0,2*6,2)][::-1])
                    except:
                        mac = "unknown"
                        
                hardware_components.append(f"MAC:{mac}")
            except:
                hardware_components.append("MAC:unknown")
            
            # 5. 获取系统信息（快速版本）
            try:
                system_info = f"{platform.system()}-{platform.release()}"
                hardware_components.append(f"SYS:{system_info[:30]}")
            except:
                hardware_components.append("SYS:unknown")
            
            # 6. 获取机器名（快速版本）
            try:
                machine_name = platform.node()[:20]
                hardware_components.append(f"NODE:{machine_name}")
            except:
                hardware_components.append("NODE:unknown")
            
            # 组合所有硬件信息
            hardware_info = "-".join(hardware_components)
            
            # 生成硬件指纹
            fingerprint = hashlib.sha256(hardware_info.encode('utf-8')).hexdigest()[:16].upper()
            
            # 更新缓存
            self._hardware_fp_cache = fingerprint
            self._cache_timestamp = current_time
            
            return fingerprint
            
        except Exception as e:
            print(f"获取硬件指纹失败: {e}")
            # 使用缓存的指纹（如果有）
            if self._hardware_fp_cache:
                return self._hardware_fp_cache
                
            # 最终备用方案：使用基础信息
            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                               for elements in range(0,2*6,2)][::-1])
                system_info = f"{platform.system()}-{platform.release()}"
                machine_name = platform.node()
                backup_info = f"{mac}-{system_info}-{machine_name}"
                fingerprint = hashlib.sha256(backup_info.encode('utf-8')).hexdigest()[:16].upper()
                
                # 更新缓存
                self._hardware_fp_cache = fingerprint
                self._cache_timestamp = current_time
                
                return fingerprint
            except:
                # 绝对备用方案
                fallback_info = f"FALLBACK-{int(time.time())//86400}"
                fingerprint = hashlib.sha256(fallback_info.encode('utf-8')).hexdigest()[:16].upper()
                
                # 更新缓存
                self._hardware_fp_cache = fingerprint
                self._cache_timestamp = current_time
                
                return fingerprint
    
    def generate_license(self, days=30, user_info="", target_hardware=""):
        """生成许可证"""
        try:
            # 获取硬件指纹
            if target_hardware and target_hardware.strip():
                hardware_fp = target_hardware.strip()
            else:
                hardware_fp = self.get_hardware_fingerprint()
            
            # 计算过期时间
            expire_date = datetime.now() + timedelta(days=days)
            expire_timestamp = int(expire_date.timestamp())
            
            # 创建许可证数据
            license_data = {
                'hardware': hardware_fp,
                'expire': expire_timestamp,
                'user': user_info,
                'version': '2.0',
                'product': 'B站视频上传助手'
            }
            
            # 转换为JSON字符串
            license_json = json.dumps(license_data, separators=(',', ':'))
            
            # 使用HMAC签名
            signature = hmac.new(
                self.secret_key, 
                license_json.encode('utf-8'), 
                hashlib.sha256
            ).hexdigest()
            
            # 组合许可证和签名
            full_license = f"{license_json}:{signature}"
            
            # Base64编码
            encoded_license = base64.b64encode(full_license.encode('utf-8')).decode('utf-8')
            
            # 格式化许可证（每40个字符一行）
            formatted_license = '\n'.join([encoded_license[i:i+40] 
                                         for i in range(0, len(encoded_license), 40)])
            
            return {
                'success': True,
                'license': formatted_license,
                'hardware_fp': hardware_fp,
                'expire_date': expire_date.strftime('%Y-%m-%d %H:%M:%S'),
                'days': days
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"生成许可证失败: {str(e)}"
            }
    
    def verify_license(self, license_text):
        """验证许可证"""
        try:
            # 移除换行符和空格
            clean_license = license_text.replace('\n', '').replace(' ', '').strip()
            
            # Base64解码
            try:
                decoded_license = base64.b64decode(clean_license).decode('utf-8')
            except:
                return {
                    'valid': False,
                    'error': "许可证格式错误"
                }
            
            # 分离许可证数据和签名
            if ':' not in decoded_license:
                return {
                    'valid': False,
                    'error': "许可证格式无效"
                }
            
            license_json, signature = decoded_license.rsplit(':', 1)
            
            # 验证签名
            expected_signature = hmac.new(
                self.secret_key, 
                license_json.encode('utf-8'), 
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return {
                    'valid': False,
                    'error': "许可证签名无效"
                }
            
            # 解析许可证数据
            try:
                license_data = json.loads(license_json)
            except:
                return {
                    'valid': False,
                    'error': "许可证数据格式错误"
                }
            
            # 检查必要字段
            required_fields = ['hardware', 'expire', 'version']
            for field in required_fields:
                if field not in license_data:
                    return {
                        'valid': False,
                        'error': f"许可证缺少必要字段: {field}"
                    }
            
            # 验证硬件指纹
            current_hardware = self.get_hardware_fingerprint()
            if license_data['hardware'] != current_hardware:
                return {
                    'valid': False,
                    'error': "硬件指纹不匹配，此许可证不适用于当前设备",
                    'current_hardware': current_hardware,
                    'license_hardware': license_data['hardware']
                }
            
            # 检查过期时间
            expire_timestamp = license_data['expire']
            current_timestamp = int(datetime.now().timestamp())
            
            if current_timestamp > expire_timestamp:
                expire_date = datetime.fromtimestamp(expire_timestamp)
                return {
                    'valid': False,
                    'error': f"许可证已过期，过期时间: {expire_date.strftime('%Y-%m-%d %H:%M:%S')}"
                }
            
            # 计算剩余天数
            remaining_seconds = expire_timestamp - current_timestamp
            remaining_days = remaining_seconds // (24 * 3600)
            
            expire_date = datetime.fromtimestamp(expire_timestamp)
            
            return {
                'valid': True,
                'hardware_fp': license_data['hardware'],
                'expire_date': expire_date.strftime('%Y-%m-%d %H:%M:%S'),
                'remaining_days': remaining_days,
                'user_info': license_data.get('user', ''),
                'version': license_data.get('version', '2.0'),
                'product': license_data.get('product', 'B站视频上传助手')
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"验证许可证时发生错误: {str(e)}"
            }
    
    def save_license_to_file(self, license_text, filename="license.key"):
        """保存许可证到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(license_text)
            return True
        except Exception as e:
            print(f"保存许可证失败: {e}")
            return False
    
    def load_license_from_file(self, filename="license.key"):
        """从文件加载许可证"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            return None
        except Exception as e:
            print(f"加载许可证失败: {e}")
            return None


def main():
    """主函数 - 用于测试和生成许可证"""
    license_system = LicenseSystem()
    
    print("=" * 60)
    print("B站视频上传助手 - 许可证系统")
    print("=" * 60)
    
    while True:
        print("\n请选择操作:")
        print("1. 生成许可证")
        print("2. 验证许可证")
        print("3. 查看当前硬件指纹")
        print("4. 从文件验证许可证")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-4): ").strip()
        
        if choice == '1':
            print("\n--- 生成许可证 ---")
            try:
                days = int(input("请输入有效天数 (默认30天): ") or "30")
                user_info = input("请输入用户信息 (可选): ").strip()
                
                result = license_system.generate_license(days, user_info)
                
                if result['success']:
                    print(f"\n✅ 许可证生成成功!")
                    print(f"硬件指纹: {result['hardware_fp']}")
                    print(f"过期时间: {result['expire_date']}")
                    print(f"有效天数: {result['days']}")
                    print(f"\n许可证内容:")
                    print("-" * 50)
                    print(result['license'])
                    print("-" * 50)
                    
                    # 询问是否保存到文件
                    save_choice = input("\n是否保存到文件? (y/n): ").strip().lower()
                    if save_choice == 'y':
                        filename = input("请输入文件名 (默认: license.key): ").strip() or "license.key"
                        if license_system.save_license_to_file(result['license'], filename):
                            print(f"✅ 许可证已保存到: {filename}")
                        else:
                            print("❌ 保存失败")
                else:
                    print(f"❌ {result['error']}")
                    
            except ValueError:
                print("❌ 请输入有效的天数")
            except Exception as e:
                print(f"❌ 生成失败: {e}")
        
        elif choice == '2':
            print("\n--- 验证许可证 ---")
            print("请粘贴许可证内容 (输入完成后按两次回车):")
            
            license_lines = []
            empty_count = 0
            while True:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    license_lines.append(line)
            
            license_text = '\n'.join(license_lines)
            
            if license_text.strip():
                result = license_system.verify_license(license_text)
                
                if result['valid']:
                    print("\n✅ 许可证验证成功!")
                    print(f"硬件指纹: {result['hardware_fp']}")
                    print(f"过期时间: {result['expire_date']}")
                    print(f"剩余天数: {result['remaining_days']}")
                    if result['user_info']:
                        print(f"用户信息: {result['user_info']}")
                    print(f"版本: {result['version']}")
                    print(f"产品: {result['product']}")
                else:
                    print(f"\n❌ 许可证验证失败: {result['error']}")
                    if 'current_hardware' in result:
                        print(f"当前硬件指纹: {result['current_hardware']}")
                        print(f"许可证硬件指纹: {result['license_hardware']}")
            else:
                print("❌ 未输入许可证内容")
        
        elif choice == '3':
            print("\n--- 当前硬件指纹 ---")
            hardware_fp = license_system.get_hardware_fingerprint()
            print(f"硬件指纹: {hardware_fp}")
            print("请将此硬件指纹提供给许可证生成者")
        
        elif choice == '4':
            print("\n--- 从文件验证许可证 ---")
            filename = input("请输入许可证文件名 (默认: license.key): ").strip() or "license.key"
            
            license_text = license_system.load_license_from_file(filename)
            if license_text:
                result = license_system.verify_license(license_text)
                
                if result['valid']:
                    print("\n✅ 许可证验证成功!")
                    print(f"硬件指纹: {result['hardware_fp']}")
                    print(f"过期时间: {result['expire_date']}")
                    print(f"剩余天数: {result['remaining_days']}")
                    if result['user_info']:
                        print(f"用户信息: {result['user_info']}")
                    print(f"版本: {result['version']}")
                    print(f"产品: {result['product']}")
                else:
                    print(f"\n❌ 许可证验证失败: {result['error']}")
            else:
                print(f"❌ 无法读取许可证文件: {filename}")
        
        elif choice == '0':
            print("\n再见!")
            break
        
        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    main() 