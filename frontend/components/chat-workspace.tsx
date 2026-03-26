"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "ai/react";

import { ToolCallBadge } from "@/components/tool-call-badge";
import { ToolPayloadPanel, type ToolPayload } from "@/components/tool-payload-panel";

function createSessionId() {
  return `session-${crypto.randomUUID()}`;
}

export function ChatWorkspace() {
  const [sessionId, setSessionId] = useState(createSessionId);
  const [toolCalls, setToolCalls] = useState<string[]>([]);
  const [toolPayloads, setToolPayloads] = useState<ToolPayload[]>([]);
  const [traceId, setTraceId] = useState<string>("-");
  const [isResetting, setIsResetting] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const { messages, input, handleInputChange, handleSubmit, isLoading, setMessages, setInput } = useChat({
    id: sessionId,
    api: "/api/chat",
    streamProtocol: "text",
    body: {
      session_id: sessionId,
      user_id: "portfolio-user",
    },
    onResponse(response) {
      setTraceId(response.headers.get("x-trace-id") ?? "-");

      try {
        setToolCalls(JSON.parse(response.headers.get("x-tool-calls") ?? "[]") as string[]);
      } catch {
        setToolCalls([]);
      }

      try {
        setToolPayloads(JSON.parse(response.headers.get("x-tool-payloads") ?? "[]") as ToolPayload[]);
      } catch {
        setToolPayloads([]);
      }
    },
  });

  useEffect(() => {
    const node = scrollerRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages]);

  function submitChat() {
    if (input.trim().length === 0 || isLoading) {
      return;
    }

    const form = document.querySelector(".composer") as HTMLFormElement | null;
    form?.requestSubmit();
  }

  async function resetChat() {
    if (isLoading || isResetting) {
      return;
    }

    setIsResetting(true);
    try {
      const response = await fetch("/api/chat/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error("Reset session failed");
      }

      setSessionId(createSessionId());
      setMessages([]);
      setInput("");
      setToolCalls([]);
      setToolPayloads([]);
      setTraceId("-");
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="app-container">
        <header className="topbar">
          <div>
            <span className="eyebrow">AI customer service</span>
            <h1>AI CSKH Chat</h1>
          </div>
          <div className="topbar-actions">
            <button className="reset-button" onClick={resetChat} disabled={isLoading || isResetting}>
              {isResetting ? "Dang tao chat moi..." : "New chat"}
            </button>
            <div className="trace-badge">Trace ID: {traceId}</div>
          </div>
        </header>

        <div className="demo-strip">
          <span className="demo-pill">Chat streaming</span>
          <span className="demo-pill">RAG FAQ</span>
          <span className="demo-pill">Order lookup</span>
          <span className="demo-pill">Auto ticket</span>
        </div>

        <div className="workspace">
          <section className="chat-shell">
            <div className="message-list" ref={scrollerRef}>
              {messages.length === 0 ? (
                <div className="message assistant">
                  Xin chào. Bạn có thể hỏi về FAQ, trạng thái đơn hàng, giao lại, hủy đơn hoặc hoàn tiền.
                </div>
              ) : null}

              {messages.map((message) => (
                <div
                  className={`message ${message.role === "user" ? "user" : "assistant"}`}
                  key={message.id}
                >
                  {message.content}
                </div>
              ))}
            </div>

            <form
              className="composer"
              onSubmit={(event) =>
                handleSubmit(event, { body: { session_id: sessionId, user_id: "portfolio-user" } })
              }
            >
              <textarea
                name="prompt"
                placeholder="Ví dụ: Tôi chưa nhận được hàng dù đã quá ngày dự kiến"
                value={input}
                onChange={handleInputChange}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitChat();
                  }
                }}
              />
              <div className="composer-footer">
                <div className="composer-note">Trang demo, không phản ánh chất lượng thật</div>
                <button className="submit-button" disabled={isLoading || input.trim().length === 0}>
                  {isLoading ? "Đang xử lý..." : "Gửi"}
                </button>
              </div>
            </form>
          </section>

          <aside className="side-shell">
            <section className="side-section">
              <h2>Tool Calls</h2>
              <ToolCallBadge toolCalls={toolCalls} />
            </section>

            <section className="side-section">
              <h2>Tool Payloads</h2>
              <ToolPayloadPanel payloads={toolPayloads} />
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
