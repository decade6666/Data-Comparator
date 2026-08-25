import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import CompareForm from "../components/CompareForm.vue";
import ParameterCard from "../components/ParameterCard.vue";

// 只 stub 外部交互组件，保留 ParameterCard 本体以断言其 props
const stubs = {
  PathSelector: { name: "PathSelectorStub", template: '<div class="stub-path" />' },
  StructureRow: { name: "StructureRowStub", template: '<div class="stub-structure" />' },
  ColorSettings: { name: "ColorSettingsStub", template: '<div class="stub-colors" />' },
  ParameterEditDialog: defineComponent({
    name: "ParameterEditDialogStub",
    props: ["modelValue"],
    emits: ["save", "update:modelValue"],
    setup(props, { slots }) {
      return () =>
        h("div", { class: "stub-edit-dialog" }, [
          props.modelValue ? h("div", { class: "stub-edit-open" }, props.modelValue.title) : null,
          slots.default ? slots.default() : null,
        ]);
    },
  }),
};

function mountForm(config = {}) {
  return mount(CompareForm, {
    props: {
      config: {
        old_file_path: "",
        new_file_path: "",
        anchor_row_num: 1,
        header_row_num: 1,
        merge_deleted_data: true,
        include_sheets: [],
        exclude_sheets: [],
        sheet_order: [],
        ignore_cols: [],
        sheet_ignore_cols: {},
        default_keys: [],
        sheet_key_map: {},
        common_cols: [],
        sheet_common_cols: {},
        colors: {},
        ...config,
      },
    },
    global: { stubs },
  });
}

function cardByTitle(wrapper, title) {
  return wrapper
    .findAllComponents(ParameterCard)
    .find((card) => card.props("title") === title);
}

async function openCardAndSave(wrapper, title, value) {
  cardByTitle(wrapper, title).vm.$emit("edit");
  await wrapper.vm.$nextTick();
  const dialog = wrapper.findComponent({ name: "ParameterEditDialogStub" });
  dialog.vm.$emit("save", value);
  await wrapper.vm.$nextTick();
}

describe("CompareForm 参数卡片映射", () => {
  it("排除字段以 {global, perSheet} 形态传给 ParameterCard", () => {
    const wrapper = mountForm({
      common_cols: ["A"],
      sheet_common_cols: { AE: ["B"] },
    });
    const card = cardByTitle(wrapper, "排除字段");
    expect(card.exists()).toBe(true);
    expect(card.props("value")).toEqual({
      global: ["A"],
      perSheet: { AE: ["B"] },
    });
  });

  it("保存排除字段同时 patch common_cols 与 sheet_common_cols", async () => {
    const wrapper = mountForm();
    await openCardAndSave(wrapper, "排除字段", {
      global: ["X"],
      perSheet: { DM: ["Y"] },
    });
    const patches = wrapper.emitted("update:config");
    expect(patches).toEqual(
      expect.arrayContaining([
        [{ common_cols: ["X"] }],
        [{ sheet_common_cols: { DM: ["Y"] } }],
      ])
    );
  });

  it("保存忽略字段仍落在 ignore_cols / sheet_ignore_cols（不串写排除字段）", async () => {
    const wrapper = mountForm();
    await openCardAndSave(wrapper, "忽略字段", {
      global: ["C"],
      perSheet: { AE: ["D"] },
    });
    const patches = wrapper.emitted("update:config");
    expect(patches).toEqual(
      expect.arrayContaining([
        [{ ignore_cols: ["C"] }],
        [{ sheet_ignore_cols: { AE: ["D"] } }],
      ])
    );
    expect(patches).not.toEqual(
      expect.arrayContaining([
        [{ common_cols: ["C"] }],
        [{ sheet_common_cols: { AE: ["D"] } }],
      ])
    );
  });

  it("保存锚点仍落在 default_keys / sheet_key_map", async () => {
    const wrapper = mountForm();
    await openCardAndSave(wrapper, "锚点", {
      global: ["E"],
      perSheet: { AE: ["F"] },
    });
    const patches = wrapper.emitted("update:config");
    expect(patches).toEqual(
      expect.arrayContaining([
        [{ default_keys: ["E"] }],
        [{ sheet_key_map: { AE: ["F"] } }],
      ])
    );
  });

  it("保存比对表单仍 patch include_sheets / exclude_sheets", async () => {
    const wrapper = mountForm();
    await openCardAndSave(wrapper, "比对表单", {
      include: ["AE"],
      exclude: ["DM"],
    });
    const patches = wrapper.emitted("update:config");
    expect(patches).toEqual(
      expect.arrayContaining([
        [{ include_sheets: ["AE"] }],
        [{ exclude_sheets: ["DM"] }],
      ])
    );
  });
});
