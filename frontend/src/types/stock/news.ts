export interface StockNews {
  title: string;
  content: string;
  source: string;
  publish_time: string;
  url: string;
  author: string;
  read_count: number;
  comment_count: number;
  image_url: string;
  category?: string;
  source_api?: string;
}

export interface CategorizedStockNews {
  code: string;
  eastmoney_news: StockNews[];
  cls_news: StockNews[];
}

export interface StockBulletin {
  id: string;
  title: string;
  date: string;
  type: string;
  type2: string;
  url: string;
  pdf_url: string;
  origin: string;
  source: string;
  source_api: string;
}

export interface StockBulletinPage {
  code: string;
  name: string;
  page: number;
  page_size: number;
  total_pages: number;
  source: string;
  items: StockBulletin[];
}

export interface StockResearchReport {
  id: string;
  title: string;
  org: string;
  author: string;
  date: string;
  rating: string;
  goal_price: number | null;
  report_type: string;
  url: string;
  source: string;
  source_api: string;
}

export interface StockReportPage {
  code: string;
  months: number;
  total_count: number;
  items: StockResearchReport[];
}

export interface FeedNewsItem {
  title: string;
  content: string;
  source: string;
  publish_time: string;
  url: string;
  author: string;
  read_count: number;
  comment_count: number;
  image_url?: string;
  category?: string;
  source_api?: string;
}

export interface RetailSentimentPost {
  text: string;
  author: string | null;
  publish_time: string | null;
}

export interface RetailSentiment {
  code: string;
  score: number | null;
  post_count: number;
  bullish_ratio: number | null;
  bearish_ratio: number | null;
  sample_posts: RetailSentimentPost[];
  summary: string;
  guba_post_count: number;
  partial?: boolean;
  unavailable_sections?: string[];
  field_sources?: Record<string, string>;
  source_apis?: Record<string, string>;
}

export interface StockSentiment {
  code: string;
  heat_score: number | null;
  hot_rank: number | null;
  news_count: number | null;
  partial?: boolean;
  unavailable_sections?: string[];
  field_sources?: Record<string, string>;
  source_apis?: Record<string, string>;
}

export interface NewsAnalysisRef {
  title: string;
  url: string;
}

export interface NewsAnalysisItem {
  text: string;
  urls?: NewsAnalysisRef[];
}

export interface NewsAnalysisSection {
  title: string;
  icon: string;
  items: NewsAnalysisItem[];
}

export interface NewsAnalysis {
  market_sentiment: string;
  summary: string;
  sections: NewsAnalysisSection[];
}
