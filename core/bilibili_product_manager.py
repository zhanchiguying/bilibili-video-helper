#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站带货商品管理器 - 自动化选品流程
"""

import re
import json
import requests
import time
from typing import Dict, List, Optional, Tuple, Any
from .logger import get_logger


class BilibiliProductManager:
    """B站带货商品管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # B站API地址
        self.distinguish_url = "https://cm.bilibili.com/dwp/api/web_api/v1/item/distinguish/urls"
        self.add_to_cart_url = "https://cm.bilibili.com/dwp/api/web_api/v1/selection/car/item/add"
        self.delete_from_cart_url = "https://cm.bilibili.com/dwp/api/web_api/v1/selection/car/item/delete"
        
        # 京东商品链接模板
        self.jd_item_url_template = "https://item.jd.com/{}.html"
        
        # 请求头
        self.headers = {
            'content-type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def extract_product_id_from_filename(self, filename: str) -> Optional[str]:
        """从视频文件名中提取商品ID"""
        try:
            # 匹配格式：65944106150----高端行李箱 谁能不爱.mp4
            # 提取开头的数字ID
            pattern = r'^(\d+)----'
            match = re.match(pattern, filename)
            
            if match:
                product_id = match.group(1)
                self.logger.info(f"从文件名 {filename} 提取到商品ID: {product_id}")
                return product_id
            else:
                self.logger.warning(f"文件名格式不匹配: {filename}")
                return None
                
        except Exception as e:
            self.logger.error(f"提取商品ID失败: {e}")
            return None
    
    def build_jd_url(self, product_id: str) -> str:
        """构建京东商品链接"""
        url = self.jd_item_url_template.format(product_id)
        self.logger.debug(f"构建京东链接: {url}")
        return url
    
    def distinguish_product(self, product_url: str, cookies: str) -> Tuple[bool, Optional[Dict]]:
        """
        验证商品是否在B站联盟库中
        
        Args:
            product_url: 京东商品链接
            cookies: B站登录cookie
            
        Returns:
            (是否成功, 商品信息)
        """
        try:
            headers = self.headers.copy()
            headers['cookie'] = cookies
            
            data = {
                "itemUrls": product_url
            }
            
            self.logger.info(f"验证商品: {product_url}")
            
            response = requests.post(
                self.distinguish_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('code') == 0:
                    data = result.get('data', {})
                    success_list = data.get('successList', [])
                    fail_list = data.get('failList', [])
                    
                    if success_list:
                        product_info = success_list[0]
                        self.logger.info(f"商品验证成功: {product_info.get('goodsName', '未知商品')}")
                        self.logger.info(f"价格: ¥{product_info.get('price', 0)}")
                        self.logger.info(f"佣金: ¥{product_info.get('commissionFee', 0)}")
                        return True, product_info
                    elif fail_list:
                        fail_info = fail_list[0]
                        error_msg = fail_info.get('distinguishTips', '验证失败')
                        self.logger.error(f"商品验证失败: {error_msg}")
                        return False, None
                    else:
                        self.logger.error("商品验证返回空结果")
                        return False, None
                else:
                    self.logger.error(f"API返回错误: {result.get('message', '未知错误')}")
                    return False, None
            else:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"商品验证异常: {e}")
            return False, None
    
    def add_to_selection_cart(self, product_info: Dict, cookies: str) -> bool:
        """
        将商品添加到选品车
        
        Args:
            product_info: 从distinguish_product获取的商品信息
            cookies: B站登录cookie
            
        Returns:
            是否添加成功
        """
        try:
            headers = self.headers.copy()
            headers['cookie'] = cookies
            
            # 构建请求数据
            goods_data = {
                "mid": product_info.get("mid"),
                "url": product_info.get("url"),
                "itemId": product_info.get("itemId"),
                "outerId": product_info.get("outerId"),
                "requestOuterId": product_info.get("requestOuterId"),
                "sourceType": product_info.get("sourceType"),
                "mainImgUrl": product_info.get("mainImgUrl"),
                "goodsName": product_info.get("goodsName"),
                "price": product_info.get("price"),
                "commissionType": product_info.get("commissionType"),
                "commissionRate": product_info.get("commissionRate"),
                "commissionFee": product_info.get("commissionFee"),
                "shopName": product_info.get("shopName"),
                "rewardInfo": product_info.get("rewardInfo"),
                "distinguishState": product_info.get("distinguishState"),
                "distinguishTips": product_info.get("distinguishTips"),
                "salesType": product_info.get("salesType"),
                "goodsDto": product_info.get("goodsDto"),
                "bestCommissionRate": product_info.get("bestCommissionRate"),
                "bestCommissionFee": product_info.get("bestCommissionFee"),
                "success": True
            }
            
            data = {
                "goods": [goods_data],
                "operateSource": 2,
                "bizExtraInfo": "",
                "fromType": 12
            }
            
            self.logger.info(f"添加商品到选品车: {product_info.get('goodsName', '未知商品')}")
            
            response = requests.post(
                self.add_to_cart_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('code') == 0:
                    infos = result.get('data', {}).get('infos', [])
                    if infos and infos[0].get('resCode') == 0:
                        self.logger.info(f"商品添加成功: {infos[0].get('resMsg', '操作成功')}")
                        return True
                    else:
                        error_msg = infos[0].get('resMsg', '添加失败') if infos else '添加失败'
                        self.logger.error(f"添加商品失败: {error_msg}")
                        return False
                else:
                    self.logger.error(f"API返回错误: {result.get('message', '未知错误')}")
                    return False
            else:
                self.logger.error(f"请求失败，状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"添加商品到选品车异常: {e}")
            return False
    
    def delete_from_selection_cart(self, item_ids: List[str], cookies: str) -> bool:
        """
        从选品车删除商品
        
        Args:
            item_ids: 要删除的商品ID列表
            cookies: B站登录cookie
            
        Returns:
            是否删除成功
        """
        try:
            headers = self.headers.copy()
            headers['cookie'] = cookies
            
            data = {
                "itemIds": item_ids
            }
            
            self.logger.info(f"从选品车删除商品: {item_ids}")
            
            response = requests.post(
                self.delete_from_cart_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 根据用户提供的示例，成功响应格式：
                # {"status": "success", "data": 1, "current_time": 1750678922068, "code": 0, "message": ""}
                if result.get('code') == 0 and result.get('status') == 'success':
                    self.logger.info(f"商品删除成功: {len(item_ids)} 个商品，影响行数: {result.get('data', 0)}")
                    return True
                else:
                    self.logger.error(f"删除商品API返回错误: code={result.get('code')}, message={result.get('message', '未知错误')}")
                    return False
            else:
                self.logger.error(f"删除请求失败，状态码: {response.status_code}, 响应: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除商品异常: {e}")
            return False
    
    def delete_single_item_from_cart(self, item_id: str, cookies: str) -> bool:
        """
        从选品车删除单个商品
        
        Args:
            item_id: 要删除的商品ID
            cookies: B站登录cookie
            
        Returns:
            是否删除成功
        """
        return self.delete_from_selection_cart([item_id], cookies)
    
    def process_video_file(self, filename: str, cookies: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        处理单个视频文件的带货商品
        
        Args:
            filename: 视频文件名
            cookies: B站登录cookie
            
        Returns:
            (是否处理成功, 错误信息, 商品ID)
        """
        try:
            # 1. 提取商品ID
            product_id = self.extract_product_id_from_filename(filename)
            if not product_id:
                return False, "无法从文件名提取商品ID", None
            
            # 2. 构建京东链接
            jd_url = self.build_jd_url(product_id)
            
            # 3. 验证商品
            success, product_info = self.distinguish_product(jd_url, cookies)
            if not success or product_info is None:
                return False, "商品验证失败，可能商品不在B站联盟库中或已下架", None
            
            # 4. 添加到选品车
            add_success = self.add_to_selection_cart(product_info, cookies)
            if not add_success:
                return False, "添加到选品车失败", None
            
            # 5. 获取商品ID用于后续操作
            item_id = product_info.get("itemId")
            
            self.logger.info(f"视频文件 {filename} 的带货商品处理完成，商品ID: {item_id}")
            return True, None, item_id
            
        except Exception as e:
            error_msg = f"处理视频文件异常: {e}"
            self.logger.error(error_msg)
            return False, error_msg, None
    
    def batch_process_video_files(self, filenames: List[str], cookies: str) -> Dict[str, Any]:
        """
        批量处理多个视频文件的带货商品
        
        Args:
            filenames: 视频文件名列表
            cookies: B站登录cookie
            
        Returns:
            处理结果统计
        """
        results = {
            'total': len(filenames),
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        self.logger.info(f"开始批量处理 {len(filenames)} 个视频文件的带货商品")
        
        for filename in filenames:
            try:
                success, error_msg, item_id = self.process_video_file(filename, cookies)
                
                detail = {
                    'filename': filename,
                    'success': success,
                    'error_msg': error_msg,
                    'item_id': item_id
                }
                results['details'].append(detail)
                
                if success:
                    results['success'] += 1
                    self.logger.info(f"✅ {filename} 处理成功，商品ID: {item_id}")
                else:
                    results['failed'] += 1
                    self.logger.error(f"❌ {filename} 处理失败: {error_msg}")
                
                # 请求间隔，避免频率限制
                time.sleep(1)
                
            except Exception as e:
                results['failed'] += 1
                error_msg = f"处理异常: {e}"
                detail = {
                    'filename': filename,
                    'success': False,
                    'error_msg': error_msg,
                    'item_id': None
                }
                results['details'].append(detail)
                self.logger.error(f"❌ {filename} 处理异常: {e}")
        
        self.logger.info(f"批量处理完成: 总数 {results['total']}, 成功 {results['success']}, 失败 {results['failed']}")
        return results
    
    def batch_delete_processed_items(self, processing_results: Dict[str, Any], cookies: str) -> bool:
        """
        批量删除已处理成功的商品
        
        Args:
            processing_results: batch_process_video_files的返回结果
            cookies: B站登录cookie
            
        Returns:
            是否删除成功
        """
        try:
            # 收集所有成功处理的商品ID
            item_ids = []
            for detail in processing_results.get('details', []):
                if detail.get('success') and detail.get('item_id'):
                    item_ids.append(detail['item_id'])
            
            if not item_ids:
                self.logger.warning("没有找到需要删除的商品ID")
                return True
            
            self.logger.info(f"准备删除 {len(item_ids)} 个已处理的商品")
            return self.delete_from_selection_cart(item_ids, cookies)
            
        except Exception as e:
            self.logger.error(f"批量删除已处理商品异常: {e}")
            return False
    
    def get_cookies_from_account(self, account) -> Optional[str]:
        """从账号对象获取cookie字符串"""
        try:
            if not account or not account.cookies:
                return None
            
            # 将cookie列表转换为字符串
            cookie_pairs = []
            for cookie in account.cookies:
                if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                    cookie_pairs.append(f"{cookie['name']}={cookie['value']}")
            
            if cookie_pairs:
                cookie_string = '; '.join(cookie_pairs)
                self.logger.debug(f"生成cookie字符串，包含 {len(cookie_pairs)} 个cookie")
                return cookie_string
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"获取cookie失败: {e}")
            return None
    



# 单例模式
_product_manager_instance = None

def get_product_manager():
    """获取商品管理器实例"""
    global _product_manager_instance
    if _product_manager_instance is None:
        _product_manager_instance = BilibiliProductManager()
    return _product_manager_instance