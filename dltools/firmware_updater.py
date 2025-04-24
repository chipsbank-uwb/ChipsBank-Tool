"""
File: firmware_updater.py
Author: Roja.Zeng
Date: 2024.09
Company: ChipsBank
Version: 1.0.0
Description:
关键步骤：

初始化和打开串口：
用户初始化 FirmwareUpdater 实例。
FirmwareUpdater 打开与设备的串口连接。

读取版本号：
FirmwareUpdater 向设备发送读取版本号命令。
设备返回当前固件版本号，FirmwareUpdater 显示给用户。

检查OTA更新：
FirmwareUpdater 向设备发送检查OTA更新命令。
设备返回检查结果，如果版本低于当前固件，则显示信息并设置状态为 FAILURE；否则继续下一步。

发送固件包：
FirmwareUpdater 开始逐块发送固件包数据，并等待设备确认。
每发送一块数据后，更新进度条。

校验固件：
FirmwareUpdater 发送固件校验命令。
设备返回校验结果，如果校验失败则设置状态为 FAILURE；否则继续下一步。

请求结束升级：
FirmwareUpdater 发送请求结束升级命令。
设备返回确认响应。

软重启设备：
FirmwareUpdater 发送软重启命令。
设备返回确认响应，FirmwareUpdater 显示升级成功信息。

关闭串口和启用控件：
FirmwareUpdater 关闭串口连接。
启用所有控件，允许用户进行其他操作。
"""
import threading
import time
import serial
import os
import struct
import zlib
from cb_const import *
import ttkbootstrap as ttkb

        
is_upgrading = False
def set_upgrading_state(state: bool):  # 设置升级状态
    global is_upgrading
    is_upgrading = state

def is_firmware_upgrading() -> bool:    # 获取升级状态
    return is_upgrading

class FirmwareUpdater:
    def __init__(self, parent, port, file_path, update_pb, update_pb_percent, update_button, frame, label, cb_show_log, custom_show_toast, enable_all_controls, disable_all_controls):
        self.port = port
        self.serial_port = None
        self.parent = parent
        self.file_path = file_path
        self.update_pb = update_pb
        self.update_pb_percent = update_pb_percent
        self.update_button = update_button
        self.frame = frame
        self.label = label
        self.cb_show_log = cb_show_log
        self.custom_show_toast = custom_show_toast
        self.enable_all_controls = enable_all_controls
        self.disable_all_controls = disable_all_controls
        self.state = "DONE"
        self.readed_version = None
        self.retry_count = 0
        self.max_retries = 1#3
        self.max_value = 100
        self.baudrate = 115200
        self.error_code = UpdateErrorCode.NORSP_ERR
        self.first_chunk_sent = False

        # self.version_input = self.parent.loc_version_widget.get()
        self.baudrate = int(self.parent.loc_baudrate_widget.get())
        # print(f"version_input={self.version_input}, baudrate={self.baudrate}")
        
        self.read_version_button = ttkb.Button(
            self.frame, 
            text="读取版本号", 
            command=lambda: self.read_version_only(), 
            bootstyle='outline'
        )
        self.read_version_button.grid(row=1, column=3, padx=5, pady=2)
        self.read_version_button.config(width=10) # 设置按键的最小宽度为10
        self.check_port_valid()
        # self.is_upgrading = False  # 增加升级状态标志


    def check_port_valid(self):
        self.read_version_only()


    def build_command(self, cmd_h, cmd_l, data):
        start_byte = 0x5A
        end_byte = 0x5B
        data_length = len(data)
        checksum = (cmd_h + cmd_l + data_length + sum(data)) & 0xFF
        command = [start_byte, cmd_h, cmd_l, 0x00, data_length] + data + [checksum, end_byte]
        
        # 打印命令的十六进制表示
        # command_bytes = bytes(command)
        # print(f"发送的命令: {command_bytes.hex().upper()}")

        return bytes(command)

    def parse_response(self, response):
        # print(f"收到的响应: {response.hex().upper()}")
        if len(response) < 6 or response[0] != 0x5A :#or response[-1] != 0x5B
            self.error_code = UpdateErrorCode.UNKNOWN_CMD
            return None
        cmd_h, cmd_l, resp, data_length = response[1:5]
        data = response[5:5+data_length]
        checksum = response[5+data_length]
        # 计算校验和，不包含包头
        calculated_checksum = (cmd_h + cmd_l + resp+ data_length + sum(data)) & 0xFF
        #print(f"---------------checksum={checksum}, calculated_checksum={calculated_checksum}")


        if checksum != calculated_checksum:
            self.error_code = UpdateErrorCode.CHECKSUM_ERR
            return None
        # print(f"cmd_h={cmd_h}, cmd_l={cmd_l}, resp={resp}, data_length={data_length}, data={data}, checksum={checksum}, calculated_checksum={calculated_checksum}")
        return cmd_h, cmd_l, resp, data
    
        

    def send_command(self, cmd_h, cmd_l, data):
        command = self.build_command(cmd_h, cmd_l, data)
        # print(f"Sending command: {command.hex()}")  # 打印发送的命令
        # 设置写超时为1s
        self.serial_port.write_timeout = 1
        try:
            self.serial_port.write(command)
        except serial.SerialTimeoutException as e:
            self.cb_show_log(f"写命令失败: {e}\n", "red")
            self.state = "QUIT_DIRECTLY"
            return None

        start_time = time.time()

        timeout = 3 if not self.first_chunk_sent else 0.5           # 升级失败重传机制的超时时间设置：重传的首包超时时间为3s，其他包的超时时间为0.5s
        
        # 逐字节读取，直到找到包头
        while True:
            # if time.time() - start_time > 5:  # 超时时间5秒
            if time.time() - start_time > timeout: 
                self.state = "FAILURE"
                self.error_code = UpdateErrorCode.NORSP_ERR
                return None
            start_byte = self.serial_port.read(1)
            if start_byte == b'\x5A':
                # 读取固定长度的前4字节（命令码 + 响应位 + 数据长度）
                header = self.serial_port.read(4)
                if len(header) < 4:
                    self.state = "FAILURE"
                    self.error_code = UpdateErrorCode.UNKNOWN_CMD
                    continue  # 包不完整，重新查找下一个5A
                
                # 解析数据长度
                data_length = header[3]
                
                # 读取剩余字节（数据 + 校验和）
                remaining_length = data_length + 1  # 数据长度 + 校验和
                data = self.serial_port.read(remaining_length)
                if len(data) < remaining_length:
                    # 数据不完整，重新查找下一个5A
                    continue
                
                # 组合完整的响应
                response = start_byte + header + data
                
                # 校验和验证（假设最后一个字节是校验和）
                checksum = sum(response[1:-1]) & 0xFF  # 从 header 开始计算，不包括 start_byte (0x5A) 和最后一个字节（校验和）
                if checksum != response[-1]:  # 校验和不匹配
                    print(f"Checksum error: expected {checksum}, got {response[-1]}, response={response}")
                    continue  # 校验失败，重新找下一个5A
                
                # 包合法，返回响应
                # print(f"Valid response: {response}")
                return self.parse_response(response)
                # return cmd_h, cmd_l, resp, data
        

    def update_firmware_thread(self):
        self.baudrate = int(self.parent.loc_baudrate_widget.get())
        if self.serial_port:
            if self.serial_port.is_open:
                self.serial_port.close()
                self.serial_port = None
        self.serial_port = serial.Serial(self.port, baudrate=self.baudrate, timeout=1)
        self.update_pb.config(bootstyle='success')
        self.cb_show_log(f"\n--------------------开始升级--------------------\n")
        self.cb_show_log(f"准备升级,当前波特率{self.baudrate}\n", "black")
        self.update_success_count = 0
        self.update_failure_count = 0
        while True:
            self.state = "READ_VERSION"
            while self.state != "DONE":
                if self.state == "READ_VERSION":            # 读取版本号
                    self.read_version()
                elif self.state == "CHECK_OTA":             # 固件版本检查
                    self.check_ota()
                elif self.state == "START_OTA":             # OTA开启请求
                    self.start_ota()
                elif self.state == "TRANSFER_PACKAGE":      # 传输固件包
                    self.transfer_package()
                elif self.state == "SOFT_RESET":            # 软重启设备
                    self.soft_reset()
                elif self.state == "RESET_UWB":             # 重启UWB模块
                    self.reset_uwb()
                elif self.state == "OTA_UPGRADE":           # 升级结束请求
                    self.ota_upgrade()
                elif self.state == "CHECK_FIRMWARE":        # 校验固件
                    self.check_firmware()
                elif self.state == "FAILURE":               # 升级失败
                    self.handle_failure()
                elif self.state == "QUIT_DIRECTLY":         # 退出升级
                    self.handle_quit()
                    break

            time.sleep(1)

            if not self.parent.loop_upgrade_var.get():
                break

            if self.error_code == UpdateErrorCode.SUCCESS:
                self.update_success_count += 1
                self.cb_show_log(f"----------------------------------升级成功次数:{self.update_success_count}     失败次数:{self.update_failure_count}\n", "green")
            else:
                self.update_failure_count += 1
                self.cb_show_log(f"----------------------------------升级成功次数:{self.update_success_count}     失败次数:{self.update_failure_count}\n", "red")
                    
        if self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None
        self.enable_all_controls()

    def read_version_only(self):
        print(self.state)
        if self.state not in ['DONE', 'FAILURE']:
            self.cb_show_log(f"正在升级，请稍后再尝试读取版本号\n", "red")
            return
        if not self.serial_port:
            self.baudrate = int(self.parent.loc_baudrate_widget.get())
            self.serial_port = serial.Serial(self.port, baudrate=self.baudrate, timeout=1)
        self.cb_show_log(f"\n-----------------读取单板版本号----------------\n")
        self.cb_show_log(f"正在尝试读取版本号\n", "black")
        response = self.send_command(0x01, 0x00, [])
        if self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None
        if response:
            cmd_h, cmd_l, resp, data = response
            if data[0] == 0xff and data[1] == 0xff:
                self.cb_show_log(f"读取固件版本失败\n", "red")
                self.readed_version = data      
            else:
                version_high = data[0]
                version_low = data[1]

                version_low = int.from_bytes(data[1:2], 'big')  
                version_decimal = f"{version_high:02X}{version_low:02X}"  
                self.cb_show_log(f"当前单板固件版本号: {version_decimal}\n", "green")
        else:
            self.cb_show_log(f"读取固件版本失败\n", "red")


    def read_version(self):
        self.cb_show_log(f"开始检测硬件版本\n", "black")
        response = self.send_command(0x01, 0x00, [])
        if response:
            #有响应说明串口是能正常通信的，把灯设置为绿色
            self.parent.update_status_icon(str(img_parent_path)+ '/icon/status_g.png')
            # self.cb_show_log(f"回应不为空\n")
            cmd_h, cmd_l, resp, data = response
            if (cmd_h != 0x01 or cmd_l != 0x00):
                self.cb_show_log(f"读取版本号的命令响应错误\n", "red")
                self.state = "FAILURE"
            else:
                if data[0] == 0xff and data[1] == 0xff:
                    self.cb_show_log(f"读取固件版本失败\n", "red")
                    self.readed_version = data
                    self.state = "FAILURE"
                    
                else:
                    version_high = data[0]
                    version_low = data[1]
                    # 假设 version_low 是 ASCII 字符，需要转换为整数
                    version_low = int.from_bytes(data[1:2], 'big')  # 将 ASCII 字符转换为整数
                    version_decimal = f"{version_high:02X}{version_low:02X}"  # 格式化为十进制字符串
                    self.cb_show_log(f"当前单板固件版本: {version_decimal}\n", "green")
                    # self.cb_show_log(f"当前单板固件版本: {data}\n", "green")
                    self.state = "CHECK_OTA"
        else:
            self.cb_show_log(f"读取固件版本失败\n", "red")
            self.state = "FAILURE"     #发送版本号命令后，如果没有响应重新发送版本命令。用于处理芯片在响应软复位命令后掉电的情况


    def check_ota(self):
        # self.version_input = self.parent.loc_version_widget.get()
        # firmware_version = [int(self.version_input[:2], 16), int(self.version_input[2:], 16)]
        file_path = self.file_path
        firmware_version = self.read_firmware_file_version(file_path)
        # print(f"firmware_version={firmware_version}")
        #firmware_version = [0x00, 0x01]  # 假设固件版本为1.0
        # self.cb_show_log(f"版本号检测：{firmware_version}\n", "black")
        version_hex = ''.join(f"{byte:02X}" for byte in firmware_version)
        self.cb_show_log(f"固件包版本号检测：{version_hex}\n", "green")
        response = self.send_command(0x01, 0x10, firmware_version)
        # return

        if response:
            cmd_h, cmd_l, resp, data = response
            # self.cb_show_log(f"cmd_h={cmd_h}, cmd_l={cmd_l}, resp={resp}, data={data}\n","black")
            if data[0] == 0x00:
                self.state = "TRANSFER_PACKAGE"#"START_OTA"
                # self.cb_show_log(f"开始发送固件包，版本号：{firmware_version}\n", "black")
                # self.cb_show_log(f"开始发送固件包，版本号：{version_hex}\n", "black")
                self.cb_show_log(f"开始发送固件包......\n", "black")
            elif data[0] == 0x01:
                self.cb_show_log(f"版本相同\n", "red")
                self.error_code = UpdateErrorCode.VERSION_ERR_0
                self.state = "FAILURE"
            elif data[0] == 0x02:
                self.cb_show_log(f"版本低于当前固件\n", "red")
                self.error_code = UpdateErrorCode.VERSION_ERR_0
                self.state = "FAILURE"
            else:
                self.cb_show_log(f"OTA开启请求失败0\n", "red")
                self.state = "FAILURE"
        else:
            self.cb_show_log(f"OTA开启请求失败1\n", "red")
            self.state = "FAILURE"

    def read_firmware_file_version(self, file_path):
        with open(file_path, 'rb') as f:
            f.seek(0x2000)  # 移动到0x2000位置
            version_bytes = f.read(2)  # 读取两个字节
            if len(version_bytes) < 2:
                raise ValueError("文件内容不足，无法读取版本号")
            # print(f"Read version bytes: {version_bytes[0]:02X}, {version_bytes[1]:02X}")  # 打印读取到的版本字节
            # print(f"Read version: {version_bytes[0]}.{version_bytes[1]}")  # 打印读取到的版本
            # return [version_bytes[0], version_bytes[1]]
            return [version_bytes[1], version_bytes[0]]
    
    def start_ota(self):
        self.cb_show_log(f"发送固件包完毕，固件正在升级，请勿断开连接或电源\n", "black")
        response = self.send_command(0x01, 0x10, [0x00, 0x00])  # 带固件版本
        if response and response[2] == 0x00:
            #cmd_h, cmd_l, resp, data = response #response[2]就是resp
            self.state = "TRANSFER_PACKAGE"
        else:
            self.state = "FAILURE"

    def transfer_package(self):
        set_upgrading_state(True)  # 开启升级标志
        # print(is_upgrading)
        try:
            with open(self.file_path, 'rb') as f:
                data = f.read()
                print(f"len(data)={len(data)}")
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset+128]
                chunk_length = len(chunk)
                #chunk_crc = struct.unpack('<I', struct.pack('<I', sum(chunk) & 0xFFFFFFFF))[0]
                chunk_crc = zlib.crc32(chunk) & 0xFFFFFFFF
                #chunk_crc = struct.unpack('>I', struct.pack('<I', chunk_crc))[0]
                payload = struct.pack('>I', offset) + struct.pack('B', chunk_length) + chunk + struct.pack('>I', chunk_crc)

                # response = self.send_command(0x01, 0x11, list(payload))
                # if response:
                #     cmd_h, cmd_l, resp, resp_data = response
                #     rsp_result = int(resp_data[0])
                #     #print(f"rsp_result={rsp_result}")
                #     if rsp_result != 0x00:
                #         self.state = "FAILURE"
                #         self.error_code = 19+rsp_result
                #         return
                # else:
                #     self.state = "FAILURE"
                #     return
                


                attempts = 3#单包传输失败重试次数
                while attempts > 0:
                    response = self.send_command(0x01, 0x11, list(payload))
                    if offset == 0:
                        self.first_chunk_sent = True  # 首包发送成功，重置标志
                    if response:
                        cmd_h, cmd_l, resp, resp_data = response
                        rsp_result = int(resp_data[0])
                        #print(f"rsp_result={rsp_result}")
                        if rsp_result == 0x00:
                            break
                    attempts -= 1

                    if attempts == 0:
                        self.state = "FAILURE"
                        self.error_code = 19 + rsp_result if response else UpdateErrorCode.UNKNOWN_ERR
                        return

                offset += chunk_length
                #print(f"chunk={chunk},\r\n chunk_crc={chunk_crc:08X}\r\n, payload={payload}\r\n")
                self.update_pb["value"] = int(offset / len(data) * 100)
                self.frame.update_idletasks()
                self.update_pb_percent.config(text=f"{int(offset / len(data) * 100)}%")
            #self.state = "CHECK_OTA"
            self.cb_show_log(f"已发送{offset}字节数据\r\n", "black")
            self.state = "CHECK_FIRMWARE"
            self.first_chunk_sent = False  # 重传结束，重置标志位
        except Exception as e:
            # self.custom_show_toast("升级失败，错误码0x0001")
            self.state = "FAILURE"
        finally:
            set_upgrading_state(False)  # 关闭升级标志
            # print(is_upgrading)
            # print("升级结束")

    def check_firmware(self):
        # 读取bin文件内容
        with open(self.file_path, 'rb') as f:
            data = f.read()
            # 计算文件的 CRC32 值
        total_crc = zlib.crc32(data) & 0xFFFFFFFF
        print(f"total_crc={total_crc:08X}")
        response = self.send_command(0x01, 0x12, list(struct.pack('>I', total_crc)))

        if response:
            cmd_h, cmd_l, resp, resp_data = response
            rsp_result = int(resp_data[0])
            #print(f"rsp_result={rsp_result}")
            if rsp_result != 0x00:
                self.state = "FAILURE"
                self.error_code = UpdateErrorCode.FILE_CRC_ERR
                return
            else:
                self.state = "OTA_UPGRADE"
        else:
            self.state = "FAILURE"

    def soft_reset(self):
        self.cb_show_log(f"请求结束升级成功，正在重启设备。\n", 'green')
        response = self.send_command(0x01, 0x20, [])
        if response:
            cmd_h, cmd_l, resp, resp_data = response
            rsp_result = int(resp_data[0])
            #print(f"rsp_result={rsp_result}")
            if rsp_result != 0x00:
                self.state = "FAILURE"
                self.error_code = UpdateErrorCode.REQ_RESET_ERR
                return
            else:
                self.state = "DONE"   
                # self.cb_show_log(f"升级完成。\n", 'green')
                self.cb_show_log(f"\n--------------------升级完成--------------------\n", 'green')
                self.error_code = UpdateErrorCode.SUCCESS
                # self.update_success_count += 1
                # 继续读取串口数据，超时时间1秒
                start_time = time.time()
                while time.time() - start_time < 1:
                    reboot_serial_data = self.serial_port.read_until()
                    if reboot_serial_data:
                        self.cb_show_log(f"{reboot_serial_data}\n", 'green')
                        return
                    time.sleep(1)  # 等待1秒后再尝试读取
        else:
            self.state = "FAILURE"

    def reset_uwb(self):
        response = self.send_command(0x01, 0x20, [])
        if response and response[2] == 0x00:
            self.state = "OTA_UPGRADE"
        else:
            self.state = "FAILURE"

    def ota_upgrade(self):
        self.cb_show_log(f"文件校验成功,正在请求结束升级。\n", 'green')
        response = self.send_command(0x01, 0x13, [])

        if response:
            cmd_h, cmd_l, resp, resp_data = response
            rsp_result = int(resp_data[0])
            #print(f"rsp_result={rsp_result}")
            if rsp_result != 0x00:
                self.state = "FAILURE"
                self.error_code = UpdateErrorCode.REQ_END_ERR
                return
            else:
                self.state = "SOFT_RESET"
        else:
            self.state = "FAILURE"

    def handle_failure(self):
        set_upgrading_state(False)  # 关闭升级标志
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            # self.update_failure_count += 1
            if isinstance(self.error_code, UpdateErrorCode):
                error_code_int = self.error_code.value  # 获取枚举的整数值
            else:
                error_code_int = int(self.error_code)  # 确保 error_code 是整数类型
            self.cb_show_log(f"升级失败  错误码:0X{error_code_int:04X}\n", 'red')
            self.state = "DONE"
            #             self.update_pb["value"] = int(offset / len(data) * 100)
            self.update_pb.config(bootstyle='danger')
            self.enable_all_controls()
        else:
            self.cb_show_log(f"重试第{self.retry_count}次\n", 'red')
            self.state = "READ_VERSION"
    
    def handle_quit(self):
        self.state = "DONE"
        self.cb_show_log(f"升级已取消\n", 'red')
        set_upgrading_state(False)  # 关闭升级标志


