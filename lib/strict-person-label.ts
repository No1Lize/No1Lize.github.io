export type StrictPersonLabelValidation = {
  valid: boolean;
  normalized: string;
  displayName: string;
  handle: string;
  searchTerms: string[];
  xEnabled: boolean;
  message: string;
};

const GENERIC_PERSON_LABELS = new Set([
  "人物",
  "专家",
  "研究员",
  "科学家",
  "创始人",
  "创业者",
  "投资人",
  "ceo",
  "cto",
  "founder",
  "researcher",
  "scientist",
]);

function cleanText(value: unknown, maxLength = 100): string {
  return typeof value === "string"
    ? value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength)
    : "";
}

function trimSeparators(value: string): string {
  return value
    .replace(/^[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+/, "")
    .replace(/[\s|｜·•:：,，;；/\\\-—–()（）\[\]【】]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function validateStrictPersonLabel(value: unknown): StrictPersonLabelValidation {
  const raw = cleanText(value).replace(/＠/g, "@");
  const invalid = (message: string): StrictPersonLabelValidation => ({
    valid: false,
    normalized: "",
    displayName: "",
    handle: "",
    searchTerms: [],
    xEnabled: false,
    message,
  });

  if (!raw) return invalid("人物或账号标签不能为空。");
  if (/^https?:\/\//i.test(raw) || /(?:x|twitter)\.com\//i.test(raw)) {
    return invalid("请填写“显示名 @handle”，不要直接粘贴 X 链接。");
  }

  const atCount = (raw.match(/@/g) ?? []).length;
  if (atCount > 1) return invalid("一个标签只能包含一个 X handle。");

  if (atCount === 1) {
    const atIndex = raw.indexOf("@");
    const before = raw.slice(0, atIndex);
    const after = raw.slice(atIndex + 1);
    const handleMatch = after.match(
      /^([A-Za-z0-9_]{1,15})(?:[\s|｜,，;；)）\]】]*)$/,
    );
    if (!handleMatch) {
      return invalid(
        "X handle 必须完整位于标签末尾，只能包含 1–15 位英文字母、数字或下划线。",
      );
    }

    const handle = handleMatch[1];
    const displayName = trimSeparators(before);
    if (displayName && !/[A-Za-z0-9\u3400-\u9fff]/.test(displayName)) {
      return invalid("显示名至少需要包含一个中文、英文或数字字符。");
    }
    const normalized = displayName ? `${displayName} @${handle}` : `@${handle}`;
    const searchTerms = [...new Set([displayName, handle, `@${handle}`].filter(Boolean))];
    return {
      valid: true,
      normalized,
      displayName,
      handle,
      searchTerms,
      xEnabled: true,
      message: "格式有效：会抓取该 X 账号，并将显示名和 handle 分别用于公开搜索。",
    };
  }

  const displayName = trimSeparators(raw);
  if (
    displayName.length < 2 ||
    !/[A-Za-z0-9\u3400-\u9fff]/.test(displayName) ||
    GENERIC_PERSON_LABELS.has(displayName.toLocaleLowerCase("zh-CN"))
  ) {
    return invalid("标签过于宽泛。请填写具体姓名、组织名，最好补充 @handle。");
  }

  return {
    valid: true,
    normalized: displayName,
    displayName,
    handle: "",
    searchTerms: [displayName],
    xEnabled: false,
    message: "标签有效，但没有 @handle，只会参与新闻、论文和公开网页搜索。",
  };
}
