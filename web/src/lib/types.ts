export type Account = {
  id: string;
  name: string;
  industry: string;
  country: string;
  segment: string;
  employee_count: number;
};

export type Opportunity = {
  id: string;
  account_id: string;
  name: string;
  stage: string;
  summary: string;
  priority_requirements: string[];
};

export type ProductSpecs = {
  processor: string;
  memory_gb: number;
  storage_gb: number;
  gpu: string;
  display: string;
  battery_hours: number;
  weight_kg: number;
  os: string;
};

export type ProductInventory = {
  status: string;
  countries: string[];
  quantity: number;
};

export type Product = {
  id: string;
  name: string;
  category: string;
  family: string;
  form_factor: string;
  summary: string;
  personas: string[];
  use_cases: string[];
  tags: string[];
  price_usd: number;
  image_url: string;
  specs: ProductSpecs;
  inventory: ProductInventory;
};

export type WorkflowStep = {
  id: string;
  label: string;
  status: string;
  detail: string;
};

export type RecommendationOption = {
  product: Product;
  score: number;
  badge: 'Best' | 'Better' | 'Good' | string;
  matched_requirements: string[];
  reasoning: string;
};

export type WorkflowResult = {
  workflow_id: string;
  query: string;
  account: Account | null;
  opportunity: Opportunity | null;
  steps: WorkflowStep[];
  recommendations: RecommendationOption[];
  summary: string;
};

export type WorkflowResultEnvelope = {
  workflow_id: string;
  result: WorkflowResult;
};

export type WorkflowStatus = {
  workflow_id: string;
  status: string;
  steps: WorkflowStep[];
  terminal: boolean;
};

export type ChatResponse = {
  chat_id: string;
  message_id: string;
  content: string;
  intent: string;
  chat_name: string;
  workflow_id: string | null;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  workflowId?: string | null;
};
