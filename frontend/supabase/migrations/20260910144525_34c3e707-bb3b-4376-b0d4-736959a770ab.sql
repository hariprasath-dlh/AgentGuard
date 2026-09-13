CREATE TYPE public.app_role AS ENUM ('ADMIN','SECURITY','AUDITOR','MANAGER','DEVELOPER');

CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text,
  full_name text,
  organization_name text NOT NULL DEFAULT 'My Organization',
  organization_slug text NOT NULL DEFAULT 'my-organization',
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own profile" ON public.profiles FOR ALL TO authenticated USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

CREATE TABLE public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  UNIQUE (user_id, role)
);
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read own roles" ON public.user_roles FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.has_role(_user_id uuid, _role public.app_role)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role)
$$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, organization_name, organization_slug)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(COALESCE(NEW.email,'user'), '@', 1)),
    COALESCE(NULLIF(NEW.raw_user_meta_data->>'organization_name',''), 'My Organization'),
    lower(regexp_replace(COALESCE(NULLIF(NEW.raw_user_meta_data->>'organization_name',''), 'My Organization'), '[^a-zA-Z0-9]+', '-', 'g'))
  );
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, COALESCE(NULLIF(NEW.raw_user_meta_data->>'role',''), 'ADMIN')::public.app_role)
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE TABLE public.agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'ACTIVE',
  api_key_prefix text,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agents TO authenticated;
GRANT ALL ON public.agents TO service_role;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own agents" ON public.agents FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.tools (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  risk_level text NOT NULL DEFAULT 'LOW',
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tools TO authenticated;
GRANT ALL ON public.tools TO service_role;
ALTER TABLE public.tools ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own tools" ON public.tools FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  tool_id uuid NOT NULL REFERENCES public.tools(id) ON DELETE CASCADE,
  is_allowed boolean NOT NULL DEFAULT true,
  max_calls_per_day integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agent_id, tool_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.permissions TO authenticated;
GRANT ALL ON public.permissions TO service_role;
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own permissions" ON public.permissions FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  policy_type text NOT NULL DEFAULT 'TOOL_ACCESS',
  rules jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.policies TO authenticated;
GRANT ALL ON public.policies TO service_role;
ALTER TABLE public.policies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own policies" ON public.policies FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.budgets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL UNIQUE REFERENCES public.agents(id) ON DELETE CASCADE,
  max_requests_per_minute integer,
  max_requests_per_day integer,
  max_cost_per_session numeric,
  max_cost_per_day numeric,
  current_session_cost numeric NOT NULL DEFAULT 0,
  current_daily_cost numeric NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.budgets TO authenticated;
GRANT ALL ON public.budgets TO service_role;
ALTER TABLE public.budgets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own budgets" ON public.budgets FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.hitl_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  tool_id uuid REFERENCES public.tools(id) ON DELETE SET NULL,
  tool_name text,
  risk_level text,
  status text NOT NULL DEFAULT 'PENDING',
  reason text,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  requested_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT now() + interval '1 hour',
  review_notes text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.hitl_requests TO authenticated;
GRANT ALL ON public.hitl_requests TO service_role;
ALTER TABLE public.hitl_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own hitl" ON public.hitl_requests FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.activity_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  agent_name text,
  tool_name text,
  decision text NOT NULL DEFAULT 'ALLOW',
  reason text,
  latency_ms integer,
  cost numeric NOT NULL DEFAULT 0,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  timestamp timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.activity_events TO authenticated;
GRANT ALL ON public.activity_events TO service_role;
ALTER TABLE public.activity_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own activity" ON public.activity_events FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
  sequence_number bigint NOT NULL,
  event_type text NOT NULL,
  decision text,
  event_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  previous_hash text,
  current_hash text NOT NULL,
  timestamp timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, sequence_number)
);
GRANT SELECT, INSERT ON public.audit_logs TO authenticated;
GRANT ALL ON public.audit_logs TO service_role;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read own audit" ON public.audit_logs FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.append_audit(_user_id uuid, _event_type text, _decision text, _event_data jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  _seq bigint;
  _prev text;
  _ts timestamptz := now();
BEGIN
  SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO _seq FROM public.audit_logs WHERE user_id = _user_id;
  SELECT current_hash INTO _prev FROM public.audit_logs WHERE user_id = _user_id ORDER BY sequence_number DESC LIMIT 1;
  INSERT INTO public.audit_logs (user_id, sequence_number, event_type, decision, event_data, previous_hash, current_hash, timestamp)
  VALUES (
    _user_id, _seq, _event_type, _decision, _event_data, _prev,
    encode(sha256(convert_to(COALESCE(_prev,'') || _seq::text || _event_type || COALESCE(_decision,'') || _event_data::text || _ts::text, 'UTF8')), 'hex'),
    _ts
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.audit_row_change()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  _row jsonb := to_jsonb(COALESCE(NEW, OLD));
BEGIN
  PERFORM public.append_audit(
    (_row->>'user_id')::uuid,
    upper(TG_TABLE_NAME) || '_' || TG_OP,
    CASE WHEN TG_OP = 'DELETE' THEN 'DENY' ELSE 'ALLOW' END,
    _row
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER audit_agents AFTER INSERT OR UPDATE OR DELETE ON public.agents FOR EACH ROW EXECUTE FUNCTION public.audit_row_change();
CREATE TRIGGER audit_tools AFTER INSERT OR UPDATE OR DELETE ON public.tools FOR EACH ROW EXECUTE FUNCTION public.audit_row_change();
CREATE TRIGGER audit_policies AFTER INSERT OR UPDATE OR DELETE ON public.policies FOR EACH ROW EXECUTE FUNCTION public.audit_row_change();
CREATE TRIGGER audit_hitl AFTER INSERT OR UPDATE ON public.hitl_requests FOR EACH ROW EXECUTE FUNCTION public.audit_row_change();

CREATE OR REPLACE FUNCTION public.verify_audit_chain()
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
  r record;
  _prev text := NULL;
  _count int := 0;
  _expected text;
BEGIN
  FOR r IN SELECT * FROM public.audit_logs WHERE user_id = auth.uid() ORDER BY sequence_number ASC LOOP
    _expected := encode(sha256(convert_to(COALESCE(_prev,'') || r.sequence_number::text || r.event_type || COALESCE(r.decision,'') || r.event_data::text || r.timestamp::text, 'UTF8')), 'hex');
    IF r.current_hash <> _expected OR COALESCE(r.previous_hash,'') <> COALESCE(_prev,'') THEN
      RETURN jsonb_build_object('is_valid', false, 'total_records', _count + 1, 'records_verified', _count,
        'broken_at_sequence', r.sequence_number, 'verified_at', now(),
        'details', 'Hash mismatch detected at sequence ' || r.sequence_number);
    END IF;
    _prev := r.current_hash;
    _count := _count + 1;
  END LOOP;
  RETURN jsonb_build_object('is_valid', true, 'total_records', _count, 'records_verified', _count, 'verified_at', now());
END;
$$;