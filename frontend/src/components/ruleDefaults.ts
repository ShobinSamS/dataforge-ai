import type { RuleOptions } from "../types";

export const defaultRuleOptions: RuleOptions = {
  date_format: "yyyy-mm-dd",
  date_start: "2015-01-01",
  date_end: "2025-12-31",
  identifier_pattern: "",
  literal_text: null,
  portrait_source: "illustration",
  portrait_asset_ids: [],
  character_length: null,
  character_set: "alnum",
  font_id: "auto",
  font_size: null,
  text_color: "#000000",
  color_mode: "black",
  font_weight: "auto",
  background_mode: "auto",
  background_color: "#ffffff",
};
