#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频上传器 - 性能优化版本
专门处理视频上传逻辑的独立模块，使用智能等待机制
"""

import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .ui_config import UIConfig, SmartWaitManager
from .account_manager import account_manager

class BilibiliVideoUploader:
    """B站视频上传器 - 优化版本"""
    
    def __init__(self, status_callback=None, config_manager=None):
        """初始化上传器"""
        self.status_callback = status_callback
        self.config_manager = config_manager
        self.dialog_handled = False
        self.wait_manager = SmartWaitManager()
    
    def emit_status(self, message):
        """发送状态消息"""
        if self.status_callback:
            self.status_callback(message)
        print(f"[上传器] {message}")

    def smart_wait_for_element(self, driver, selector, timeout=10, condition="clickable"):
        """智能等待元素 - 优化版本"""
        return self.wait_manager.wait_for_element_optimized(driver, selector, timeout, condition)

    def handle_notification_dialog(self, driver):
        """智能处理页面弹窗/通知对话框 - 优化版本"""
        try:
            # 减少弹窗检测时间，使用智能等待
            popup_selectors = [
                '.bili-modal-close',
                '.close-btn', 
                '[class*="close"]',
                '.modal-close',
                '.dialog-close'
            ]
            
            for selector in popup_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            try:
                                driver.execute_script("arguments[0].click();", element)
                                self.emit_status(f"✅ 已关闭网页弹窗")
                            except:
                                element.click()
                                self.emit_status(f"✅ 已关闭网页弹窗")
                            
                            # 使用智能等待替代固定延迟
                            self.wait_manager.smart_sleep(1)
                            return True
                                
                except Exception as e:
                    continue
            
            return True
            
        except Exception as e:
            print(f"处理弹窗时出错: {e}")
            return True
    
    def upload_video(self, driver, video_path, account_name="unknown", need_popup_handling=True):
        """真实视频上传 - 性能优化版本"""
        try:
            # 🎯 位置1：开始计时
            self.start_time = time.time()
            self.video_path = video_path
            self.emit_status(f"🚀 开始投稿 (3分钟超时): {os.path.basename(video_path)}")
            
            # 🎯 关键修复：先导航到视频上传页面
            self.emit_status("导航到视频上传页面...")
            upload_url = "https://member.bilibili.com/platform/upload/video/frame"
            driver.get(upload_url)
            
            self.emit_status("⏳ 立即开始检测上传按钮...")
            
            # 🚀 优化：立即开始持续检测上传按钮，不等待固定时间
            upload_btn = None
            upload_selectors = [
                'div[data-v-f601fcc2].upload-btn',
                '.upload-btn',
                '.upload-wrapper .upload-btn',
                "[class*='upload-btn']",
                "input[type='file']"
            ]
            
            # 🎯 持续检测策略：1分钟内持续尝试
            max_wait_seconds = 60  # 最多等待1分钟
            check_interval = 2     # 每2秒检查一次
            total_waited = 0
            
            while total_waited < max_wait_seconds and not upload_btn:
                # 处理可能的弹窗（在检测过程中）
                if total_waited == 4:  # 4秒后检查一次弹窗
                    self.handle_notification_dialog(driver)
                
                for selector in upload_selectors:
                    try:
                        # 快速检测，不等待
                        upload_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        if upload_btn and upload_btn.is_displayed() and upload_btn.is_enabled():
                            self.emit_status(f"✅ 上传按钮已就绪 (检测{total_waited}秒后, 选择器: {selector})")
                            break
                        else:
                            upload_btn = None  # 重置，继续寻找
                    except:
                        continue
                
                if upload_btn:
                    break
                
                # 等待并更新计时
                self.wait_manager.smart_sleep(check_interval)
                total_waited += check_interval
                
                # 每10秒报告一次状态
                if total_waited % 10 == 0:
                    self.emit_status(f"⏳ 持续检测上传按钮... (已检测{total_waited}秒)")
            
            if not upload_btn:
                current_url = driver.current_url
                page_title = driver.title
                self.emit_status(f"❌ 上传按钮检测超时 (1分钟):")
                self.emit_status(f"   当前URL: {current_url}")
                self.emit_status(f"   页面标题: {page_title}")
                
                # 🎯 出问题后的处理策略
                self.emit_status("🔄 尝试解决方案...")
                
                # 方案1：刷新页面重试
                try:
                    self.emit_status("🔄 方案1: 刷新页面重试...")
                    driver.refresh()
                    self.wait_manager.smart_sleep(3)
                    
                    # 快速重试检测
                    for selector in upload_selectors:
                        try:
                            upload_btn = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            if upload_btn:
                                self.emit_status("✅ 刷新后找到上传按钮")
                                break
                        except:
                            continue
                except Exception as e:
                    self.emit_status(f"⚠️ 刷新页面失败: {e}")
                
                # 方案2：重新导航
                if not upload_btn:
                    try:
                        self.emit_status("🔄 方案2: 重新导航到上传页面...")
                        driver.get(upload_url)
                        self.wait_manager.smart_sleep(3)
                        
                        for selector in upload_selectors:
                            try:
                                upload_btn = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                )
                                if upload_btn:
                                    self.emit_status("✅ 重新导航后找到上传按钮")
                                    break
                            except:
                                continue
                    except Exception as e:
                        self.emit_status(f"⚠️ 重新导航失败: {e}")
                
                # 最终检查
                if not upload_btn:
                    self.emit_status("❌ 所有解决方案均失败，可能需要重新登录或检查网络")
                    raise Exception("上传按钮检测失败，页面可能有问题")
            
            # 处理文件上传 - 优化逻辑
            file_input = None
            
            # 如果找到的直接是文件输入框，跳过点击
            if upload_btn.tag_name == "input" and upload_btn.get_attribute("type") == "file":
                self.emit_status("✅ 直接找到文件输入框")
                file_input = upload_btn
            else:
                self.emit_status("点击上传视频按钮...")
                
                # 点击上传按钮
                try:
                    driver.execute_script("arguments[0].click();", upload_btn)
                except:
                    upload_btn.click()
                
                # 智能等待文件输入框出现
                self.emit_status("智能等待文件选择框...")
                try:
                    file_input = WebDriverWait(driver, 6).until(  # 减少等待时间
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                    )
                except:
                    # 最后尝试：直接查找所有文件输入框
                    file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    for input_elem in file_inputs:
                        if input_elem.is_displayed() or input_elem.get_attribute("style") != "display: none;":
                            file_input = input_elem
                            break
                    
                    if not file_input:
                        raise Exception("未找到文件输入框")
            
            # 验证文件输入框
            if not file_input:
                raise Exception("未找到有效的文件输入框")
            
            # 上传文件
            self.emit_status(f"选择视频文件: {os.path.basename(video_path)}")
            
            # 确保文件路径存在
            if not os.path.exists(video_path):
                raise Exception(f"视频文件不存在: {video_path}")
            
            file_input.send_keys(video_path)
            
            self.emit_status("等待视频上传完成...")
            
            # 智能检测上传进度
            try:
                WebDriverWait(driver, 8).until(  # 减少等待时间
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".upload-progress, .progress, [class*='progress']"))
                )
                self.emit_status("视频上传中...")
            except:
                self.emit_status("未检测到上传进度，继续等待...")
            
            # 智能等待上传完成 - 优化版本
            upload_complete = False
            max_wait_minutes = 10
            wait_seconds = 0
            check_interval = 3  # 减少检查间隔
            
            while wait_seconds < max_wait_minutes * 60 and not upload_complete:
                try:
                    # 检查多种上传完成标志
                    success_indicators = [
                        "span[data-v-8b3d1a4c].success",  # 🎯 用户提供的上传完成标识
                        ".upload-success",
                        ".upload-complete", 
                        "[class*='success']",
                        ".next-step",
                        "[class*='next']"
                    ]
                    
                    for indicator in success_indicators:
                        try:
                            driver.find_element(By.CSS_SELECTOR, indicator)
                            upload_complete = True
                            break
                        except:
                            continue
                    
                    # 检查URL变化
                    current_url = driver.current_url
                    if "edit" in current_url or "submit" in current_url:
                        upload_complete = True
                    
                    # 检查编辑页面元素
                    try:
                        driver.find_element(By.CSS_SELECTOR, "input[placeholder*='标题'], input[placeholder*='title']")
                        upload_complete = True
                    except:
                        pass
                    
                    if upload_complete:
                        break
                    
                    # 使用智能等待
                    self.wait_manager.smart_sleep(check_interval)
                    wait_seconds += check_interval
                    
                    # 更新状态
                    minutes_waited = wait_seconds // 60
                    self.emit_status(f"视频上传中... (已等待 {minutes_waited} 分钟)")
                    
                except Exception as e:
                    print(f"检查上传状态时出错: {e}")
                    self.wait_manager.smart_sleep(check_interval)
                    wait_seconds += check_interval
            
            if upload_complete:
                self.emit_status("视频上传完成!")
                
                # 🎯 上传完成后处理弹窗 - 根据账号和浏览器状态决定
                if need_popup_handling:
                    self.emit_status(f"🎯 [{account_name}] 首次上传，处理弹窗...")
                    self._handle_popup_dialogs(driver)
                    
                    # 🎯 快速检测第二个弹窗（缩短检测时间）
                    self.emit_status("🎯 快速检测第二个弹窗...")
                    
                    # 缩短等待时间
                    self.wait_manager.smart_sleep(0.3)
                    
                    # 快速检测弹窗指示器
                    popup_detected = False
                    popup_indicators = [".bcc-dialog", ".ant-modal", ".modal", "[role='dialog']"]
                    
                    for indicator in popup_indicators:
                        try:
                            popups = driver.find_elements(By.CSS_SELECTOR, indicator)
                            for popup in popups:
                                if popup.is_displayed():
                                    popup_detected = True
                                    self.emit_status("🎯 检测到第二个弹窗，正在处理...")
                                    break
                            if popup_detected:
                                break
                        except:
                            continue
                    
                    if popup_detected:
                        # 有第二个弹窗，处理它
                        self._handle_popup_dialogs(driver)
                    else:
                        self.emit_status("ℹ️ 未检测到第二个弹窗，跳过处理")
                    
                    self.emit_status(f"✅ [{account_name}] 首次上传弹窗处理完成，该浏览器后续上传将跳过弹窗检测")
                else:
                    self.emit_status(f"ℹ️ [{account_name}] 非首次上传，跳过弹窗检测")
                
                return True
            else:
                self.emit_status("视频上传超时")
                return False
            
        except Exception as e:
            self.emit_status(f"视频上传失败: {e}")
            print(f"视频上传失败: {e}")
            return False

    def fill_video_info(self, driver, video_filename, upload_settings, product_info):
        """填写视频信息 - 优化版本"""
        try:
            self.emit_status("等待视频信息编辑页面...")
            
            # 🎯 修复：更全面的标题输入框选择器
            title_input = None
            # 🎯 简化的选择器 - 优先使用最准确的
            title_selectors = [
                "input.input-val",  # 您发现的B站标题输入框
                "input[placeholder='请输入稿件标题']",  # 精确匹配
                ".video-title-content input",  # 标题区域
                "input[placeholder*='标题']",  # 包含"标题"的placeholder
                "input[type='text']:first-of-type"  # 备用：第一个文本输入框
            ]
            
            # 🎯 简化的查找逻辑
            for selector in title_selectors:
                try:
                    title_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_input and title_input.is_displayed():
                        self.emit_status(f"✅ 找到标题输入框")
                        break
                except:
                    continue
            
            if not title_input:
                self.emit_status("❌ 未找到标题输入框，尝试通用方法...")
                # 最后尝试：查找所有可见的text输入框
                try:
                    text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                    for inp in text_inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            # 检查是否可能是标题输入框（通常在页面上方）
                            location = inp.location
                            if location['y'] < 400:  # 通常标题输入框在页面上方
                                title_input = inp
                                self.emit_status("✅ 通过位置推断找到可能的标题输入框")
                                break
                except:
                    pass
            
            if not title_input:
                self.emit_status("❌ 完全无法找到标题输入框")
                return False

            # 🎯 修复：优先使用预处理的标题，否则从文件名提取
            if 'title' in upload_settings and upload_settings['title']:
                # 使用预处理的标题（来自GUI层的正确提取）
                title = upload_settings['title']
                self.emit_status(f"✅ 使用预处理标题: {title}")
            else:
                # 如果没有预处理标题，从文件名提取（向后兼容）
                self.emit_status("📝 从文件名提取标题...")
                title_template = upload_settings.get('title_template', '{filename}')
                
                # 从文件名提取标题：去掉扩展名
                filename_without_ext = video_filename.split('.')[0]
                
                # 🎯 关键修正：从文件名中正确提取标题
                if '----' in filename_without_ext:
                    extracted_title = filename_without_ext.split('----', 1)[1]
                else:
                    extracted_title = filename_without_ext
                
                # 应用标题模板
                if '{filename}' in title_template:
                    title = title_template.replace('{filename}', extracted_title)
                else:
                    title = extracted_title
            
            # 替换其他模板变量
            title = title.replace('{product_name}', product_info.get('goodsName', ''))
            if '{product_id}' in title:
                product_id = product_info.get('itemId', '')
                title = title.replace('{product_id}', str(product_id))
            
            self.emit_status(f"填写视频标题: {title}")
            
            # 🎯 完全重写的标题填写逻辑 - 多重保障
            success = False
            
            # 方法1: 高级JavaScript填写（适用于React/Vue等现代框架）
            try:
                self.emit_status("尝试方法1: 高级JavaScript填写...")
                
                # 滚动到输入框
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", title_input)
                self.wait_manager.smart_sleep(1)
                
                # 🎯 简化的JavaScript填写 - 专门针对B站Vue组件
                script = """
                var input = arguments[0];
                var value = arguments[1];
                
                // 清空并设置新值
                input.focus();
                input.value = '';
                input.value = value;
                
                // 触发Vue.js事件
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                
                // Vue组件特殊处理
                if (input.__vue__) {
                    input.__vue__.$emit('input', value);
                }
                
                // 更新字符计数器
                var counter = input.closest('.input-container')?.querySelector('.input-max-tip');
                if (counter) {
                    counter.textContent = value.length + '/' + (input.maxLength || 80);
                }
                
                return input.value === value;
                """
                
                result = driver.execute_script(script, title_input, title)
                if result:
                    self.emit_status("✅ 方法1成功：JavaScript填写")
                    success = True
                else:
                    self.emit_status("⚠️ 方法1失败，尝试其他方法")
                    
            except Exception as e:
                self.emit_status(f"❌ 方法1失败: {e}")
            
            # 方法2: 模拟真实用户打字（特别适合Vue.js）
            if not success:
                try:
                    self.emit_status("尝试方法2: 模拟真实用户打字...")
                    
                    # 聚焦输入框
                    title_input.click()
                    self.wait_manager.smart_sleep(0.5)
                    
                    # 清空输入框（模拟Ctrl+A + Delete）
                    from selenium.webdriver.common.keys import Keys
                    title_input.send_keys(Keys.CONTROL + "a")
                    self.wait_manager.smart_sleep(0.2)
                    title_input.send_keys(Keys.DELETE)
                    self.wait_manager.smart_sleep(0.5)
                    
                    # 🎯 逐字符输入（模拟真实打字）
                    for char in title:
                        title_input.send_keys(char)
                        self.wait_manager.smart_sleep(0.05)  # 每个字符间隔50ms
                    
                    # 按Tab键确认输入
                    title_input.send_keys(Keys.TAB)
                    self.wait_manager.smart_sleep(1)
                    
                    # 验证输入结果
                    current_value = title_input.get_attribute('value')
                    if current_value == title:
                        self.emit_status("✅ 方法2成功：模拟真实打字")
                        success = True
                    else:
                        self.emit_status(f"⚠️ 方法2部分成功：期望'{title}'，实际'{current_value}'")
                        
                except Exception as e:
                    self.emit_status(f"❌ 方法2失败: {e}")
            
            # 方法3: 强制设置（最后手段）
            if not success:
                try:
                    self.emit_status("尝试方法3: 强制设置...")
                    
                    # 直接设置value属性
                    driver.execute_script("arguments[0].value = arguments[1];", title_input, title)
                    
                    # 强制触发事件
                    driver.execute_script("""
                        var input = arguments[0];
                        var event = new Event('input', { bubbles: true });
                        Object.defineProperty(event, 'target', { value: input, enumerable: true });
                        input.dispatchEvent(event);
                        
                        var changeEvent = new Event('change', { bubbles: true });
                        Object.defineProperty(changeEvent, 'target', { value: input, enumerable: true });
                        input.dispatchEvent(changeEvent);
                    """, title_input)
                    
                    self.emit_status("✅ 方法3完成：强制设置")
                    success = True
                    
                except Exception as e:
                    self.emit_status(f"❌ 方法3失败: {e}")
            
            # 🎯 简化的最终验证
            try:
                final_value = title_input.get_attribute('value')
                if final_value == title:
                    self.emit_status("🎉 标题填写成功！")
                elif final_value:
                    self.emit_status(f"⚠️ 标题内容不匹配：期望'{title}' vs 实际'{final_value}'")
                else:
                    self.emit_status("❌ 标题填写失败，输入框为空")
            except Exception as e:
                self.emit_status(f"❌ 验证失败: {e}")
            
            # 等待一下让页面反应
            self.wait_manager.smart_sleep(2)
            
            # 🎯 智能选择话题 - 优化版本
            self.emit_status("选择参与话题...")
            try:
                # 智能等待话题区域加载
                topic_area = None
                topic_area_selectors = [
                    ".tag-topic-wrp",
                    ".tag-topic-list", 
                    "div[class*='tag-topic']",
                    ".tag-wrp"
                ]
                
                for selector in topic_area_selectors:
                    try:
                        topic_area = WebDriverWait(driver, 3).until(  # 减少等待时间
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if topic_area.is_displayed():
                            # 滚动到话题区域
                            driver.execute_script("arguments[0].scrollIntoView(true);", topic_area)
                            # 使用智能等待
                            self.wait_manager.smart_sleep(0.5)
                            break
                    except:
                        continue
                
                # 智能查找第一个话题
                first_topic = None
                precise_selectors = [
                    ".tag-topic-list span:first-child .hot-tag-container .hot-tag-item",
                    ".tag-topic-list span:first-child .hot-tag-item",
                    ".hot-tag-container:first-child .hot-tag-item",
                    ".hot-tag-container .hot-tag-item:first-child",
                    ".hot-tag-item"
                ]
                
                for selector in precise_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if elements:
                            for i, element in enumerate(elements):
                                try:
                                    if element.is_displayed() and element.is_enabled():
                                        element_text = element.text
                                        if "解锁夏日时髦vibe" in element_text or i == 0:
                                            first_topic = element
                                            self.emit_status(f"✅ 选中话题: {element_text[:20]}")
                                            break
                                except:
                                    continue
                        
                        if first_topic:
                            break
                            
                    except:
                        continue
                
                if first_topic:
                    # 智能点击话题
                    try:
                        driver.execute_script("arguments[0].click();", first_topic)
                        self.emit_status("✅ 话题选择成功")
                    except:
                        first_topic.click()
                        self.emit_status("✅ 话题选择成功")
                        
            except Exception as e:
                self.emit_status(f"⚠️ 话题选择异常: {str(e)}")
            
            self.emit_status("视频信息填写完成")
            return True
            
        except Exception as e:
            self.emit_status(f"填写视频信息失败: {e}")
            print(f"填写视频信息失败: {e}")
            return False

    def add_product_to_video(self, driver, video_filename, product_info):
        """通过链接选品方式添加商品 - 优化版本"""
        try:
            self.emit_status("开始商品添加流程...")
            # 使用智能等待
            self.wait_manager.smart_sleep(1)
            
            # 步骤1: 选中必要的checkbox
            try:
                checkbox_selectors = [
                    '.video-porder-check-wrp .bcc-checkbox-checkbox input[name="默认"]',
                    '.video-porder-check-wrp .bcc-checkbox-checkbox input[type="checkbox"]',
                    'div.video-porder-check-wrp .bcc-checkbox-checkbox input',
                ]
                
                checkbox_found = False
                for selector in checkbox_selectors:
                    try:
                        checkbox = driver.find_element(By.CSS_SELECTOR, selector)
                        if not checkbox.is_selected():
                            driver.execute_script("arguments[0].click();", checkbox)
                            self.emit_status("✅ 已选中必要的checkbox")
                            checkbox_found = True
                            self.wait_manager.smart_sleep(0.5)
                            break
                        else:
                            self.emit_status("✅ 必要的checkbox已选中")
                            checkbox_found = True
                            break
                    except:
                        continue
                
                if not checkbox_found:
                    self.emit_status("⚠️ 未找到checkbox，继续流程")
            except Exception as e:
                self.emit_status(f"⚠️ 选择checkbox失败: {str(e)}")
            
            # 步骤2: 选择"视频带货"标签
            try:
                video_tab_selectors = [
                    'div[name="视频带货"]',
                    "//div[contains(text(), '视频带货')]"
                ]
                
                for selector in video_tab_selectors:
                    try:
                        if "//" in selector:
                            video_porder_tab = driver.find_element(By.XPATH, selector)
                        else:
                            video_porder_tab = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if video_porder_tab.is_displayed():
                            video_porder_tab.click()
                            self.emit_status("✅ 已选择视频带货标签")
                            self.wait_manager.smart_sleep(0.5)
                            break
                    except:
                        continue
            except Exception as e:
                self.emit_status(f"⚠️ 选择视频带货标签失败: {str(e)}")

            # 步骤3: 点击"添加商品"按钮
            try:
                add_goods_selectors = [
                    'div[data-v-b829c3e4].btn',
                    "//*[@data-v-b829c3e4 and @class='btn' and contains(text(), '添加商品')]",
                    "//*[contains(text(), '添加商品')]"
                ]
                
                add_btn_found = False
                for selector in add_goods_selectors:
                    try:
                        if "//" in selector:
                            add_goods_btn = driver.find_element(By.XPATH, selector)
                        else:
                            add_goods_btn = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if add_goods_btn.is_displayed():
                            btn_text = add_goods_btn.text.strip()
                            if "添加商品" in btn_text:
                                driver.execute_script("arguments[0].click();", add_goods_btn)
                                self.emit_status(f"✅ 已点击正确的添加商品按钮: {btn_text}")
                                add_btn_found = True
                                
                                # 智能等待弹窗加载
                                try:
                                    WebDriverWait(driver, 8).until(  # 减少等待时间
                                        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                                    )
                                    self.emit_status("✅ 商品选择弹窗已加载")
                                except:
                                    try:
                                        WebDriverWait(driver, 4).until(
                                            EC.presence_of_element_located((By.CSS_SELECTOR, ".link-add-btn, [class*='modal'], [class*='dialog']"))
                                        )
                                        self.emit_status("✅ 弹窗已加载")
                                    except:
                                        self.wait_manager.smart_sleep(1)
                                break
                    except:
                        continue
                
                if not add_btn_found:
                    self.emit_status("⚠️ 未找到正确的添加商品按钮")
                    return False
                    
            except Exception as e:
                self.emit_status(f"⚠️ 点击添加商品按钮失败: {str(e)}")
                return False
            
            # 步骤4: 点击"链接选品"
            try:
                iframes = WebDriverWait(driver, 8).until(  # 减少等待时间
                    lambda d: d.find_elements(By.TAG_NAME, "iframe")
                )
                
                if len(iframes) >= 2:
                    driver.switch_to.frame(iframes[1])
                    link_btn = WebDriverWait(driver, 6).until(  # 减少等待时间
                        EC.element_to_be_clickable((By.CSS_SELECTOR, '.link-add-btn'))
                    )
                    link_btn.click()
                    self.emit_status("✅ 已点击链接选品")
                else:
                    raise Exception("找不到足够的iframe")
            except Exception as e:
                driver.switch_to.default_content()
                self.emit_status(f"⚠️ 点击链接选品失败: {str(e)}")
                return False
            
            # 步骤5: 输入商品链接
            try:
                video_filename_without_ext = video_filename.split('.')[0]
                if '----' in video_filename_without_ext:
                    product_id = video_filename_without_ext.split('----')[0]
                else:
                    self.emit_status("⚠️ 无法从文件名提取商品ID")
                    return False
                
                product_link = f"https://item.jd.com/{product_id}.html"
                self.emit_status(f"📦 商品链接: {product_link}")
                
                textarea = driver.find_element(By.CSS_SELECTOR, '.indetify-input textarea.ivu-input')
                textarea.clear()
                textarea.send_keys(product_link)
                self.emit_status("✅ 已输入商品链接")
                self.wait_manager.smart_sleep(0.5)
            except Exception as e:
                self.emit_status(f"⚠️ 输入商品链接失败: {str(e)}")
                return False
            
            # 步骤6: 点击"识别链接"按钮 - 优化版本
            try:
                identify_btn = driver.find_element(By.CSS_SELECTOR, 'div.identify-btn span')
                
                # 使用智能等待检查按钮状态
                def check_button_ready():
                    try:
                        return identify_btn.is_enabled() and identify_btn.is_displayed()
                    except:
                        return False
                
                self.wait_manager.smart_sleep(0.5, check_button_ready, 3)
                
                driver.execute_script("arguments[0].click();", identify_btn)
                self.emit_status("✅ 已点击识别链接")
                
                # 智能等待确定按钮变色 - 优化版本
                self.emit_status("⏳ 等待商品识别完成...")
                
                def check_confirm_ready():
                    try:
                        confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                        is_enabled = confirm_btn.is_enabled()
                        btn_class = confirm_btn.get_attribute("class") or ""
                        return is_enabled and "disabled" not in btn_class
                    except:
                        return False
                
                # 使用智能等待，最多等待12秒
                self.wait_manager.smart_sleep(1, check_confirm_ready, 12)
                
                # 步骤7: 点击确定按钮 - 优化版本
                final_confirm_btn = None
                try:
                    final_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                    if final_confirm_btn.is_enabled():
                        self.emit_status("✅ 确定按钮已就绪")
                    else:
                        self.emit_status("⚠️ 确定按钮仍未就绪，尝试点击")
                except:
                    # 如果在当前iframe中找不到，尝试其他iframe
                    try:
                        iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        for iframe in iframes:
                            try:
                                driver.switch_to.frame(iframe)
                                final_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                if final_confirm_btn:
                                    break
                            except:
                                driver.switch_to.default_content()
                                continue
                    except:
                        pass
                
                if final_confirm_btn:
                    driver.execute_script("arguments[0].click();", final_confirm_btn)
                    self.emit_status("✅ 已点击第一个确定按钮")
                    
                    # 等待并点击第二个确定按钮 - 使用智能等待
                    self.wait_manager.smart_sleep(1)
                    
                    def find_second_confirm():
                        try:
                            second_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                            return second_btn.is_enabled() and second_btn.is_displayed()
                        except:
                            return False
                    
                    # 尝试找到第二个确定按钮
                    self.wait_manager.smart_sleep(0.5, find_second_confirm, 5)
                    
                    try:
                        # 🎯 修复stale element问题：点击前重新查找元素
                        initial_iframe_count = len(driver.find_elements(By.TAG_NAME, "iframe"))
                        self.emit_status(f"📊 点击确定前iframe数量: {initial_iframe_count}")
                        
                        # 重新查找第二个确定按钮避免stale element错误
                        second_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                        if second_confirm_btn.is_enabled() and second_confirm_btn.is_displayed():
                            driver.execute_script("arguments[0].click();", second_confirm_btn)
                            self.emit_status("✅ 已点击第二个确定按钮")
                            
                            # 🎯 等待第二个确定按钮的窗口消失（简化逻辑）
                            self.emit_status("⏳ 等待第二个确定窗口消失...")
                            max_wait_time = 8  # 最多等待8秒
                            wait_time = 0
                            popup_dismissed = False
                            
                            while wait_time < max_wait_time:
                                self.wait_manager.smart_sleep(0.5)
                                wait_time += 0.5
                                
                                try:
                                    # 🎯 检测确定按钮是否还存在
                                    confirm_buttons = driver.find_elements(By.CSS_SELECTOR, 'div.btn-confirm')
                                    if not confirm_buttons or not any(btn.is_displayed() for btn in confirm_buttons):
                                        popup_dismissed = True
                                        self.emit_status(f"✅ 第二个确定窗口已消失! (等待{wait_time}秒)")
                                        break
                                    else:
                                        # 每2秒输出一次状态
                                        if int(wait_time * 2) % 4 == 0:
                                            self.emit_status(f"⏳ 第二个确定窗口仍在，继续等待... ({wait_time:.1f}s)")
                                except:
                                    # 找不到确定按钮，说明窗口关闭了
                                    popup_dismissed = True
                                    self.emit_status(f"✅ 第二个确定窗口已消失! (等待{wait_time}秒)")
                                    break
                            
                            # 🎯 如果超时还没消失，尝试再点击一次
                            if not popup_dismissed:
                                self.emit_status("⚠️ 第二个确定窗口未消失，尝试再点击一次")
                                try:
                                    second_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                    if second_confirm_btn.is_enabled() and second_confirm_btn.is_displayed():
                                        driver.execute_script("arguments[0].click();", second_confirm_btn)
                                        self.emit_status("✅ 已重新点击第二个确定按钮")
                                        
                                        # 再等待确认
                                        self.wait_manager.smart_sleep(3)
                                        try:
                                            confirm_buttons = driver.find_elements(By.CSS_SELECTOR, 'div.btn-confirm')
                                            if not confirm_buttons or not any(btn.is_displayed() for btn in confirm_buttons):
                                                self.emit_status("✅ 重试成功！第二个确定窗口已消失")
                                            else:
                                                self.emit_status("⚠️ 重试后第二个确定窗口仍未消失")
                                        except:
                                            self.emit_status("✅ 重试成功！第二个确定窗口已消失")
                                    else:
                                        self.emit_status("⚠️ 重新查找的确定按钮不可用")
                                except Exception as retry_e:
                                    self.emit_status(f"⚠️ 重试点击第二个确定按钮失败: {str(retry_e)}")
                        else:
                            self.emit_status("⚠️ 第二个确定按钮未就绪")
                    except Exception as e:
                        self.emit_status(f"⚠️ 第二个确定按钮处理失败: {str(e)}")
                else:
                    self.emit_status("⚠️ 未找到第一个确定按钮")
                    return False
                
                # 切换回主页面
                driver.switch_to.default_content()
                self.wait_manager.smart_sleep(1)
                
                # 🎯 新增步骤：点击"添加评论"按钮并完成评论流程
                try:
                    # 🎯 确保在主页面，等待页面稳定
                    driver.switch_to.default_content()
                    self.wait_manager.smart_sleep(3)  # 增加等待时间
                    
                    # 🎯 可能需要刷新页面状态或滚动到相关区域
                    try:
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
                        self.wait_manager.smart_sleep(1)
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
                        self.wait_manager.smart_sleep(1)
                    except:
                        pass
                    
                    self.emit_status("🔍 查找添加评论按钮...")
                    
                    # 🎯 尝试多种选择器策略
                    add_comment_btn = None
                    comment_selectors = [
                        'div.link-list > div:nth-of-type(2) div.list-block-header-right > div',  # 原有效选择器
                        'div.list-block-header-right > div.btn',  # 备用选择器1
                        'div.list-block-header-right div[class*="btn"]',  # 备用选择器2
                        '//*[contains(@class, "list-block-header-right")]//*[contains(text(), "添加评论")]',  # XPath备用
                        '//*[contains(text(), "添加评论")]'  # 最宽泛的XPath
                    ]
                    
                    for i, selector in enumerate(comment_selectors):
                        try:
                            if "//" in selector:
                                elements = driver.find_elements(By.XPATH, selector)
                            else:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            
                            for element in elements:
                                if element.is_displayed():
                                    element_text = element.text.strip()
                                    if "添加评论" in element_text:
                                        add_comment_btn = element
                                        self.emit_status(f"✅ 找到添加评论按钮 (选择器{i+1})")
                                        break
                            
                            if add_comment_btn:
                                break
                        except:
                            continue
                    
                    if add_comment_btn:
                        # 点击添加评论按钮
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", add_comment_btn)
                        self.wait_manager.smart_sleep(0.5)
                        driver.execute_script("arguments[0].click();", add_comment_btn)
                        self.emit_status("✅ 已点击添加评论按钮")
                        self.wait_manager.smart_sleep(2)
                        
                        # 步骤2：查找选择商品区域
                        self.emit_status("🔍 查找选择商品区域...")
                        select_goods_btn = None
                        try:
                            # 🎯 遍历所有iframe查找选择商品区域（iframe数量可能变化）
                            iframes = driver.find_elements(By.TAG_NAME, "iframe")
                            self.emit_status(f"🔍 发现 {len(iframes)} 个iframe")
                            
                            select_goods_btn = None
                            
                            # 遍历所有iframe查找
                            for i, iframe in enumerate(iframes):
                                try:
                                    driver.switch_to.frame(iframe)
                                    self.emit_status(f"🔍 在iframe[{i}]中查找选择商品区域...")
                                    
                                    select_goods_btn = driver.find_element(By.CSS_SELECTOR, "div.add-goods-block")
                                    if select_goods_btn.is_displayed():
                                        self.emit_status(f"✅ 在iframe[{i}]中找到选择商品区域")
                                        break
                                    else:
                                        select_goods_btn = None
                                        
                                except Exception as frame_e:
                                    self.emit_status(f"⚠️ iframe[{i}]查找失败: {str(frame_e)}")
                                    select_goods_btn = None
                                    driver.switch_to.default_content()
                                    continue
                            
                            # 如果所有iframe都没找到，尝试在主页面查找
                            if not select_goods_btn:
                                self.emit_status("🔍 在主页面查找选择商品区域...")
                                driver.switch_to.default_content()
                                try:
                                    select_goods_btn = driver.find_element(By.CSS_SELECTOR, "div.add-goods-block")
                                    if select_goods_btn.is_displayed():
                                        self.emit_status("✅ 在主页面找到选择商品区域")
                                    else:
                                        select_goods_btn = None
                                except:
                                    select_goods_btn = None
                                    
                        except Exception as e:
                            self.emit_status(f"⚠️ 查找选择商品区域失败: {str(e)}")
                            select_goods_btn = None
                        
                        if select_goods_btn:
                            driver.execute_script("arguments[0].click();", select_goods_btn)
                            self.emit_status("✅ 已点击选择商品区域")
                            self.wait_manager.smart_sleep(2)
                            
                            # 步骤3：点击链接选品
                            self.emit_status("🔍 查找链接选品按钮...")
                            link_select_btn = None
                            try:
                                link_select_btn = driver.find_element(By.XPATH, "//*[contains(text(), '链接选品')]")
                                if not link_select_btn.is_displayed():
                                    link_select_btn = None
                            except:
                                link_select_btn = None
                            
                            if link_select_btn:
                                driver.execute_script("arguments[0].click();", link_select_btn)
                                self.emit_status("✅ 已点击链接选品按钮")
                                self.wait_manager.smart_sleep(3)
                                
                                # 步骤4：在弹窗中输入链接
                                try:
                                    # 初始化变量
                                    input_element = None
                                    
                                    # 🎯 使用准确的选择器在当前iframe中查找
                                    try:
                                        input_element = driver.find_element(By.CSS_SELECTOR, 'div.modal-body-without-padding textarea')
                                        if input_element.is_displayed():
                                            self.emit_status("✅ 在当前iframe[1]中找到textarea输入框")
                                        else:
                                            input_element = None
                                    except:
                                        # 备用选择器
                                        try:
                                            input_element = driver.find_element(By.CSS_SELECTOR, 'textarea[placeholder*="输入商品链接"]')
                                            if input_element.is_displayed():
                                                self.emit_status("✅ 在当前iframe中找到备用输入框")
                                            else:
                                                input_element = None
                                        except:
                                            input_element = None
                                    
                                    # 如果没找到，可能需要查找新的iframe
                                    if not input_element:
                                        self.emit_status("🔍 在其他iframe中查找输入框...")
                                        current_frame = driver.current_window_handle  # 保存当前状态
                                        driver.switch_to.default_content()  # 切换回主页面
                                        
                                        iframes = driver.find_elements(By.TAG_NAME, "iframe")
                                        self.emit_status(f"🔍 发现 {len(iframes)} 个iframe用于输入框查找")
                                        
                                        for i, iframe in enumerate(iframes):
                                            try:
                                                driver.switch_to.frame(iframe)
                                                # 使用准确的选择器
                                                input_element = driver.find_element(By.CSS_SELECTOR, 'div.modal-body-without-padding textarea')
                                                if input_element and input_element.is_displayed():
                                                    self.emit_status(f"✅ 在iframe[{i}]中找到textarea输入框")
                                                    break
                                                else:
                                                    # 尝试备用选择器
                                                    input_element = driver.find_element(By.CSS_SELECTOR, 'textarea[placeholder*="输入商品链接"]')
                                                    if input_element and input_element.is_displayed():
                                                        self.emit_status(f"✅ 在iframe[{i}]中找到备用输入框")
                                                        break
                                                    else:
                                                        input_element = None
                                            except:
                                                input_element = None
                                                driver.switch_to.default_content()
                                                continue
                                    
                                    if input_element:
                                        # 输入链接
                                        input_element.clear()
                                        product_url = product_info.get('url', '')
                                        input_element.send_keys(product_url)
                                        self.emit_status("✅ 已输入商品链接")
                                        self.wait_manager.smart_sleep(1)
                                        
                                        # 点击识别按钮
                                        identify_btn = driver.find_element(By.CSS_SELECTOR, 'div.identify-btn span')
                                        driver.execute_script("arguments[0].click();", identify_btn)
                                        self.emit_status("✅ 已点击识别链接")
                                        
                                        # 🎯 复制主流程的两个确定按钮处理逻辑
                                        # 智能等待第一个确定按钮变色 - 从主流程复制
                                        self.emit_status("⏳ 等待商品识别完成...")
                                        
                                        def check_confirm_ready():
                                            try:
                                                confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                                is_enabled = confirm_btn.is_enabled()
                                                btn_class = confirm_btn.get_attribute("class") or ""
                                                return is_enabled and "disabled" not in btn_class
                                            except:
                                                return False
                                        
                                        # 使用智能等待，最多等待12秒
                                        self.wait_manager.smart_sleep(1, check_confirm_ready, 12)
                                        
                                        # 点击第一个确定按钮 - 从主流程复制
                                        final_confirm_btn = None
                                        try:
                                            final_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                            if final_confirm_btn.is_enabled():
                                                self.emit_status("✅ 第一个确定按钮已就绪")
                                            else:
                                                self.emit_status("⚠️ 第一个确定按钮仍未就绪，尝试点击")
                                        except:
                                            # 如果在当前iframe中找不到，尝试其他iframe
                                            try:
                                                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                                                for iframe in iframes:
                                                    try:
                                                        driver.switch_to.frame(iframe)
                                                        final_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                                        if final_confirm_btn:
                                                            break
                                                    except:
                                                        driver.switch_to.default_content()
                                                        continue
                                            except:
                                                pass
                                        
                                        if final_confirm_btn:
                                            driver.execute_script("arguments[0].click();", final_confirm_btn)
                                            self.emit_status("✅ 已点击第一个确定按钮")
                                            
                                            # 等待并点击第二个确定按钮 - 从主流程复制
                                            self.wait_manager.smart_sleep(1)
                                            
                                            def find_second_confirm():
                                                try:
                                                    second_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                                    return second_btn.is_enabled() and second_btn.is_displayed()
                                                except:
                                                    return False
                                            
                                            # 尝试找到第二个确定按钮
                                            self.wait_manager.smart_sleep(0.5, find_second_confirm, 5)
                                            
                                            try:
                                                # 重新查找第二个确定按钮避免stale element错误
                                                second_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                                if second_confirm_btn.is_enabled() and second_confirm_btn.is_displayed():
                                                    driver.execute_script("arguments[0].click();", second_confirm_btn)
                                                    self.emit_status("✅ 已点击第二个确定按钮")
                                                    
                                                    # 🎯 等待第二个确定按钮的窗口消失（从主流程复制）
                                                    self.emit_status("⏳ 等待第二个确定窗口消失...")
                                                    max_wait_time = 8  # 最多等待8秒
                                                    wait_time = 0
                                                    popup_dismissed = False
                                                    
                                                    while wait_time < max_wait_time:
                                                        self.wait_manager.smart_sleep(0.5)
                                                        wait_time += 0.5
                                                        
                                                        try:
                                                            # 🎯 检测确定按钮是否还存在
                                                            confirm_buttons = driver.find_elements(By.CSS_SELECTOR, 'div.btn-confirm')
                                                            if not confirm_buttons or not any(btn.is_displayed() for btn in confirm_buttons):
                                                                popup_dismissed = True
                                                                self.emit_status(f"✅ 第二个确定窗口已消失! (等待{wait_time}秒)")
                                                                break
                                                            else:
                                                                # 每2秒输出一次状态
                                                                if int(wait_time * 2) % 4 == 0:
                                                                    self.emit_status(f"⏳ 第二个确定窗口仍在，继续等待... ({wait_time:.1f}s)")
                                                        except:
                                                            # 找不到确定按钮，说明窗口关闭了
                                                            popup_dismissed = True
                                                            self.emit_status(f"✅ 第二个确定窗口已消失! (等待{wait_time}秒)")
                                                            break
                                                    
                                                    # 🎯 如果超时还没消失，尝试再点击一次
                                                    if not popup_dismissed:
                                                        self.emit_status("⚠️ 第二个确定窗口未消失，尝试再点击一次")
                                                        try:
                                                            second_confirm_btn = driver.find_element(By.CSS_SELECTOR, 'div.btn-confirm')
                                                            if second_confirm_btn.is_enabled() and second_confirm_btn.is_displayed():
                                                                driver.execute_script("arguments[0].click();", second_confirm_btn)
                                                                self.emit_status("✅ 已重新点击第二个确定按钮")
                                                                
                                                                # 再等待确认
                                                                self.wait_manager.smart_sleep(3)
                                                                try:
                                                                    confirm_buttons = driver.find_elements(By.CSS_SELECTOR, 'div.btn-confirm')
                                                                    if not confirm_buttons or not any(btn.is_displayed() for btn in confirm_buttons):
                                                                        self.emit_status("✅ 重试成功！第二个确定窗口已消失")
                                                                    else:
                                                                        self.emit_status("⚠️ 重试后第二个确定窗口仍未消失")
                                                                except:
                                                                    self.emit_status("✅ 重试成功！第二个确定窗口已消失")
                                                            else:
                                                                self.emit_status("⚠️ 重新查找的确定按钮不可用")
                                                        except Exception as retry_e:
                                                            self.emit_status(f"⚠️ 重试点击第二个确定按钮失败: {str(retry_e)}")
                                                else:
                                                    self.emit_status("⚠️ 第二个确定按钮未就绪")
                                            except Exception as e:
                                                self.emit_status(f"⚠️ 第二个确定按钮处理失败: {str(e)}")
                                        else:
                                            self.emit_status("⚠️ 未找到第一个确定按钮")
                                        
                                        # 等待页面稳定
                                        self.wait_manager.smart_sleep(1)
                                        
                                        # 步骤5：点击最终添加按钮 - 需要等待页面稳定
                                        try:
                                            # 🎯 等待页面状态稳定，类似确定按钮的处理
                                            self.emit_status("🔍 等待最终添加按钮出现...")
                                            self.wait_manager.smart_sleep(2)  # 等待页面稳定
                                            
                                            # 🎯 尝试多种选择器查找最终添加按钮
                                            final_add_selectors = [
                                                "//button[contains(text(), '添加')]",
                                                "//span[contains(text(), '添加')]/parent::button",
                                                "button.ivu-btn.ivu-btn-primary",
                                                "button[data-v-28929046].ivu-btn.ivu-btn-primary",
                                                ".ivu-btn.ivu-btn-primary",
                                                "button[type='button']"
                                            ]
                                            
                                            final_add_btn = None
                                            current_iframe_count = len(driver.find_elements(By.TAG_NAME, "iframe"))
                                            self.emit_status(f"🔍 当前iframe数量: {current_iframe_count}")
                                            
                                            # 在当前iframe中查找
                                            for i, selector in enumerate(final_add_selectors):
                                                try:
                                                    if "//" in selector:
                                                        elements = driver.find_elements(By.XPATH, selector)
                                                    else:
                                                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                                    
                                                    for element in elements:
                                                        if element.is_displayed() and element.is_enabled():
                                                            # 验证按钮文本
                                                            btn_text = element.text.strip()
                                                            if "添加" in btn_text or btn_text == "":  # 有些按钮文本可能为空
                                                                final_add_btn = element
                                                                self.emit_status(f"✅ 找到最终添加按钮 (选择器{i+1}): '{btn_text}'")
                                                                break
                                                    
                                                    if final_add_btn:
                                                        break
                                                except:
                                                    continue
                                            
                                            # 如果在当前iframe没找到，切换回主页面再试
                                            if not final_add_btn:
                                                self.emit_status("🔍 在主页面查找最终添加按钮...")
                                                driver.switch_to.default_content()
                                                
                                                for i, selector in enumerate(final_add_selectors):
                                                    try:
                                                        if "//" in selector:
                                                            elements = driver.find_elements(By.XPATH, selector)
                                                        else:
                                                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                                        
                                                        for element in elements:
                                                            if element.is_displayed() and element.is_enabled():
                                                                btn_text = element.text.strip()
                                                                if "添加" in btn_text:
                                                                    final_add_btn = element
                                                                    self.emit_status(f"✅ 在主页面找到最终添加按钮 (选择器{i+1}): '{btn_text}'")
                                                                    break
                                                        
                                                        if final_add_btn:
                                                            break
                                                    except:
                                                        continue
                                            
                                            if final_add_btn:
                                                driver.execute_script("arguments[0].click();", final_add_btn)
                                                self.emit_status("✅ 已点击最终添加按钮")
                                                
                                                # 🎯 等待并验证添加是否成功（类似确定按钮的处理）
                                                self.wait_manager.smart_sleep(2)
                                                final_iframe_count = len(driver.find_elements(By.TAG_NAME, "iframe"))
                                                
                                                if final_iframe_count < current_iframe_count:
                                                    self.emit_status(f"✅ 添加成功！iframe数量从{current_iframe_count}减少到{final_iframe_count}")
                                                    self.emit_status("🎉 添加评论流程完成！")
                                                else:
                                                    self.emit_status(f"⚠️ 添加状态不明确，iframe数量: {final_iframe_count}")
                                            else:
                                                self.emit_status("⚠️ 未找到最终添加按钮")
                                        except Exception as e:
                                            self.emit_status(f"⚠️ 点击最终添加按钮失败: {str(e)}")
                                    else:
                                        self.emit_status("⚠️ 未找到链接输入框")
                                except Exception as e:
                                    self.emit_status(f"⚠️ 处理链接输入失败: {str(e)}")
                            else:
                                self.emit_status("⚠️ 未找到链接选品按钮")
                        else:
                            self.emit_status("⚠️ 未找到选择商品区域")
                    else:
                        self.emit_status("⚠️ 未找到添加评论按钮")
                
                except Exception as e:
                    self.emit_status(f"⚠️ 添加评论流程失败: {str(e)}")
                
                # 最终切换回主页面
                driver.switch_to.default_content()
                self.wait_manager.smart_sleep(0.5)
                
            except Exception as e:
                driver.switch_to.default_content()
                self.emit_status(f"⚠️ 点击识别链接失败: {str(e)}")
                return False
            
            self.emit_status("✅ 链接选品流程完成")
            return True
                
        except Exception as e:
            self.emit_status(f"添加商品失败: {e}")
            print(f"添加商品失败: {e}")
            return False

    def publish_video(self, driver, account_name="unknown"):
        """发布视频 - 优化版本，增加智能滚动确保按钮可见，并检测投稿成功状态"""
        try:
            self.emit_status("准备发布视频，确保页面完整显示...")
            
            # 🎯 关键修复：先滚动到页面底部，确保发布按钮可见
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.wait_manager.smart_sleep(1)  # 等待滚动完成
                self.emit_status("✅ 已滚动到页面底部")
            except Exception as scroll_error:
                self.emit_status(f"⚠️ 滚动页面失败: {scroll_error}")
            
            self.emit_status("查找立即投稿按钮...")
            
            # 优化的选择器列表
            publish_selectors = [
                "span.submit-add",  # 最新的B站发布按钮
                ".submit-add",
                "[class*='submit']",
                "button[type='submit']",
            ]
            
            publish_btn = None
            
            # 使用智能等待查找发布按钮
            for selector in publish_selectors:
                try:
                    publish_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if publish_btn:
                        self.emit_status(f"✅ 找到立即投稿按钮 (选择器: {selector})")
                        break
                except:
                    continue
            
            # 如果CSS选择器找不到，尝试XPath
            if not publish_btn:
                xpath_selectors = [
                    "//span[contains(text(), '立即投稿')]",
                    "//button[contains(text(), '立即投稿')]",
                    "//div[contains(text(), '立即投稿')]",
                ]
                
                for xpath in xpath_selectors:
                    try:
                        publish_btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        if publish_btn:
                            self.emit_status(f"✅ 通过XPath找到立即投稿按钮")
                            break
                    except:
                        continue
            
            if not publish_btn:
                self.emit_status("❌ 未找到立即投稿按钮")
                return False
            
            # 🎯 关键修复：在点击按钮前，确保按钮在视窗中央可见
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", publish_btn)
                self.wait_manager.smart_sleep(1)  # 等待滚动完成
                
                # 验证按钮是否在视窗内
                button_rect = driver.execute_script("""
                    var rect = arguments[0].getBoundingClientRect();
                    var windowHeight = window.innerHeight;
                    return {
                        top: rect.top,
                        bottom: rect.bottom,
                        visible: rect.top >= 0 && rect.bottom <= windowHeight
                    };
                """, publish_btn)
                
                if button_rect['visible']:
                    self.emit_status("✅ 立即投稿按钮已在视窗内可见")
                else:
                    self.emit_status(f"⚠️ 按钮位置: top={button_rect['top']}, bottom={button_rect['bottom']}")
                    # 如果按钮仍不可见，再次滚动
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", publish_btn)
                    self.wait_manager.smart_sleep(0.5)
                    
            except Exception as scroll_error:
                self.emit_status(f"⚠️ 滚动到按钮失败: {scroll_error}")
            
            # 正式投稿流程
            
            # 点击立即投稿按钮
            self.emit_status("点击立即投稿...")
            try:
                # 使用JavaScript点击，避免元素被遮挡
                driver.execute_script("arguments[0].click();", publish_btn)
                self.emit_status("✅ 使用JavaScript成功点击立即投稿按钮")
            except Exception as js_error:
                try:
                    # 如果JavaScript失败，尝试普通点击
                    publish_btn.click()
                    self.emit_status("✅ 使用普通点击成功点击立即投稿按钮")
                except Exception as click_error:
                    self.emit_status(f"❌ 点击立即投稿按钮失败: {click_error}")
                    return False
            
            # 🎯 移除立即投稿后的弹窗检测，因为用户反馈此时没有弹窗
            # self.emit_status("🔍 检测可能的弹窗...")
            # self._handle_popup_dialogs(driver)
            
            # 🎯 新增：智能检测投稿成功状态
            self.emit_status("⏳ 等待投稿处理结果...")
            
            # 智能等待投稿成功标识出现
            success_detected = False
            max_wait_time = 30  # 最多等待30秒
            check_interval = 1  # 每秒检查一次
            wait_time = 0
            
            while wait_time < max_wait_time and not success_detected:
                # 🎯 位置2：检测投稿成功时检查超时
                if self.start_time and time.time() - self.start_time > 180:  # 3分钟
                    self.emit_status(f"⏰ 3分钟超时！删除视频: {os.path.basename(self.video_path)}")
                    try:
                        if os.path.exists(self.video_path):
                            os.remove(self.video_path)
                            self.emit_status(f"✅ 已删除超时视频，跳过到下一个")
                    except Exception as e:
                        self.emit_status(f"❌ 删除视频失败: {e}")
                    return False
                
                try:
                    # 🎯 优先检查"再投一个"和"查看稿件"按钮（优先级高于文本判断）
                    high_priority_selectors = [
                        # "再投一个"按钮
                        'button[data-v-3d42d966].bcc-button.bcc-button--default.max-large.group-2-btn',
                        'button.bcc-button.bcc-button--default.max-large.group-2-btn',
                        'button.group-2-btn',
                        # "查看稿件"按钮  
                        'button[data-v-3d42d966].bcc-button.bcc-button--default.max-large:not(.group-2-btn)',
                        'button.bcc-button.bcc-button--default.max-large:not(.group-2-btn)',
                    ]
                    
                    # 检查高优先级按钮是否存在
                    for selector in high_priority_selectors:
                        try:
                            button_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for button_element in button_elements:
                                if button_element and button_element.is_displayed():
                                    button_text = button_element.text.strip()
                                    if "再投一个" in button_text or "查看稿件" in button_text:
                                        success_detected = True
                                        self.emit_status(f"🎉 检测到投稿成功按钮: {button_text} (高优先级)")
                                        break
                        except:
                            continue
                        
                        if success_detected:
                            break
                    
                    # 如果高优先级按钮检测成功，跳出循环
                    if success_detected:
                        break
                    
                    # 🎯 备用方案：使用XPath查找按钮文本（增强版）
                    if not success_detected:
                        button_xpath_selectors = [
                            # 直接查找包含文本的按钮
                            "//button[contains(text(), '再投一个')]",
                            "//button[contains(text(), '查看稿件')]",
                            # 查找span内包含文本的按钮
                            "//button[.//span[contains(text(), '再投一个')]]",
                            "//button[.//span[contains(text(), '查看稿件')]]",
                            # 反向查找：从文本找父级按钮
                            "//span[contains(text(), '再投一个')]/parent::button",
                            "//span[contains(text(), '查看稿件')]/parent::button",
                            # 更宽泛的查找
                            "//*[contains(text(), '再投一个') and (name()='button' or contains(@class, 'btn'))]",
                            "//*[contains(text(), '查看稿件') and (name()='button' or contains(@class, 'btn'))]",
                        ]
                        
                        for xpath_selector in button_xpath_selectors:
                            try:
                                button_elements = driver.find_elements(By.XPATH, xpath_selector)
                                for button_element in button_elements:
                                    if button_element and button_element.is_displayed():
                                        button_text = button_element.text.strip()
                                        if "再投一个" in button_text or "查看稿件" in button_text:
                                            success_detected = True
                                            self.emit_status(f"🎉 检测到投稿成功按钮: {button_text} (XPath发现)")
                                            break
                            except:
                                continue
                            
                            if success_detected:
                                break
                    
                    # 如果按钮检测成功，跳出循环
                    if success_detected:
                        break
                    
                    # 🎯 最后检查文本标识（优先级较低）
                    success_selectors = [
                        'div[data-v-3d42d966].step-des',  # 精确的成功标识
                        'div.step-des',  # 备用选择器
                        "[class*='step-des']",  # 更宽泛的选择器
                    ]
                    
                    for selector in success_selectors:
                        try:
                            success_element = driver.find_element(By.CSS_SELECTOR, selector)
                            if success_element and success_element.is_displayed():
                                element_text = success_element.text.strip()
                                if "稿件投递成功" in element_text or "投稿成功" in element_text:
                                    success_detected = True
                                    self.emit_status(f"🎉 检测到投稿成功标识: {element_text} (文本判断)")
                                    break
                        except:
                            continue
                    
                    # 如果找到成功标识，跳出循环
                    if success_detected:
                        break
                    
                    # 检查是否有错误信息
                    error_selectors = [
                        "[class*='error']",
                        "[class*='fail']",
                        ".message-error",
                        ".error-msg"
                    ]
                    
                    for error_selector in error_selectors:
                        try:
                            error_elements = driver.find_elements(By.CSS_SELECTOR, error_selector)
                            for error_element in error_elements:
                                if error_element.is_displayed():
                                    error_text = error_element.text.strip()
                                    if error_text and len(error_text) > 0:
                                        self.emit_status(f"⚠️ 检测到可能的错误信息: {error_text}")
                        except:
                            continue
                    
                    # 等待一秒后继续检查
                    self.wait_manager.smart_sleep(check_interval)
                    wait_time += check_interval
                    
                    # 每5秒输出一次等待状态
                    if wait_time % 5 == 0:
                        self.emit_status(f"⏳ 等待投稿结果中... ({wait_time}/{max_wait_time}秒)")
                    
                except Exception as check_error:
                    self.emit_status(f"⚠️ 检查投稿状态时出错: {check_error}")
                    self.wait_manager.smart_sleep(check_interval)
                    wait_time += check_interval
            
            # 根据检测结果返回
            if success_detected:
                self.emit_status("🎉 检测到投稿成功标识！立即检查弹窗...")
                
                # 🎯 使用用户配置的投稿成功等待时间
                if self.config_manager:
                    try:
                        ui_settings = self.config_manager.get('ui_settings', {})
                        observation_time = ui_settings.get('success_wait_time', 2)  # 默认2秒
                        self.emit_status(f"📝 使用配置的投稿成功等待时间: {observation_time}秒")
                    except:
                        observation_time = 2  # 出错时使用默认值
                        self.emit_status("⚠️ 获取配置失败，使用默认等待时间: 2秒")
                else:
                    observation_time = 2  # 没有配置管理器时使用默认值
                    self.emit_status("📝 使用默认投稿成功等待时间: 2秒")
                for i in range(observation_time):
                    self.wait_manager.smart_sleep(1)
                    self.emit_status(f"⏳ 快速确认中... ({i+1}/{observation_time}秒)")
                    
                    # 继续验证成功状态（优先检查按钮，然后检查文本）
                    try:
                        # 首先检查高优先级按钮是否仍然存在
                        button_still_exists = False
                        high_priority_selectors = [
                            'button[data-v-3d42d966].bcc-button.bcc-button--default.max-large.group-2-btn',
                            'button.bcc-button.bcc-button--default.max-large.group-2-btn',
                            'button.group-2-btn',
                            'button[data-v-3d42d966].bcc-button.bcc-button--default.max-large:not(.group-2-btn)',
                            'button.bcc-button.bcc-button--default.max-large:not(.group-2-btn)',
                        ]
                        
                        for selector in high_priority_selectors:
                            try:
                                button_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for button_element in button_elements:
                                    if button_element and button_element.is_displayed():
                                        button_text = button_element.text.strip()
                                        if "再投一个" in button_text or "查看稿件" in button_text:
                                            button_still_exists = True
                                            break
                            except:
                                continue
                            if button_still_exists:
                                break
                        
                        # 如果按钮不存在，检查文本状态
                        if not button_still_exists:
                            success_element = driver.find_element(By.CSS_SELECTOR, 'div[data-v-3d42d966].step-des')
                            if success_element and success_element.is_displayed():
                                element_text = success_element.text.strip()
                                if "稿件投递成功" not in element_text and "投稿成功" not in element_text:
                                    self.emit_status("⚠️ 观察期间成功状态发生变化")
                                    break
                    except:
                        # 元素消失可能是正常的页面跳转
                        pass
                
                self.emit_status("🎉 视频投稿成功！")
                
                # 🎯 更新账号发布计数
                try:
                    account_manager.update_publish_count(account_name)
                    self.emit_status(f"✅ 已更新账号 {account_name} 的发布计数")
                except Exception as e:
                    self.emit_status(f"⚠️ 更新发布计数失败: {e}")
                
                return True
            else:
                # 如果没有检测到成功标识，记录当前页面信息用于调试
                try:
                    current_url = driver.current_url
                    page_title = driver.title
                    self.emit_status(f"⚠️ 未检测到投稿成功标识")
                    self.emit_status(f"   当前URL: {current_url}")
                    self.emit_status(f"   页面标题: {page_title}")
                    
                    # 尝试获取页面中包含"成功"字样的元素
                    success_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '成功')]")
                    if success_elements:
                        self.emit_status(f"   页面中找到包含'成功'的元素:")
                        for i, elem in enumerate(success_elements[:3]):  # 只显示前3个
                            try:
                                if elem.is_displayed():
                                    self.emit_status(f"     {i+1}. {elem.text.strip()}")
                            except:
                                continue
                    
                except Exception as debug_error:
                    self.emit_status(f"⚠️ 获取调试信息失败: {debug_error}")
                
                self.emit_status("❌ 投稿状态检测超时或失败")
                return False
            
        except Exception as e:
            self.emit_status(f"❌ 发布视频失败: {e}")
            return False

    def _handle_popup_dialogs(self, driver):
        """处理B站上传过程中的弹窗对话框 - 优化版本"""
        try:
            self.emit_status("🔍 快速检测弹窗对话框...")
            
            # 缩短等待时间，但先检测弹窗是否已存在
            popup_detected = False
            
            # 🎯 首先快速检测是否有弹窗出现（包含B站特有的弹窗类名）
            popup_indicators = [
                ".bcc-dialog",     # 🎯 B站弹窗容器（从HTML代码推断）
                ".ant-modal",      # ant design模态框
                ".modal",          # 通用模态框
                "[role='dialog']", # ARIA对话框
                ".popup",          # 弹窗类
                "[class*='dialog']",  # 包含dialog的类
                "[class*='modal']"    # 包含modal的类
            ]
            
            for indicator in popup_indicators:
                try:
                    popups = driver.find_elements(By.CSS_SELECTOR, indicator)
                    for popup in popups:
                        if popup.is_displayed():
                            popup_detected = True
                            self.emit_status("🎯 检测到弹窗，准备处理...")
                            break
                    if popup_detected:
                        break
                except:
                    continue
            
            if popup_detected:
                # 等待弹窗完全加载（缩短时间）
                self.wait_manager.smart_sleep(0.5)
            else:
                # 如果没有检测到弹窗，短暂等待再次检查（缩短时间）
                self.wait_manager.smart_sleep(0.2)
                for indicator in popup_indicators:
                    try:
                        popups = driver.find_elements(By.CSS_SELECTOR, indicator)
                        for popup in popups:
                            if popup.is_displayed():
                                popup_detected = True
                                break
                        if popup_detected:
                            break
                    except:
                        continue
            
            # 🎯 优先检测具体的弹窗按钮（用户提供的准确信息）
            skip_button_texts = [
                "知道了",        # 用户提供的第一个弹窗按钮
                "稍后设置",      # 用户明确提到的按钮
                "暂不设置",      # 备用选项
                "稍后",          # 简短版本
                "跳过设置",      # 另一种表达
                "暂时跳过"       # 类似表达
            ]
            
            skip_button_found = False
            for button_text in skip_button_texts:
                if skip_button_found:
                    break
                    
                try:
                    # 🎯 优先使用用户提供的精确选择器，然后回退到通用选择器
                    if button_text == "知道了":
                        # 用户提供的精确选择器：知道了按钮
                        css_selectors = [
                            "button[data-v-feb251b4].bcc-button.vp-nd-f.bcc-button--primary.small",  # 精确的完整类名
                            "button.bcc-button.bcc-button--primary.small",  # 通用的B站按钮类
                            "button.bcc-button--primary",  # 主要按钮类
                            ".bcc-button.small"  # 小按钮类
                        ]
                        
                        # 先尝试CSS选择器
                        for css_selector in css_selectors:
                            try:
                                skip_buttons = driver.find_elements(By.CSS_SELECTOR, css_selector)
                                for skip_button in skip_buttons:
                                    if skip_button.is_displayed() and skip_button.is_enabled():
                                        # 🎯 验证按钮文本确实包含目标文本
                                        button_text_content = skip_button.text or ""
                                        if button_text not in button_text_content:
                                            continue
                                        parent_modal = driver.execute_script("""
                                            var element = arguments[0];
                                            var parent = element.closest('.bcc-dialog, .ant-modal, .modal, .popup, .dialog, [role="dialog"]');
                                            return parent !== null;
                                        """, skip_button)
                                        
                                        if parent_modal or popup_detected:
                                            self.emit_status(f"🎯 通过CSS选择器发现'{button_text}'按钮，正在点击...")
                                            try:
                                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", skip_button)
                                                self.wait_manager.smart_sleep(0.3)
                                                driver.execute_script("arguments[0].click();", skip_button)
                                                self.emit_status(f"✅ 已点击'{button_text}'按钮")
                                                skip_button_found = True
                                                self.wait_manager.smart_sleep(0.5)
                                                break
                                            except Exception as click_error:
                                                self.emit_status(f"⚠️ 点击'{button_text}'按钮失败: {click_error}")
                                                continue
                                
                                if skip_button_found:
                                    break
                            except Exception:
                                continue
                        
                        if skip_button_found:
                            break
                    
                    # 使用XPath查找包含特定文本的按钮类元素
                    xpath_selectors = [
                        f"//button[contains(text(), '{button_text}')]",
                        f"//span[contains(text(), '{button_text}')]",
                        f"//div[contains(text(), '{button_text}') and (contains(@class, 'btn') or contains(@class, 'button'))]",
                        f"//*[contains(text(), '{button_text}') and (contains(@class, 'ant-btn') or contains(@role, 'button'))]",
                        f"//button[contains(@class, 'bcc-button') and .//span[contains(text(), '{button_text}')]]"  # B站特定按钮
                    ]
                    
                    for xpath_selector in xpath_selectors:
                        try:
                            skip_buttons = driver.find_elements(By.XPATH, xpath_selector)
                            
                            for skip_button in skip_buttons:
                                if skip_button.is_displayed() and skip_button.is_enabled():
                                    # 确认按钮在弹窗内
                                    parent_modal = driver.execute_script("""
                                        var element = arguments[0];
                                        var parent = element.closest('.ant-modal, .modal, .popup, .dialog, [role="dialog"]');
                                        return parent !== null;
                                    """, skip_button)
                                    
                                    if parent_modal or popup_detected:
                                        self.emit_status(f"🎯 发现'{button_text}'按钮，正在点击...")
                                        try:
                                            # 快速滚动到按钮位置
                                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", skip_button)
                                            self.wait_manager.smart_sleep(0.3)
                                            
                                            # 使用JavaScript点击
                                            driver.execute_script("arguments[0].click();", skip_button)
                                            self.emit_status(f"✅ 已点击'{button_text}'按钮")
                                            skip_button_found = True
                                            
                                            # 缩短等待弹窗关闭的时间
                                            self.wait_manager.smart_sleep(0.5)
                                            break
                                            
                                        except Exception as click_error:
                                            self.emit_status(f"⚠️ 点击'{button_text}'按钮失败: {click_error}")
                                            continue
                            
                            if skip_button_found:
                                break
                                
                        except Exception:
                            continue
                    
                    if skip_button_found:
                        break
                        
                except Exception:
                    continue
            
            # 🎯 如果没有找到"稍后设置"类按钮，检测其他常见弹窗按钮（但优先级较低）
            if not skip_button_found and popup_detected:
                other_popup_buttons = [
                    ("确定", "确认对话框"),
                    ("知道了", "提示对话框"),
                    ("确认", "确认对话框"),
                    ("取消", "取消对话框")
                ]
                
                for button_text, button_desc in other_popup_buttons:
                    if skip_button_found:
                        break
                        
                    try:
                        xpath_selector = f"//*[contains(text(), '{button_text}') and (name()='button' or name()='span' or contains(@class, 'btn'))]"
                        popup_buttons = driver.find_elements(By.XPATH, xpath_selector)
                        
                        for popup_button in popup_buttons:
                            if popup_button.is_displayed() and popup_button.is_enabled():
                                # 检查是否在模态框或弹窗中
                                parent_modal = driver.execute_script("""
                                    var element = arguments[0];
                                    var parent = element.closest('.bcc-dialog, .ant-modal, .modal, .popup, .dialog, [role="dialog"]');
                                    return parent !== null;
                                """, popup_button)
                                
                                if parent_modal:
                                    self.emit_status(f"🎯 发现{button_desc}按钮：{button_text}")
                                    try:
                                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", popup_button)
                                        self.wait_manager.smart_sleep(0.3)
                                        driver.execute_script("arguments[0].click();", popup_button)
                                        self.emit_status(f"✅ 已点击{button_desc}按钮")
                                        skip_button_found = True
                                        self.wait_manager.smart_sleep(0.3)
                                        break
                                    except Exception as click_error:
                                        self.emit_status(f"⚠️ 点击{button_desc}按钮失败: {click_error}")
                                        continue
                    except Exception:
                        continue
            
            # 🎯 最后尝试关闭按钮（仅在没有找到其他按钮时）
            if not skip_button_found and popup_detected:
                try:
                    close_selectors = [
                        ".bcc-dialog__close.bcc-iconfont.bcc-icon-ic_delete_",  # 🎯 用户提供的B站弹窗关闭按钮
                        "i.bcc-dialog__close",  # B站弹窗关闭按钮（简化版）
                        ".ant-modal-close",  # ant design模态框关闭按钮
                        ".modal-close",      # 通用模态框关闭按钮
                        "[class*='close']:visible",  # 可见的包含close的类名
                        ".fa-times",         # FontAwesome关闭图标
                        ".icon-close"        # 通用关闭图标
                    ]
                    
                    for close_selector in close_selectors:
                        if skip_button_found:
                            break
                            
                        try:
                            close_buttons = driver.find_elements(By.CSS_SELECTOR, close_selector)
                            for close_button in close_buttons:
                                if close_button.is_displayed() and close_button.is_enabled():
                                    # 确认是在弹窗中的关闭按钮
                                    parent_modal = driver.execute_script("""
                                        var element = arguments[0];
                                        var parent = element.closest('.ant-modal, .modal, .popup, .dialog, [role="dialog"]');
                                        return parent !== null;
                                    """, close_button)
                                    
                                    if parent_modal:
                                        self.emit_status("🎯 发现弹窗关闭按钮")
                                        try:
                                            driver.execute_script("arguments[0].click();", close_button)
                                            self.emit_status("✅ 已关闭弹窗")
                                            skip_button_found = True
                                            self.wait_manager.smart_sleep(0.3)
                                            break
                                        except Exception as click_error:
                                            continue
                        except Exception:
                            continue
                
                except Exception as close_error:
                    self.emit_status(f"⚠️ 处理关闭按钮时出错: {close_error}")
            
            if not skip_button_found and not popup_detected:
                self.emit_status("ℹ️ 未检测到弹窗")
            elif not skip_button_found and popup_detected:
                self.emit_status("⚠️ 检测到弹窗但未找到可处理的按钮")
            else:
                self.emit_status("✅ 弹窗处理完成")
            
        except Exception as e:
            self.emit_status(f"⚠️ 弹窗处理过程出错: {e}")
    
def create_uploader(status_callback=None, config_manager=None):
    """创建上传器实例"""
    return BilibiliVideoUploader(status_callback, config_manager) 