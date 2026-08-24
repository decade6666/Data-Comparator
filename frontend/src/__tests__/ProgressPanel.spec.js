import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import ProgressPanel from "../components/ProgressPanel.vue";

const elStubs = {
  "el-progress": {
    name: "ElProgressStub",
    props: ["percentage", "strokeWidth", "striped", "color"],
    template: '<div class="el-progress-stub"><slot /></div>',
  },
};

describe("ProgressPanel 只显示进度", () => {
  it("不渲染任何操作按钮", () => {
    const wrapper = mount(ProgressPanel, {
      props: { progress: 50, message: "处理中", status: "running" },
      global: { stubs: elStubs },
    });
    expect(wrapper.findAll("button").length).toBe(0);
    expect(wrapper.findAll("[aria-label]").length).toBe(0);
  });
});
