type OrderItem = {
  name: string;
  quantity: number;
  price: number;
};

type OrderPayload = {
  type: "order_lookup";
  tool: string;
  requested_action?: string;
  eligibility?: string;
  next_step?: string;
  decision_source?: string;
  decision_confidence?: number;
  reasoning?: string;
  needs_clarification?: boolean;
  order?: {
    order_id: string;
    customer: string;
    phone: string;
    status: string;
    payment_status: string;
    payment_method: string;
    carrier: string;
    tracking_code: string;
    eta: string;
    total: number;
    address: string;
    note: string;
    items: OrderItem[];
  };
};

type TicketPayload = {
  type: "ticket";
  tool: string;
  ticket_id: string;
  requested_action?: string;
  order_id?: string;
  message: string;
};

export type ToolPayload = OrderPayload | TicketPayload;

type ToolPayloadPanelProps = {
  payloads: ToolPayload[];
};

function formatCurrency(value: number) {
  return `${value.toLocaleString("vi-VN")}đ`;
}

export function ToolPayloadPanel({ payloads }: ToolPayloadPanelProps) {
  const latestOrder = [...payloads].reverse().find((payload) => payload.type === "order_lookup") as
    | OrderPayload
    | undefined;
  const latestTicket = [...payloads].reverse().find((payload) => payload.type === "ticket") as
    | TicketPayload
    | undefined;

  if (!latestOrder && !latestTicket) {
    return <div className="payload-card">Chưa có payload nào để hiển thị.</div>;
  }

  return (
    <div className="payload-panel">
      {latestOrder?.order ? (
        <section className="payload-card">
          <div className="payload-header">
            <span className="eyebrow">Order</span>
            <strong>{latestOrder.order.order_id}</strong>
          </div>

          <div className="payload-grid">
            <div>
              <span className="payload-label">Khách hàng</span>
              <p>{latestOrder.order.customer}</p>
            </div>
            <div>
              <span className="payload-label">Trạng thái</span>
              <p>{latestOrder.order.status}</p>
            </div>
            <div>
              <span className="payload-label">Thanh toán</span>
              <p>
                {latestOrder.order.payment_method} | {latestOrder.order.payment_status}
              </p>
            </div>
            <div>
              <span className="payload-label">Vận chuyển</span>
              <p>
                {latestOrder.order.carrier || "Chưa có"} | {latestOrder.order.tracking_code || "Chưa có"}
              </p>
            </div>
          </div>

          <div className="payload-block">
            <span className="payload-label">Sản phẩm</span>
            <p>
              {latestOrder.order.items
                .map((item) => `${item.name} x${item.quantity} (${formatCurrency(item.price)})`)
                .join("; ")}
            </p>
          </div>

          <div className="payload-grid">
            <div>
              <span className="payload-label">Decision Source</span>
              <p>{latestOrder.decision_source || "N/A"}</p>
            </div>
            <div>
              <span className="payload-label">Confidence</span>
              <p>
                {typeof latestOrder.decision_confidence === "number"
                  ? `${Math.round(latestOrder.decision_confidence * 100)}%`
                  : "N/A"}
              </p>
            </div>
          </div>

          <div className="payload-block">
            <span className="payload-label">Reasoning</span>
            <p>{latestOrder.reasoning || "Không có."}</p>
          </div>

          <div className="payload-block">
            <span className="payload-label">Đề xuất xử lý</span>
            <p>{latestOrder.next_step || "Đã tra cứu thông tin đơn hàng."}</p>
          </div>

          {latestOrder.needs_clarification ? (
            <div className="payload-block">
              <span className="payload-label">Clarification</span>
              <p>Agent đang yêu cầu người dùng làm rõ trước khi xử lý tiếp.</p>
            </div>
          ) : null}
        </section>
      ) : null}

      {latestTicket ? (
        <section className="payload-card payload-card-accent">
          <div className="payload-header">
            <span className="eyebrow">Ticket</span>
            <strong>{latestTicket.ticket_id}</strong>
          </div>

          <div className="payload-block">
            <span className="payload-label">Liên kết</span>
            <p>{latestTicket.order_id ? `Đơn hàng ${latestTicket.order_id}` : "Yêu cầu hỗ trợ chung"}</p>
          </div>

          <div className="payload-block">
            <span className="payload-label">Thông điệp</span>
            <p>{latestTicket.message}</p>
          </div>
        </section>
      ) : null}
    </div>
  );
}
