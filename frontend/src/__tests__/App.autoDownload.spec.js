import { describe, expect, it, vi, beforeEach } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";

vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const { api } = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    download: vi.fn(),
  },
}));

const autoDownloadEnabled = ref(true);
const downloadedJobIds = new Set();

vi.mock("../composables/useApi", () => ({ api }));

vi.mock("../composables/useAutoDownload", () => ({
  useAutoDownload: () => ({
    enabled: autoDownloadEnabled,
    setEnabled: vi.fn(),
    downloadedJobIds,
    resetDownloaded: vi.fn(() => downloadedJobIds.clear()),
  }),
}));

// 可控的 useJob mock：暴露 onTerminal 回调供测试驱动终态触发
// setOnTerminal 的实现写模块级变量，测试通过 fireTerminal 直接调用。
let onTerminalCallback = null;
const jobMock = {
  jobId: ref(null),
  status: ref("idle"),
  progress: ref(0),
  progressMessage: ref("准备就绪"),
  logLines: ref([]),
  logCursor: ref(0),
  outputPath: ref(null),
  error: ref(null),
  outputName: ref(""),
  submit: vi.fn(),
  cancel: vi.fn(),
  download: vi.fn(),
  downloadLogs: vi.fn(),
  downloadFor: vi.fn(),
  downloadLogsFor: vi.fn(),
  entryFor: vi.fn(() => undefined),
  setOnTerminal: vi.fn((cb) => {
    onTerminalCallback = cb;
  }),
  reset: vi.fn(),
};

vi.mock("../composables/useJob", () => ({ useJob: () => jobMock }));

const elStubs = {
  "el-button": {
    name: "ElButtonStub",
    props: ["type", "icon", "loading", "disabled", "link", "size"],
    template:
      '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  "el-tooltip": {
    name: "ElTooltipStub",
    template: '<span class="el-tooltip-stub"><slot /></span>',
  },
  "el-tag": {
    name: "ElTagStub",
    template: '<span class="el-tag-stub"><slot /></span>',
  },
  "el-icon": {
    name: "ElIconStub",
    template: '<span class="el-icon-stub"><slot /></span>',
  },
  "el-progress": {
    name: "ElProgressStub",
    props: ["percentage", "strokeWidth", "striped", "color"],
    template: '<div class="el-progress-stub"><slot /></div>',
  },
  "el-dialog": {
    name: "ElDialogStub",
    props: ["modelValue", "title", "width", "appendToBody"],
    template:
      '<div v-if="modelValue" class="el-dialog-stub"><div class="el-dialog-title">{{ title }}</div><slot /><slot name="footer" /></div>',
  },
};

async function mountApp() {
  const App = (await import("../App.vue")).default;
  const wrapper = mount(App, {
    global: {
      stubs: {
        ConfigSidebar: { template: '<div class="stub-config-sidebar" />' },
        CompareForm: { template: '<div class="stub-compare-form" />' },
        ProgressPanel: { template: '<div class="stub-progress-panel" />' },
        ActionBar: { template: '<div class="stub-action-bar" />' },
        NewConfigDialog: true,
        AdvancedSettingsDialog: true,
        LoginView: true,
        ...elStubs,
      },
    },
  });
  await flushPromises();
  return wrapper;
}

// 直接触发终态回调，模拟 useJob 轮询检测到任务完成
function fireTerminal(snapshot) {
  onTerminalCallback(snapshot);
  return new Promise((r) => setTimeout(r, 1000)); // 等待 800ms 串行间隔
}

describe("App 自动下载策略", () => {
  beforeEach(() => {
    // vi.resetModules();
    localStorage.clear();
    onTerminalCallback = null;
    Object.assign(jobMock, {
      jobId: ref(null),
      status: ref("idle"),
      progress: ref(0),
      progressMessage: ref("准备就绪"),
      logLines: ref([]),
      logCursor: ref(0),
      outputPath: ref(null),
      error: ref(null),
      outputName: ref(""),
    });
    jobMock.submit.mockReset().mockResolvedValue("job-1");
    jobMock.download.mockReset().mockResolvedValue();
    jobMock.downloadLogs.mockReset().mockResolvedValue();
    jobMock.downloadFor.mockReset().mockResolvedValue();
    jobMock.downloadLogsFor.mockReset().mockResolvedValue();
    jobMock.entryFor.mockReset().mockImplementation(() => undefined);
    autoDownloadEnabled.value = true;
    downloadedJobIds.clear();
    api.download.mockReset().mockResolvedValue();
  });

  it("completed 触发报告和日志各一次", async () => {
    await mountApp();
    await fireTerminal({
      jobId: "job-1",
      status: "completed",
      outputName: "项目A-比对报告.xlsx",
      logLines: ["line-1"],
    });
    expect(api.download).toHaveBeenCalledWith(
      "/jobs/job-1/download",
      "项目A-比对报告.xlsx"
    );
    expect(api.download).toHaveBeenCalledWith(
      "/jobs/job-1/log",
      "比对日志-项目A-比对报告.xlsx.txt"
    );
  });

  it("同一任务重复终态只下载一次（去重）", async () => {
    await mountApp();
    await fireTerminal({ jobId: "job-1", status: "completed", outputName: "A.xlsx", logLines: [] });
    await fireTerminal({ jobId: "job-1", status: "completed", outputName: "A.xlsx", logLines: [] });
    expect(api.download.mock.calls.filter((c) => c[0] === "/jobs/job-1/download")).toHaveLength(1);
  });

  it("failed 只触发日志", async () => {
    await mountApp();
    await fireTerminal({ jobId: "job-2", status: "failed", outputName: "A.xlsx", logLines: ["e"] });
    expect(api.download.mock.calls.filter((c) => c[0] === "/jobs/job-2/log")).toHaveLength(1);
    expect(api.download.mock.calls.filter((c) => c[0] === "/jobs/job-2/download")).toHaveLength(0);
  });

  it("cancelled 不触发下载", async () => {
    await mountApp();
    await fireTerminal({ jobId: "job-3", status: "cancelled", outputName: "A.xlsx", logLines: [] });
    expect(api.download).not.toHaveBeenCalled();
  });

  it("开关关闭时不下载", async () => {
    autoDownloadEnabled.value = false;
    await mountApp();
    await fireTerminal({ jobId: "job-4", status: "completed", outputName: "A.xlsx", logLines: [] });
    expect(api.download).not.toHaveBeenCalled();
  });

  it("下载失败给警告不抛", async () => {
    api.download.mockRejectedValueOnce(new Error("blocked"));
    await mountApp();
    await fireTerminal({ jobId: "job-5", status: "completed", outputName: "A.xlsx", logLines: [] });
    expect(api.download).toHaveBeenCalledTimes(1);
  });

  it("已切走项目的任务完成仍触发下载（回调与活跃项目无关）", async () => {
    await mountApp();
    await fireTerminal({
      jobId: "job-6",
      status: "completed",
      outputName: "原项目-比对报告.xlsx",
      logLines: [],
    });
    expect(api.download).toHaveBeenCalledWith(
      "/jobs/job-6/download",
      "原项目-比对报告.xlsx"
    );
  });
});
