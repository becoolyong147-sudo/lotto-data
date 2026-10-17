// 用 Claude 帮你写回复草稿; 可以查号码历史和最新成绩
import fs from "node:fs";
import path from "node:path";
import Anthropic from "@anthropic-ai/sdk";
import { lookupNumber, latestResults, marketNames } from "./data.js";

const MODEL = process.env.BOT_MODEL || "claude-opus-5-5";
const RULES = path.join(import.meta.dirname, "rules.md"); // 本机自己的规则, 不上传
const RULES_EXAMPLE = path.join(import.meta.dirname, "rules.example.md");
const client = new Anthropic();

const tools = [
  {
    name: "lookup_number",
    description: "查一个4位号码以前在各市场开过没有(头二三奖+特别奖), 包括打包(数字一样顺序不同)。客户问某个号码开过没有、几时开时用。",
    strict: true,
    input_schema: {
      type: "object",
      properties: {
        number: { type: "string", description: "4位号码, 例 1234" },
        market: { type: ["string", "null"], description: "只查某个市场时填市场名, 查全部填 null" },
      },
      required: ["number", "market"],
      additionalProperties: false,
    },
  },
  {
    name: "latest_results",
    description: "拿各市场最新一期的成绩(头二三奖+特别奖)。客户问今天/最新开什么时用。",
    strict: true,
    input_schema: {
      type: "object",
      properties: {
        market: { type: ["string", "null"], description: "某个市场名, 全部填 null" },
      },
      required: ["market"],
      additionalProperties: false,
    },
  },
];

function runTool(name, input) {
  if (name === "lookup_number") return lookupNumber(input.number, input.market || undefined);
  if (name === "latest_results") return latestResults(input.market || undefined);
  return { error: "没有这个工具" };
}

function systemPrompt() {
  let rules = "";
  try { rules = fs.readFileSync(RULES, "utf8"); } catch {
    try { rules = fs.readFileSync(RULES_EXAMPLE, "utf8"); } catch {}
  }
  return [
    "你在帮店主写 WhatsApp 回复草稿。店主会先看过、改过才发出去。",
    "只输出要发给客户的那段话本身, 不要加解释、引号或前言。",
    "号码相关的事实一定先用工具查, 不要凭记忆编。",
    `可查的市场: ${marketNames().join("、")}。`,
    `今天是 ${new Date().toISOString().slice(0, 10)}。`,
    "",
    "店主定的规则:",
    rules,
  ].join("\n");
}

// history: [{ fromMe, name, body }], 最旧在前, 最后一条是要回的那条
export async function draftReply(history) {
  const convo = history
    .map((m) => `${m.fromMe ? "我(店主)" : m.name || "客户"}: ${m.body}`)
    .join("\n");
  const messages = [
    {
      role: "user",
      content: `这是最近的聊天记录:\n\n${convo}\n\n帮我写一句回复客户最后那条消息的草稿。`,
    },
  ];

  for (let i = 0; i < 6; i++) {
    const res = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 4000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low" },
      system: systemPrompt(),
      tools,
      messages,
    });

    if (res.stop_reason === "refusal") return "[AI 不肯写这条, 请自己回]";

    if (res.stop_reason === "tool_use") {
      messages.push({ role: "assistant", content: res.content });
      const results = res.content
        .filter((b) => b.type === "tool_use")
        .map((b) => ({
          type: "tool_result",
          tool_use_id: b.id,
          content: JSON.stringify(runTool(b.name, b.input)),
        }));
      messages.push({ role: "user", content: results });
      continue;
    }

    return res.content
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("")
      .trim();
  }
  return "[AI 查太多次没写出来, 请自己回]";
}
