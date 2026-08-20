export function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes)) || Number(bytes) < 0) return '-'
  const value = Math.trunc(Number(bytes))
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = value
  for (const unit of units) {
    size /= 1024
    if (size < 1024) {
      if (size < 1) return '< 1 KB'
      return `${size.toFixed(1)} ${unit}`
    }
  }
  return `${size.toFixed(1)} TB`
}
