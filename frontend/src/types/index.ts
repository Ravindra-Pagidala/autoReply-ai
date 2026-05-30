export interface User {
  id: string
  email: string
  token: string
}

export interface BusinessProfile {
  id: string
  user_id: string
  business_name: string | null
  industry: string | null
  description: string | null
  whatsapp_number: string | null
  phone_number: string | null
  business_email: string | null
  bot_active: boolean
  bot_tone: string
  bot_language: string
  fallback_message: string | null
  working_hours_start: string | null
  working_hours_end: string | null
  working_days: string
  escalation_threshold: number
  timezone: string
  onboarding_completed: boolean
  onboarding_step: number
  created_at: string | null
  updated_at: string | null
}

export interface Conversation {
  id: string
  user_id: string
  channel: 'whatsapp' | 'voice' | 'email'
  from_contact: string
  status: 'ai_handled' | 'escalated' | 'resolved'
  escalated: boolean
  resolved: boolean
  response_time_ms: number | null
  intent: string | null
  confidence: number | null
  sentiment: 'positive' | 'neutral' | 'negative' | 'frustrated' | null
  sentiment_score: number | null
  created_at: string | null
  updated_at: string | null
}

export interface Message {
  id: string
  conversation_id: string
  user_id: string
  direction: 'inbound' | 'outbound'
  content: string
  sent_by: 'ai' | 'human' | 'customer'
  created_at: string | null
}

export interface Lead {
  id: string
  user_id: string
  conversation_id: string | null
  name: string | null
  phone: string | null
  email: string | null
  channel: string
  query: string | null
  status: 'new' | 'follow_up' | 'resolved' | 'lost'
  lead_score: number | null
  lead_temperature: 'hot' | 'warm' | 'cold' | null
  score_reason: string | null
  recommendation: { label: string; icon: string; priority: 'high' | 'medium' | 'low' } | null
  created_at: string | null
  updated_at: string | null
}

export interface Escalation {
  id: string
  user_id: string
  conversation_id: string
  channel: string
  from_contact: string
  reason: string
  status: 'open' | 'assigned' | 'resolved'
  assigned_to: string | null
  human_reply: string | null
  resolved_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  reference_id: string | null
  reference_type: string | null
  created_at: string | null
}

export interface KnowledgeBase {
  id: string
  user_id: string
  filename: string
  file_type: string | null
  file_size: number | null
  chunk_count: number
  training_status: 'pending' | 'processing' | 'trained' | 'failed'
  training_error: string | null
  trained: boolean
  created_at: string | null
  updated_at: string | null
}

export interface TeamMember {
  id: string
  owner_id: string
  member_email: string
  member_user_id: string | null
  role: 'owner' | 'agent' | 'viewer'
  status: 'pending' | 'accepted' | 'rejected'
  invited_at: string | null
  accepted_at: string | null
  created_at: string | null
}

export interface Appointment {
  id: string
  user_id: string
  conversation_id: string | null
  customer_name: string | null
  customer_phone: string | null
  customer_email: string | null
  channel: string
  service_type: string | null
  appointment_date: string | null
  appointment_time: string | null
  notes: string | null
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed'
  created_at: string | null
  updated_at: string | null
}

export interface DashboardStats {
  messages_today: number
  leads_today: number
  calls_today: number
  emails_today: number
  escalations_open: number
  avg_response_ms: number
  total_conversations: number
  total_leads: number
  unread_notifications: number
}

export interface TestRun {
  id: string
  user_id: string
  test_type: string
  triggered_by: string
  total_sent: number
  total_success: number
  total_failed: number
  whatsapp_sent: number
  whatsapp_success: number
  voice_sent: number
  voice_success: number
  email_sent: number
  email_success: number
  avg_response_ms: number
  leads_captured: number
  status: 'running' | 'completed' | 'failed'
  created_at: string | null
  completed_at: string | null
}

export interface TestResult {
  id: string
  test_run_id: string
  user_id: string
  channel: string
  message_sent: string
  reply_received: string | null
  response_time_ms: number | null
  success: boolean
  error_reason: string | null
  created_at: string | null
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface ApiError {
  success: false
  error_code: string
  message: string
}

export interface ApiSuccess {
  success: true
  message: string
}