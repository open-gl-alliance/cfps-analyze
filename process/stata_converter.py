"""
该文件接受 stata 文件并根据 stata 输出 schema （纲要）文件
纲要文件储存了每一列的意义、取值范围等信息
"""

import pandas as pd
import os
import sys
from utils import require_python_310, write_json

BASIC_MAPPING_A = {-10: '无法判断', -9: '缺失', -8: '不适用', -2: '拒绝回答', -1: '不知道'}
BASIC_MAPPING_B = {-9: '缺失', -8: '不适用', -2: '拒绝回答', -1: '不知道'}
BASIC_MAPPINGS = [BASIC_MAPPING_A, BASIC_MAPPING_B,
                  {
                      -10: "无法判断",
                      -9: "缺失",
                      -8: "不适用",
                      -2: "拒绝回答",
                      -1: "不知道",
                      1: "是",
                      5: "否",
                      79: "情况不适用"
                  },
                  {
                      -10: "无法判断",
                      -9: "缺失",
                      -8: "不适用",
                      -2: "拒绝回答",
                      -1: "不知道",
                      77: "其他",
                      78: "以上都没有",
                      79: "没有"
                  }, ]


def is_basic_mapping(mapping) -> bool:
    return mapping in BASIC_MAPPINGS


def convert_sta_file_to_reader(file_path):
    """
    返回一种特殊的格式：StataReader，专用于处理 Stata 的类
    """
    stata = pd.read_stata(file_path, iterator=True)
    return stata


def convert_sta_file_to_df(file_path: str) -> pd.DataFrame:
    """
    利用 pandas 直接将 stata 文件读取为 DataFrame 格式
    """
    stata = pd.read_stata(file_path, convert_categoricals=False)
    return stata


def write_sta_file_variable_labels(reader, sta_path):
    # .variable_labels(): Return a dict associating each variable name with corresponding label
    write_json(reader.variable_labels(), sta_path + '.labels.json')


def convert_numpy_indexed_dict_to_serializable_dict(dic):
    return {key.item(): dic[key] for key in dic}


def any_number_not_in_enum_range(df_col, range):
    return any(num not in range and not pd.isna(num) for num in df_col)


def convert_to_serializable_num(n):
    return n.item() if 'item' in dir(n) else n


def write_sta_file_variable_schemas(reader, df: pd.DataFrame, sta_path):
    """
    处理 stata 并输出数据的纲要文件（json 格式）
    """
    print(f"Processing: {sta_path}")
    labels = reader.variable_labels() # 取出每列的表情
    vlabels = reader.value_labels() # 
    schemas = {key: {
        'type': 'enum' if not is_basic_mapping(vlabels.get(key, BASIC_MAPPING_A)) else str(df[key].dtype),
        'key': labels[key],
        'range': convert_numpy_indexed_dict_to_serializable_dict(vlabels[key]) if not is_basic_mapping(
            vlabels.get(key, BASIC_MAPPING_A))
        else list(convert_to_serializable_num(v) for v in df[key].unique()),
        'details': [],
        'minmax': list(map(convert_to_serializable_num, [df[key].min(), df[key].max()]))
            if df[key].dtype != 'object' else None
    } for key in labels}
    for x in schemas:
        value = schemas[x]
        if value['type'] == 'float64':
            if all(num.is_integer() for num in value['range']):
                value['range'] = [int(x) for x in value['range']]
                value['type'] = 'int32'
        if len(value['range']) == len(df[x]):
            value['range'] = {"min": min(
                value['range']), "max": max(value['range'])}
            value['details'].append(f"{x} 取值各不相同，疑似 ID，已转换 range 为最大、最小值")
        elif len(value['range']) > 500 and value['type'] != 'enum':
            value['range'] = {"min": min(
                value['range']), "max": max(value['range'])}
            value['details'].append(f"{x} 取值多于 500 个，已转换 range 为最大、最小值")
        write_json(schemas, sta_path + '.schemas.json')


if __name__ == "__main__":
    require_python_310()
    # sys.argv 读取命令行输入的参数
    # 例如 python process/stata_converter.py gen-schemas dataset 中
    # 会返回字符串列表 ["process/stata_converter.py", "gen-schemas", "dataset"]
    if len(sys.argv) != 3:
        print("错误！参数不足。")
        sys.exit(1)
    dir_path = sys.argv[2]
    if not os.path.isdir(dir_path):
        print("错误！指定的目录不存在。")
        sys.exit(1)
    match sys.argv[1]:
        case "gen-labels":
            # 遍历文件，对于每个 .dta 文件，输出所有列名
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(".dta"):
                        file_path = os.path.join(root, file)
                        reader = convert_sta_file_to_reader(file_path)
                        write_sta_file_variable_labels(reader, file_path)
            print("成功！")
        case "gen-csv":
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(".dta"):
                        file_path = os.path.join(root, file)
                        df = convert_sta_file_to_df(file_path)
                        df.to_csv(file_path + ".csv")
            print("成功！")
        case "gen-schemas":
            # 输出所有列的大纲
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(".dta"):
                        file_path = os.path.join(root, file)
                        df = convert_sta_file_to_df(file_path)
                        reader = convert_sta_file_to_reader(file_path)
                        write_sta_file_variable_schemas(reader, df, file_path)
            print("成功！")
