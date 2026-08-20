export const PARAMETER_DESCRIPTIONS = {
  common_cols: '读取时直接丢弃、不参与比对和输出的列。',
  sheet_scope: '选择需要参与比对和输出的表单；列表来自上传文件扫描结果。',
  ignore_settings: '字段仍会输出，但差异不计入高亮与汇总；填写表单时只对该表单生效。',
  anchor_settings: '用于定位新旧数据对应行的关键列；填写表单时覆盖默认锚点。',
  sheet_order: '设置结果文件中的表单输出顺序，未列出的表单追加在末尾。',
}

export function parameterDescription(key) {
  return PARAMETER_DESCRIPTIONS[key] || '配置项功能说明。'
}
