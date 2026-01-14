-- ============================================================================
-- POLYWRITE DATABASE SCHEMA
-- A trust and semantic-governance layer for AI-assisted writing
-- ============================================================================
-- INSTRUCTIONS:
-- Copy this entire file and paste into Supabase SQL Editor
-- Run it once to set up all tables, policies, and triggers
-- ============================================================================

-- ============================================================================
-- CLEANUP: Drop existing objects to ensure clean setup
-- (Safe to run multiple times)
-- ============================================================================

-- Drop trigger first (depends on function)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS public.audit_logs CASCADE;
DROP TABLE IF EXISTS public.rate_limits CASCADE;
DROP TABLE IF EXISTS public.profiles CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS public.handle_new_user();
DROP FUNCTION IF EXISTS public.ensure_all_profiles_exist();

-- ============================================================================
-- PHASE 1: PROFILES TABLE
-- Every authenticated user MUST have exactly one profile
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT DEFAULT 'free' CHECK (role IN ('free', 'internal')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

-- Users can update their own profile (but not role - that's admin only)
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Service role can do everything (for backend operations)
CREATE POLICY "Service role full access to profiles" ON public.profiles
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- PHASE 4: RATE LIMITING TABLE
-- Tracks per-user request counts for rate limiting
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.rate_limits (
    user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    requests_today INTEGER DEFAULT 0,
    requests_this_minute INTEGER DEFAULT 0,
    last_minute_reset TIMESTAMPTZ DEFAULT NOW(),
    last_day_reset DATE DEFAULT CURRENT_DATE
);

-- Enable RLS
ALTER TABLE public.rate_limits ENABLE ROW LEVEL SECURITY;

-- Only service role manages rate limits
CREATE POLICY "Service role manages rate limits" ON public.rate_limits
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- PHASE 9: AUDIT LOGS TABLE
-- Immutable log of all AI interactions for accountability
-- ============================================================================
-- 
-- CORE PURPOSE:
-- 1. Who initiated an AI-assisted action?
-- 2. What kind of action was it?
-- 3. What did the system decide?
-- 4. Why did it decide that?
-- 5. When did it happen?
--
-- WITHOUT storing user content (only hashes for integrity verification).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id),
    
    -- Action metadata
    action_type TEXT NOT NULL CHECK (action_type IN ('rewrite', 'humanize', 'clarify')),
    
    -- Content integrity (hashes only, no raw text)
    original_text_hash TEXT NOT NULL,  -- SHA-256 hash
    proposed_text_hash TEXT NOT NULL,  -- SHA-256 hash
    
    -- Semantic validation result
    similarity_score NUMERIC(4,3) NOT NULL,
    risk_label TEXT NOT NULL CHECK (risk_label IN ('safe', 'risky', 'dangerous')),
    
    -- Final decision (Phase 8)
    decision TEXT NOT NULL CHECK (decision IN ('allowed', 'allowed_with_warning', 'blocked')),
    
    -- Timestamp (UTC, immutable)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Users can view their own audit logs
CREATE POLICY "Users can view own audit logs" ON public.audit_logs
    FOR SELECT USING (auth.uid() = user_id);

-- Only service role can insert audit logs (immutable - no updates/deletes by anyone)
CREATE POLICY "Service role inserts audit logs" ON public.audit_logs
    FOR INSERT WITH CHECK (auth.role() = 'service_role');


-- ============================================================================
-- AUTO-CREATE PROFILE ON USER SIGNUP
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Create profile
    INSERT INTO public.profiles (id, email, role)
    VALUES (NEW.id, NEW.email, 'free')
    ON CONFLICT (id) DO NOTHING;
    
    -- Create rate limit entry
    INSERT INTO public.rate_limits (user_id)
    VALUES (NEW.id)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists (for re-running)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create trigger
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- HELPER FUNCTION: Ensure profile exists for existing users
-- Run this once if you have existing auth users without profiles
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ensure_all_profiles_exist()
RETURNS void AS $$
BEGIN
    INSERT INTO public.profiles (id, email, role)
    SELECT id, email, 'free'
    FROM auth.users
    WHERE id NOT IN (SELECT id FROM public.profiles)
    ON CONFLICT (id) DO NOTHING;
    
    INSERT INTO public.rate_limits (user_id)
    SELECT id
    FROM public.profiles
    WHERE id NOT IN (SELECT user_id FROM public.rate_limits)
    ON CONFLICT (user_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Uncomment the line below to run it immediately:
-- SELECT public.ensure_all_profiles_exist();

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ============================================================================
-- DONE! Your database is ready for PolyWrite.
-- ============================================================================
