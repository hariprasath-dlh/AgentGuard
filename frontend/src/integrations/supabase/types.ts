export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      activity_events: {
        Row: {
          agent_id: string | null
          agent_name: string | null
          cost: number
          decision: string
          id: string
          latency_ms: number | null
          payload: Json
          reason: string | null
          timestamp: string
          tool_name: string | null
          user_id: string
        }
        Insert: {
          agent_id?: string | null
          agent_name?: string | null
          cost?: number
          decision?: string
          id?: string
          latency_ms?: number | null
          payload?: Json
          reason?: string | null
          timestamp?: string
          tool_name?: string | null
          user_id?: string
        }
        Update: {
          agent_id?: string | null
          agent_name?: string | null
          cost?: number
          decision?: string
          id?: string
          latency_ms?: number | null
          payload?: Json
          reason?: string | null
          timestamp?: string
          tool_name?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "activity_events_agent_id_fkey"
            columns: ["agent_id"]
            isOneToOne: false
            referencedRelation: "agents"
            referencedColumns: ["id"]
          },
        ]
      }
      agents: {
        Row: {
          api_key_prefix: string | null
          created_at: string
          description: string | null
          id: string
          name: string
          status: string
          user_id: string
        }
        Insert: {
          api_key_prefix?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name: string
          status?: string
          user_id?: string
        }
        Update: {
          api_key_prefix?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name?: string
          status?: string
          user_id?: string
        }
        Relationships: []
      }
      audit_logs: {
        Row: {
          current_hash: string
          decision: string | null
          event_data: Json
          event_type: string
          id: string
          previous_hash: string | null
          sequence_number: number
          timestamp: string
          user_id: string
        }
        Insert: {
          current_hash: string
          decision?: string | null
          event_data?: Json
          event_type: string
          id?: string
          previous_hash?: string | null
          sequence_number: number
          timestamp?: string
          user_id?: string
        }
        Update: {
          current_hash?: string
          decision?: string | null
          event_data?: Json
          event_type?: string
          id?: string
          previous_hash?: string | null
          sequence_number?: number
          timestamp?: string
          user_id?: string
        }
        Relationships: []
      }
      budgets: {
        Row: {
          agent_id: string
          created_at: string
          current_daily_cost: number
          current_session_cost: number
          id: string
          max_cost_per_day: number | null
          max_cost_per_session: number | null
          max_requests_per_day: number | null
          max_requests_per_minute: number | null
          user_id: string
        }
        Insert: {
          agent_id: string
          created_at?: string
          current_daily_cost?: number
          current_session_cost?: number
          id?: string
          max_cost_per_day?: number | null
          max_cost_per_session?: number | null
          max_requests_per_day?: number | null
          max_requests_per_minute?: number | null
          user_id?: string
        }
        Update: {
          agent_id?: string
          created_at?: string
          current_daily_cost?: number
          current_session_cost?: number
          id?: string
          max_cost_per_day?: number | null
          max_cost_per_session?: number | null
          max_requests_per_day?: number | null
          max_requests_per_minute?: number | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "budgets_agent_id_fkey"
            columns: ["agent_id"]
            isOneToOne: true
            referencedRelation: "agents"
            referencedColumns: ["id"]
          },
        ]
      }
      hitl_requests: {
        Row: {
          agent_id: string
          created_at: string
          expires_at: string
          id: string
          parameters: Json
          reason: string | null
          requested_at: string
          review_notes: string | null
          reviewed_at: string | null
          risk_level: string | null
          status: string
          tool_id: string | null
          tool_name: string | null
          user_id: string
        }
        Insert: {
          agent_id: string
          created_at?: string
          expires_at?: string
          id?: string
          parameters?: Json
          reason?: string | null
          requested_at?: string
          review_notes?: string | null
          reviewed_at?: string | null
          risk_level?: string | null
          status?: string
          tool_id?: string | null
          tool_name?: string | null
          user_id?: string
        }
        Update: {
          agent_id?: string
          created_at?: string
          expires_at?: string
          id?: string
          parameters?: Json
          reason?: string | null
          requested_at?: string
          review_notes?: string | null
          reviewed_at?: string | null
          risk_level?: string | null
          status?: string
          tool_id?: string | null
          tool_name?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "hitl_requests_agent_id_fkey"
            columns: ["agent_id"]
            isOneToOne: false
            referencedRelation: "agents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "hitl_requests_tool_id_fkey"
            columns: ["tool_id"]
            isOneToOne: false
            referencedRelation: "tools"
            referencedColumns: ["id"]
          },
        ]
      }
      permissions: {
        Row: {
          agent_id: string
          created_at: string
          id: string
          is_allowed: boolean
          max_calls_per_day: number | null
          tool_id: string
          user_id: string
        }
        Insert: {
          agent_id: string
          created_at?: string
          id?: string
          is_allowed?: boolean
          max_calls_per_day?: number | null
          tool_id: string
          user_id?: string
        }
        Update: {
          agent_id?: string
          created_at?: string
          id?: string
          is_allowed?: boolean
          max_calls_per_day?: number | null
          tool_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "permissions_agent_id_fkey"
            columns: ["agent_id"]
            isOneToOne: false
            referencedRelation: "agents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "permissions_tool_id_fkey"
            columns: ["tool_id"]
            isOneToOne: false
            referencedRelation: "tools"
            referencedColumns: ["id"]
          },
        ]
      }
      policies: {
        Row: {
          created_at: string
          description: string | null
          id: string
          is_active: boolean
          name: string
          policy_type: string
          rules: Json
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          name: string
          policy_type?: string
          rules?: Json
          user_id?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          name?: string
          policy_type?: string
          rules?: Json
          user_id?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          created_at: string
          email: string | null
          full_name: string | null
          id: string
          organization_name: string
          organization_slug: string
        }
        Insert: {
          created_at?: string
          email?: string | null
          full_name?: string | null
          id: string
          organization_name?: string
          organization_slug?: string
        }
        Update: {
          created_at?: string
          email?: string | null
          full_name?: string | null
          id?: string
          organization_name?: string
          organization_slug?: string
        }
        Relationships: []
      }
      tools: {
        Row: {
          created_at: string
          description: string | null
          id: string
          is_active: boolean
          name: string
          risk_level: string
          user_id: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          name: string
          risk_level?: string
          user_id?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          is_active?: boolean
          name?: string
          risk_level?: string
          user_id?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      append_audit: {
        Args: {
          _decision: string
          _event_data: Json
          _event_type: string
          _user_id: string
        }
        Returns: undefined
      }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      verify_audit_chain: { Args: never; Returns: Json }
    }
    Enums: {
      app_role: "ADMIN" | "SECURITY" | "AUDITOR" | "MANAGER" | "DEVELOPER"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["ADMIN", "SECURITY", "AUDITOR", "MANAGER", "DEVELOPER"],
    },
  },
} as const
