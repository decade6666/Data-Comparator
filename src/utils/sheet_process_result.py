import pandas as pd

class SheetProcessResult:
    """单个sheet的处理结果
    封装了单个Excel Sheet比对处理后的所有相关信息和结果。
    """
    def __init__(self, sheet_name):
        """
        初始化SheetProcessResult对象。
        Args:
            sheet_name (str): 被处理的Sheet名称。
        """
        self.sheet_name = sheet_name # Sheet名称
        self.success = False # 处理是否成功
        self.error_message = None # 如果处理失败，存储错误信息
        # self.worksheet_data = None # 已移除: 不再存储 openpyxl worksheet 对象，避免内存占用
        self.change_type = None  # 变更类型：'new'（新增）, 'missing'（缺失）, 'data_changed'（数据有变化）, None（无变化）
        self.differences = None # 存储单元格级别的差异信息（dict格式）
        self.add_sas_names = [] # 新增的SAS列名列表
        self.del_sas_names = [] # 删除的SAS列名列表
        self.sas_file_names = [] # 最终结果DataFrame的列名（SASFieldNames）
        self.sas_file_labels = [] # 最终结果DataFrame的列标签（SASFieldLabels）
        self.sas_name_to_label = {} # SAS列名到列标签的映射字典
        self.is_split_result = False    # 是否为拆分处理的结果（目前未使用，保留）
        self.split_chunks = []          # 拆分的子结果列表（目前未使用，保留）
        self.original_source_file = None # 原始Excel文件路径（用于复制格式）
        self.original_source_sheet_name = None # 原始Sheet名称（用于复制格式）
        self.df = None # 直接存储最终的DataFrame，用于后续合并和保存
        # 以下三个字段用于“比对结果汇总”统计
        self.updated_rows_count = 0
        self.deleted_rows_count = 0
        self.added_rows_count = 0 