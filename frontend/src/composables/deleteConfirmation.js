function formatQuestionTargetText(targetText) {
  return /["”]$/.test(targetText) ? `${targetText} ` : targetText
}

export async function confirmDelete(confirm, options = {}) {
  const actionText = options.actionText || '删除'
  const targetText = options.targetText || '该内容'
  await confirm(`确认${actionText}${formatQuestionTargetText(targetText)}吗？`, options.title || '确认', {
    type: 'warning',
    confirmButtonText: options.firstConfirmButtonText || `确认${actionText}`,
    cancelButtonText: '取消',
  })
}

export async function confirmFinalDelete(confirm, options = {}) {
  const actionText = options.actionText || '删除'
  const targetText = options.targetText || '该内容'
  const recoveryNotice = options.recoverable
    ? '删除后如需恢复，请联系管理员。'
    : '此操作不可恢复。'
  await confirm(
    `请再次确认：确定要${actionText}${formatQuestionTargetText(targetText)}吗？${recoveryNotice}`,
    '最终确认',
    {
      type: 'warning',
      confirmButtonText: options.confirmButtonText || '确认删除',
      cancelButtonText: '取消',
    }
  )
}
