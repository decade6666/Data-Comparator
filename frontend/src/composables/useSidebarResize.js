import { ref } from 'vue'

export function useSidebarResize() {
  const sidebarWidth = ref(220)
  const resizerStyle = ref({})

  function startResize(event) {
    const startX = event.clientX
    const startWidth = sidebarWidth.value
    resizerStyle.value = { cursor: 'col-resize', userSelect: 'none' }

    function onMove(moveEvent) {
      const width = startWidth + (moveEvent.clientX - startX)
      sidebarWidth.value = Math.min(400, Math.max(120, width))
    }

    function onUp() {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      resizerStyle.value = {}
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return { sidebarWidth, resizerStyle, startResize }
}
