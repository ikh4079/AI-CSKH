type ToolCallBadgeProps = {
  toolCalls: string[];
};

export function ToolCallBadge({ toolCalls }: ToolCallBadgeProps) {
  if (toolCalls.length === 0) {
    return <div className="payload-card">Chưa có tool call nào trong lượt chat này.</div>;
  }

  return (
    <div className="tool-strip">
      {toolCalls.map((toolCall) => (
        <span className="tool-badge" key={toolCall}>
          {toolCall}
        </span>
      ))}
    </div>
  );
}

