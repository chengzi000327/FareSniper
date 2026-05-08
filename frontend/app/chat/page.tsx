"use client";

import React from "react";
import { useChatSession } from "@/lib/useChatSession";

export default function ChatPage() {
  const { messages, send } = useChatSession();
  const [input, setInput] = React.useState("");

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    await send(text);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <span className="inline-block rounded-2xl px-4 py-2 text-sm bg-white border">
              {m.content}
            </span>
          </div>
        ))}
      </div>
      <div className="p-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="比如：五一去三亚，预算 600..."
          className="flex-1 rounded-2xl border px-4 py-2 text-sm"
        />
        <button
          type="button"
          onClick={handleSend}
          className="rounded-2xl bg-black px-4 py-2 text-sm text-white"
        >
          发送
        </button>
      </div>
    </div>
  );
}
