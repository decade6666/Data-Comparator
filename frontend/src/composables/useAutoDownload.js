import { ref } from "vue";

const STORAGE_KEY = "dc_auto_download";

const enabled = ref(localStorage.getItem(STORAGE_KEY) !== "off");

// 任务级去重：同一任务只自动下载一次（含切走项目后再完成、重复轮询命中）。
// 模块级 Set，跨组件重渲染稳定；测试通过 resetDownloaded() 清空。
const downloadedJobIds = new Set();

export function useAutoDownload() {
  function setEnabled(value) {
    enabled.value = value;
    localStorage.setItem(STORAGE_KEY, value ? "on" : "off");
  }

  function resetDownloaded() {
    downloadedJobIds.clear();
  }

  return { enabled, setEnabled, downloadedJobIds, resetDownloaded };
}
