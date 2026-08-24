import { ref } from "vue";

const STORAGE_KEY = "dc_auto_download";

const enabled = ref(localStorage.getItem(STORAGE_KEY) !== "off");

// 自动下载把 jobId 绑定到「提交时刻」的项目：提交后切换项目再完成，
// 仍下载原项目的结果，不会错下新项目（Critical 修复）。
const committedJobId = ref(null);

export function useAutoDownload() {
  function setEnabled(value) {
    enabled.value = value;
    localStorage.setItem(STORAGE_KEY, value ? "on" : "off");
  }

  function captureJobId(jobId) {
    committedJobId.value = jobId;
  }

  function resetCommittedJobId() {
    committedJobId.value = null;
  }

  return { enabled, setEnabled, committedJobId, captureJobId, resetCommittedJobId };
}
