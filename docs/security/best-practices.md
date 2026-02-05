# Security Best Practices for MegaBot

This guide outlines security best practices for deploying, configuring, and operating MegaBot in production environments.

## Deployment Security

### 1. Network Configuration

#### Local-Only Mode (Recommended for Development)
```yaml
system:
  local_only: true  # Restricts to localhost connections only
```

#### Production with VPN
```yaml
system:
  local_only: false
  # Use Tailscale or equivalent for secure remote access
```

#### Cloudflare Tunnel Setup
```yaml
# Enable secure tunneling for web access
adapters:
  gateway:
    enable_cloudflare: true
    cloudflare_token: "${MEGABOT_SECRET_CLOUDFLARE_TOKEN}"
```

### 2. Container Security

#### Docker Best Practices
```dockerfile
# Use non-root user
USER megabot

# Minimal base image
FROM python:3.11-slim

# No unnecessary packages
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Read-only filesystem where possible
VOLUME ["/app/data", "/app/logs"]
```

#### Docker Compose Security
```yaml
services:
  megabot:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### 3. Secret Management

#### Environment Variables
```bash
# Use prefixed environment variables
export MEGABOT_SECRET_ANTHROPIC_API_KEY="sk-ant-..."
export MEGABOT_SECRET_DATABASE_URL="postgresql://..."
export MEGABOT_SECRET_ENCRYPTION_KEY="your-256-bit-key"
```

#### File-Based Secrets
```bash
# Create secrets directory with restricted permissions
mkdir -p secrets
chmod 700 secrets

# Store secrets in individual files
echo "your-secret-key" > secrets/api_key
chmod 600 secrets/api_key
```

#### Configuration Encryption
```yaml
security:
  megabot_backup_key: "${MEGABOT_SECRET_BACKUP_KEY}"
  megabot_encryption_salt: "unique-salt-per-deployment"
  megabot_media_path: "/secure/media/directory"
```

## Access Control

### 1. Admin Configuration

#### Principle of Least Privilege
```yaml
# Only essential administrators
admins:
  - "admin_primary_id"
  # Remove test/development admins before production
```

#### Multi-Admin Setup
```yaml
admins:
  - "admin_operations"
  - "admin_security"
  - "admin_development"
```

### 2. Permission Policies

#### Conservative Default (Recommended)
```yaml
policies:
  # Start restrictive, expand based on needs
  allow:
    - "git status"
    - "read *.md"
    - "read *.txt"
  deny:
    - "rm -rf *"
    - "sudo *"
    - "chmod *"
    - "chown *"
    - "mount *"
    - "umount *"
    - "* > /dev/null"  # Prevent output redirection attacks
```

#### Git Operations Policy
```yaml
policies:
  allow:
    - "git status"
    - "git log"
    - "git diff"
    - "git show"
    - "git branch"
  deny:
    - "git push origin main"  # Require manual review
    - "git push --force"      # Always block force push
```

#### File System Access
```yaml
policies:
  allow:
    - "read *.py"       # Allow reading Python files
    - "read *.md"       # Allow reading documentation
    - "write *.tmp"     # Allow writing temp files
  deny:
    - "write /etc/*"    # Block system configuration
    - "read /etc/shadow" # Block password files
    - "write ~/.ssh/*"   # Block SSH keys
```

### 3. Voice Escalation Setup

#### Phone Number Configuration
```yaml
system:
  admin_phone: "+1234567890"  # Verified phone number
```

#### DND Configuration
```yaml
system:
  dnd_start: 22  # 10 PM - stop voice calls
  dnd_end: 7     # 7 AM - resume voice calls
```

## Operational Security

### 1. Monitoring and Alerting

#### Health Monitoring Setup
```python
# Configure health checks for all components
health_checks = {
    "memory": {"interval": 60, "retries": 3},
    "openclaw": {"interval": 30, "retries": 5},
    "mcp": {"interval": 120, "retries": 2}
}
```

#### Log Security
```python
# Ensure sensitive data is scrubbed from logs
logger.addFilter(SecretScrubbingFilter())
logger.addFilter(IPScrubbingFilter())
```

#### Alert Configuration
```yaml
alerts:
  security_events:
    - "approval_timeout"
    - "permission_denied"
    - "redaction_failure"
  system_events:
    - "component_down"
    - "high_memory_usage"
    - "backup_failure"
```

### 2. Backup Security

#### Encrypted Backups
```python
# Configure encrypted backup storage
backup_config = {
    "encryption_key": get_secret("backup_key"),
    "storage_path": "/secure/backups",
    "retention_days": 90,
    "compression": "gzip"
}
```

#### Backup Verification
```bash
# Regular backup integrity checks
#!/bin/bash
for backup in /secure/backups/*.enc; do
    if ! verify_backup_integrity "$backup"; then
        alert "Backup corruption detected: $backup"
    fi
done
```

### 3. Update Management

#### Dependency Updates
```bash
# Regular security updates
pip audit  # Check for known vulnerabilities
pip install --upgrade --no-deps -r requirements.txt
```

#### Automated Security Scanning
```yaml
# CI/CD security checks
security_checks:
  - "safety check"      # Python security scanner
  - "bandit -r ."       # Python security linter
  - "docker scan"       # Container vulnerability scan
```

## Data Protection

### 1. Content Sanitization

#### Tirith Guard Configuration
```python
# Enable all sanitization features
guard_config = {
    "ansi_escape_removal": True,
    "unicode_normalization": True,
    "homoglyph_detection": True,
    "control_char_filtering": True
}
```

#### Visual Redaction Settings
```python
# Configure image redaction sensitivity
redaction_config = {
    "face_detection": True,
    "text_detection": True,
    "pii_detection": True,
    "blur_strength": 15,
    "verification_required": True
}
```

### 2. Memory Security

#### Chat History Pruning
```python
# Configure automatic cleanup
memory_config = {
    "max_history_per_chat": 500,
    "prune_interval_hours": 24,
    "keep_forever_tags": ["security", "architecture", "decision"]
}
```

#### Memory Encryption
```python
# Encrypt sensitive memory entries
memory_security = {
    "encrypt_pii": True,
    "encrypt_credentials": True,
    "key_rotation_days": 30
}
```

## Incident Response

### 1. Security Incident Procedures

#### Immediate Response Checklist
1. **Isolate**: Disconnect affected systems
2. **Assess**: Review logs and approval history
3. **Contain**: Block malicious actions via policies
4. **Eradicate**: Remove backdoors and malware
5. **Recover**: Restore from clean backups
6. **Lessons Learned**: Update policies and documentation

#### Emergency Commands
```bash
# Immediate shutdown
docker-compose down --remove-orphans

# Emergency policy lockdown
echo "policies:\n  allow: []\n  deny: ['*']" > emergency-policy.yaml

# Full system reset
rm -rf /app/data/* && git checkout clean-state
```

### 2. Log Analysis for Incidents

#### Security Event Patterns
```python
# Monitor for suspicious patterns
security_patterns = {
    "brute_force": r"Failed login attempts > 5 in 1 minute",
    "data_exfiltration": r"Large file downloads to external IPs",
    "policy_violations": r"Multiple denied actions per user",
    "unusual_commands": r"Commands not in whitelist"
}
```

#### Automated Alerting
```python
def alert_on_suspicious_activity(log_entry):
    if matches_security_pattern(log_entry):
        # Immediate admin notification
        send_alert_admins(f"Security Alert: {log_entry}")
        # Log for investigation
        security_logger.critical(f"SUSPICIOUS: {log_entry}")
```

## Compliance Considerations

### 1. Data Privacy

#### GDPR Compliance
- **Data Minimization**: Only collect necessary data
- **Purpose Limitation**: Use data only for intended purposes
- **Storage Limitation**: Automatic data cleanup policies
- **Data Portability**: Export capabilities for user data

#### Personal Data Handling
```python
# Configure data handling policies
privacy_config = {
    "data_retention_days": 365,
    "anonymize_after_days": 90,
    "export_formats": ["json", "csv"],
    "consent_required": True
}
```

### 2. Audit Requirements

#### Comprehensive Logging
```python
audit_config = {
    "log_level": "INFO",
    "log_retention_days": 2555,  # 7 years for compliance
    "immutable_logs": True,
    "tamper_detection": True
}
```

#### Regular Audits
```bash
# Monthly security audit script
#!/bin/bash
echo "=== Monthly Security Audit ==="
check_file_permissions
audit_user_access
review_approval_history
scan_for_vulnerabilities
verify_backup_integrity
```

## Performance vs Security Trade-offs

### Balancing Act
- **Development**: Relaxed policies for productivity
- **Staging**: Moderate security for testing
- **Production**: Strict security with monitoring

### Performance Optimization
```python
# Optimize security checks for performance
security_optimization = {
    "cache_permissions": True,      # Cache permission lookups
    "batch_image_scanning": True,   # Scan images in batches
    "async_approvals": True,        # Non-blocking approval checks
    "lazy_loading": True            # Load security modules on demand
}
```

## Testing Security

### 1. Security Testing Checklist

#### Pre-Deployment Tests
- [ ] Permission policy validation
- [ ] Approval workflow testing
- [ ] Content sanitization verification
- [ ] Image redaction accuracy
- [ ] Backup encryption testing

#### Penetration Testing
- [ ] Attempt command injection
- [ ] Test permission bypass attempts
- [ ] Verify input sanitization
- [ ] Check for information disclosure
- [ ] Test denial of service scenarios

### 2. Automated Security Tests

```python
def test_security_features():
    # Test permission system
    assert permissions.is_authorized("safe_command") == True
    assert permissions.is_authorized("dangerous_command") is None

    # Test content sanitization
    malicious_input = "\x1b[31mRed Text\e[0m"
    assert guard.sanitize(malicious_input) == "Red Text"

    # Test visual redaction
    sensitive_image = load_test_image()
    redacted = redact_sensitive_content(sensitive_image)
    assert verify_redaction(redacted) == True
```

## Conclusion

MegaBot's security model provides comprehensive protection while maintaining usability. Following these best practices ensures secure deployment across different environments. Regular review and updates of security policies are essential for maintaining robust protection.

**Key Takeaways:**
- Start with restrictive policies and gradually relax based on operational needs
- Implement multi-layer security with human oversight
- Regular monitoring and automated alerts are critical
- Test security features regularly and maintain incident response procedures
- Balance security with usability - overly restrictive systems reduce effectiveness</content>
<parameter name="filePath">docs/security/best-practices.md