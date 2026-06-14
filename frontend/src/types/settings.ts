export interface ProviderDefault {
  base_url: string;
  model: string;
}

export interface ConfigData {
  llm_provider: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  llm_temperature: number;
  feishu_enabled: boolean;
  feishu_app_id: string;
  feishu_app_secret: string;
  feishu_folder_token: string;
  feishu_wiki_space_id: string;
  feishu_wiki_daily_review_parent: string;
  feishu_wiki_analysis_parent: string;
  feishu_daily_review_folder: string;
  feishu_analysis_folder: string;
  feishu_default_receiver: string;
  notion_enabled: boolean;
  notion_parent_page_id: string;
  notion_database_id: string;
  iwencai_enabled: boolean;
  iwencai_base_url: string;
  iwencai_api_key: string;
  provider_defaults: Record<string, ProviderDefault>;
  twitter_feeds: string[];
  eastmoney_cookie: string;
  baidu_cookie: string;
}

export type ConfigUpdate = Partial<Omit<ConfigData, "provider_defaults">>;
