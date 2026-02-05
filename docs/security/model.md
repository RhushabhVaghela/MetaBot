# Security Architecture Overview

MegaBot implements a comprehensive security model designed to protect against unauthorized access, data breaches, and malicious activities while maintaining operational flexibility for AI-assisted workflows.

## Core Security Principles

### Defense in Depth
MegaBot employs multiple security layers:
- **Permission-based Access Control**: Granular permissions for all system actions
- **Approval Interlock**: Human oversight for sensitive operations
- **Content Sanitization**: Protection against injection attacks and malicious content
- **End-to-End Encryption**: Secure communication across all platforms
- **Visual Redaction**: Automatic detection and blurring of sensitive image content

### Zero-Trust Architecture
- No implicit trust between components
- All actions require explicit authorization
- Continuous verification of system state
- Least privilege access by default

## Security Components

### 1. Permission Manager (`core/permissions.py`)

Manages granular permissions across the entire system using a hierarchical policy system.

#### Permission Levels
- **AUTO**: Action is performed without asking (for trusted operations)
- **ASK_EACH**: Action requires manual approval every time (default for sensitive operations)
- **NEVER**: Action is always blocked (for dangerous operations)

#### Policy Structure
```yaml
policies:
  allow:
    - "git status"      # Allow safe Git operations
    - "read *.md"       # Allow reading documentation
  deny:
    - "rm -rf"          # Block dangerous deletions
    - "sudo *"          # Block privilege escalation
```

#### Scope Matching
Permissions use hierarchical scoping with pattern matching:
- Exact matches: `shell.rm`
- Parent matches: `filesystem` applies to `filesystem.read`, `filesystem.write`
- Command prefixes: `git` applies to all git commands

### 2. Approval Workflow

All sensitive operations require explicit admin approval through a multi-channel notification system.

#### Approval Queue
- Actions are queued when permission level is `ASK_EACH`
- Admins receive notifications across all connected platforms
- Escalation to voice calls after 5 minutes if no response
- Automatic DND (Do Not Disturb) detection via calendar integration

#### Supported Approval Methods
- Chat commands: `!approve [action_id]` or `!yes`
- Voice calls with IVR (Interactive Voice Response)
- Calendar-based DND detection
- Automatic timeout handling

### 3. Content Security (Tirith Guard)

Inspired by the Tirith terminal security project, protects against common attack vectors.

#### Sanitization Features
- **ANSI Escape Sequence Removal**: Prevents terminal control character injection
- **Unicode Normalization**: Converts text to NFC form for consistent processing
- **Control Character Filtering**: Removes dangerous control characters while preserving newlines/tabs
- **Homoglyph Detection**: Identifies suspicious Unicode characters used in phishing attacks

#### Validation Rules
- Blocks Cyrillic characters commonly used in homograph attacks
- Prevents Right-to-Left Override (RLO) attacks
- Detects bidirectional control characters

### 4. Visual Redaction System

Automatic detection and redaction of sensitive information in images.

#### Image Processing Pipeline
1. **Content Analysis**: Uses computer vision to detect sensitive regions (faces, text, etc.)
2. **Region Blurring**: Applies Gaussian blur to identified sensitive areas
3. **Redaction Verification**: Double-checks that sensitive content is properly obscured
4. **Metadata Tagging**: Marks redacted images for audit trails

#### Supported Detection Types
- Personal identifiable information (PII)
- Sensitive text content
- Facial recognition data
- Location data

### 5. Secret Management (`core/secrets.py`)

Centralized secret handling with secure injection and scrubbing.

#### Secret Sources
- Environment variables prefixed with `MEGABOT_SECRET_`
- Files in the `secrets/` directory
- API credentials from central `api-credentials.py` file

#### Security Features
- **Template Injection**: Replace `{{SECRET_NAME}}` placeholders with actual values
- **Log Scrubbing**: Automatically redact secrets from logs and output
- **Isolated Storage**: Secrets kept separate from main configuration

### 6. Identity Management

Unified identity system across multiple platforms with secure linking.

#### Identity Linking
- Cross-platform identity unification
- Manual approval required for identity claims
- Persistent identity mapping in memory database
- Support for multiple platforms (Telegram, Signal, Discord, etc.)

#### Identity Verification
- Platform-specific ID validation
- Unified identity resolution
- Identity claim detection and approval workflow

## Platform Security

### Multi-Platform Communication
- **End-to-End Encryption**: All messaging platforms use E2E encryption
- **Platform Isolation**: Each platform connection is sandboxed
- **Unified Gateway**: Secure routing through Cloudflare Tunnel and Tailscale VPN

### Network Security
- **Local-Only Mode**: Default configuration restricts to localhost
- **VPN Integration**: Optional Tailscale VPN for remote access
- **Cloudflare Tunnel**: Secure HTTPS tunneling for web access

## Operational Security

### System Monitoring
- **Health Monitoring**: Continuous component health checking
- **Auto-Healing**: Automatic restart of failed components
- **Heartbeat Loops**: Regular system state verification
- **Alert System**: Notifications for security events

### Backup and Recovery
- **Encrypted Backups**: Memory database backups with encryption
- **Automatic Scheduling**: Regular backup intervals (12 hours)
- **Backup Verification**: Integrity checking of backup files
- **Recovery Procedures**: Documented restore processes

### Audit and Logging
- **Activity Logging**: All actions logged with timestamps
- **Approval Tracking**: Complete audit trail of approval decisions
- **Error Logging**: Security-relevant errors captured and monitored
- **Log Rotation**: Automatic cleanup of old log entries

## Deployment Security

### Configuration Security
- **Encrypted Configuration**: Sensitive config values encrypted at rest
- **Environment Separation**: Different configs for development/production
- **Access Control**: Configuration file permissions restricted

### Container Security (Docker)
- **Non-Root Execution**: Services run as non-privileged users
- **Minimal Images**: Use of slim base images to reduce attack surface
- **Secret Management**: Docker secrets for sensitive environment variables
- **Network Isolation**: Container network segmentation

## Security Best Practices

### For Administrators
1. **Regular Policy Review**: Audit and update permission policies quarterly
2. **Backup Verification**: Regularly test backup restoration procedures
3. **Access Management**: Limit admin privileges to essential personnel
4. **Monitoring Setup**: Configure alerts for security-relevant events

### For Developers
1. **Input Validation**: Always validate and sanitize user inputs
2. **Permission Checks**: Implement permission checks for all sensitive operations
3. **Error Handling**: Avoid leaking sensitive information in error messages
4. **Logging Hygiene**: Use log scrubbing for sensitive data

### For Operations
1. **Update Management**: Keep all dependencies and base images updated
2. **Network Security**: Use firewalls and VPNs for remote access
3. **Incident Response**: Have documented procedures for security incidents
4. **Regular Audits**: Conduct periodic security assessments

## Security Architecture Benefits

- **Human-in-the-Loop**: Critical decisions require human oversight
- **Scalable Permissions**: Granular control that scales with complexity
- **Multi-Platform Security**: Consistent security across all communication channels
- **Automated Redaction**: Prevents accidental data exposure
- **Defense in Depth**: Multiple security layers provide redundancy
- **Audit Trail**: Complete visibility into system activities

This security architecture ensures MegaBot can safely operate as a powerful AI assistant while maintaining strict control over sensitive operations and data protection.</content>
<parameter name="filePath">docs/security/model.md