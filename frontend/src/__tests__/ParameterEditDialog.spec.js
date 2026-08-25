import { describe, expect, it } from "vitest";
import { h, onMounted } from "vue";
import { mount } from "@vue/test-utils";
import ParameterEditDialog from "../components/ParameterEditDialog.vue";

// el-dialog stub：渲染 default + footer 双插槽，并在挂载时主动触发 open
// （openDialog 初始化逻辑绑定在 @open 上，不触发则 rows/checkedSheets 为空）
const elDialogStub = {
  name: "ElDialogStub",
  props: ["modelValue"],
  emits: ["open"],
  setup(props, { emit, slots }) {
    onMounted(() => {
      if (props.modelValue) emit("open");
    });
    return () =>
      h("div", { class: "el-dialog-stub" }, [
        slots.default ? slots.default() : null,
        slots.footer ? slots.footer() : null,
      ]);
  },
};

// el-select stub：同时支持单选/多选，暴露 allow-create 与 multiple 标记，
// 并把 option label 渲染到 DOM 便于断言候选集
const elSelectStub = {
  name: "ElSelectStub",
  props: ["modelValue", "multiple", "allowCreate", "clearable", "filterable"],
  emits: ["update:modelValue"],
  setup(props, { slots }) {
    return () =>
      h(
        "div",
        {
          class: "el-select-stub",
          "data-multiple": String(props.multiple !== undefined),
          "data-allow-create": String(props.allowCreate !== undefined),
        },
        slots.default ? slots.default() : []
      );
  },
};

const elOptionStub = {
  name: "ElOptionStub",
  props: ["label", "value"],
  template:
    '<span class="el-option-stub" :data-value="value">{{ label }}</span>',
};

const stubs = {
  "el-dialog": elDialogStub,
  "el-select": elSelectStub,
  "el-option": elOptionStub,
  "el-button": {
    name: "ElButtonStub",
    template: '<button class="el-button-stub"><slot /></button>',
  },
  "el-input": {
    name: "ElInputStub",
    props: ["modelValue", "size", "placeholder"],
    emits: ["update:modelValue"],
    template: '<input class="el-input-stub" :value="modelValue" />',
  },
  "el-tooltip": {
    name: "ElTooltipStub",
    template: '<span class="el-tooltip-stub"><slot /></span>',
  },
};

async function mountDialog(model, props = {}) {
  const wrapper = mount(ParameterEditDialog, {
    props: {
      modelValue: model,
      value: props.value ?? [],
      sheetNames: props.sheetNames ?? [],
      selectedSheets: props.selectedSheets ?? [],
      excludeSheets: props.excludeSheets ?? [],
    },
    global: { stubs },
  });
  // openDialog 由 el-dialog @open 同步触发，但模板重渲染需等微任务；
  // 不等待则 rows/checkedSheets 的 DOM 尚未更新
  await wrapper.vm.$nextTick();
  return wrapper;
}

function selectStubs(wrapper) {
  return wrapper.findAllComponents(elSelectStub);
}

function optionLabels(selectWrapper) {
  return selectWrapper.findAll(".el-option-stub").map((n) => n.text());
}

async function clickSave(wrapper) {
  // footer 插槽在 el-dialog stub 中最后渲染，确定按钮即最后一个 .el-button-stub
  const buttons = wrapper.findAll(".el-button-stub");
  await buttons[buttons.length - 1].trigger("click");
}

describe("ParameterEditDialog fields 类型（排除字段/忽略字段共用表格）", () => {
  it("value 为 {global, perSheet} 时往返保存不变", async () => {
    const wrapper = await mountDialog(
      { type: "fields", title: "排除字段", hint: "" },
      { value: { global: ["A"], perSheet: { AE: ["B"] } } }
    );
    // 全局 + AE 共 2 行（不含表头行）
    expect(wrapper.findAll(".dict-row").length).toBe(3); // 表头 + 2 行
    await clickSave(wrapper);
    const payload = wrapper.emitted("save")[0][0];
    expect(payload).toEqual({ global: ["A"], perSheet: { AE: ["B"] } });
  });

  it("字段为空的整行被丢弃", async () => {
    const wrapper = await mountDialog(
      { type: "fields", title: "排除字段", hint: "" },
      { value: { global: ["A"], perSheet: {} } }
    );
    await wrapper.find(".dict-toolbar .el-button-stub").trigger("click"); // 新增一行
    await clickSave(wrapper);
    const payload = wrapper.emitted("save")[0][0];
    expect(payload).toEqual({ global: ["A"], perSheet: {} });
  });

  it("表单列候选 = allSheets ∪ 本行已填值", async () => {
    const wrapper = await mountDialog(
      { type: "fields", title: "排除字段", hint: "" },
      {
        sheetNames: ["AE", "DM"],
        value: { global: [], perSheet: { FUTURE: ["X"] } },
      }
    );
    const labels = optionLabels(selectStubs(wrapper)[0]);
    expect(labels).toEqual(expect.arrayContaining(["AE", "DM", "FUTURE"]));
  });

  it("表单列下拉开启 allow-create 与 clearable", async () => {
    const wrapper = await mountDialog(
      { type: "fields", title: "排除字段", hint: "" },
      { value: { global: ["A"], perSheet: {} } }
    );
    const select = selectStubs(wrapper)[0];
    expect(select.attributes("data-allow-create")).toBe("true");
    // 模板里 clearable/filterable 是无值布尔属性 → stub 收到空字符串，但属性已传递
    expect(select.props("clearable")).not.toBeUndefined();
    expect(select.props("filterable")).not.toBeUndefined();
  });

  it("表单列为 null 时保存不抛异常并按全局处理", async () => {
    const wrapper = await mountDialog(
      { type: "fields", title: "排除字段", hint: "" },
      { value: { global: ["A"], perSheet: {} } }
    );
    const select = selectStubs(wrapper)[0];
    select.vm.$emit("update:modelValue", null);
    await expect(clickSave(wrapper)).resolves.not.toThrow();
    const payload = wrapper.emitted("save")[0][0];
    expect(payload).toEqual({ global: ["A"], perSheet: {} });
  });

  it("anchors 类型走同一段表格模板", async () => {
    const wrapper = await mountDialog(
      { type: "anchors", title: "锚点", hint: "" },
      { value: { global: ["SUBJID"], perSheet: { AE: ["AENUM"] } } }
    );
    expect(wrapper.findAll(".dict-row").length).toBe(3);
    await clickSave(wrapper);
    expect(wrapper.emitted("save")[0][0]).toEqual({
      global: ["SUBJID"],
      perSheet: { AE: ["AENUM"] },
    });
  });
});

describe("ParameterEditDialog sheets 类型（比对表单多选下拉）", () => {
  it("渲染多选下拉，候选含未扫描但已选的表单", async () => {
    const wrapper = await mountDialog(
      { type: "sheets", title: "比对表单", hint: "" },
      { sheetNames: ["AE", "DM"], selectedSheets: ["AE", "ZZ"] }
    );
    const select = selectStubs(wrapper)[0];
    expect(select.attributes("data-multiple")).toBe("true");
    expect(optionLabels(select)).toEqual(
      expect.arrayContaining(["AE", "DM", "ZZ"])
    );
  });

  it("未扫描文件时保留降级提示", async () => {
    const wrapper = await mountDialog(
      { type: "sheets", title: "比对表单", hint: "" },
      { sheetNames: [], selectedSheets: [] }
    );
    expect(wrapper.find(".edit-empty").exists()).toBe(true);
    expect(wrapper.text()).toContain("请先上传");
  });

  it("保存把未选中的扫描表单写进 exclude，并保留未扫描的旧排除项", async () => {
    const wrapper = await mountDialog(
      { type: "sheets", title: "比对表单", hint: "" },
      {
        sheetNames: ["AE", "DM"],
        selectedSheets: ["AE", "DM"],
        excludeSheets: ["OLD"],
      }
    );
    const select = selectStubs(wrapper)[0];
    select.vm.$emit("update:modelValue", ["AE"]);
    await clickSave(wrapper);
    const payload = wrapper.emitted("save")[0][0];
    expect(payload).toEqual({ include: ["AE"], exclude: ["DM", "OLD"] });
  });
});
