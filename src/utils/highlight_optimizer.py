import openpyxl

class HighlightOptimizer:
    """高亮标记优化器，提供缓存和批量处理功能。
    旨在提高Excel写入时高亮操作的性能，通过缓存单元格值和行状态来减少重复计算和Openpyxl的API调用。
    """
    
    def __init__(self):
        """初始化高亮优化器。"""
        # 缓存字典
        self.cell_value_cache = {}  # 缓存单元格值，格式为 {(row_idx, col_idx): value_str}
        self.row_status_cache = {}  # 缓存行状态，格式为 {(sheet_title, row_idx): status_dict}
        self.empty_rows_cache = set()  # 缓存空行信息（行索引集合）
        self.non_empty_rows_cache = set()  # 缓存非空行信息（行索引集合）
        
    def clear_cache(self):
        """清空所有缓存，在处理新的工作表或文件前调用。"""
        self.cell_value_cache.clear()
        self.row_status_cache.clear()
        self.empty_rows_cache.clear()
        self.non_empty_rows_cache.clear()
    
    def get_cell_value_cached(self, cell):
        """获取单元格值（带缓存）。
        Args:
            cell (openpyxl.cell.cell.Cell): Openpyxl单元格对象。
        Returns:
            str: 单元格的字符串值，去除首尾空格。
        """
        cell_key = (cell.row, cell.column) # 使用行号和列号作为缓存键
        if cell_key not in self.cell_value_cache:
            value = cell.value
            self.cell_value_cache[cell_key] = str(value).strip() if value else "" # 缓存处理后的字符串值
        return self.cell_value_cache[cell_key]
    
    def is_row_empty_cached(self, sheet, row_idx, start_col=1, end_col=None):
        """检查行是否为空（带缓存）。
        Args:
            sheet (openpyxl.worksheet.worksheet.Worksheet): Openpyxl工作表对象。
            row_idx (int): 行索引（1-based）。
            start_col (int, optional): 开始检查的列索引（1-based）。默认为1。
            end_col (int, optional): 结束检查的列索引（1-based）。默认为工作表的最后一列。
        Returns:
            bool: 如果行为空则返回True。
        """
        if row_idx in self.empty_rows_cache:
            return True # 已知为空行，直接返回
        if row_idx in self.non_empty_rows_cache:
            return False # 已知为非空行，直接返回
            
        # 实际检查逻辑
        if end_col is None:
            end_col = sheet.max_column
            
        is_empty = True
        row = sheet[row_idx] # 获取整行数据
        for col_idx in range(start_col - 1, min(end_col, len(row))): # 遍历指定列范围
            if col_idx < len(row):
                cell = row[col_idx]
                if cell and cell.value is not None and str(cell.value).strip():
                    is_empty = False # 发现非空单元格
                    break
        
        # 缓存结果
        if is_empty:
            self.empty_rows_cache.add(row_idx)
        else:
            self.non_empty_rows_cache.add(row_idx)
            
        return is_empty
    
    def batch_get_category_values(self, sheet, category_col_letter, start_row, end_row):
        """批量获取"更新情况（标记）"列的值。
        Args:
            sheet (openpyxl.worksheet.worksheet.Worksheet): Openpyxl工作表对象。
            category_col_letter (str): "更新情况（标记）"列的字母表示（如'A'）。
            start_row (int): 开始行索引（1-based）。
            end_row (int): 结束行索引（1-based）。
        Returns:
            dict: 格式为 {row_idx: category_value} 的字典。
        """
        category_values = {}
        try:
            category_column = sheet[category_col_letter] # 获取整列数据
            for row_idx in range(start_row, min(end_row + 1, len(category_column) + 1)): # 遍历指定行范围
                if row_idx - 1 < len(category_column):
                    cell = category_column[row_idx - 1]
                    if cell:
                        value = self.get_cell_value_cached(cell) # 使用缓存获取单元格值
                        category_values[row_idx] = value
        except Exception as e:
            # 如果批量获取失败，回退到逐个获取（此分支通常不应发生，除非Openpyxl内部错误）
            pass
        return category_values
    
    def get_row_status_cached(self, sheet, row_idx, category_value, diff_info, col_name_to_idx):
        """获取行状态（带缓存）。
        判断行是否需要高亮，并找出需要高亮的具体单元格。
        Args:
            sheet (openpyxl.worksheet.worksheet.Worksheet): Openpyxl工作表对象。
            row_idx (int): 行索引（1-based）。
            category_value (str): "更新情况（标记）"列的值（如"新增", "删除", "更新"）。
            diff_info (dict): 单元格级别的差异信息（来自compare_columns_by_sas_names的diff_dict）。
            col_name_to_idx (dict): 列名到列索引（1-based）的映射。
        Returns:
            dict: 包含行状态信息的字典。
        """
        cache_key = (sheet.title, row_idx) # 使用工作表标题和行号作为缓存键
        if cache_key in self.row_status_cache:
            return self.row_status_cache[cache_key] # 已知行状态，直接返回
        
        # 计算行状态
        status = {
            'category': category_value, # 变更类别
            'needs_highlight': False, # 是否需要高亮整行或部分单元格
            'highlight_cells': [], # 需要高亮的单元格列表 (存储列名或列索引，而非单元格对象)
            'is_empty': False # 行是否为空（目前未使用，保留）
        }
        
        if category_value in ["新增", "删除", "更新"]:
            status['needs_highlight'] = True # 标记该行需要高亮
            
            if category_value in ["新增", "删除"]:
                # 对于新增或删除的行，标记高亮整行 (通过设置highlight_cells为特殊的'ALL'标记)
                status['highlight_cells'] = ['ALL'] 
                    
            elif category_value == "更新":
                # 对于更新的行，返回需要高亮的列名列表
                data_row_idx = row_idx - 2 # df_row_idx是DataFrame的0-based索引，而Excel的row_idx是1-based，且包含表头。
                if diff_info and data_row_idx in diff_info: # 检查该行是否有详细差异信息
                    status['highlight_cells'] = list(diff_info[data_row_idx].keys()) # 存储有差异的列名
        
        # 缓存结果
        self.row_status_cache[cache_key] = status
        return status 