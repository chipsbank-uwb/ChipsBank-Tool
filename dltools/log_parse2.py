
import re
from collections import defaultdict


limit_up = 1000
limit_down = -1000
limit_control = 0


def parse_line(line):
    """
    解析单行日志，提取 key-value 对，并自动添加全局序号前缀。
    支持逗号、分号分割，支持括号值、单位、嵌套结构等复杂格式。
    """
    line = line.replace(" ", "")
    def add_global_index_to_segments(full_line):
        # 使用负向先行断言分割逗号或分号（跳过括号内部分）
        parts = re.split(r'[;,](?![^()]*\))', full_line)
        valid_parts = [part.strip() for part in parts if part.strip()]
        return [f"{i}_{part}" for i, part in enumerate(valid_parts)]
    
    def remove_non_numeric_parentheses(s):
        """移除括号内全是非数值字符的部分"""
        def replace(match):
            content = match.group(1)
            if not re.search(r'[0-9.-]', content):
                return ''  # 全非数值，移除括号及内容
            return match.group(0)  # 包含数值，保留括号及内容
        return re.sub(r'\(([^()]*)\)', replace, s)

    processed_parts = add_global_index_to_segments(remove_non_numeric_parentheses(line))
    processed_line = ",".join(processed_parts)

    def parse_segment(segment_str, prefix=""):
        parsed = {}

        parts = re.split(r',(?![^()]*\))', segment_str)
        # print("parts:",parts)
        for part in parts:
            part = part.strip()
            if not part:
                continue
        

            # 匹配 "Key: (val1,val2)unit"
            if match := re.match(r'^\s*([\w\s]+?)\s*:\s*\(([^)]+)\)\s*(\w*)\s*$', part):
                key = prefix + match.group(1).strip()
                values = [v.strip() for v in match.group(2).split(',') if v.strip()]
                filtered_values = []
                for val in values:
                    try:
                        f_val = float(val)
                        if limit_control:
                            if f_val >= limit_up:
                                f_val = limit_up
                            elif f_val <= limit_down:
                                f_val = limit_down
                        filtered_values.append(f_val)
                    except:
                        pass
                for idx, val in enumerate(filtered_values):
                    parsed[f"{key}_{idx}"] = val
                continue

            # 匹配 "Key: valueunit" （如 D:15.812289cm）
            if match := re.match(r'^\s*([\w\s]+?)\s*:\s*([+-]?\d+\.?\d*)\s*(\w*)\s*$', part):
                key = prefix + match.group(1).strip()
                val_str = match.group(2)
                try:
                    val = float(val_str)
                    if limit_control:
                        if val >= limit_up:
                            val=limit_up
                        elif val <= limit_down:
                            val=limit_down
                    parsed[key] = val
                except:
                    pass
                continue

            # 新增：匹配 "Key: value (description)"，如 PD12:67.172462 (in degrees)
            if match := re.match(r'^\s*([\w\d_]+)\s*:\s*([+-]?\d+\.?\d*)\s*$(?:[^)]*)?$', part):
                key = prefix + match.group(1).strip()
                try:
                    val = float(match.group(2))
                    if limit_control:
                        if val >= limit_up:
                            val=limit_up
                        elif val <= limit_down:
                            val=limit_down
                    parsed[key] = val
                except:
                    pass
                continue

            # 处理混合内容中的括号数值（如 MixCase:Hello,(1.1,2.2),End）
            if '(' in part and ')' in part:
                for nested_match in re.finditer(r'\(([^)]+)\)', part):
                    values = [v.strip() for v in nested_match.group(1).split(',') if v.strip()]
                    temp_key = f"{prefix}mixed_{len(parsed)}"
                    filtered_values = []
                    for val in values:
                        try:
                            f_val = float(val)
                            if limit_control:
                                if f_val >= limit_up:
                                    f_val=limit_up
                                elif f_val <= limit_down:
                                    f_val=limit_down
                            filtered_values.append(f_val)
                        except:
                            pass
                    for idx, val in enumerate(filtered_values):
                        parsed[f"{temp_key}_{idx}"] = val
                continue

            # 处理嵌套结构（如 INIT:Azi:10deg）
            if match := re.match(r'^\s*(\w+)\s*:\s*(.+)', part):
                key, sub = match.groups()
                parsed.update(parse_segment(sub, prefix=f"{prefix}{key}_"))

        return parsed

    result = {}
    for segment in processed_line.split(";"):
        result.update(parse_segment(segment.strip()))
    return result

def aggregate_logs(datasets):
    for name, lines in datasets.items():
        print(f"\n{'='*30} {name} {'='*30}")

#         # Step 1: 找到连续三行键一致的起始索引
#         standard_keys = None
#         window_size = 3
#         valid_data = []

#         for i in range(len(lines) - window_size + 1):
#             window_lines = lines[i:i+window_size]
#             parsed_list = [parse_line(line) for line in window_lines]

#             key_sets = [set(parsed.keys()) for parsed in parsed_list]
#             lengths = [len(keys) for keys in key_sets]

#             if all(keys == key_sets[0] for keys in key_sets) and len(set(lengths)) == 1:
#                 standard_keys = key_sets[0]
#                 print(f"使用第 {i+1}-{i+3} 行作为标准键：{standard_keys}")
#                 valid_data.extend(parsed_list)
#                 break

#         if not standard_keys:
#             print("未找到连续三行键一致的数据")
#             return

#         # Step 2: 继续解析后续所有行，并只保留键一致的
#         for line in lines[i+window_size:]:
#             parsed = parse_line(line)
#             if set(parsed.keys()) == standard_keys:
#                 valid_data.append(parsed)

#         # Step 3: 聚合结果
#         aggregated = defaultdict(list)
#         for data in valid_data:
#             for key in sorted(standard_keys):
#                 aggregated[key].append(data.get(key))

#         # 输出结果
#         for key in sorted(standard_keys):
#             print(f"{key.ljust(20)}: {aggregated[key]}")

# if __name__ == "__main__":
#     # 定义所有数据集
#     datasets = {
#         "lines": [
#             "Cycle:4857, D:15.812289cm,PD01:15.007782, PD02:82.180244, PD12:67.172462 (in degrees),azimuth: 15.944541 degrees,elevation: -30.000000 degrees",
#             "Cycle:4858, D:15.577863cm,PD01:22.028259, PD02:85.075226, PD12:63.162327 (in degrees),azimuth: 17.093344 degrees,elevation: -30.000000 degrees",
#             "Cycle:4859, D:14.406153cm,PD01:13.052156, PD02:78.186592, PD12:65.134438 (in degrees),azimuth: 14.359758 degrees,elevation: -30.000000 degrees",
#             "NewKey:100,UnknownTuple:(1,2,3)"
#         ],
#         "lines0": [
#             "Idx:47,D:332.10cm,MPF:0,INIT:Temp:33.7C,RESP:Azi:-40.09deg,Ele:-10000deg,PDOA:(-10000,-116.21,-10000)deg,RSSI:(-65,-10000,-58)dBm,Gain_idx:3,Temp:35.0C",
#             "Idx:48,D:332.22cm,MPF:0,INIT:Temp:34.6C,RESP:Azi:-40.09deg,Ele:-10000deg,PDOA:(-10000,-115.95,-10000)deg,RSSI:(-65,-10000,-58)dBm,Gain_idx:3,Temp:35.9C",
#             "Idx:49,D:331.75cm,MPF:0,INIT:Temp:33.7C,RESP:Azi:-39.86deg,Ele:-10000deg,PDOA:(-10000,-115.44,-10000)deg,RSSI:(-65,-10000,-58)dBm,Gain_idx:3,Temp:35.0C"
#         ],
#         "lines1": [
#                 "Idx:29921,Dis:107.69cm,MPF:0,INIT:Azi:0.00deg,PDOA:(2.07)deg,RSSI:(0,0)dBm,Gain_idx:0;RESP:Azi:8.64deg,Ele:0.00deg,PDOA:(-27.54,16.48,44.46)deg,RSSI:(-80,0,0)dBm,Gain_idx:1",
#                 "Idx:29922,Dis:108.51cm,MPF:0,INIT:Azi:0.00deg,PDOA:(2.07)deg,RSSI:(0,0)dBm,Gain_idx:0;RESP:Azi:8.78deg,Ele:0.00deg,PDOA:(-28.91,16.05,45.08)deg,RSSI:(-78,0,0)dBm,Gain_idx:0",
#                 "Idx:29923,Dis:107.69cm,MPF:0,INIT:Azi:0.00deg,PDOA:(2.07)deg,RSSI:(0,0)dBm,Gain_idx:0;RESP:Azi:8.44deg,Ele:0.00deg,PDOA:(-28.97,14.70,43.52)deg,RSSI:(-79,0,0)dBm,Gain_idx:0",
#                 "Idx:29925,Dis:107.69cm,MPF:0,INIT:Azi:0.00deg,PDOA:(2.07)deg,RSSI:(0,0)dBm,Gain_idx:0;RESP:Azi:9.10deg,Ele:0.00deg,PDOA:(-28.64,17.24,46.57)deg,RSSI:(-79,0,0)dBm,Gain_idx:0",
#         ]
#     }

#     aggregate_logs(datasets)

    # # 新增测试用例验证修复
    # test_cases = {
    #     "fix_test": [
    #         "SingleValue:(123.45)",         # 带括号单值
    #         "MultiValues:(1, 2.3, -4)",     # 带括号多值
    #         "WithUnit:(56.7)dBm",           # 带单位
    #         "SpaceTest : ( 78.9 ) deg",      # 含空格
    #         "MixCase:Hello,(1.1,2.2),End" ,  # 混合内容
    #         "PD12:67.172462 (in degrees)",
    #     ]
    # }
    # aggregate_logs(test_cases)