import { ref } from "vue";

const STORAGE_KEY = "dc_auto_download";

const enabled = ref(localStorage.getItem(STORAGE_KEY) !== "off");

export function useAutoDownload() {
  function setEnabled(value) {
    enabled.value = value;
    localStorage.setItem(STORAGE_KEY, value ? "on" : "off");
  }

  return { enabled, setEnabled };
}
