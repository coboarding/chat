-- Create coBoarding database schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Candidates table
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    location VARCHAR(255),
    title VARCHAR(255),
    summary TEXT,
    experience_years INTEGER DEFAULT 0,
    skills JSONB DEFAULT '[]',
    cv_data JSONB,
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours')
);

-- Job listings table
CREATE TABLE IF NOT EXISTS job_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255) NOT NULL,
    position VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    remote BOOLEAN DEFAULT false,
    requirements JSONB DEFAULT '[]',
    salary_range VARCHAR(100),
    urgent BOOLEAN DEFAULT false,
    notification_config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT true
);

-- Applications table
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_listing_id UUID REFERENCES job_listings(id) ON DELETE CASCADE,
    match_score DECIMAL(3,2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'pending',
    conversation_data JSONB DEFAULT '{}',
    technical_questions JSONB DEFAULT '[]',
    technical_answers JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_deadline TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours')
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    message_data JSONB,
    sent_at TIMESTAMP,
    delivery_status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs table (for GDPR compliance)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id UUID,
    old_data JSONB,
    new_data JSONB,
    user_info JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retention_until TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days')
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_candidates_session_id ON candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_expires_at ON candidates(expires_at);
CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);

CREATE INDEX IF NOT EXISTS idx_job_listings_active ON job_listings(active);
CREATE INDEX IF NOT EXISTS idx_job_listings_urgent ON job_listings(urgent);

CREATE INDEX IF NOT EXISTS idx_applications_candidate_id ON applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_applications_job_listing_id ON applications(job_listing_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_response_deadline ON applications(response_deadline);

CREATE INDEX IF NOT EXISTS idx_notifications_application_id ON notifications(application_id);
CREATE INDEX IF NOT EXISTS idx_notifications_delivery_status ON notifications(delivery_status);

CREATE INDEX IF NOT EXISTS idx_audit_logs_session_id ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_retention_until ON audit_logs(retention_until);

-- Insert sample job listings
INSERT INTO job_listings (company_name, position, location, remote, requirements, salary_range, urgent, notification_config) VALUES
('TechStart Berlin', 'Senior Python Developer', 'Berlin, Germany', true, '["Python", "Django", "PostgreSQL", "Docker", "AWS"]', '€60,000 - €80,000', true, '{"slack_webhook": "", "email": "hr@techstart.berlin", "teams_webhook": ""}'),
('AI Solutions Warsaw', 'ML Engineer', 'Warsaw, Poland', true, '["Python", "TensorFlow", "PyTorch", "MLOps", "Docker"]', '€50,000 - €70,000', true, '{"email": "careers@aisolutions.pl"}'),
('FinTech Amsterdam', 'Full Stack Developer', 'Amsterdam, Netherlands', false, '["React", "Node.js", "TypeScript", "AWS", "MongoDB"]', '€65,000 - €85,000', false, '{"email": "jobs@fintech.amsterdam"}'),
('Startup Krakow', 'Frontend Developer', 'Krakow, Poland', true, '["React", "TypeScript", "Next.js", "Tailwind CSS"]', '€40,000 - €55,000', true, '{"email": "team@startup.krakow"}'),
('DevOps Company Munich', 'DevOps Engineer', 'Munich, Germany', true, '["Docker", "Kubernetes", "AWS", "Terraform", "Linux"]', '€70,000 - €90,000', false, '{"email": "hr@devops.munich"}'
);

-- Function to automatically delete expired records
CREATE OR REPLACE FUNCTION delete_expired_candidates()
RETURNS void AS $
BEGIN
    DELETE FROM candidates WHERE expires_at < CURRENT_TIMESTAMP;
    DELETE FROM audit_logs WHERE retention_until < CURRENT_TIMESTAMP;
END;
$ LANGUAGE plpgsql;

-- Create n8n schema
CREATE SCHEMA IF NOT EXISTS n8n;
