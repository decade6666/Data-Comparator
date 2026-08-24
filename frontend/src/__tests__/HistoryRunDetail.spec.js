import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import HistoryRunDetail from "../components/HistoryRunDetail.vue";

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
};

function mountDetail(params = {}) {
  return mount(HistoryRunDetail, {
    props: { parameters: params },
    global: { stubs: elStubs },
  });
}

describe("HistoryRunDetail 参数分组", () => {
  it("完整参数映射出结构/参数/颜色三组", () => {
    const wrapper = mountDetail({
      anchor_row_num: 2,
      header_row_num: 3,
      merge_deleted_data: false,
      anchor_row_content: "SASFieldName",
      header_row_content: "SASFieldLabel",
      max_workers: 8,
      common_cols: ["A", "B"],
      ignore_cols: ["C"],
      sheet_ignore_cols: { S1: ["D"] },
      default_keys: ["E"],
      sheet_key_map: { S1: ["F"] },
      sheet_order: ["S2", "S1"],
      colors: { highlight_fill: "#ff0000" },
    });
    const text = wrapper.text();
    expect(text).toContain("结构设置");
    expect(text).toContain("锚点行号");
    expect(text).toContain("2");
    expect(text).toContain("比对参数");
    expect(text).toContain("排除字段");
    expect(text).toContain("颜色设置");
  });

  it("空参数不抛异常", () => {
    const wrapper = mountDetail({});
    expect(wrapper.text()).toContain("结构设置");
  });

  it("merge_deleted_data 布尔映射", () => {
    const keep = mountDetail({ merge_deleted_data: true });
    expect(keep.text()).toContain("保留");
    const drop = mountDetail({ merge_deleted_data: false });
    expect(drop.text()).toContain("舍弃");
  });

  it("颜色键显示中文标签", () => {
    const wrapper = mountDetail({
      colors: {
        highlight_fill: "#ff0000",
        missing_sheet_tab: "#00ff00",
        new_sheet_tab: "#0000ff",
      },
    });
    const text = wrapper.text();
    expect(text).toContain("更新颜色");
    expect(text).toContain("删除颜色");
    expect(text).toContain("新增颜色");
  });
});
