// WhatsApp 回复助手: 收到私聊 -> AI 写草稿 -> 你在 http://localhost:7790 看过再发
import fs from "node:fs";
import path from "node:path";
import express from "express";
import QRCode from "qrcode";
import { draftReply } from "./ai.js";

const PORT = 7790;
const DIR = import.meta.dirname;
const DRAFTS = path.join(DIR, "drafts.json");
const TEST_MODE = process.env.NO_WA === "1"; // 不连 WhatsApp, 只测页面和 AI

const state = { status: "starting", qr: null, me: null, error: null };
let drafts = [];
try { drafts = JSON.parse(fs.readFileSync(DRAFTS, "utf8")); } catch {}
const save = () => fs.writeFileSync(DRAFTS, JSON.stringify(drafts.slice(-200), null, 1));

// ---------- WhatsApp ----------
let wa = null;

async function startWhatsApp() {
  const { default: pkg } = await import("whatsapp-web.js");
  const { Client, LocalAuth } = pkg;
  wa = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(DIR, ".wwebjs_auth") }),
    puppeteer: {
      headless: true,
      executablePath: process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    },
  });
  wa.on("qr", async (qr) => {
    state.status = "qr";
    state.qr = await QRCode.toDataURL(qr);
  });
  wa.on("authenticated", () => { state.status = "loading"; state.qr = null; });
  wa.on("ready", () => {
    state.status = "ready";
    state.me = wa.info?.pushname || wa.info?.wid?.user || null;
    console.log("WhatsApp 已连上");
  });
  wa.on("auth_failure", (m) => { state.status = "error"; state.error = "登录失败: " + m; });
  wa.on("disconnected", (r) => { state.status = "disconnected"; state.error = String(r); });
  wa.on("message", onMessage);
  await wa.initialize();
}

async function onMessage(msg) {
  try {
    if (msg.fromMe || msg.from === "status@broadcast" || msg.isStatus) return;
    const chat = await msg.getChat();
    if (chat.isGroup) return;
    const contact = await msg.getContact();
    const name = contact.pushname || contact.name || contact.number || msg.from;
    const recent = await chat.fetchMessages({ limit: 12 });
    const history = recent.map((m) => ({
      fromMe: m.fromMe,
      name,
      body: m.body || (m.hasMedia ? "[图片/语音/文件]" : ""),
    }));
    addDraft({ chatId: msg.from, name, body: msg.body || "[图片/语音/文件]", history });
  } catch (e) {
    console.error("处理消息出错:", e);
  }
}

// ---------- 草稿 ----------
function addDraft({ chatId, name, body, history }) {
  // 同一个人还没处理的旧草稿, 合并成新的一条(新草稿会看到完整聊天记录)
  for (const d of drafts) {
    if (d.chatId === chatId && (d.status === "ready" || d.status === "thinking")) d.status = "merged";
  }
  const d = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    chatId, name, body, history,
    time: new Date().toISOString(),
    status: "thinking",
    draft: "",
  };
  drafts.push(d);
  save();
  makeDraft(d);
  return d;
}

async function makeDraft(d) {
  d.status = "thinking";
  try {
    d.draft = await draftReply(d.history);
    if (d.status === "thinking") d.status = "ready";
  } catch (e) {
    console.error("AI 出错:", e);
    d.status = "error";
    d.draft = "";
    d.error = e.status === 401 ? "API key 不对或没设置" : String(e.message || e);
  }
  save();
}

// ---------- 网页 ----------
const app = express();
app.use(express.json());
app.use(express.static(path.join(DIR, "public")));

app.get("/api/state", (req, res) => {
  res.json({
    ...state,
    testMode: TEST_MODE,
    drafts: drafts.filter((d) => d.status !== "merged").slice(-60).reverse(),
  });
});

const find = (id) => drafts.find((d) => d.id === id);

app.post("/api/drafts/:id/send", async (req, res) => {
  const d = find(req.params.id);
  const text = String(req.body?.text ?? "").trim();
  if (!d || !text) return res.status(400).json({ error: "没有内容" });
  try {
    if (!TEST_MODE) {
      if (state.status !== "ready") throw new Error("WhatsApp 还没连上");
      await wa.sendMessage(d.chatId, text);
    }
    d.status = "sent";
    d.sent = text;
    save();
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
});

app.post("/api/drafts/:id/skip", (req, res) => {
  const d = find(req.params.id);
  if (!d) return res.status(404).end();
  d.status = "skipped";
  save();
  res.json({ ok: true });
});

app.post("/api/drafts/:id/redo", (req, res) => {
  const d = find(req.params.id);
  if (!d) return res.status(404).end();
  makeDraft(d);
  res.json({ ok: true });
});

// 测试模式: 假装收到一条消息
app.post("/api/test-message", (req, res) => {
  if (!TEST_MODE) return res.status(403).end();
  const body = String(req.body?.body ?? "");
  const name = String(req.body?.name ?? "测试客户");
  const d = addDraft({ chatId: "test", name, body, history: [{ fromMe: false, name, body }] });
  res.json({ id: d.id });
});

app.listen(PORT, "127.0.0.1", () => {
  console.log(`打开 http://localhost:${PORT} 看草稿`);
});

if (TEST_MODE) {
  state.status = "ready";
  state.me = "测试模式";
} else {
  startWhatsApp().catch((e) => {
    console.error(e);
    state.status = "error";
    state.error = String(e.message || e);
  });
}
