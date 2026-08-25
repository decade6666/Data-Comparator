import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../composables/useApi", () => ({
  api: { get: vi.fn(), put: vi.fn(), post: vi.fn(), del: vi.fn() },
}));

import {
  applyDocument,
  buildJobPayload,
  buildParameters,
  config,
  emptyConfig,
} from "../composables/useConfig";

function resetConfig() {
  const defaults = emptyConfig();
  for (const key of Object.keys(defaults)) {
    config[key] = defaults[key];
  }
}

beforeEach(() => {
  resetConfig();
});

describe("useConfig sheet_common_cols", () => {
  it("emptyConfig 默认 sheet_common_cols 为 {}", () => {
    expect(emptyConfig().sheet_common_cols).toEqual({});
  });

  it("buildParameters 输出 sheet_common_cols", () => {
    config.sheet_common_cols = { AE: ["B"] };
    expect(buildParameters().sheet_common_cols).toEqual({ AE: ["B"] });
  });

  it("buildJobPayload 透传 sheet_common_cols", () => {
    config.sheet_common_cols = { AE: ["B"] };
    expect(buildJobPayload().sheet_common_cols).toEqual({ AE: ["B"] });
  });

  it("applyDocument 能把文档里的 sheet_common_cols 写进 config", () => {
    applyDocument({ sheet_common_cols: { AE: ["B"] } });
    expect(config.sheet_common_cols).toEqual({ AE: ["B"] });
  });

  it("加载缺键的老配置后 sheet_common_cols 重置为 {}", () => {
    config.sheet_common_cols = { AE: ["B"] };
    applyDocument({ common_cols: ["A"] });
    expect(config.sheet_common_cols).toEqual({});
    expect(config.common_cols).toEqual(["A"]);
  });
});
