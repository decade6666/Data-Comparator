# 全局配置变量
EDC = "" # 电子数据采集系统类型（如CIMS, TM等），用于解析Excel表头结构
EXCLUDE_SHEETS = [] # 需要排除不进行比对的Sheet名称列表
COMMON_COLS_TO_DROP = [] # 在生成结果时需要删除的通用列名列表
DEFAULT_KEYS = [] # 默认的锚点列（用于行匹配的唯一标识符），当特定Sheet没有指定锚点时使用
SHEET_KEY_MAP = {} # 存储特定Sheet的锚点列映射，键为Sheet名称，值为锚点列列表
HIGHLIGHT_FILL = None  # 用于高亮显示差异单元格的填充样式
MISSING_SHEET_TAB_FILL = None # 用于标记缺失Sheet（在新文件中不存在）的标签填充样式
NEW_SHEET_TAB_FILL = None # 用于标记新增Sheet（在旧文件中不存在）的标签填充样式 