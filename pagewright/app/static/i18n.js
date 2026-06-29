"use strict";
/* Bilingual UI strings. Both versions ship in one app; a toggle swaps them live and the
   choice is remembered. data-i18n=text, data-i18n-ph=placeholder, data-i18n-html=innerHTML,
   data-i18n-title=title. */
const I18N = {
  "zh-CN": {
    _name: "中文", _other: "EN", _html: "zh-CN",
    tagline: "详情页工作室",
    settings: "设置",
    "status.unset": "未配置模型", "status.ready": "已就绪", "status.norender": "缺少渲染浏览器",
    "tab.manual": "上传素材", "tab.url": "商品链接",
    "manual.images": "商品图片",
    "dz.title": "拖入图片，或 <span class=\"link\">点击选择</span>",
    "dz.sub": "包装图 · 实拍图 · 规格图 — 越全越好",
    "manual.desc": "商品描述 / 卖点 / 规格",
    "manual.descPh": "把商品名称、价格、卖点、规格参数粘进来，中英文皆可。信息越完整，生成越精准。",
    "url.label": "商品页链接",
    "url.note": "遇到需登录 / 验证的站点可能抓不全，建议改用「上传素材」。",
    "opt.lang": "目标语言", "opt.style": "视觉风格",
    "lang.zh": "中文（中英对照）", "lang.none": "原文不翻译", "lang.en": "English", "lang.ja": "日本語",
    "style.editorial": "Editorial · 暖色高级", "style.cool": "Cool · 科技蓝",
    cta: "生成详情页",
    privacy: "图片与生成全程在本机；仅你配置的模型调用会联网。",
    "empty.title": "预览区", "empty.sub": "生成的长图会在这里呈现，可直接下载整图或分段。",
    "prog.title": "正在生成…", "prog.done": "完成",
    "result.done": "完成",
    "dl.full": "下载整图", "dl.spec": "数据 JSON", "dl.panel": "下载该分段",
    "set.title": "模型设置",
    "set.sub": "本工具不内置任何模型。填入你自己的 Key —— 仅保存在本机，不上传。",
    "prov.claude": "Anthropic 官方",
    "prov.openaiName": "OpenAI / 兼容 / 本地", "prov.openaiDesc": "含 Ollama、DeepSeek、通义…",
    "set.keyPh": "粘贴你的 API Key",
    "set.baseUrl": "接口地址 Base URL",
    "set.model": "模型 <em class=\"opt\">可留空用默认</em>",
    "set.note": "从图片 / 描述生成需要一个<b>支持看图</b>的模型；纯渲染则无需模型。",
    "set.cancel": "取消", "set.save": "保存设置",
    // toasts / dynamic
    "t.saved": "设置已保存", "t.needInput": "请上传图片或填写描述", "t.needUrl": "请填写商品链接",
    "t.failed": "生成失败：", "t.reqfail": "请求失败：",
    // progress step keys (server-emitted)
    "p.fetch": "正在抓取页面…", "p.read": "正在用模型读取内容…", "p.translate": "正在翻译…",
    "p.compose": "正在排版…", "p.render": "正在渲染长图…", "p.done": "完成",
    "count.suffix": " 字",
    history: "历史",
    "lib.title": "作品库 · 历史版本", "lib.empty": "还没有作品。生成一张详情页，它会自动存到这里。",
    "lib.view": "查看", "lib.download": "下载", "lib.regen": "重渲染", "lib.delete": "删除",
    "lib.confirmDel": "确定删除这个版本？", "lib.regenDone": "已重渲染为新版本",
    "lib.deleted": "已删除", "lib.versions": "个版本",
  },
  "en": {
    _name: "English", _other: "中", _html: "en",
    tagline: "Detail-Page Studio",
    settings: "Settings",
    "status.unset": "Model not set", "status.ready": "Ready", "status.norender": "No renderer found",
    "tab.manual": "Upload assets", "tab.url": "Product URL",
    "manual.images": "Product images",
    "dz.title": "Drop images, or <span class=\"link\">click to choose</span>",
    "dz.sub": "Packaging · photos · spec sheets — the more the better",
    "manual.desc": "Description / selling points / specs",
    "manual.descPh": "Paste the product name, price, selling points and specs. Any language. The more complete, the better the result.",
    "url.label": "Product page URL",
    "url.note": "Sites behind login / verification may not fully load — prefer “Upload assets”.",
    "opt.lang": "Target language", "opt.style": "Visual style",
    "lang.zh": "Chinese (bilingual)", "lang.none": "Keep original", "lang.en": "English", "lang.ja": "Japanese",
    "style.editorial": "Editorial · warm premium", "style.cool": "Cool · tech blue",
    cta: "Generate page",
    privacy: "Images and rendering stay on your machine; only the model calls you configure go online.",
    "empty.title": "Preview", "empty.sub": "Your long image appears here — download it whole or in panels.",
    "prog.title": "Generating…", "prog.done": "Done",
    "result.done": "Done",
    "dl.full": "Download full", "dl.spec": "Data JSON", "dl.panel": "Download this panel",
    "set.title": "Model settings",
    "set.sub": "No model is bundled. Paste your own key — stored only on this machine, never uploaded.",
    "prov.claude": "Anthropic official",
    "prov.openaiName": "OpenAI / compatible / local", "prov.openaiDesc": "incl. Ollama, DeepSeek, Qwen…",
    "set.keyPh": "Paste your API key",
    "set.baseUrl": "Base URL",
    "set.model": "Model <em class=\"opt\">leave blank for default</em>",
    "set.note": "Generating from images / text needs a <b>vision-capable</b> model; rendering needs none.",
    "set.cancel": "Cancel", "set.save": "Save settings",
    "t.saved": "Settings saved", "t.needInput": "Add an image or a description", "t.needUrl": "Enter a product URL",
    "t.failed": "Generation failed: ", "t.reqfail": "Request failed: ",
    "p.fetch": "Fetching the page…", "p.read": "Reading content with the model…", "p.translate": "Translating…",
    "p.compose": "Laying out…", "p.render": "Rendering the long image…", "p.done": "Done",
    "count.suffix": " chars",
    history: "History",
    "lib.title": "Library · version history", "lib.empty": "No work yet. Generate a page and it's saved here automatically.",
    "lib.view": "View", "lib.download": "Download", "lib.regen": "Re-render", "lib.delete": "Delete",
    "lib.confirmDel": "Delete this version?", "lib.regenDone": "Re-rendered as a new version",
    "lib.deleted": "Deleted", "lib.versions": "versions",
  },
};

const _qLang = new URLSearchParams(location.search).get("lang");
let LANG = (_qLang === "en" || _qLang === "zh-CN") ? _qLang
  : localStorage.getItem("pw_lang")
  || ((navigator.language || "en").toLowerCase().startsWith("zh") ? "zh-CN" : "en");

function t(key) { return (I18N[LANG] && I18N[LANG][key]) ?? (I18N.en[key] ?? key); }

function applyI18n() {
  document.documentElement.lang = t("_html");
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  const lb = document.querySelector("#langBtn span");
  if (lb) lb.textContent = t("_other");
}

function setLang(l) { LANG = l; localStorage.setItem("pw_lang", l); applyI18n(); }
function toggleLang() { setLang(LANG === "zh-CN" ? "en" : "zh-CN"); document.dispatchEvent(new Event("langchange")); }
