# Contributing to Documentation

Welcome! This guide explains how to contribute to MegaBot's documentation.

## Documentation Structure

```
docs/
├── index.md                 # Central documentation index
├── getting-started.md       # Quick start guide
├── architecture/
│   └── overview.md         # System architecture
├── api/
│   ├── index.md            # REST API reference
│   └── websocket.md        # WebSocket API specification
├── adapters/
│   └── framework.md        # Adapter development guide
├── deployment/
│   ├── installation.md     # Installation instructions
│   ├── configuration.md    # Configuration reference
│   ├── scaling.md          # Production deployment
│   └── troubleshooting.md  # Common issues
├── development/
│   ├── index.md            # Development guide
│   ├── testing.md          # Testing guide
│   ├── ci-cd.md            # CI/CD pipelines
│   └── contributing.md     # This file
├── features/
│   ├── memory.md           # Memory system
│   ├── rag.md              # RAG system
│   └── loki.md             # Loki mode
└── security/
    ├── model.md            # Security architecture
    ├── approvals.md        # Approval workflows
    └── best-practices.md   # Security guidelines
```

## Writing Guidelines

### Style and Tone

- **Clear and Concise**: Use simple language. Avoid jargon unless necessary.
- **Active Voice**: Use "Click the button" instead of "The button should be clicked".
- **Consistent Terminology**: Use consistent terms throughout (e.g., always "MegaBot", not "megabot" or "the bot").
- **Inclusive Language**: Use gender-neutral pronouns and inclusive terminology.

### Formatting Standards

- **Markdown**: All documentation uses GitHub-flavored Markdown.
- **Headers**: Use proper header hierarchy (# ## ### ####).
- **Code Blocks**: Use triple backticks with language specification.
- **Links**: Use relative links for internal documentation.
- **Tables**: Use Markdown tables for structured data.
- **Lists**: Use consistent bullet styles and indentation.

### Content Organization

- **Table of Contents**: Include TOC for documents longer than 3 sections.
- **Progressive Disclosure**: Start with basics, then advanced topics.
- **Cross-References**: Link to related documentation sections.
- **Examples First**: Show examples before explaining concepts.

## Documentation Types

### 1. Reference Documentation

**Purpose**: API references, configuration options, command lists.

**Structure**:
- Overview/introduction
- Table of contents
- Detailed sections with examples
- Error handling (where applicable)

**Example**: `docs/api/index.md`, `docs/deployment/configuration.md`

### 2. Tutorial Documentation

**Purpose**: Step-by-step guides for specific tasks.

**Structure**:
- Prerequisites
- Step-by-step instructions
- Expected results
- Troubleshooting
- Next steps

**Example**: `docs/getting-started.md`, `docs/deployment/installation.md`

### 3. Conceptual Documentation

**Purpose**: Explain how things work, architecture, design decisions.

**Structure**:
- Overview
- Key concepts
- Architecture diagrams (ASCII/text-based)
- Examples
- Related documentation

**Example**: `docs/architecture/overview.md`, `docs/features/memory.md`

### 4. Troubleshooting Documentation

**Purpose**: Help users solve common problems.

**Structure**:
- Common symptoms/issues
- Diagnostic steps
- Solutions
- Prevention tips
- When to seek help

**Example**: `docs/deployment/troubleshooting.md`

## Templates

### New Feature Documentation Template

```markdown
# Feature Name

Brief description of what this feature does and why it matters.

## Overview

Detailed explanation of the feature, its purpose, and key concepts.

## Configuration

How to enable and configure the feature.

```yaml
# Example configuration
feature:
  enabled: true
  setting: value
```

## Usage

### Basic Usage

```bash
# Example commands or API calls
command --option value
```

### Advanced Usage

More complex examples and use cases.

## API Reference

If applicable, document the API endpoints or interfaces.

## Examples

Real-world examples showing the feature in action.

## Troubleshooting

Common issues and solutions.

## Related Documentation

- [Related Feature](path/to/related.md)
- [Configuration Guide](deployment/configuration.md)
```

### API Endpoint Documentation Template

```markdown
### METHOD /path/to/endpoint

Description of what this endpoint does.

**Parameters:**
- `param1` (type): Description
- `param2` (type, optional): Description

**Request:**
```json
{
  "field": "value"
}
```

**Response:**
```json
{
  "result": "success",
  "data": {}
}
```

**Errors:**
- `400 Bad Request`: Invalid parameters
- `403 Forbidden`: Insufficient permissions

**Example:**
```bash
curl -X METHOD http://localhost:8000/path/to/endpoint \
  -H "Authorization: Bearer token" \
  -d '{"field": "value"}'
```
```

### Configuration Section Template

```markdown
### Section Name

```yaml
section:
  setting1: "default_value"    # Description of setting1
  setting2: 42                 # Description of setting2
  setting3:                    # Description of setting3
    nested_setting: true       # Nested setting description
```

#### Setting Details

**setting1** (string):
- Description of what this setting controls
- Valid values: option1, option2, option3
- Default: "default_value"

**setting2** (integer):
- Description of what this setting controls
- Range: 1-100
- Default: 42
```

## Quality Checklist

Before submitting documentation changes:

- [ ] **Spelling and Grammar**: Run spell check and proofread
- [ ] **Links**: All links work and point to correct locations
- [ ] **Examples**: Code examples are tested and functional
- [ ] **Consistency**: Follows established patterns and terminology
- [ ] **Completeness**: Covers all aspects of the topic
- [ ] **Accessibility**: Clear headings, alt text for images
- [ ] **Mobile-Friendly**: Content works on mobile devices

## Testing Documentation

### Link Validation

```bash
# Check for broken internal links
find docs/ -name "*.md" -exec grep -l "\[.*\](\.\." {} \; | xargs -I {} sh -c 'cd docs && markdown-link-check {}'
```

### Example Testing

- Copy code examples into a test environment
- Verify API examples work with `curl`
- Test configuration examples can be loaded
- Check command examples execute successfully

## Contribution Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b docs/improve-contributing-guide`
3. **Make** your changes following the guidelines above
4. **Test** your changes (links, examples, formatting)
5. **Commit** with descriptive messages: `docs: improve contributing guide with templates`
6. **Push** to your fork
7. **Create** a pull request with a clear description

## Review Process

Documentation pull requests will be reviewed for:

- **Technical Accuracy**: Content matches actual functionality
- **Clarity**: Easy to understand for target audience
- **Completeness**: Covers all necessary information
- **Style Consistency**: Follows established patterns
- **Link Integrity**: All references work correctly

## Maintenance

### Keeping Documentation Current

- **Code Changes**: Update documentation when code changes
- **Version Updates**: Document breaking changes and new features
- **User Feedback**: Monitor issues and incorporate user feedback
- **Regular Reviews**: Periodically review for outdated information

### Documentation Metrics

Track these metrics to measure documentation quality:

- **Time to Complete Tasks**: How long users take to complete guided tasks
- **User Feedback**: Ratings and comments on documentation
- **Search Analytics**: What users search for most
- **Link Click-through Rates**: Which sections are most accessed

## Tools and Resources

### Writing Tools
- **Markdown Preview**: Use VS Code or GitHub's preview
- **Grammar Check**: Use Grammarly or similar tools
- **Link Checkers**: `markdown-link-check` for validation

### Testing Tools
- **API Testing**: Postman, curl, or httpie
- **Configuration Testing**: Load configs in test environment
- **Spell Check**: `aspell` or `hunspell`

### Collaboration
- **GitHub Issues**: Report documentation bugs or request improvements
- **Discussions**: Discuss documentation improvements
- **Pull Requests**: Submit documentation changes

---

Thank you for helping improve MegaBot's documentation! Your contributions make MegaBot more accessible to users and developers.