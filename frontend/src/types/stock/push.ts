export interface PushRequest {
  target: "notion" | "feishu";
  type: "daily_review" | "analysis" | "chat" | "industry_chain";
  date?: string;
  code?: string;
  feishu_receiver?: string;
  chat_title?: string;
  chat_content?: string;
  industry_name?: string;
  archive_id?: string;
}

export interface PushResponse {
  success: boolean;
  target: string;
  url: string;
  title: string;
  message: string;
}
