export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  artifact?: unknown;
  status: "pending" | "completed" | "error" | "interrupted";
}

export interface SubAgent {
  id: string;
  name: string;
  subAgentName: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: "pending" | "active" | "completed" | "error";
}

export interface FileItem {
  path: string;
  content: string;
  generatedFileKind?: string;
  displayName?: string;
}

export interface TodoItem {
  id: string;
  content: string;
  status: "pending" | "in_progress" | "completed";
  updatedAt?: Date;
}

export interface Thread {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface InterruptData {
  value: any;
  ns?: string[];
  scope?: string;
}

export interface ActionRequest {
  name: string;
  args: Record<string, unknown>;
  description?: string;
}

export interface ReviewConfig {
  actionName: string;
  allowedDecisions?: string[];
}

export interface ToolApprovalInterruptData {
  action_requests: ActionRequest[];
  review_configs?: ReviewConfig[];
}

export interface ParameterRequestQuestion {
  key: string;
  label: string;
  why_needed: string;
  severity: string;
  input_kind?: string;
  options?: string[];
  recommended_value?: unknown;
  allowed_units?: string[];
  source_type?: string;
  lock_status?: string;
  can_use_default?: boolean;
  current_value?: unknown;
}

export interface ParameterRequestPayload {
  request_id: string;
  method_id?: string;
  method_label?: string;
  release_status: string;
  question_order: string[];
  remaining_required_count: number;
  questions: ParameterRequestQuestion[];
}
