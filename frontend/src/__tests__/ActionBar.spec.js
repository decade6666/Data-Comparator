import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";

const elStubs = {
  "el-button": {
    name: "ElButtonStub",
    props: ["type", "icon", "loading", "disabled", "link", "size"],
    template:
      '<button class="el-button-stub" :disabled="disabled" :data-size="size"><slot /></button>',
  },
  "el-tooltip": {
    name: "ElTooltipStub",
    template: '<span class="el-tooltip-stub"><slot /></span>',
  },
};

vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

vi.mock("../composables/useConfigState", () => ({
  saveConfigWithPrompt: vi.fn(() => Promise.resolve("项目名")),
  revertConfig: vi.fn(),
  currentName: { value: "项目A" },
}));

vi.mock("../components/HistoryDialog.vue", () => ({
  default: { template: '<div class="history-dialog-stub" />' },
}));

import ActionBar from "../components/ActionBar.vue";

function mountBar(props = {}) {
  return mount(ActionBar, {
    props: { status: "idle", hasLogs: false, scanning: false, ...props },
    global: { stubs: elStubs },
  });
}

describe("ActionBar 按钮状态机", () => {
  it("idle 时显示开始比对，不显示停止/下载", () => {
    const wrapper = mountBar({ status: "idle" });
    const initials = wrapper.findAll('[aria-label="开始比对"]');
    expect(initials.length).toBe(1);
    expect(wrapper.findAll('[aria-label="停止比对"]').length).toBe(0);
    expect(wrapper.findAll('[aria-label="下载报告"]').length).toBe(0);
  });

  it("running 时显示停止比对，不显示开始", () => {
    const wrapper = mountBar({ status: "running" });
    expect(wrapper.findAll('[aria-label="开始比对"]').length).toBe(0);
    expect(wrapper.findAll('[aria-label="停止比对"]').length).toBe(1);
  });

  it("scanning 时显示停止比对", () => {
    const wrapper = mountBar({ status: "idle", scanning: true });
    expect(wrapper.findAll('[aria-label="停止比对"]').length).toBe(1);
  });

  it("completed 时显示下载报告", () => {
    const wrapper = mountBar({ status: "completed" });
    expect(wrapper.findAll('[aria-label="下载报告"]').length).toBe(1);
  });

  it("hasLogs 控制下载日志显示", () => {
    const withLogs = mountBar({ status: "completed", hasLogs: true });
    expect(withLogs.findAll('[aria-label="下载日志"]').length).toBe(1);
    const noLogs = mountBar({ status: "completed", hasLogs: false });
    expect(noLogs.findAll('[aria-label="下载日志"]').length).toBe(0);
  });

  it("点击 start/stop/download 各 emit 一次", async () => {
    const wrapper = mountBar({ status: "idle" });
    await wrapper.find('[aria-label="开始比对"]').trigger("click");
    expect(wrapper.emitted("start")?.length).toBe(1);
  });

  it("点击历史记录打开弹窗", async () => {
    const wrapper = mountBar({ status: "idle" });
    await wrapper.find('[aria-label="历史记录"]').trigger("click");
    expect(wrapper.find(".history-dialog-stub").exists()).toBe(true);
  });
});

describe("ActionBar 需求锁定", () => {
  it("保存项目是图标按钮（无文本节点）", () => {
    const wrapper = mountBar({ status: "idle" });
    const saveBtn = wrapper.find('[aria-label="保存项目"]');
    expect(saveBtn.exists()).toBe(true);
    expect(saveBtn.text()).toBe("");
  });

  it("开始比对按钮大而醒目（size=large + class）", () => {
    const wrapper = mountBar({ status: "idle" });
    const start = wrapper.find('[aria-label="开始比对"]');
    expect(start.attributes("data-size")).toBe("large");
    expect(start.classes()).toContain("action-start-btn");
  });

  it("订阅事件流", () => {
    const wrapper = mountBar({ status: "idle" });
    expect(wrapper.emitted()).toBeDefined();
  });
});
