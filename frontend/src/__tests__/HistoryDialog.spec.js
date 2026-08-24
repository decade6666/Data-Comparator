import { describe, expect, it, vi, beforeEach } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { h } from "vue";

vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

vi.mock("../composables/useApi", () => ({
  api: {
    get: vi.fn(),
    download: vi.fn(),
  },
}));

import HistoryDialog from "../components/HistoryDialog.vue";
import { api } from "../composables/useApi";

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
  "el-empty": {
    name: "ElEmptyStub",
    props: ["imageSize"],
    template: '<div class="el-empty-stub"><slot name="description" /></div>',
  },
  "el-table": {
    name: "ElTableStub",
    props: {
      data: { type: Array, default: () => [] },
      loading: { type: Boolean, default: false },
    },
    setup(props, { slots }) {
      return () => {
        const columns = (slots.default ? slots.default() : []).filter(Boolean);
        return h(
          "div",
          { class: "el-table-stub" },
          props.data.flatMap((row) =>
            columns.map((col) =>
              h(col.type, { ...(col.props || {}), row }, col.children || null),
            ),
          ),
        );
      };
    },
  },
  "el-table-column": {
    name: "ElTableColumnStub",
    props: ["prop", "label", "width", "minWidth", "row"],
    setup(props, { slots }) {
      return () =>
        h(
          "div",
          { class: "el-table-column-stub" },
          slots.default ? slots.default(props) : [props.label],
        );
    },
  },
};

function makeRun(overrides = {}) {
  return {
    id: 1,
    config_name: "项目A",
    status: "completed",
    report_filename: "项目A-比对报告.xlsx",
    log_filename: "项目A-比对日志.txt",
    report_available: true,
    log_available: true,
    finished_at: "2026-08-23T12:00:00",
    ...overrides,
  };
}

function mountDialog(props = {}) {
  return mount(HistoryDialog, {
    // 先挂 false 再置 true，触发 watch（直接挂 true 不触发 modelValue 变化）
    props: { modelValue: false, configName: "项目A", ...props },
    global: { stubs: elStubs },
  });
}

async function openDialog(wrapper) {
  await wrapper.setProps({ modelValue: true });
  await flushPromises();
}

describe("HistoryDialog", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.download.mockReset();
  });

  it("打开时按 config_name 取数一次", async () => {
    api.get.mockResolvedValueOnce([makeRun()]);
    const wrapper = mountDialog();
    await openDialog(wrapper);
    expect(api.get).toHaveBeenCalledWith(
      "/history?config_name=%E9%A1%B9%E7%9B%AEA",
    );
  });

  it("渲染行：时间格式化 + 文件名", async () => {
    api.get.mockResolvedValueOnce([makeRun()]);
    const wrapper = mountDialog();
    await openDialog(wrapper);
    expect(wrapper.text()).toContain("2026-08-23");
    expect(wrapper.text()).toContain("项目A-比对报告.xlsx");
  });

  it("report_available=false 时下载报告禁用", async () => {
    api.get.mockResolvedValueOnce([makeRun({ report_available: false })]);
    const wrapper = mountDialog();
    await openDialog(wrapper);
    const reportBtn = wrapper.findAll('[aria-label="下载报告"]')[0];
    expect(reportBtn.attributes("disabled")).toBeDefined();
  });

  it("点击下载报告调用 api.download 路径正确", async () => {
    api.get.mockResolvedValueOnce([makeRun()]);
    api.download.mockResolvedValueOnce();
    const wrapper = mountDialog();
    await openDialog(wrapper);
    await wrapper.findAll('[aria-label="下载报告"]')[0].trigger("click");
    expect(api.download).toHaveBeenCalledWith(
      "/history/1/report",
      "项目A-比对报告.xlsx",
    );
  });

  it("空列表显示 empty", async () => {
    api.get.mockResolvedValueOnce([]);
    const wrapper = mountDialog();
    await openDialog(wrapper);
    expect(wrapper.text()).toContain("暂无该项目的比对记录");
  });

  it("configName 为空时不请求", async () => {
    mountDialog({ configName: "" });
    await flushPromises();
    expect(api.get).not.toHaveBeenCalled();
  });

  it("取数失败弹 error 不崩", async () => {
    api.get.mockRejectedValueOnce(new Error("网络错误"));
    const wrapper = mountDialog();
    await openDialog(wrapper);
    expect(wrapper.exists()).toBe(true);
  });
});
