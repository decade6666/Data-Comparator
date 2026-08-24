import { describe, expect, it, vi, beforeEach } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { nextTick, ref } from "vue";

vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const autoDownloadEnabled = ref(true);

vi.mock("../composables/useAutoDownload", () => ({
  useAutoDownload: () => ({
    enabled: autoDownloadEnabled,
    setEnabled: vi.fn(),
  }),
}));

// 可控的 useJob mock：通过 jobMock 暴露 refs 供测试驱动状态流转
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
  reset: vi.fn(),
};

vi.mock("../composables/useJob", () => ({
  useJob: () => jobMock,
}));

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

describe("App 自动下载策略", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
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
    jobMock.download.mockReset().mockResolvedValue();
    jobMock.downloadLogs.mockReset().mockResolvedValue();
    autoDownloadEnabled.value = true;
  });

  it("completed 触发报告和日志各一次", async () => {
    await mountApp();
    jobMock.jobId.value = "job-1";
    jobMock.status.value = "completed";
    jobMock.outputName.value = "项目A-比对报告.xlsx";
    await nextTick();
    await flushPromises();
    // 等待 800ms 串行间隔
    await new Promise((r) => setTimeout(r, 1000));
    expect(jobMock.download).toHaveBeenCalledTimes(1);
    expect(jobMock.downloadLogs).toHaveBeenCalledTimes(1);
  });

  it("二次轮询命中 completed 不重复触发", async () => {
    await mountApp();
    jobMock.jobId.value = "job-1";
    jobMock.status.value = "completed";
    await nextTick();
    await flushPromises();
    await new Promise((r) => setTimeout(r, 1000));
    jobMock.status.value = "completed"; // 再次命中（同 jobId）
    await nextTick();
    await flushPromises();
    expect(jobMock.download).toHaveBeenCalledTimes(1);
  });

  it("failed 只触发日志", async () => {
    await mountApp();
    jobMock.jobId.value = "job-2";
    jobMock.status.value = "failed";
    await nextTick();
    await flushPromises();
    expect(jobMock.downloadLogs).toHaveBeenCalledTimes(1);
    expect(jobMock.download).not.toHaveBeenCalled();
  });

  it("cancelled 不触发下载", async () => {
    await mountApp();
    jobMock.jobId.value = "job-3";
    jobMock.status.value = "cancelled";
    await nextTick();
    await flushPromises();
    expect(jobMock.download).not.toHaveBeenCalled();
    expect(jobMock.downloadLogs).not.toHaveBeenCalled();
  });

  it("开关关闭时不下载", async () => {
    autoDownloadEnabled.value = false;
    await mountApp();
    jobMock.jobId.value = "job-4";
    jobMock.status.value = "completed";
    await nextTick();
    await flushPromises();
    await new Promise((r) => setTimeout(r, 1000));
    expect(jobMock.download).not.toHaveBeenCalled();
    expect(jobMock.downloadLogs).not.toHaveBeenCalled();
  });

  it("下载失败给警告不抛", async () => {
    jobMock.download.mockRejectedValueOnce(new Error("blocked"));
    jobMock.downloadLogs.mockRejectedValueOnce(new Error("blocked"));
    await mountApp();
    jobMock.jobId.value = "job-5";
    jobMock.status.value = "completed";
    await nextTick();
    await flushPromises();
    await new Promise((r) => setTimeout(r, 1000));
    expect(jobMock.download).toHaveBeenCalledTimes(1);
  });
});
